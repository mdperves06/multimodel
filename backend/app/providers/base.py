"""Provider-agnostic adapter contract.

Everything provider-specific (endpoints, auth, error formats, rate-limit headers) lives in a
concrete adapter. The job system only ever talks to `ProviderAdapter`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

IMAGE_GENERATION = "image_generation"

Credentials = dict[str, Any]


class ProviderError(Exception):
    """Base class. `message` is safe to show to users (never contains credentials)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProviderAuthError(ProviderError):
    """The provider rejected the credentials."""


class ProviderRateLimitError(ProviderError):
    """HTTP 429. `retry_after` is the provider's own guidance in seconds."""

    def __init__(self, message: str, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ProviderQuotaError(ProviderRateLimitError):
    """Billing/quota exhausted. Retrying soon will not help."""


class ProviderTransientError(ProviderError):
    """Timeouts, 5xx and network failures: safe to retry with backoff."""


class ProviderRequestError(ProviderError):
    """The request itself was refused (bad params, policy). Retrying will not help."""


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    capability: str = IMAGE_GENERATION
    max_outputs_per_request: int = 1
    sizes: tuple[str, ...] = ()
    default_size: str | None = None
    qualities: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "capability": self.capability,
            "max_outputs_per_request": self.max_outputs_per_request,
            "sizes": list(self.sizes),
            "default_size": self.default_size,
            "qualities": list(self.qualities),
        }


@dataclass
class ImageRequest:
    prompt: str
    n: int
    model: str
    size: str | None = None
    quality: str | None = None


@dataclass
class GeneratedImage:
    data: bytes
    mime_type: str = "image/png"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageResult:
    images: list[GeneratedImage]
    model: str
    usage: dict[str, int] | None = None  # e.g. input_tokens / output_tokens, if reported
    limits: dict[str, Any] | None = None  # rate-limit info reported by the provider


@dataclass
class ValidationResult:
    valid: bool
    error: str | None = None
    limits: dict[str, Any] | None = None


@dataclass
class UsageInfo:
    available: bool
    message: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class LimitsInfo:
    available: bool
    limits: dict[str, Any] = field(default_factory=dict)


UNAVAILABLE_USAGE_MESSAGE = "Usage information unavailable for this provider."


class ProviderAdapter(ABC):
    slug: ClassVar[str]
    name: ClassVar[str]
    capabilities: ClassVar[tuple[str, ...]] = (IMAGE_GENERATION,)
    models: ClassVar[tuple[ModelInfo, ...]] = ()
    supports_usage_api: ClassVar[bool] = False

    def get_model(self, model_id: str) -> ModelInfo | None:
        return next((m for m in self.models if m.id == model_id), None)

    def default_model(self, capability: str = IMAGE_GENERATION) -> str | None:
        return next((m.id for m in self.models if m.capability == capability), None)

    def supports(self, capability: str, model_id: str | None = None) -> bool:
        if capability not in self.capabilities:
            return False
        if model_id is None:
            return True
        model = self.get_model(model_id)
        return model is not None and model.capability == capability

    @abstractmethod
    def validate_credentials(self, credentials: Credentials) -> ValidationResult:
        """Check the credentials against the provider without generating billable content."""

    @abstractmethod
    def generate_image(self, credentials: Credentials, request: ImageRequest) -> ImageResult:
        """Run ONE provider request. `request.n` must not exceed the model's per-request max."""

    @abstractmethod
    def get_usage(self, credentials: Credentials) -> UsageInfo:
        """Usage as reported by the provider. Must not invent numbers."""

    @abstractmethod
    def get_limits(self, credentials: Credentials) -> LimitsInfo:
        """Rate limits as reported by the provider."""
