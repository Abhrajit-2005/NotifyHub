import logging
from fastapi import HTTPException, status, Depends
from redis.asyncio import Redis
from app.core.redis import get_redis
from app.api.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

RATE_LIMIT = 20
WINDOW_SECONDS = 60

async def check_rate_limit(
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis)
):
    if not redis:
        logger.error("Redis is unavailable, failing closed for rate limiting.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable"
        )
        
    key = f"rate_limit:notifications:{current_user.id}"
    
    try:
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        results = await pipe.execute()
        
        current_count = results[0]
        ttl = results[1]
        
        if ttl == -1:  # Key has no expiration
            await redis.expire(key, WINDOW_SECONDS)
            
        if current_count > RATE_LIMIT:
            logger.warning(f"User {current_user.id} exceeded rate limit")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error communicating with Redis for rate limiting: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable"
        )
        
    return current_user
