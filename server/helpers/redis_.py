import redis

from configs import settings

r = redis.StrictRedis.from_url(
    settings.REDIS_URL,
    db=settings.REDIS_DB,
    decode_responses=True,
)
