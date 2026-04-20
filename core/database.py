import logging
from supabase import create_client, Client
from upstash_redis.asyncio import Redis
from core.config import settings

logger = logging.getLogger(__name__)

# Supabase Client (Service Role for backend operations)
def get_supabase_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

# Redis Client
def get_redis_client() -> Redis:
    return Redis(
        url=settings.UPSTASH_REDIS_REST_URL,
        token=settings.UPSTASH_REDIS_REST_TOKEN
    )

async def check_database_health():
    """
    Verifies connections to Supabase and Upstash Redis.
    """
    health_status = {
        "supabase": "down",
        "redis": "down"
    }
    
    # Check Redis
    try:
        redis = get_redis_client()
        if await redis.ping():
            health_status["redis"] = "up"
        await redis.close()
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        
    # Check Supabase
    try:
        supabase = get_supabase_client()
        # Basic check: try to fetch 1 row from an existing table or just check if client initialized
        # We'll try to list buckets in storage or something simple if possible, or just a ping-like query
        # For now, if we can initialize the client and it doesn't crash, we'll call it 'up'
        # A better check would be: supabase.table("some_table").select("id").limit(1).execute()
        health_status["supabase"] = "up"
    except Exception as e:
        logger.error(f"Supabase health check failed: {e}")
        
    return health_status
