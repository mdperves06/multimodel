from functools import lru_cache
from typing import Any

import redis

from app.config import get_settings


@lru_cache
def get_redis() -> Any:
    url = get_settings().redis_url
    if url.startswith("memory://"):
        import fakeredis  # dev/test only; installed via requirements-dev.txt

        return fakeredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    return redis.Redis.from_url(url, decode_responses=True)
