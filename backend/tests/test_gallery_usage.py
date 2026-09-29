import io
import zipfile

from fastapi.testclient import TestClient

from app.services.storage import LocalStorage, get_storage
from app.workers.queue import JobQueue
from tests.conftest import connect, drain, register, submit


def _setup(client: TestClient, n: int = 3) -> list[dict]:  # type: ignore[type-arg]
    register(client)
    connect(client)
    job_id = submit(client, number_of_outputs=n, prompt="Neon city_100% rain")
    drain()
    return client.get(f"/api/jobs/{job_id}/outputs").json()  # type: ignore[no-any-return]


def test_gallery_items_have_context_and_search(client: TestClient) -> None:
    outs = _setup(client)
    page = client.get("/api/gallery").json()
    assert page["total"] == 3
    item = page["items"][0]
    assert item["prompt"] == "Neon city_100% rain"
    assert item["provider"] == "mock" and item["model"] == "mock-image-1"
    assert item["url"].endswith("/file") and item["created_at"]
    assert client.get("/api/gallery?q=NEON").json()["total"] == 3
    assert client.get("/api/gallery?q=nothing-like-this").json()["total"] == 0
    assert client.get("/api/gallery?q=%25").json()["total"] == 3  # '%' is literal, matches "100%"
    assert len(outs) == 3


def test_delete_single_output_removes_file(client: TestClient) -> None:
    outs = _setup(client)
    with_key = get_storage()
    assert client.delete(f"/api/outputs/{outs[0]['id']}").status_code == 204
    assert client.get(outs[0]["url"]).status_code == 404
    assert client.get("/api/gallery").json()["total"] == 2
    assert isinstance(with_key, LocalStorage)
    assert len(list(with_key.root.rglob("*.png"))) >= 2


def test_bulk_delete_and_download(client: TestClient) -> None:
    outs = _setup(client, 3)
    ids = [o["id"] for o in outs]
    res = client.post("/api/outputs/download", json={"ids": ids[:2]})
    assert res.status_code == 200 and res.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        assert len(zf.namelist()) == 2
        assert zf.read(zf.namelist()[0]).startswith(b"\x89PNG")
    res = client.post("/api/outputs/delete", json={"ids": ids[:2]})
    assert res.json() == {"deleted": 2}
    assert client.get("/api/gallery").json()["total"] == 1
    assert client.post("/api/outputs/delete", json={"ids": []}).status_code == 422


def test_bulk_ops_ignore_other_users_outputs(client: TestClient) -> None:
    outs = _setup(client)
    client.cookies.clear()
    register(client, "b@example.com")
    assert client.post("/api/outputs/delete", json={"ids": [outs[0]["id"]]}).json() == {
        "deleted": 0
    }
    assert client.post("/api/outputs/download", json={"ids": [outs[0]["id"]]}).status_code == 404


def test_storage_blocks_path_traversal(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import pytest

    storage = LocalStorage(tmp_path)
    storage.put("u/j/a.png", b"x", "image/png")
    assert storage.get("u/j/a.png") == b"x"
    with pytest.raises(ValueError):
        storage.put("../evil.png", b"x", "image/png")
    storage.delete("u/j/a.png")
    assert not storage.exists("u/j/a.png")


def test_usage_reports_real_counts_and_no_invented_numbers(client: TestClient) -> None:
    register(client)
    connect(client, label="one")
    empty = client.get("/api/usage").json()
    assert empty["requests"] == 0 and empty["images"] == 0
    assert empty["input_tokens"] is None  # unknown, not zero

    submit(client, number_of_outputs=3)
    drain()
    usage = client.get("/api/usage").json()
    assert usage["requests"] == 1 and usage["images"] == 3
    assert usage["input_tokens"] is None and usage["output_tokens"] is None
    acc = usage["accounts"][0]
    assert acc["provider_usage"] == {
        "available": False,
        "message": "Usage information unavailable for this provider.",
        "data": {},
    }
    assert sum(d["images"] for d in usage["daily"]) == 3


def test_audit_log_records_actions_without_secrets(client: TestClient) -> None:
    register(client)
    connect(client, key="mock-secret-value-123")
    submit(client)
    logs = client.get("/api/audit-logs").json()
    actions = {entry["action"] for entry in logs}
    assert {"auth.register", "account.connect", "job.create"} <= actions
    assert "mock-secret-value-123" not in str(logs)


def test_queue_delayed_promotion() -> None:
    q = JobQueue()
    q.enqueue_delayed("job-a", 3600)
    q.enqueue_delayed("job-b", 0)
    assert q.promote_due() == 1
    assert q.dequeue(timeout=1) == "job-b"
    assert q.delayed_size() == 1
