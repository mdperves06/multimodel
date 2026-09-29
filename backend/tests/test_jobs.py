from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session_factory
from app.models import ConnectedAccount, Job, UsageRecord
from app.models.base import utcnow
from app.security.crypto import encrypt_credentials
from app.services.storage import get_storage
from app.workers.queue import JobQueue
from tests.conftest import connect, drain, make_all_delayed_due, register, submit


def job(client: TestClient, job_id: str) -> dict[str, Any]:
    res = client.get(f"/api/jobs/{job_id}")
    assert res.status_code == 200, res.text
    data: dict[str, Any] = res.json()
    return data


# ---------- creation & validation ----------


def test_create_job_returns_queued(client: TestClient) -> None:
    register(client)
    connect(client)
    res = client.post(
        "/api/jobs",
        json={
            "type": "image_generation",
            "prompt": "A futuristic city at night",
            "number_of_outputs": 4,
            "provider": "auto",
        },
    )
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "queued" and body["job_id"]
    assert JobQueue().size() == 1


def test_jobs_require_auth(client: TestClient) -> None:
    assert client.post("/api/jobs", json={"prompt": "x"}).status_code == 401
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/gallery").status_code == 401
    assert client.get("/api/usage").status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"prompt": ""},
        {"prompt": "   "},
        {"prompt": "x", "number_of_outputs": 0},
        {"prompt": "x", "number_of_outputs": 11},
        {"prompt": "x", "type": "video_generation"},
        {"prompt": "x", "provider": "Bad Provider!"},
        {"prompt": "x", "size": "huge"},
        {"prompt": "x" * 4001},
    ],
)
def test_invalid_job_payloads_rejected(client: TestClient, payload: dict[str, Any]) -> None:
    register(client)
    assert client.post("/api/jobs", json=payload).status_code == 422


def test_unknown_provider_or_model_rejected(client: TestClient) -> None:
    register(client)
    assert client.post("/api/jobs", json={"prompt": "x", "provider": "nope"}).status_code == 400
    assert (
        client.post(
            "/api/jobs", json={"prompt": "x", "provider": "mock", "model": "gpt-9"}
        ).status_code
        == 400
    )


def test_active_job_cap(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "max_active_jobs_per_user", 2)
    register(client)
    submit(client)
    submit(client)
    assert client.post("/api/jobs", json={"prompt": "x"}).status_code == 429


# ---------- queue processing & results ----------


def test_job_completes_and_stores_results(client: TestClient) -> None:
    register(client)
    connect(client)
    job_id = submit(client, number_of_outputs=4)
    assert job(client, job_id)["status"] == "queued"

    assert drain() == 1
    j = job(client, job_id)
    assert j["status"] == "completed" and len(j["outputs"]) == 4
    assert j["provider_used"] == "mock" and j["model_used"] == "mock-image-1"
    assert j["started_at"] and j["completed_at"]
    stages = [e["stage"] for e in j["events"]]
    assert stages == ["created", "queued", "processing", "generating", "storing", "completed"]

    # bytes live in object storage, not in the database
    storage = get_storage()
    with get_session_factory()() as db:
        outputs = list(db.scalars(select(Job)))[0].outputs
        assert len(outputs) == 4
        for o in outputs:
            assert storage.exists(o.storage_key) and o.size_bytes > 100
            assert o.storage_key.startswith(f"{o.user_id}/{o.job_id}/")

    # file is served to the owner with safe headers
    url = j["outputs"][0]["url"]
    res = client.get(url)
    assert res.status_code == 200 and res.content.startswith(b"\x89PNG")
    assert res.headers["content-type"] == "image/png"
    assert "attachment" in client.get(url + "?download=true").headers["content-disposition"]


def test_large_job_is_split_into_provider_sized_batches(client: TestClient) -> None:
    register(client)
    acc = connect(client)
    job_id = submit(client, number_of_outputs=6)  # mock allows 4 per request
    drain()
    assert len(job(client, job_id)["outputs"]) == 6
    usage = client.get(f"/api/accounts/{acc['id']}/usage").json()
    assert usage["requests"] == 2 and usage["images"] == 6


