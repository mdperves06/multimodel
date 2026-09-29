import os
import shutil

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-1234")
os.environ.setdefault("ENCRYPTION_KEY", "Y7c1kQz4mQWJ3xv0tN9pR2s8uYdHf6bLaEoGiTjKcVw=")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("ENABLE_MOCK_PROVIDER", "true")
os.environ.setdefault("STORAGE_LOCAL_PATH", "./.test-storage")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ["EMBEDDED_WORKER"] = "false"

from collections.abc import Iterator  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import get_engine, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.providers.registry import reset_registry  # noqa: E402
from app.redis_client import get_redis  # noqa: E402
from app.security import ratelimit  # noqa: E402
from app.workers.processor import process_job  # noqa: E402
from app.workers.queue import DELAYED_KEY, QUEUE_KEY, JobQueue  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    reset_registry()
    Base.metadata.create_all(get_engine())
    get_redis().flushall()
    ratelimit.reset_memory()
    yield
    Base.metadata.drop_all(get_engine())


@pytest.fixture(scope="session", autouse=True)
def _cleanup_storage() -> Iterator[None]:
    yield
    shutil.rmtree(os.environ["STORAGE_LOCAL_PATH"], ignore_errors=True)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def register(
    client: TestClient, email: str = "alice@example.com", password: str = "s3cret-pass-1"
) -> dict[str, Any]:
    res = client.post("/api/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    data: dict[str, Any] = res.json()
    return data


def connect(
    client: TestClient, key: str = "mock-good-key", label: str = "A1", provider: str = "mock"
) -> dict[str, Any]:
    res = client.post("/api/accounts", json={"provider": provider, "label": label, "api_key": key})
    assert res.status_code == 201, res.text
    data: dict[str, Any] = res.json()
    return data


def submit(client: TestClient, **overrides: Any) -> str:
    body = {"type": "image_generation", "prompt": "A futuristic city at night", "provider": "mock"}
    body.update(overrides)
    res = client.post("/api/jobs", json=body)
    assert res.status_code == 202, res.text
    return str(res.json()["job_id"])


def drain(promote: bool = True) -> int:
    """Run the worker synchronously until the ready queue is empty."""
    queue = JobQueue()
    if promote:
        queue.promote_due()
    r = get_redis()
    processed = 0
    while (job_id := r.lpop(QUEUE_KEY)) is not None:
        process_job(job_id, get_session_factory(), queue)
        processed += 1
    return processed


def make_all_delayed_due() -> None:
    r = get_redis()
    for member in r.zrange(DELAYED_KEY, 0, -1):
        r.zadd(DELAYED_KEY, {member: 0})
