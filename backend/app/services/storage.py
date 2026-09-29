"""Object storage abstraction. Image bytes never go into PostgreSQL.

To add S3 / Cloudflare R2: implement `Storage` (put/get/delete/exists) with boto3 and return it
from `get_storage()` for STORAGE_TYPE=s3|r2 (R2 is S3-compatible; only the endpoint differs).
"""

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.config import get_settings


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Invalid storage key")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_type == "local":
        return LocalStorage(settings.storage_local_path)
    raise RuntimeError(
        f"STORAGE_TYPE={settings.storage_type!r} is not implemented yet. "
        "Implement the Storage protocol in app/services/storage.py to add it."
    )
