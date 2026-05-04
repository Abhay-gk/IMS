import logging
from abc import ABC, abstractmethod
from models.schemas import IncidentStatus, SignalPayload, Severity, ComponentType, RCASubmission
from db.database import get_pg

logger = logging.getLogger("ims.workflow")

# --- Alerting Strategy Pattern ---

class AlertStrategy(ABC):
    @abstractmethod
    def evaluate(self, component_type: ComponentType, error_type: str) -> Severity:
        pass

class RDBMSAlertStrategy(AlertStrategy):
    def evaluate(self, component_type: ComponentType, error_type: str) -> Severity:
        if error_type in ["CONNECTION_REFUSED", "OOM", "DATA_CORRUPTION"]:
            return Severity.P0
        return Severity.P1

class CacheAlertStrategy(AlertStrategy):
    def evaluate(self, component_type: ComponentType, error_type: str) -> Severity:
        return Severity.P2

class DefaultAlertStrategy(AlertStrategy):
    def evaluate(self, component_type: ComponentType, error_type: str) -> Severity:
        return Severity.P3

def get_alert_strategy(component_type: ComponentType) -> AlertStrategy:
    if component_type == ComponentType.RDBMS:
        return RDBMSAlertStrategy()
    elif component_type == ComponentType.CACHE:
        return CacheAlertStrategy()
    return DefaultAlertStrategy()

async def process_new_work_item(signal: SignalPayload):
    """Create a new Work Item based on a signal"""
    strategy = get_alert_strategy(signal.component_type)
    severity = strategy.evaluate(signal.component_type, signal.error_type)
    
    title = f"{signal.component_type.value} Alert: {signal.error_type} on {signal.component_id}"
    
    pg_pool = get_pg()
    query = """
        INSERT INTO work_items (component_id, component_type, severity, title, first_signal_at, last_signal_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
    """
    try:
        async with pg_pool.acquire() as conn:
            await conn.fetchval(
                query,
                signal.component_id,
                signal.component_type.value,
                severity.value,
                title,
                signal.timestamp,
                signal.timestamp
            )
            logger.info(f"Created Work Item: {title} with Severity {severity.value}")
    except Exception as e:
        logger.error(f"Failed to create Work Item: {e}")

# --- State Transition Pattern ---

class WorkItemState:
    async def transition(self, work_item_id: str, new_status: IncidentStatus) -> bool:
        if not await self._validate_transition(work_item_id, new_status):
            return False
            
        pg_pool = get_pg()
        query = "UPDATE work_items SET status = $1, updated_at = NOW() WHERE id = $2"
        async with pg_pool.acquire() as conn:
            await conn.execute(query, new_status.value, work_item_id)
        return True
        
    async def _validate_transition(self, work_item_id: str, new_status: IncidentStatus) -> bool:
        # Mandatory RCA Check when moving to CLOSED
        if new_status == IncidentStatus.CLOSED:
            pg_pool = get_pg()
            query = "SELECT id FROM rca_records WHERE work_item_id = $1"
            async with pg_pool.acquire() as conn:
                rca = await conn.fetchval(query, work_item_id)
                if not rca:
                    logger.warning(f"Attempted to close {work_item_id} without RCA.")
                    raise ValueError("Mandatory RCA missing. Cannot close incident.")
        return True

async def submit_rca(work_item_id: str, rca: RCASubmission):
    """Submit RCA with validation and calculate MTTR"""
    # Validate RCA is complete
    if not rca.root_cause_detail or len(rca.root_cause_detail) < 10:
        raise ValueError("Root cause detail must be at least 10 characters")
    if not rca.fix_applied or len(rca.fix_applied) < 10:
        raise ValueError("Fix applied must be at least 10 characters")
    if not rca.prevention_steps or len(rca.prevention_steps) < 10:
        raise ValueError("Prevention steps must be at least 10 characters")
    if rca.incident_end <= rca.incident_start:
        raise ValueError("Incident end time must be after start time")
    
    # Calculate MTTR in seconds
    mttr_seconds = int((rca.incident_end - rca.incident_start).total_seconds())
    
    pg_pool = get_pg()
    query = """
        INSERT INTO rca_records (
            work_item_id, incident_start, incident_end, root_cause_category,
            root_cause_detail, fix_applied, prevention_steps, mttr_seconds
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
    """
    async with pg_pool.acquire() as conn:
        # We need a transaction to insert RCA and update Work Item state
        async with conn.transaction():
            rca_id = await conn.fetchval(
                query,
                work_item_id,
                rca.incident_start,
                rca.incident_end,
                rca.root_cause_category.value,
                rca.root_cause_detail,
                rca.fix_applied,
                rca.prevention_steps,
                mttr_seconds
            )
            
            # Transition state to closed
            state_manager = WorkItemState()
            await state_manager.transition(work_item_id, IncidentStatus.CLOSED)
            
            logger.info(f"RCA submitted for {work_item_id} with MTTR: {mttr_seconds}s")
            
    return {"rca_id": str(rca_id), "mttr_seconds": mttr_seconds}
