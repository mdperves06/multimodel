"""Development/test-only provider. Registered only when ENABLE_MOCK_PROVIDER=true.

It never talks to a network. It exists so the queue, storage and UI can be exercised without
spending real provider credits. Special API keys trigger failure paths:

  mock-invalid    -> authentication failure
  mock-ratelimit  -> HTTP-429-style rate limit (retry_after=2s)
  mock-quota      -> quota exhausted
  mock-flaky      -> transient failure
"""

import hashlib
import struct
import zlib

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
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTransientError,
    UsageInfo,
    ValidationResult,
)


def _png(width: int, height: int, seed: bytes) -> bytes:
    """Deterministic gradient PNG derived from `seed`."""
    r0, g0, b0, r1, g1, b1 = seed[:6]
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter type: none
        for x in range(width):
            t = (x + y) / (width + height)
            rows += bytes(
                (
                    int(r0 + (r1 - r0) * t),
                    int(g0 + (g1 - g0) * t),
                    int(b0 + (b1 - b0) * t),
                )
            )

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b"")
    )


class MockAdapter(ProviderAdapter):
    slug = "mock"
    name = "Mock Provider (development)"
    supports_usage_api = False
    models = (
        ModelInfo(
            id="mock-image-1",
            name="Mock Image 1",
            max_outputs_per_request=4,
            sizes=("256x256",),
            default_size="256x256",
        ),
    )

    def validate_credentials(self, credentials: Credentials) -> ValidationResult:
        if credentials.get("api_key") == "mock-invalid":
            return ValidationResult(False, "Mock provider rejected the API key")
        return ValidationResult(True, None, None)

    def generate_image(self, credentials: Credentials, request: ImageRequest) -> ImageResult:
        key = credentials.get("api_key")
        if key == "mock-invalid":
            raise ProviderAuthError("Mock provider rejected the API key")
        if key == "mock-ratelimit":
            raise ProviderRateLimitError("Mock rate limit reached", retry_after=2.0)
        if key == "mock-quota":
            raise ProviderQuotaError("Mock quota exhausted", retry_after=3600.0)
        if key == "mock-flaky":
            raise ProviderTransientError("Mock transient failure")
        images = []
        for i in range(request.n):
            seed = hashlib.sha256(f"{request.prompt}:{i}".encode()).digest()
            images.append(
                GeneratedImage(
                    _png(256, 256, seed),
                    "image/png",
                    {"size": "256x256", "index": i, "mock": True},
                )
            )
        return ImageResult(images, request.model, usage=None, limits=None)

    def get_usage(self, credentials: Credentials) -> UsageInfo:
        return UsageInfo(available=False, message=UNAVAILABLE_USAGE_MESSAGE)

    def get_limits(self, credentials: Credentials) -> LimitsInfo:
        return LimitsInfo(available=False)
