import base64
import json

import httpx
import pytest

from app.providers.base import (
    ImageRequest,
    ProviderAuthError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTransientError,
)
from app.providers.openai import OpenAIAdapter, parse_duration

CREDS = {"api_key": "sk-test-abcdefghijklmnop"}
PNG_B64 = base64.b64encode(b"\x89PNG fake bytes").decode()


def adapter(handler) -> OpenAIAdapter:  # type: ignore[no-untyped-def]
    return OpenAIAdapter(base_url="https://api.test/v1", transport=httpx.MockTransport(handler))


def test_parse_duration() -> None:
    assert parse_duration("1s") == 1
    assert parse_duration("6m0s") == 360
    assert parse_duration("250ms") == 0.25
    assert parse_duration("17") == 17
    assert parse_duration("junk") is None


def test_validate_ok_and_sends_bearer_key() -> None:
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers["authorization"]
        seen["path"] = req.url.path
        return httpx.Response(
            200, json={"data": []}, headers={"x-ratelimit-remaining-requests": "99"}
        )

    res = adapter(handler).validate_credentials(CREDS)
    assert res.valid and res.limits == {"remaining_requests": 99}
    assert seen == {"auth": f"Bearer {CREDS['api_key']}", "path": "/v1/models"}


def test_validate_invalid_key_does_not_leak_key() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": {"message": "Incorrect API key provided: sk-test-abc***"}}
        )

    res = adapter(handler).validate_credentials(CREDS)
    assert not res.valid and "sk-" not in (res.error or "")


def test_generate_image_success() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        assert body["model"] == "gpt-image-1" and body["n"] == 2
        assert "response_format" not in body
        return httpx.Response(
            200,
            json={
                "data": [{"b64_json": PNG_B64}, {"b64_json": PNG_B64}],
                "usage": {"input_tokens": 10, "output_tokens": 200, "total_tokens": 210},
            },
        )

    res = adapter(handler).generate_image(
        CREDS, ImageRequest(prompt="a cat", n=2, model="gpt-image-1", size="1024x1024")
    )
    assert len(res.images) == 2 and res.images[0].data.startswith(b"\x89PNG")
    assert res.usage == {"input_tokens": 10, "output_tokens": 200}


def test_dalle_requests_b64_and_enforces_batch_size() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert json.loads(req.content)["response_format"] == "b64_json"
        return httpx.Response(200, json={"data": [{"b64_json": PNG_B64}]})

    a = adapter(handler)
    assert len(a.generate_image(CREDS, ImageRequest("x", 1, "dall-e-3")).images) == 1
    with pytest.raises(ProviderRequestError):
        a.generate_image(CREDS, ImageRequest("x", 2, "dall-e-3"))


def test_429_uses_retry_after_header() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, json={"error": {"code": "rate_limit_exceeded"}}, headers={"retry-after": "37"}
        )

    with pytest.raises(ProviderRateLimitError) as exc:
        adapter(handler).generate_image(CREDS, ImageRequest("x", 1, "gpt-image-1"))
    assert exc.value.retry_after == 37


def test_429_falls_back_to_reset_header() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"x-ratelimit-reset-requests": "6m0s"})

    with pytest.raises(ProviderRateLimitError) as exc:
        adapter(handler).generate_image(CREDS, ImageRequest("x", 1, "gpt-image-1"))
    assert exc.value.retry_after == 360


def test_insufficient_quota_is_not_a_short_retry() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"code": "insufficient_quota"}})

    with pytest.raises(ProviderQuotaError) as exc:
        adapter(handler).generate_image(CREDS, ImageRequest("x", 1, "gpt-image-1"))
    assert exc.value.retry_after >= 3600


@pytest.mark.parametrize(
    ("status", "exc"),
    [(401, ProviderAuthError), (500, ProviderTransientError), (400, ProviderRequestError)],
)
def test_error_mapping(status: int, exc: type[Exception]) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": "nope"}})

    with pytest.raises(exc):
        adapter(handler).generate_image(CREDS, ImageRequest("x", 1, "gpt-image-1"))


def test_network_failure_is_transient() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(ProviderTransientError):
        adapter(handler).generate_image(CREDS, ImageRequest("x", 1, "gpt-image-1"))


def test_usage_is_honestly_unavailable() -> None:
    info = adapter(lambda _: httpx.Response(200)).get_usage(CREDS)
    assert not info.available and info.message == "Usage information unavailable for this provider."
