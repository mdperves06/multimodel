"""OpenAI adapter using the official OpenAI REST API (https://api.openai.com/v1)."""

import base64
import re
from typing import Any

import httpx

from app.providers.base import (
    UNAVAILABLE_USAGE_MESSAGE,
    Credentials,
    GeneratedImage,
    ImageRequest,
    ImageResult,
    LimitsInfo,
    ModelInfo,
    ProviderAdapter,
    ProviderAuthError,
    ProviderError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTransientError,
    UsageInfo,
    ValidationResult,
)

DEFAULT_RETRY_AFTER = 20.0
QUOTA_RETRY_AFTER = 3600.0
_DURATION = re.compile(r"(?:(\d+(?:\.\d+)?)(ms|h|m|s))")
_LIMIT_HEADERS = {
    "x-ratelimit-limit-requests": "limit_requests",
    "x-ratelimit-remaining-requests": "remaining_requests",
    "x-ratelimit-reset-requests": "reset_requests",
    "x-ratelimit-limit-tokens": "limit_tokens",
    "x-ratelimit-remaining-tokens": "remaining_tokens",
    "x-ratelimit-reset-tokens": "reset_tokens",
}


def parse_duration(value: str) -> float | None:
    """Parse OpenAI durations such as '1s', '6m0s', '250ms'."""
    parts = _DURATION.findall(value.strip())
    if not parts:
        try:
            return float(value)
        except ValueError:
            return None
    factor = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}
    return sum(float(num) * factor[unit] for num, unit in parts)


def parse_limits(headers: httpx.Headers) -> dict[str, Any] | None:
    found: dict[str, Any] = {}
    for header, key in _LIMIT_HEADERS.items():
        raw = headers.get(header)
        if raw is None:
            continue
        if key.startswith("reset"):
            found[key + "_seconds"] = parse_duration(raw)
        else:
            try:
                found[key] = int(raw)
            except ValueError:
                continue
    return found or None


def retry_after_seconds(headers: httpx.Headers) -> float:
    raw = headers.get("retry-after")
    if raw:
        parsed = parse_duration(raw)
        if parsed is not None:
            return max(parsed, 1.0)
    candidates = [
        parse_duration(headers[h])
        for h in ("x-ratelimit-reset-requests", "x-ratelimit-reset-tokens")
        if h in headers
    ]
    values = [c for c in candidates if c is not None]
    return max(min(values), 1.0) if values else DEFAULT_RETRY_AFTER


def _error_info(response: httpx.Response) -> tuple[str, str]:
    try:
        err = response.json().get("error") or {}
        return str(err.get("message") or ""), str(err.get("code") or err.get("type") or "")
    except (ValueError, AttributeError):
        return "", ""


class OpenAIAdapter(ProviderAdapter):
    slug = "openai"
    name = "OpenAI"
    supports_usage_api = False  # usage endpoints need organisation admin keys
    models = (
        ModelInfo(
            id="gpt-image-1",
            name="GPT Image 1",
            max_outputs_per_request=10,
            sizes=("1024x1024", "1536x1024", "1024x1536", "auto"),
            default_size="1024x1024",
            qualities=("low", "medium", "high", "auto"),
        ),
        ModelInfo(
            id="dall-e-3",
            name="DALL·E 3",
            max_outputs_per_request=1,
            sizes=("1024x1024", "1792x1024", "1024x1792"),
            default_size="1024x1024",
            qualities=("standard", "hd"),
        ),
        ModelInfo(
            id="dall-e-2",
            name="DALL·E 2",
            max_outputs_per_request=10,
            sizes=("256x256", "512x512", "1024x1024"),
            default_size="1024x1024",
        ),
    )

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        transport: httpx.BaseTransport | None = None,
        timeout: float = 180.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout

    def _client(self, credentials: Credentials) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {credentials['api_key']}"},
            timeout=self._timeout,
            transport=self._transport,
        )

    def _request(
        self, credentials: Credentials, method: str, path: str, **kw: Any
    ) -> httpx.Response:
        try:
            with self._client(credentials) as client:
                response = client.request(method, path, **kw)
        except httpx.TimeoutException:
            raise ProviderTransientError("Request to OpenAI timed out") from None
        except httpx.TransportError:
            raise ProviderTransientError("Could not reach OpenAI") from None
        self._raise_for_status(response)
        return response

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        if status < 400:
            return
        message, code = _error_info(response)
        if status == 401:
            raise ProviderAuthError("OpenAI rejected the API key")
        if status == 429:
            if code == "insufficient_quota":
                raise ProviderQuotaError(
                    "OpenAI quota exhausted for this key. Check billing.", QUOTA_RETRY_AFTER
                )
            raise ProviderRateLimitError(
                "OpenAI rate limit reached", retry_after_seconds(response.headers)
            )
        if status >= 500:
            raise ProviderTransientError(f"OpenAI server error ({status})")
        if status == 403:
            raise ProviderRequestError(
                message or "Access denied. The key may lack access to this model."
            )
        raise ProviderRequestError(message or f"OpenAI rejected the request ({status})")

    def validate_credentials(self, credentials: Credentials) -> ValidationResult:
        try:
            response = self._request(credentials, "GET", "/models")
        except ProviderAuthError:
            return ValidationResult(False, "OpenAI rejected the API key")
        except ProviderRateLimitError as exc:
            return ValidationResult(False, f"{exc.message}. Try again shortly.")
        except ProviderError as exc:
            return ValidationResult(False, exc.message)
        return ValidationResult(True, None, parse_limits(response.headers))

    def generate_image(self, credentials: Credentials, request: ImageRequest) -> ImageResult:
        model = self.get_model(request.model)
        if model is None:
            raise ProviderRequestError(f"Unsupported model: {request.model}")
        if request.n > model.max_outputs_per_request:
            raise ProviderRequestError(
                f"{model.id} supports at most {model.max_outputs_per_request} images per request"
            )
        payload: dict[str, Any] = {"model": model.id, "prompt": request.prompt, "n": request.n}
        if request.size:
            payload["size"] = request.size
        if request.quality:
            payload["quality"] = request.quality
        if model.id.startswith("dall-e"):
            payload["response_format"] = "b64_json"  # gpt-image-1 always returns base64

        response = self._request(credentials, "POST", "/images/generations", json=payload)
        body = response.json()
        images: list[GeneratedImage] = []
        for item in body.get("data", []):
            b64 = item.get("b64_json")
            if not b64:
                continue
            meta: dict[str, Any] = {"size": request.size, "quality": request.quality}
            if item.get("revised_prompt"):
                meta["revised_prompt"] = item["revised_prompt"]
            images.append(GeneratedImage(base64.b64decode(b64), "image/png", meta))
        if not images:
            raise ProviderTransientError("OpenAI returned no images")
        usage_raw = body.get("usage") or {}
        usage = {
            k: int(usage_raw[k]) for k in ("input_tokens", "output_tokens") if k in usage_raw
        } or None
        return ImageResult(images, model.id, usage, parse_limits(response.headers))

    def get_usage(self, credentials: Credentials) -> UsageInfo:
        return UsageInfo(available=False, message=UNAVAILABLE_USAGE_MESSAGE)

    def get_limits(self, credentials: Credentials) -> LimitsInfo:
        try:
            response = self._request(credentials, "GET", "/models")
        except ProviderError:
            return LimitsInfo(available=False)
        limits = parse_limits(response.headers)
        return LimitsInfo(available=bool(limits), limits=limits or {})
