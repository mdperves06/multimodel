"""Redis-backed job queue.

`acc:queue`   list of job ids ready to run (RPUSH / BLPOP)
`acc:delayed` sorted set of job ids scored by the unix time they become runnable

Job state lives in the database; the queue only carries ids. A worker must atomically claim a
job in the database before running it, so duplicate queue entries are harmless.
"""

import time
import uuid
from typing import Any

from app.redis_client import get_redis

QUEUE_KEY = "acc:queue"
DELAYED_KEY = "acc:delayed"


class JobQueue:
    def __init__(self, client: Any | None = None) -> None:
        self._r = client if client is not None else get_redis()

    def enqueue(self, job_id: uuid.UUID | str) -> None:
        self._r.rpush(QUEUE_KEY, str(job_id))

    def enqueue_delayed(self, job_id: uuid.UUID | str, delay_seconds: float) -> None:
        self._r.zadd(DELAYED_KEY, {str(job_id): time.time() + max(delay_seconds, 0.0)})

    def promote_due(self) -> int:
        """Move delayed jobs whose time has come onto the ready queue."""
        due = self._r.zrangebyscore(DELAYED_KEY, 0, time.time())
        moved = 0
        for job_id in due:
            if self._r.zrem(DELAYED_KEY, job_id) == 1:  # only one worker wins
                self._r.rpush(QUEUE_KEY, job_id)
                moved += 1
        return moved

    def dequeue(self, timeout: int = 1) -> str | None:
        item = self._r.blpop(QUEUE_KEY, timeout=timeout)
        return str(item[1]) if item else None

    def size(self) -> int:
        return int(self._r.llen(QUEUE_KEY))

    def delayed_size(self) -> int:
        return int(self._r.zcard(DELAYED_KEY))
