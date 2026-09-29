import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-1234")
os.environ.setdefault("ENCRYPTION_KEY", "Y7c1kQz4mQWJ3xv0tN9pR2s8uYdHf6bLaEoGiTjKcVw=")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("ENABLE_MOCK_PROVIDER", "true")
os.environ.setdefault("STORAGE_LOCAL_PATH", "./.test-storage")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.redis_client import get_redis  # noqa: E402
from app.security import ratelimit  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    Base.metadata.create_all(get_engine())
    get_redis().flushall()
    ratelimit.reset_memory()
    yield
    Base.metadata.drop_all(get_engine())


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def register(
    client: TestClient, email: str = "alice@example.com", password: str = "s3cret-pass-1"
) -> dict:  # type: ignore[type-arg]
    res = client.post("/api/auth/register", json={"email": email, "password": password})
    assert res.status_code == 201, res.text
    return res.json()  # type: ignore[no-any-return]
