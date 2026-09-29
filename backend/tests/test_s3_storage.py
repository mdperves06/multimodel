import boto3
import pytest
from moto import mock_aws

from app.config import get_settings
from app.services import storage as storage_mod
from app.services.storage import S3Storage, build_s3_storage

BUCKET = "acc-test-bucket"


@pytest.fixture
def s3(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    settings = get_settings()
    for name, value in {
        "storage_type": "s3",
        "storage_bucket": BUCKET,
        "storage_access_key": "testing",
        "storage_secret_key": "testing",
        "storage_region": "us-east-1",
        "storage_endpoint_url": "",
    }.items():
        monkeypatch.setattr(settings, name, value)
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        yield build_s3_storage()


def test_s3_roundtrip(s3: S3Storage) -> None:
    key = "user/job/a.png"
    assert not s3.exists(key)
    s3.put(key, b"\x89PNG data", "image/png")
    assert s3.exists(key)
    assert s3.get(key) == b"\x89PNG data"
    s3.delete(key)
    assert not s3.exists(key)
    s3.delete(key)  # deleting a missing object is not an error


def test_s3_missing_object_raises_filenotfound(s3: S3Storage) -> None:
    with pytest.raises(FileNotFoundError):
        s3.get("nope/nothing.png")


def test_factory_selects_s3_and_validates_config(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_type", "s3")
    monkeypatch.setattr(settings, "storage_bucket", "")
    storage_mod.get_storage.cache_clear()
    with pytest.raises(RuntimeError, match="STORAGE_BUCKET"):
        storage_mod.get_storage()
    monkeypatch.setattr(settings, "storage_type", "r2")
    monkeypatch.setattr(settings, "storage_bucket", "b")
    with pytest.raises(RuntimeError, match="STORAGE_ENDPOINT_URL"):
        build_s3_storage()
    monkeypatch.setattr(settings, "storage_type", "bogus")
    storage_mod.get_storage.cache_clear()
    with pytest.raises(RuntimeError, match="Unknown STORAGE_TYPE"):
        storage_mod.get_storage()
    monkeypatch.setattr(settings, "storage_type", "local")
    storage_mod.get_storage.cache_clear()


def test_pipeline_uses_s3_backend(client, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    """Full job -> stored image -> served image, with S3 as the backend."""
    from tests.conftest import connect, drain, register, submit

    settings = get_settings()
    for name, value in {
        "storage_type": "s3",
        "storage_bucket": BUCKET,
        "storage_access_key": "testing",
        "storage_secret_key": "testing",
        "storage_region": "us-east-1",
    }.items():
        monkeypatch.setattr(settings, name, value)
    storage_mod.get_storage.cache_clear()
    try:
        with mock_aws():
            boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
            register(client)
            connect(client)
            submit(client, number_of_outputs=2)
            drain()
            out = client.get("/api/jobs").json()["items"][0]["outputs"]
            assert len(out) == 2
            res = client.get(out[0]["url"])
            assert res.status_code == 200 and res.content.startswith(b"\x89PNG")
            assert client.delete(f"/api/outputs/{out[0]['id']}").status_code == 204
            assert client.get(out[0]["url"]).status_code == 404
    finally:
        monkeypatch.setattr(settings, "storage_type", "local")
        storage_mod.get_storage.cache_clear()
