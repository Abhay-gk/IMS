import time
import psutil
from fastapi import APIRouter, Request, HTTPException, Query
from typing import List

from models.schemas import (
    SignalBatch, SignalPayload, WorkItemResponse, 
    RCASubmission, RCAResponse, HealthResponse, DashboardState,
    IncidentStatus
)
from services.ingestion import check_rate_limit, ingest_signal
from services.workflow import submit_rca, WorkItemState
from db.database import get_pg, get_mongo, get_redis
from config import settings

router = APIRouter()
start_time = time.time()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Observability /health endpoint"""
    redis_client = get_redis()
    pg_pool = get_pg()
    
    count_str = await redis_client.get("metric:signals_count")
    count = int(count_str) if count_str else 0
    signals_per_sec = count / 5.0 # Averaged over the 5s loop window
    
    # Rough approximation of pool stats
    pool_size = pg_pool.get_size()
    pool_free = pg_pool.get_idle_size()
    
    return HealthResponse(
        status="healthy",
        uptime_seconds=time.time() - start_time,
        signals_per_sec=signals_per_sec,
        queue_depth=0, # Assuming background tasks handle queuing implicitly
        pg_pool_size=pool_size,
        pg_pool_free=pool_free
    )

@router.post("/signals", status_code=202)
async def ingest_signals(request: Request, batch: SignalBatch):
    """High-throughput ingestion API"""
    client_ip = request.client.host if request.client else "0.0.0.0"
    await check_rate_limit(client_ip, settings.rate_limit_per_second)
    
    for signal in batch.signals:
        await ingest_signal(signal)
    
    return {"status": "accepted", "count": len(batch.signals)}

@router.get("/work_items", response_model=List[WorkItemResponse])
async def get_work_items(limit: int = Query(50, le=500), offset: int = Query(0, ge=0)):
    """Retrieve active incidents for the UI with pagination"""
    pg_pool = get_pg()
    query = """
        SELECT id, component_id, component_type, severity, status, title, 
               signal_count, first_signal_at, last_signal_at, assigned_to, 
               created_at, updated_at
        FROM work_items
        ORDER BY 
            CASE severity 
                WHEN 'P0' THEN 1
                WHEN 'P1' THEN 2
                WHEN 'P2' THEN 3
                WHEN 'P3' THEN 4
            END,
            created_at DESC
        LIMIT $1 OFFSET $2
    """
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(query, limit, offset)
    
    return [WorkItemResponse(**dict(row)) for row in rows]

@router.get("/work_items/{item_id}/signals")
async def get_work_item_signals(item_id: str):
    """Retrieve raw signals linked to a component from MongoDB"""
    pg_pool = get_pg()
    # First get the component_id for this work item
    query = "SELECT component_id, first_signal_at FROM work_items WHERE id = $1"
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(query, item_id)
        
    if not row:
        raise HTTPException(status_code=404, detail="Work item not found")
        
    component_id = row["component_id"]
    
    mongo_db = get_mongo()
    # Fetch recent signals for this component
    cursor = mongo_db["signals"].find({"component_id": component_id}).sort("timestamp", -1).limit(100)
    signals = await cursor.to_list(length=100)
    
    # Clean up _id
    for sig in signals:
        sig["_id"] = str(sig["_id"])
        
    return signals

@router.post("/work_items/{item_id}/status")
async def update_status(item_id: str, target_status: IncidentStatus):
    state_manager = WorkItemState()
    try:
        success = await state_manager.transition(item_id, target_status)
        if success:
            return {"status": "success", "new_status": target_status}
        raise HTTPException(status_code=400, detail="Transition failed")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/work_items/{item_id}/rca")
async def create_rca(item_id: str, rca: RCASubmission):
    """Submit RCA and transition to CLOSED"""
    try:
        result = await submit_rca(item_id, rca)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
