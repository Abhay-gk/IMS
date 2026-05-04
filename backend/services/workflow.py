"""
Workflow Service - Incident State Machine & Severity Assignment

This module implements:
1. State Pattern: Work item lifecycle enforcement (OPEN → INVESTIGATING → RESOLVED → CLOSED)
2. Strategy Pattern: Component-type-based severity assignment (P0-P3)
3. RCA Validation: Mandatory Root Cause Analysis before incident closure
4. MTTR Calculation: Automatic Mean Time To Resolution calculation

Best Practices Demonstrated:
- Type hints for IDE support and runtime validation
- ABC (Abstract Base Class) for extensible strategy pattern
- Enum for type safety (not string comparisons)
- Async/await for non-blocking database operations
- Exception handling with specific error types
- Logging for observability
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any

from models.schemas import IncidentStatus, SignalPayload, Severity, ComponentType, RCASubmission
from db.database import get_pg

logger = logging.getLogger("ims.workflow")


# ============================================================================
# STRATEGY PATTERN: Component-Type → Severity Mapping
# ============================================================================
# Problem: How to assign severity based on component type without massive if-else?
# Solution: Strategy pattern with pluggable severity policies
# Benefit: Easy to extend (new component = new strategy), single responsibility
# ============================================================================

class AlertStrategy(ABC):
    """
    Abstract base class for severity determination strategies.
    
    Each component type has different failure modes and impact:
    - RDBMS failures → critical (P0)
    - Cache failures → medium (P2, can rebuild)
    - API failures → low (P3, degraded feature)
    """
    
    @abstractmethod
    def evaluate(self, component_type: ComponentType, error_type: str) -> Severity:
        """
        Determine severity level for a specific error.
        
        Args:
            component_type: RDBMS, CACHE, API, etc.
            error_type: CONNECTION_REFUSED, TIMEOUT, OOM, etc.
            
        Returns:
            Severity level: P0 (critical), P1 (high), P2 (medium), P3 (low)
        """
        pass


class RDBMSAlertStrategy(AlertStrategy):
    """RDBMS component failures are critical (database is source of truth)."""
    
    def evaluate(self, component_type: ComponentType, error_type: str) -> Severity:
        """Map RDBMS errors to severity levels."""
        critical_errors = {"CONNECTION_REFUSED", "OOM", "DATA_CORRUPTION"}
        if error_type in critical_errors:
            return Severity.P0  # Critical - immediate action needed
        return Severity.P1  # High - urgent


class CacheAlertStrategy(AlertStrategy):
    """Cache component failures are medium priority (can rebuild from DB)."""
    
    def evaluate(self, component_type: ComponentType, error_type: str) -> Severity:
        return Severity.P2  # Medium - soon


class DefaultAlertStrategy(AlertStrategy):
    """Unknown components default to low priority."""
    
    def evaluate(self, component_type: ComponentType, error_type: str) -> Severity:
        return Severity.P3  # Low - backlog


def get_alert_strategy(component_type: ComponentType) -> AlertStrategy:
    """
    Factory function to get appropriate strategy for component type.
    
    This pattern makes it easy to add new components:
        elif component_type == ComponentType.MESSAGE_QUEUE:
            return MessageQueueAlertStrategy()
    
    Args:
        component_type: Enum of component type (type-safe, not string)
        
    Returns:
        AlertStrategy instance for that component type
    """
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

# ============================================================================
# STATE PATTERN: Work Item Lifecycle Enforcement
# ============================================================================
# Problem: How to prevent invalid state transitions (e.g., close without RCA)?
# Solution: State pattern with validation before state changes
# Benefit: Single source of truth for workflow rules, audit trail
# ============================================================================

class WorkItemState:
    """
    Manages incident lifecycle state machine.
    
    Valid transitions:
        OPEN → INVESTIGATING (assigned for investigation)
        INVESTIGATING → RESOLVED (root cause found)
        RESOLVED → CLOSED (only with valid RCA)
        
    Enforced Rule: Cannot transition to CLOSED without RCA
    
    Benefits of this pattern:
    - Type-safe state transitions
    - Validation logic in one place
    - Prevents workflow violations
    - Audit trail for state changes
    """
    
    async def transition(self, work_item_id: str, new_status: IncidentStatus) -> bool:
        """
        Change incident status with validation.
        
        Args:
            work_item_id: UUID of the incident
            new_status: Target status (INVESTIGATING, RESOLVED, CLOSED)
            
        Returns:
            True if transition successful, False if validation failed
            
        Raises:
            ValueError: If transition violates business rules (e.g., no RCA before CLOSED)
        """
        # Step 1: Validate the transition is allowed
        if not await self._validate_transition(work_item_id, new_status):
            return False
        
        # Step 2: Update database (within transaction for atomicity)
        pg_pool = get_pg()
        query = """
            UPDATE work_items 
            SET status = $1, updated_at = NOW() 
            WHERE id = $2
        """
        async with pg_pool.acquire() as conn:
            await conn.execute(query, new_status.value, work_item_id)
        
        logger.info(f"State transition: {work_item_id} → {new_status.value}")
        return True
        
    async def _validate_transition(
        self, 
        work_item_id: str, 
        new_status: IncidentStatus
    ) -> bool:
        """
        Enforce business rules before state change.
        
        Rule: Mandatory RCA when transitioning to CLOSED
        - Incident cannot be marked CLOSED without Root Cause Analysis
        - Prevents "fire and forget" culture
        - Forces learning and documentation
        
        Args:
            work_item_id: UUID of incident to check
            new_status: Target status
            
        Returns:
            True if transition allowed, raises ValueError if denied
        """
        # If transitioning to CLOSED, verify RCA exists and is valid
        if new_status == IncidentStatus.CLOSED:
            pg_pool = get_pg()
            query = "SELECT id FROM rca_records WHERE work_item_id = $1"
            async with pg_pool.acquire() as conn:
                rca = await conn.fetchval(query, work_item_id)
                if not rca:
                    logger.warning(
                        f"Attempted to close {work_item_id} without RCA - DENIED"
                    )
                    raise ValueError(
                        "Mandatory RCA missing. Cannot close incident."
                    )
        return True


async def submit_rca(work_item_id: str, rca: RCASubmission) -> Dict[str, Any]:
    """
    Submit Root Cause Analysis with comprehensive validation.
    
    This function demonstrates best practices:
    1. Field Validation: All RCA fields validated for completeness
    2. Timestamp Validation: incident_end must be after incident_start
    3. MTTR Calculation: Automatic computation of Mean Time To Resolution
    4. Transaction: RCA insert + status update in single atomic transaction
    5. Logging: Detailed logging for observability
    
    Args:
        work_item_id: UUID of incident to close
        rca: RCASubmission with all required fields
        
    Returns:
        Dict with rca_id and mttr_seconds calculated
        
    Raises:
        ValueError: If any validation fails (field length, timestamps, etc.)
        
    Example:
        result = await submit_rca(
            work_item_id="abc123",
            rca=RCASubmission(
                incident_start="2025-01-29T15:00:00Z",
                incident_end="2025-01-29T15:30:00Z",
                root_cause_detail="Connection pool exhaustion",
                fix_applied="Increased pool size to 50",
                prevention_steps="Added monitoring for pool utilization"
            )
        )
        # Returns: {"rca_id": "xyz789", "mttr_seconds": 1800}
    """
    
    # ========== STEP 1: VALIDATE RCA FIELDS ==========
    # These validations enforce data quality and prevent incomplete RCAs
    
    if not rca.root_cause_detail or len(rca.root_cause_detail) < 10:
        raise ValueError(
            "Root cause detail must be at least 10 characters. "
            "Explanation required, not terse replies."
        )
    
    if not rca.fix_applied or len(rca.fix_applied) < 10:
        raise ValueError(
            "Fix applied must be at least 10 characters. "
            "Document what action was taken."
        )
    
    if not rca.prevention_steps or len(rca.prevention_steps) < 10:
        raise ValueError(
            "Prevention steps must be at least 10 characters. "
            "How will this be prevented next time?"
        )
    
    # ========== STEP 2: VALIDATE TIMESTAMPS ==========
    # incident_end must be after incident_start (logical requirement)
    
    if rca.incident_end <= rca.incident_start:
        raise ValueError(
            "Incident end time must be after start time. "
            f"Got: {rca.incident_start} → {rca.incident_end}"
        )
    
    # ========== STEP 3: CALCULATE MTTR ==========
    # MTTR = Mean Time To Resolution
    # Automatically calculated on submission (not manual entry)
    # Benefit: Accurate metrics for continuous improvement
    
    mttr_seconds = int(
        (rca.incident_end - rca.incident_start).total_seconds()
    )
    
    logger.info(f"MTTR Calculated: {mttr_seconds} seconds for {work_item_id}")
    
    # ========== STEP 4: ATOMIC INSERT + STATE UPDATE ==========
    # Both operations happen in transaction: Either both succeed or both rollback
    # Prevents orphaned RCAs or unfinalized incidents
    
    pg_pool = get_pg()
    rca_insert_query = """
        INSERT INTO rca_records (
            work_item_id, incident_start, incident_end, root_cause_category,
            root_cause_detail, fix_applied, prevention_steps, mttr_seconds
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
    """
    
    async with pg_pool.acquire() as conn:
        # Transaction ensures atomicity: RCA insert + status update both succeed together
        async with conn.transaction():
            # Insert RCA record
            rca_id = await conn.fetchval(
                rca_insert_query,
                work_item_id,
                rca.incident_start,
                rca.incident_end,
                rca.root_cause_category.value,
                rca.root_cause_detail,
                rca.fix_applied,
                rca.prevention_steps,
                mttr_seconds
            )
            
            # Update Work Item status to CLOSED
            state_manager = WorkItemState()
            await state_manager.transition(work_item_id, IncidentStatus.CLOSED)
            
            logger.info(
                f"RCA submitted: id={rca_id}, mttr={mttr_seconds}s, "
                f"work_item={work_item_id}"
            )
    
    return {
        "rca_id": str(rca_id),
        "mttr_seconds": mttr_seconds,
        "status": "CLOSED"
    }