def test_processing_is_idempotent(client: TestClient) -> None:
    register(client)
    connect(client)
    job_id = submit(client)
    drain()
    JobQueue().enqueue(job_id)  # duplicate queue entry
    drain()
    assert len(job(client, job_id)["outputs"]) == 1


# ---------- provider selection ----------


def test_no_account_fails_with_clear_message(client: TestClient) -> None:
    register(client)
    job_id = submit(client, provider="auto")
    drain()
    j = job(client, job_id)
    assert j["status"] == "failed" and "Connect a provider" in j["error"]


def test_auto_rotates_between_accounts(client: TestClient) -> None:
    register(client)
    connect(client, label="one")
    connect(client, label="two")
    j1, j2 = submit(client, provider="auto"), submit(client, provider="auto")
    drain()
    used = {job(client, j1)["account_label"], job(client, j2)["account_label"]}
    assert used == {"one", "two"}


def test_explicit_provider_without_account_fails(client: TestClient) -> None:
    register(client)
    connect(client, provider="mock")
    job_id = submit(client, provider="openai")
    drain()
    assert job(client, job_id)["status"] == "failed"


def test_selection_skips_invalid_accounts(client: TestClient) -> None:
    register(client)
    bad = connect(client, label="bad")
    connect(client, label="good")
    with get_session_factory()() as db:
        acc = db.get(ConnectedAccount, __import__("uuid").UUID(bad["id"]))
        assert acc is not None
        acc.status = "invalid"
        db.commit()
    ids = [submit(client, provider="auto") for _ in range(3)]
    drain()
    assert {job(client, i)["account_label"] for i in ids} == {"good"}


# ---------- rate limits & retries ----------


def test_rate_limit_is_respected_not_bypassed(client: TestClient) -> None:
    register(client)
    acc = connect(client, key="mock-ratelimit")
    job_id = submit(client)
    drain()

    j = job(client, job_id)
    assert j["status"] == "retrying" and j["attempts"] == 1
    assert "rate limited" in j["events"][-1]["message"].lower()
    account = client.get(f"/api/accounts/{acc['id']}").json()
    assert account["available"] is False and account["rate_limited_until"]
    assert JobQueue().delayed_size() == 1 and JobQueue().size() == 0

    # Nothing runs while the provider's window is still open.
    assert drain() == 0
    # Even if the queue entry is made due, the limited account is not called again early.
    make_all_delayed_due()
    drain()
    j = job(client, job_id)
    assert j["status"] == "retrying" and j["attempts"] == 2
    with get_session_factory()() as db:
        assert db.scalars(select(UsageRecord)).first() is None  # no request was billed


def test_rate_limited_job_moves_to_other_account(client: TestClient) -> None:
    register(client)
    connect(client, key="mock-ratelimit", label="limited")
    connect(client, key="mock-good-key", label="healthy")
    # Make "limited" the least-recently-used so it is tried first.
    with get_session_factory()() as db:
        good = db.scalar(select(ConnectedAccount).where(ConnectedAccount.label == "healthy"))
        assert good is not None
        good.last_request_at = utcnow()
        db.commit()
    job_id = submit(client, provider="auto")
    drain()
    assert job(client, job_id)["status"] == "retrying"
    make_all_delayed_due()
    drain()
    j = job(client, job_id)
    assert j["status"] == "completed" and j["account_label"] == "healthy"


def test_retry_after_window_expiry_allows_reuse(client: TestClient) -> None:
    register(client)
    acc = connect(client, key="mock-ratelimit")
    submit(client)
    drain()
    with get_session_factory()() as db:
        row = db.get(ConnectedAccount, __import__("uuid").UUID(acc["id"]))
        assert row is not None and row.rate_limited_until is not None
        assert row.rate_limited_until > utcnow() + timedelta(seconds=1)  # provider said 2s
        row.rate_limited_until = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get(f"/api/accounts/{acc['id']}").json()["available"] is True


def test_transient_errors_back_off_then_give_up(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "max_job_attempts", 3)
    register(client)
    connect(client, key="mock-flaky")
    job_id = submit(client)
    delays = []
    for _ in range(3):
        drain()
        j = job(client, job_id)
        if j["status"] == "retrying":
            delays.append(
                (
                    __import__("datetime").datetime.fromisoformat(j["next_retry_at"]) - utcnow()
                ).total_seconds()
            )
        make_all_delayed_due()
    j = job(client, job_id)
    assert j["status"] == "failed" and "gave up after 3 attempts" in j["error"]
    assert len(delays) == 2 and delays[1] > delays[0]  # exponential backoff


