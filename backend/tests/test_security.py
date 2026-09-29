import logging
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings, get_settings
from app.db import get_session_factory
from app.errors import register_error_handlers
from app.models import ConnectedAccount
from app.security import ratelimit
from app.security.redaction import RedactingFormatter, redact
from tests.conftest import connect, drain, register, submit


def test_redaction_masks_secrets() -> None:
    samples = [
        "key is sk-proj-abcdefghijklmnop1234",
        "Authorization: Bearer abc.def.ghi-123",
        'payload {"password": "hunter2hunter2", "api_key": "topsecretvalue"}',
        "token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2ln",
    ]
    leaks = ("abcdefghijklmnop1234", "abc.def.ghi", "hunter2", "topsecretvalue", "eyJhbGci")
    for text in samples:
        out = redact(text)
        for leaked in leaks:
            assert leaked not in out


def test_log_formatter_redacts_exception_tracebacks() -> None:
    fmt = RedactingFormatter("%(message)s")
    try:
        raise RuntimeError("upstream said api_key=sk-live-abcdefghijk")
    except RuntimeError:
        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "boom", None, sys.exc_info())
    assert "sk-live-abcdefghijk" not in fmt.format(record)


def test_unhandled_errors_do_not_leak_details() -> None:
    boom = FastAPI()

    @boom.get("/boom")
    def _boom() -> None:
        raise RuntimeError("secret sk-live-abcdefghijk exploded")

    register_error_handlers(boom)
    res = TestClient(boom, raise_server_exceptions=False).get("/boom")
    assert res.status_code == 500
    assert res.json()["detail"] == "Internal server error"
    assert "sk-live" not in res.text and "Traceback" not in res.text


def test_security_headers_on_api_and_images(client: TestClient) -> None:
    register(client)
    connect(client)
    submit(client)
    drain()
    job = client.get("/api/jobs").json()["items"][0]
    res = client.get(job["outputs"][0]["url"])
    assert res.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in res.headers["content-security-policy"]
    assert res.headers["referrer-policy"] == "no-referrer"
    assert client.get("/api/jobs").headers["cache-control"] == "no-store"


def test_sql_injection_payloads_are_inert(client: TestClient) -> None:
    register(client)
    evil = "'; DROP TABLE users; --"
    assert client.get("/api/gallery", params={"q": evil}).status_code == 200
    assert client.get("/api/jobs", params={"status": evil}).status_code == 400
    assert client.post("/api/jobs", json={"prompt": evil, "provider": "mock"}).status_code == 202
    assert client.get("/api/auth/me").json()["email"] == "alice@example.com"


def test_stored_prompts_are_returned_as_data_not_html(client: TestClient) -> None:
    register(client)
    xss = "<script>alert(1)</script>"
    client.post("/api/jobs", json={"prompt": xss, "provider": "mock"})
    res = client.get("/api/jobs")
    assert res.headers["content-type"].startswith("application/json")
    assert res.json()["items"][0]["prompt"] == xss  # React renders it as text, never as HTML


def test_body_size_limit(client: TestClient) -> None:
    register(client)
    res = client.post(
        "/api/jobs", content=b"x" * 1_100_000, headers={"content-type": "application/json"}
    )
    assert res.status_code == 413


def test_expensive_endpoints_are_rate_limited(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    monkeypatch.setitem(ratelimit._EXPENSIVE, ("POST", "/api/accounts"), 2)
    register(client)
    codes = [
        client.post(
            "/api/accounts",
            json={"provider": "mock", "label": f"a{i}", "api_key": "mock-key-1234"},
        ).status_code
        for i in range(4)
    ]
    assert codes == [201, 201, 429, 429]


def test_login_throttled_per_email_across_ips(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    monkeypatch.setattr(get_settings(), "auth_rate_limit_per_minute", 3)
    monkeypatch.setattr(get_settings(), "global_rate_limit_per_minute", 1000)
    monkeypatch.setattr(get_settings(), "trust_proxy", True)
    codes = [
        client.post(
            "/api/auth/login",
            json={"email": "victim@example.com", "password": "guess"},
            headers={"x-forwarded-for": f"10.0.0.{i}"},
        ).status_code
        for i in range(5)
    ]
    assert codes == [401, 401, 401, 429, 429]


def test_credentials_never_appear_in_api_responses_or_audit(client: TestClient) -> None:
    register(client)
    key = "mock-topsecret-key-98765"
    acc = connect(client, key=key)
    blobs = [
        client.get("/api/accounts").text,
        client.get(f"/api/accounts/{acc['id']}").text,
        client.post(f"/api/accounts/{acc['id']}/test").text,
        client.get("/api/audit-logs").text,
        client.get("/api/usage").text,
    ]
    assert all(key not in b for b in blobs)
    with get_session_factory()() as db:
        row = db.scalar(select(ConnectedAccount))
        assert row is not None and key not in row.encrypted_credentials


def test_production_refuses_unsafe_settings() -> None:
    from pydantic import ValidationError

    base = {
        "jwt_secret": "x" * 40,
        "encryption_key": "Y7c1kQz4mQWJ3xv0tN9pR2s8uYdHf6bLaEoGiTjKcVw=",
        "environment": "production",
        "database_url": "postgresql+psycopg://u:p@db/x",
        "redis_url": "redis://r:6379/0",
        "enable_mock_provider": False,
    }
    Settings(**base)  # valid
    bad = (
        {"redis_url": "memory://"},
        {"database_url": "sqlite:///x.db"},
        {"enable_mock_provider": True},
        {"jwt_secret": "short"},
        {"encryption_key": "nope"},
    )
    for override in bad:
        with pytest.raises(ValidationError):
            Settings(**{**base, **override})


def test_trusted_host_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import create_app

    monkeypatch.setattr(get_settings(), "allowed_hosts", "app.example.com")
    strict = TestClient(create_app())
    assert strict.get("/api/health", headers={"host": "app.example.com"}).status_code == 200
    assert strict.get("/api/health", headers={"host": "backend:8000"}).status_code == 200
    assert strict.get("/api/health", headers={"host": "127.0.0.1:8000"}).status_code == 200
    assert strict.get("/api/health", headers={"host": "evil.example"}).status_code == 400
