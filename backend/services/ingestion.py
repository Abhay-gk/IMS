import asyncio
import logging
import time
from datetime import datetime
from fastapi import HTTPException
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from models.schemas import SignalPayload
from db.database import get_redis, get_mongo, get_pg
from services.workflow import process_new_work_item

logger = logging.getLogger("ims.ingestion")

async def check_rate_limit(client_ip: str, limit: int = 15000):
    """
    Simple Redis-backed token bucket or fixed window rate limiter.
    Using a fixed window for simplicity: keys expire every second.
    """
    redis_client = get_redis()
    current_time = int(time.time())
    key = f"rate_limit:{client_ip}:{current_time}"
    
    # Increment counter
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, 2) # Expire in 2 seconds
        
    if count > limit:
        raise HTTPException(status_code=429, detail="Too Many Requests")


async def ingest_signal(signal: SignalPayload):
    """
    Ingest a signal. Offloads heavy lifting to background tasks.
    Returns immediately after rate limiting and quick debounce check.
    """
    # Rate limit check could be based on client IP, omitting here as it's checked at the router level
    
    redis_client = get_redis()
    # Increment global metric for observability loop
    await redis_client.incr("metric:signals_count")
    
    # Offload the rest to background tasks
    asyncio.create_task(process_signal_async(signal))

async def process_signal_async(signal: SignalPayload):
    """
    Background worker to process the signal.
    Includes retry logic for transient failures.
    """
    redis_client = get_redis()
    mongo_db = get_mongo()
    
    # 1. Store raw payload in Data Lake (MongoDB) with retry
    signal_dict = signal.model_dump()
    await insert_signal_with_retry(mongo_db, signal_dict)
    
    # 2. Timeseries aggregation (TimescaleDB)
    asyncio.create_task(record_timeseries_metric(signal))
    
    # 3. Debouncing Logic with atomic check-and-set
    await handle_debounce(signal, redis_client)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
    retry=retry_if_exception_type((Exception,)),
    reraise=True
)
async def insert_signal_with_retry(mongo_db, signal_dict):
    """Insert signal with exponential backoff retry on failure"""
    try:
        await mongo_db["signals"].insert_one(signal_dict)
        logger.debug(f"Signal {signal_dict.get('signal_id')} stored in MongoDB")
    except Exception as e:
        logger.error(f"Failed to insert signal: {e}, retrying...")
        raise


async def handle_debounce(signal: SignalPayload, redis_client):
    """Handle debouncing with improved atomicity"""
    debounce_key = f"debounce:{signal.component_id}"
    
    # SETNX returns 1 if set, 0 if it already exists
    is_new = await redis_client.setnx(debounce_key, signal.timestamp.isoformat())
    if is_new:
        await redis_client.expire(debounce_key, 10)
        # Create work item for new component failure
        asyncio.create_task(process_new_work_item_safe(signal))
    else:
        # Existing work item within 10s window
        asyncio.create_task(increment_work_item_signal_count(signal.component_id, signal.timestamp))


async def process_new_work_item_safe(signal: SignalPayload):
    """Safely process new work item with error handling"""
    try:
        await process_new_work_item(signal)
    except Exception as e:
        logger.error(f"Error creating work item for {signal.component_id}: {e}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
    retry=retry_if_exception_type((Exception,)),
    reraise=False  # Log but don't crash on timeseries failure (best effort)
)
async def record_timeseries_metric(signal: SignalPayload):
    """Insert into TimescaleDB with retry logic"""
    pg_pool = get_pg()
    query = """
        INSERT INTO signal_metrics (time, component_id, component_type, signal_count, avg_latency_ms)
        VALUES ($1, $2, $3, 1, $4)
    """
    try:
        async with pg_pool.acquire() as conn:
            await conn.execute(
                query,
                signal.timestamp,
                signal.component_id,
                signal.component_type.value,
                signal.latency_ms
            )
    except Exception as e:
        logger.error(f"Error inserting metric for {signal.component_id}: {e}")
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
    retry=retry_if_exception_type((Exception,)),
    reraise=False
)
async def increment_work_item_signal_count(component_id: str, timestamp: datetime):
    """Increment signal count for the latest OPEN or INVESTIGATING work item for this component"""
    pg_pool = get_pg()
    query = """
        UPDATE work_items 
        SET signal_count = signal_count + 1, last_signal_at = $1, updated_at = NOW()
        WHERE id = (
            SELECT id FROM work_items 
            WHERE component_id = $2 AND status IN ('OPEN', 'INVESTIGATING') 
            ORDER BY created_at DESC LIMIT 1
        )
    """
    try:
        async with pg_pool.acquire() as conn:
            await conn.execute(query, timestamp, component_id)
    except Exception as e:
        logger.error(f"Error incrementing signal count for {component_id}: {e}")
        raise
