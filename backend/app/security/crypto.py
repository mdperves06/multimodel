import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().encryption_key.encode())


def encrypt_credentials(credentials: dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(credentials).encode()).decode()


def decrypt_credentials(token: str) -> dict[str, Any]:
    try:
        data: dict[str, Any] = json.loads(_fernet().decrypt(token.encode()))
    except InvalidToken as exc:
        raise ValueError("Stored credentials cannot be decrypted (wrong ENCRYPTION_KEY?)") from exc
    return data
