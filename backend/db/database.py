"""
Database connection managers — PostgreSQL (asyncpg), MongoDB (motor), Redis.
All connections are pooled and managed via the FastAPI lifespan.
"""

import asyncpg
import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient

from config import settings


# ─── Global connection holders ────────────────────────────────────
pg_pool: asyncpg.Pool | None = None
mongo_client: AsyncIOMotorClient | None = None
mongo_db = None
redis_client: aioredis.Redis | None = None


async def init_postgres():
    """Create asyncpg connection pool."""
    global pg_pool
    pg_pool = await asyncpg.create_pool(
        dsn=settings.postgres_dsn,
        min_size=5,
        max_size=20,
        command_timeout=30,
    )
    return pg_pool


async def close_postgres():
    global pg_pool
    if pg_pool:
        await pg_pool.close()
        pg_pool = None


async def init_mongodb():
    """Create Motor async MongoDB client."""
    global mongo_client, mongo_db
    mongo_client = AsyncIOMotorClient(settings.mongo_uri)
    mongo_db = mongo_client[settings.mongo_db]

    # Create indexes for efficient querying
    signals_col = mongo_db["signals"]
    await signals_col.create_index([("component_id", 1), ("timestamp", -1)])
    await signals_col.create_index([("work_item_id", 1)])
    await signals_col.create_index([("timestamp", -1)])

    return mongo_db


async def close_mongodb():
    global mongo_client, mongo_db
    if mongo_client:
        mongo_client.close()
        mongo_client = None
        mongo_db = None


async def init_redis():
    """Create async Redis connection."""
    global redis_client
    redis_client = aioredis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
    )
    await redis_client.ping()
    return redis_client


async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


def get_pg() -> asyncpg.Pool:
    assert pg_pool is not None, "PostgreSQL pool not initialized"
    return pg_pool


def get_mongo():
    assert mongo_db is not None, "MongoDB not initialized"
    return mongo_db


def get_redis() -> aioredis.Redis:
    assert redis_client is not None, "Redis not initialized"
    return redis_client
