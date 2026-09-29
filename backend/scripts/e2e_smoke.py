"""End-to-end smoke test against a RUNNING stack (default: the Next.js proxy on :3000).

Needs ENABLE_MOCK_PROVIDER=true on the server. It registers a throwaway user, so run it only
against a development instance.

    python backend/scripts/e2e_smoke.py [base_url]
"""

import sys
import time
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"


def wait_for(client: httpx.Client, job_id: str, want: set[str], timeout: float = 30) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in want:
            return job
        time.sleep(0.5)
    raise SystemExit(f"timeout waiting for {want}; last status {job['status']}")


def main() -> None:
    c = httpx.Client(base_url=BASE, follow_redirects=False, timeout=30)
    email = f"e2e-{uuid.uuid4().hex[:8]}@example.com"
    assert (
        c.post(
            "/api/auth/register", json={"email": email, "password": "e2e-pass-12345"}
        ).status_code
        == 201
    )
    print("registered", email)

    assert c.get("/api/accounts").json() == []
    limited = c.post(
        "/api/accounts", json={"provider": "mock", "label": "limited", "api_key": "mock-ratelimit"}
    )
    healthy = c.post(
        "/api/accounts", json={"provider": "mock", "label": "healthy", "api_key": "mock-healthy-1"}
    )
    assert limited.status_code == healthy.status_code == 201
    assert "mock-healthy-1" not in healthy.text
    print("connected 2 accounts; keys not echoed")

    # 1) normal job
    job_id = c.post(
        "/api/jobs",
        json={"prompt": "A futuristic city at night", "number_of_outputs": 4, "provider": "auto"},
    ).json()["job_id"]
    job = wait_for(c, job_id, {"completed", "failed", "retrying"}, 60)
    print("job 1:", job["status"], job["account_label"], len(job["outputs"]), "outputs")

    # 2) force the limited account first: it is 429'd, then the job must land on 'healthy'
    ids = [
        c.post(
            "/api/jobs",
            json={"prompt": f"rate limit test {i}", "number_of_outputs": 1, "provider": "auto"},
        ).json()["job_id"]
        for i in range(4)
    ]
    finished = [wait_for(c, i, {"completed", "failed"}, 90) for i in ids]
    print(
        "statuses:",
        [j["status"] for j in finished],
        "accounts:",
        [j["account_label"] for j in finished],
    )
    assert all(j["status"] == "completed" for j in finished), (
        "jobs should fail over to the healthy account"
    )
    assert all(j["account_label"] == "healthy" for j in finished)
    limited_acc = next(a for a in c.get("/api/accounts").json() if a["label"] == "limited")
    print(
        "limited account available:",
        limited_acc["available"],
        "until",
        limited_acc["rate_limited_until"],
    )
    assert limited_acc["available"] is False  # honoring the provider's window

    # 3) results, gallery, usage
    gallery = c.get("/api/gallery").json()
    img = c.get(gallery["items"][0]["url"])
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
    usage = c.get("/api/usage").json()
    print(
        "gallery total:",
        gallery["total"],
        "| usage images:",
        usage["images"],
        "requests:",
        usage["requests"],
    )
    assert usage["input_tokens"] is None

    # 4) logout invalidates the session
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").status_code == 401
    print("ALL OK")


if __name__ == "__main__":
    main()
