import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_session_factory
from app.models import ConnectedAccount
from app.providers.openai import OpenAIAdapter
from app.providers.registry import register_adapter, reset_registry
from tests.conftest import register

KEY = "sk-live-super-secret-key-1234"


def connect(client: TestClient, provider="mock", key="mock-good-key", label="A1"):  # type: ignore[no-untyped-def]
    return client.post("/api/accounts", json={"provider": provider, "label": label, "api_key": key})


def test_providers_listed_and_require_auth(client: TestClient) -> None:
    assert client.get("/api/providers").status_code == 401
    register(client)
    slugs = {p["slug"] for p in client.get("/api/providers").json()}
    assert {"openai", "mock"} <= slugs


def test_connect_encrypts_and_never_returns_key(client: TestClient) -> None:
    register(client)
    res = connect(client, key=KEY)
    assert res.status_code == 201, res.text
    assert KEY not in res.text and res.json()["credential_hint"] == "1234"
    assert KEY not in client.get("/api/accounts").text
    assert KEY not in client.get(f"/api/accounts/{res.json()['id']}").text
    with get_session_factory()() as db:
        row = db.scalar(select(ConnectedAccount))
        assert row is not None and KEY not in row.encrypted_credentials
        assert row.encrypted_credentials.startswith("gAAAA")  # Fernet token


def test_invalid_credentials_rejected(client: TestClient) -> None:
    register(client)
    res = connect(client, key="mock-invalid")
    assert res.status_code == 400
    assert client.get("/api/accounts").json() == []


def test_unknown_provider_rejected(client: TestClient) -> None:
    register(client)
    assert connect(client, provider="nope").status_code == 400


def test_openai_connection_uses_official_api_validation(client: TestClient) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        ok = req.headers["authorization"] == f"Bearer {KEY}"
        return httpx.Response(200 if ok else 401, json={"data": []})

    reset_registry()
    register_adapter(
        OpenAIAdapter(base_url="https://x.test/v1", transport=httpx.MockTransport(handler))
    )
    try:
        register(client)
        assert connect(client, "openai", "sk-wrong-key-000000").status_code == 400
        assert connect(client, "openai", KEY).status_code == 201
    finally:
        reset_registry()


def test_test_endpoint_updates_status(client: TestClient) -> None:
    register(client)
    acc = connect(client).json()
    res = client.post(f"/api/accounts/{acc['id']}/test").json()
    assert res["ok"] and res["account"]["last_validated_at"]


def test_accounts_are_isolated_between_users(client: TestClient) -> None:
    register(client, "a@example.com")
    acc = connect(client).json()
    client.cookies.clear()
    register(client, "b@example.com")
    assert client.get("/api/accounts").json() == []
    assert client.get(f"/api/accounts/{acc['id']}").status_code == 404
    assert client.delete(f"/api/accounts/{acc['id']}").status_code == 404
    assert client.post(f"/api/accounts/{acc['id']}/test").status_code == 404


def test_delete_account_removes_credentials(client: TestClient) -> None:
    register(client)
    acc = connect(client).json()
    assert client.delete(f"/api/accounts/{acc['id']}").status_code == 204
    assert client.get(f"/api/accounts/{acc['id']}").status_code == 404
    with get_session_factory()() as db:
        assert db.scalar(select(ConnectedAccount)) is None
