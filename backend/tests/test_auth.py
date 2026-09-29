from fastapi.testclient import TestClient

from app.security.passwords import hash_password
from tests.conftest import register


def test_register_login_me_logout(client: TestClient) -> None:
    data = register(client)
    assert data["user"]["email"] == "alice@example.com"
    assert "password" not in str(data)
    assert client.get("/api/auth/me").json()["email"] == "alice@example.com"

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    res = client.post(
        "/api/auth/login", json={"email": "ALICE@example.com", "password": "s3cret-pass-1"}
    )
    assert res.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_logout_revokes_token_for_bearer_clients(client: TestClient) -> None:
    token = register(client)["access_token"]
    client.cookies.clear()
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=h).status_code == 200
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_duplicate_email_rejected(client: TestClient) -> None:
    register(client)
    res = client.post(
        "/api/auth/register", json={"email": "alice@example.com", "password": "another-pass-9"}
    )
    assert res.status_code == 409


def test_weak_password_rejected_and_not_echoed(client: TestClient) -> None:
    res = client.post("/api/auth/register", json={"email": "a@b.co", "password": "Zq9!x"})
    assert res.status_code == 422
    assert "Zq9!x" not in res.text


def test_bad_login(client: TestClient) -> None:
    register(client)
    client.cookies.clear()
    wrong = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "nope"})
    unknown = client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_password_is_hashed_in_db(client: TestClient) -> None:
    from sqlalchemy import select

    from app.db import get_session_factory
    from app.models import User

    register(client)
    with get_session_factory()() as db:
        user = db.scalar(select(User))
        assert user is not None
        assert user.password_hash.startswith("$argon2")
        assert "s3cret-pass-1" not in user.password_hash
    assert hash_password("x") != hash_password("x")


def test_private_routes_require_auth(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    )


def test_cookie_flags(client: TestClient) -> None:
    res = client.post("/api/auth/register", json={"email": "c@d.co", "password": "s3cret-pass-1"})
    cookie = res.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_cross_origin_post_blocked(client: TestClient) -> None:
    res = client.post(
        "/api/auth/login",
        json={"email": "a@b.co", "password": "x"},
        headers={"Origin": "https://evil.example"},
    )
    assert res.status_code == 403


def test_auth_rate_limit(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    monkeypatch.setattr(get_settings(), "auth_rate_limit_per_minute", 3)
    codes = [
        client.post("/api/auth/login", json={"email": "a@b.co", "password": "x"}).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]
