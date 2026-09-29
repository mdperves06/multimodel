"""Object storage abstraction. Image bytes never go into PostgreSQL.

Backends: local disk, and S3-compatible (AWS S3, Cloudflare R2, MinIO) via boto3.
`get` raises FileNotFoundError when the object does not exist, for every backend.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

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


class S3Storage:
    def __init__(self, client: Any, bucket: str) -> None:
        self._s3 = client
        self._bucket = bucket

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        try:
            body: bytes = self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except self._s3.exceptions.NoSuchKey:
            raise FileNotFoundError(key) from None
        return body

    def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)  # idempotent in S3

    def exists(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
        except self._s3.exceptions.ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True


def build_s3_storage() -> S3Storage:
    import boto3

    s = get_settings()
    if not s.storage_bucket:
        raise RuntimeError("STORAGE_BUCKET is required for S3/R2 storage")
    if s.storage_type == "r2" and not s.storage_endpoint_url:
        raise RuntimeError("STORAGE_ENDPOINT_URL is required for R2 storage")
    client = boto3.client(
        "s3",
        endpoint_url=s.storage_endpoint_url or None,
        region_name=s.storage_region or None,
        aws_access_key_id=s.storage_access_key or None,
        aws_secret_access_key=s.storage_secret_key or None,
    )
    return S3Storage(client, s.storage_bucket)


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_type == "local":
        return LocalStorage(settings.storage_local_path)
    if settings.storage_type in {"s3", "r2"}:
        return build_s3_storage()
    raise RuntimeError(f"Unknown STORAGE_TYPE={settings.storage_type!r} (use local, s3, or r2)")