def test_auth_failure_flags_account_invalid(client: TestClient) -> None:
    register(client)
    acc = connect(client)
    with get_session_factory()() as db:
        row = db.get(ConnectedAccount, __import__("uuid").UUID(acc["id"]))
        assert row is not None
        row.encrypted_credentials = encrypt_credentials({"api_key": "mock-invalid"})
        db.commit()
    job_id = submit(client)
    drain()
    make_all_delayed_due()
    drain()
    assert job(client, job_id)["status"] == "failed"
    assert client.get(f"/api/accounts/{acc['id']}").json()["status"] == "invalid"


def test_quota_exhaustion_waits_instead_of_hammering_provider(client: TestClient) -> None:
    register(client)
    connect(client, key="mock-quota")
    job_id = submit(client)
    drain()
    j = job(client, job_id)
    # quota exhaustion locks the account for ~1h; there is nothing else to run on
    assert j["status"] == "retrying"
    assert JobQueue().delayed_size() == 1


# ---------- cancel / retry ----------


def test_cancel_queued_job_is_never_processed(client: TestClient) -> None:
    register(client)
    connect(client)
    job_id = submit(client)
    res = client.post(f"/api/jobs/{job_id}/cancel")
    assert res.status_code == 200 and res.json()["status"] == "cancelled"
    drain()
    j = job(client, job_id)
    assert j["status"] == "cancelled" and j["outputs"] == []


def test_cannot_cancel_finished_job(client: TestClient) -> None:
    register(client)
    connect(client)
    job_id = submit(client)
    drain()
    assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 409


def test_retry_failed_job(client: TestClient) -> None:
    register(client)
    job_id = submit(client, provider="auto")
    drain()
    assert job(client, job_id)["status"] == "failed"
    assert client.post(f"/api/jobs/{job_id}/retry").json()["status"] == "queued"
    connect(client)
    drain()
    assert job(client, job_id)["status"] == "completed"
    assert client.post(f"/api/jobs/{job_id}/retry").status_code == 409


# ---------- ownership ----------


def test_users_cannot_see_each_others_jobs_or_images(client: TestClient) -> None:
    register(client, "a@example.com")
    connect(client)
    job_id = submit(client)
    drain()
    out = job(client, job_id)["outputs"][0]
    client.cookies.clear()
    register(client, "b@example.com")
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.get(f"/api/jobs/{job_id}/outputs").status_code == 404
    assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 404
    assert client.get(out["url"]).status_code == 404
    assert client.delete(f"/api/outputs/{out['id']}").status_code == 404
    assert client.get("/api/jobs").json()["total"] == 0
    assert client.get("/api/gallery").json()["total"] == 0


# ---------- listing ----------


def test_list_jobs_pagination_and_filter(client: TestClient) -> None:
    register(client)
    connect(client)
    for _ in range(3):
        submit(client)
    drain()
    submit(client)
    page = client.get("/api/jobs?limit=2").json()
    assert page["total"] == 4 and len(page["items"]) == 2
    assert client.get("/api/jobs?status=completed").json()["total"] == 3
    assert client.get("/api/jobs?status=queued").json()["total"] == 1
    assert client.get("/api/jobs?status=bogus").status_code == 400


# ---------- account deletion ----------


def test_account_deletion_keeps_history_but_removes_usage(client: TestClient) -> None:
    register(client)
    acc = connect(client)
    job_id = submit(client, number_of_outputs=2)
    drain()
    assert client.delete(f"/api/accounts/{acc['id']}").status_code == 204
    j = job(client, job_id)
    assert j["status"] == "completed" and len(j["outputs"]) == 2
    with get_session_factory()() as db:
        assert db.scalar(select(UsageRecord)) is None
        assert db.scalars(select(Job)).first().account_id is None  # type: ignore[union-attr]
    assert client.get(j["outputs"][0]["url"]).status_code == 200
