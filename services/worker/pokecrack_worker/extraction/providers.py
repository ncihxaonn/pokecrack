from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from math import isfinite
from typing import (
    Any,
    Literal,
    Protocol,
    TypeVar,
    runtime_checkable,
)
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

T = TypeVar("T")


class SchemaValidationError(ValueError):
    """Raised when a provider response does not match its declared JSON schema."""


class AIInputLimitError(ValueError):
    """Raised before a request when text or image safety caps are exceeded."""

    def __init__(self, limit_name: str, actual: int, limit: int) -> None:
        self.limit_name = limit_name
        self.actual = actual
        self.limit = limit
        super().__init__(f"{limit_name} exceeded: {actual} > {limit}")


class AIProviderError(RuntimeError):
    """Base error for transport and malformed-response failures."""


class AIHTTPError(AIProviderError):
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body[:10_000]
        super().__init__(f"AI provider HTTP status {status}")


class AITransportError(AIProviderError):
    """A bounded provider transport attempt failed without exposing payload data."""


class AIProviderTimeoutError(AITransportError):
    """All bounded timeout attempts were exhausted."""


class AIResponseError(AIProviderError):
    """Raised when an otherwise successful response has an invalid envelope."""


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("token counts must be non-negative")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class Pricing:
    input_per_million_aud: Decimal = Decimal("0")
    output_per_million_aud: Decimal = Decimal("0")

    def cost(self, usage: TokenUsage) -> Decimal:
        million = Decimal(1_000_000)
        return (
            Decimal(usage.input_tokens) * self.input_per_million_aud
            + Decimal(usage.output_tokens) * self.output_per_million_aud
        ) / million


@dataclass(frozen=True, slots=True)
class AIImage:
    media_type: str
    data: bytes

    def __post_init__(self) -> None:
        if not self.media_type.startswith("image/"):
            raise ValueError("media_type must be an image MIME type")
        if not self.data:
            raise ValueError("image data must not be empty")

    def as_data_url(self) -> str:
        encoded = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.media_type};base64,{encoded}"


@dataclass(frozen=True, slots=True)
class ProviderLimits:
    max_input_bytes: int = 200_000
    max_images: int = 8
    max_image_bytes: int = 8_000_000
    max_total_image_bytes: int = 20_000_000


@dataclass(frozen=True, slots=True)
class AIRequest[T]:
    operation: str
    system_prompt: str
    input_text: str
    schema_name: str
    schema: Mapping[str, Any]
    decoder: Callable[[Mapping[str, Any]], T]
    prompt_version: str = "1.0.0"
    images: tuple[AIImage, ...] = ()


@dataclass(frozen=True, slots=True)
class AIRunMetadata:
    run_id: str
    operation: str
    provider: str
    model: str
    schema_name: str
    started_at: datetime
    completed_at: datetime
    attempts: int
    usage: TokenUsage
    cost_aud: Decimal
    response_id: str | None = None
    prompt_version: str = "unknown"
    cost_is_estimate: bool = False


@dataclass(frozen=True, slots=True)
class AICompletion[T]:
    output: T
    run: AIRunMetadata


@runtime_checkable
class AIProvider(Protocol):
    def complete(self, request: AIRequest[T]) -> AICompletion[T]: ...

    async def extract(self, request: AIRequest[T]) -> AICompletion[T]: ...

    async def validate(self, request: AIRequest[T]) -> AICompletion[T]: ...

    async def escalate(self, request: AIRequest[T]) -> AICompletion[T]: ...


@dataclass(frozen=True, slots=True)
class FixtureResponse:
    payload: Mapping[str, Any]
    usage: TokenUsage = field(default_factory=lambda: TokenUsage(0, 0))
    response_id: str | None = None


@dataclass(frozen=True, slots=True)
class HTTPResponse:
    status: int
    body: bytes


class HTTPTransport(Protocol):
    def __call__(
        self, url: str, headers: dict[str, str], body: bytes, timeout: float
    ) -> HTTPResponse: ...


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Any,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


class UrllibHTTPTransport:
    """Bounded stdlib transport that refuses redirect forwarding."""

    def __init__(self, *, max_response_bytes: int = 2_000_000) -> None:
        if not 1 <= max_response_bytes <= 10_000_000:
            raise ValueError("max_response_bytes must be between 1 and 10000000")
        self.max_response_bytes = max_response_bytes
        self._opener = urllib.request.build_opener(_NoRedirectHandler())

    def _read_bounded(self, response: Any) -> bytes:
        body = response.read(self.max_response_bytes + 1)
        if not isinstance(body, bytes):
            raise AIResponseError("AI provider response body must be bytes")
        if len(body) > self.max_response_bytes:
            raise AIResponseError("AI provider response exceeds configured byte cap")
        return body

    def __call__(
        self, url: str, headers: dict[str, str], body: bytes, timeout: float
    ) -> HTTPResponse:
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            # The provider constructor rejects non-HTTPS base URLs.
            with self._opener.open(request, timeout=timeout) as response:  # nosec B310
                return HTTPResponse(status=response.status, body=self._read_bounded(response))
        except urllib.error.HTTPError as error:
            return HTTPResponse(status=error.code, body=self._read_bounded(error))


def _matches_json_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    raise SchemaValidationError(f"unsupported JSON schema type: {expected}")


def validate_json_schema(value: Any, schema: Mapping[str, Any], path: str = "$") -> None:
    """Validate the JSON-schema subset emitted by worker output models.

    This deliberately small validator avoids a runtime dependency on pydantic or
    jsonschema while enforcing types, required/excess fields, enums, bounds, and
    nested arrays/objects used in structured AI responses.
    """

    expected = schema.get("type")
    if expected is not None:
        expected_types = [expected] if isinstance(expected, str) else list(expected)
        if not any(_matches_json_type(value, item) for item in expected_types):
            names = ", ".join(expected_types)
            raise SchemaValidationError(f"{path}: expected {names}")
        if value is None:
            return

    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(f"{path}: value is not in enum")

    if isinstance(value, Mapping):
        properties = schema.get("properties", {})
        unknown = sorted(set(value) - set(properties))
        if schema.get("additionalProperties") is False and unknown:
            raise SchemaValidationError(f"{path}: unknown field(s): {', '.join(unknown)}")
        required = set(schema.get("required", ()))
        missing = sorted(required - set(value))
        if missing:
            raise SchemaValidationError(f"{path}: missing field(s): {', '.join(missing)}")
        for key, item in value.items():
            if key in properties:
                validate_json_schema(item, properties[key], f"{path}.{key}")

    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            validate_json_schema(item, schema["items"], f"{path}[{index}]")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise SchemaValidationError(f"{path}: string is too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaValidationError(f"{path}: string is too long")
        if "pattern" in schema:
            try:
                matches = re.search(str(schema["pattern"]), value)
            except re.error as error:
                raise SchemaValidationError(f"{path}: schema pattern is invalid") from error
            if matches is None:
                raise SchemaValidationError(f"{path}: string does not match pattern")
        if schema.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise SchemaValidationError(f"{path}: invalid date-time") from error
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise SchemaValidationError(f"{path}: date-time requires an offset")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise SchemaValidationError(f"{path}: array has too few items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise SchemaValidationError(f"{path}: array has too many items")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not isfinite(value):
            raise SchemaValidationError(f"{path}: number must be finite")
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaValidationError(f"{path}: value is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaValidationError(f"{path}: value is above maximum")


def enforce_request_limits(request: AIRequest[Any], limits: ProviderLimits) -> None:
    input_bytes = len(request.system_prompt.encode("utf-8")) + len(
        request.input_text.encode("utf-8")
    )
    if input_bytes > limits.max_input_bytes:
        raise AIInputLimitError("max_input_bytes", input_bytes, limits.max_input_bytes)
    if len(request.images) > limits.max_images:
        raise AIInputLimitError("max_images", len(request.images), limits.max_images)
    oversized = [
        len(image.data) for image in request.images if len(image.data) > limits.max_image_bytes
    ]
    if oversized:
        raise AIInputLimitError("max_image_bytes", max(oversized), limits.max_image_bytes)
    total_image_bytes = sum(len(image.data) for image in request.images)
    if total_image_bytes > limits.max_total_image_bytes:
        raise AIInputLimitError(
            "max_total_image_bytes", total_image_bytes, limits.max_total_image_bytes
        )


class FixtureAIProvider:
    """Deterministic, network-free provider for tests, CI, and replays."""

    provider_name = "fixture"

    def __init__(
        self,
        responses: Sequence[FixtureResponse | Mapping[str, Any]],
        *,
        model: str = "fixture-json-v1",
        pricing: Pricing | None = None,
        limits: ProviderLimits | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        normalized = [
            item if isinstance(item, FixtureResponse) else FixtureResponse(payload=item)
            for item in responses
        ]
        self._responses: deque[FixtureResponse] = deque(normalized)
        self.model = model
        self.pricing = pricing or Pricing()
        self.limits = limits or ProviderLimits()
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def remaining(self) -> int:
        return len(self._responses)

    def complete(self, request: AIRequest[T]) -> AICompletion[T]:
        enforce_request_limits(request, self.limits)
        if not self._responses:
            raise LookupError("fixture provider has no response remaining")
        started_at = self._clock()
        fixture = self._responses.popleft()
        try:
            validate_json_schema(fixture.payload, request.schema)
        except SchemaValidationError as schema_error:
            try:
                output = request.decoder(fixture.payload)
                mapper = getattr(output, "to_mapping", None)
                if not callable(mapper):
                    raise TypeError("decoded fixture must expose to_mapping")
                canonical = mapper()
                validate_json_schema(canonical, request.schema)
            except (AttributeError, TypeError, ValueError, SchemaValidationError) as error:
                raise schema_error from error
        else:
            output = request.decoder(fixture.payload)
        completed_at = self._clock()
        run = AIRunMetadata(
            run_id=str(uuid4()),
            operation=request.operation,
            provider=self.provider_name,
            model=self.model,
            schema_name=request.schema_name,
            started_at=started_at,
            completed_at=completed_at,
            attempts=1,
            usage=fixture.usage,
            cost_aud=self.pricing.cost(fixture.usage),
            response_id=fixture.response_id,
            prompt_version=request.prompt_version,
        )
        return AICompletion(output=output, run=run)

    async def extract(self, request: AIRequest[T]) -> AICompletion[T]:
        return self.complete(request)

    async def validate(self, request: AIRequest[T]) -> AICompletion[T]:
        return self.complete(request)

    async def escalate(self, request: AIRequest[T]) -> AICompletion[T]:
        return self.complete(request)


def _validated_ai_base_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("base_url must be a valid HTTPS URL") from error
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("base_url must be an HTTPS URL without userinfo, query, or fragment")
    hostname = parsed.hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    netloc = hostname if port in (None, 443) else f"{hostname}:{port}"
    path = parsed.path.rstrip("/")
    return urlunsplit(("https", netloc, path, "", ""))


class OpenAICompatibleProvider:
    """OpenAI chat-completions adapter with strict structured JSON output.

    A transport can be injected for fixture/CI use. The default stdlib transport
    is the only networked path and is never invoked merely by importing this module.
    """

    provider_name = "openai_compatible"
    _TRANSIENT_STATUSES = frozenset({408, 409, 429, 500, 502, 503, 504})

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        max_output_tokens: int = 4096,
        pricing: Pricing | None = None,
        limits: ProviderLimits | None = None,
        transport: HTTPTransport | None = None,
        sleeper: Callable[[float], None] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        if not model:
            raise ValueError("model must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 0 <= max_retries <= 5:
            raise ValueError("max_retries must be between 0 and 5")
        if retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be non-negative")
        if not 1 <= max_output_tokens <= 32_768:
            raise ValueError("max_output_tokens must be between 1 and 32768")
        self.api_key = api_key
        self.model = model
        self.base_url = _validated_ai_base_url(base_url)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.max_output_tokens = max_output_tokens
        self.pricing = pricing or Pricing()
        self.limits = limits or ProviderLimits()
        self._transport = transport or UrllibHTTPTransport()
        self._sleeper = sleeper or time.sleep
        self._clock = clock or (lambda: datetime.now(UTC))

    def _request_body(self, request: AIRequest[Any]) -> bytes:
        user_content: list[dict[str, Any]] = [{"type": "text", "text": request.input_text}]
        user_content.extend(
            {
                "type": "image_url",
                "image_url": {"url": image.as_data_url(), "detail": "auto"},
            }
            for image in request.images
        )
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_completion_tokens": self.max_output_tokens,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.schema,
                },
            },
        }
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def estimated_max_cost(self, request: AIRequest[Any]) -> Decimal:
        # One input token cannot represent less than one request byte, so using
        # serialized bytes as tokens is a conservative upper bound.
        input_token_bound = len(self._request_body(request))
        return self.pricing.cost(TokenUsage(input_token_bound, self.max_output_tokens))

    @staticmethod
    def _content_text(message: Mapping[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, Mapping):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            if parts:
                return "".join(parts)
        refusal = message.get("refusal")
        if refusal:
            raise AIResponseError(f"AI provider refused structured response: {refusal}")
        raise AIResponseError("AI response message has no JSON text content")

    @staticmethod
    def _token_usage(envelope: Mapping[str, Any]) -> TokenUsage:
        usage_value = envelope.get("usage")
        if not isinstance(usage_value, Mapping):
            raise AIResponseError("AI response usage is required")
        if "prompt_tokens" in usage_value or "completion_tokens" in usage_value:
            names = ("prompt_tokens", "completion_tokens")
        elif "input_tokens" in usage_value or "output_tokens" in usage_value:
            names = ("input_tokens", "output_tokens")
        else:
            raise AIResponseError("AI response usage token counts are required")
        input_tokens = usage_value.get(names[0])
        output_tokens = usage_value.get(names[1])
        if (
            not isinstance(input_tokens, int)
            or isinstance(input_tokens, bool)
            or not isinstance(output_tokens, int)
            or isinstance(output_tokens, bool)
        ):
            raise AIResponseError("AI response usage token counts must be integers")
        usage = TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
        if usage.total_tokens == 0:
            raise AIResponseError("AI response usage must report consumed tokens")
        return usage

    def _decode_response(
        self, response: HTTPResponse, request: AIRequest[T], started_at: datetime, attempts: int
    ) -> AICompletion[T]:
        try:
            envelope = json.loads(response.body)
            choices = envelope["choices"]
            message = choices[0]["message"]
            payload = json.loads(self._content_text(message))
            usage = self._token_usage(envelope)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            if isinstance(error, (SchemaValidationError, AIResponseError)):
                raise
            raise AIResponseError(f"malformed AI response envelope: {error}") from error
        if not isinstance(payload, Mapping):
            raise AIResponseError("structured AI response must be a JSON object")
        validate_json_schema(payload, request.schema)
        output = request.decoder(payload)
        completed_at = self._clock()
        return AICompletion(
            output=output,
            run=AIRunMetadata(
                run_id=str(uuid4()),
                operation=request.operation,
                provider=self.provider_name,
                model=self.model,
                schema_name=request.schema_name,
                started_at=started_at,
                completed_at=completed_at,
                attempts=attempts,
                usage=usage,
                cost_aud=self.pricing.cost(usage),
                response_id=envelope.get("id"),
                prompt_version=request.prompt_version,
            ),
        )

    def complete(self, request: AIRequest[T]) -> AICompletion[T]:
        enforce_request_limits(request, self.limits)
        started_at = self._clock()
        body = self._request_body(request)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        attempts_allowed = self.max_retries + 1
        last_error: BaseException | None = None
        for attempt in range(1, attempts_allowed + 1):
            try:
                response = self._transport(
                    f"{self.base_url}/chat/completions", headers, body, self.timeout_seconds
                )
            except TimeoutError:
                last_error = AIProviderTimeoutError("AI provider request timed out")
                transient = True
            except OSError:
                last_error = AITransportError("AI provider transport failed")
                transient = True
            else:
                if 200 <= response.status < 300:
                    return self._decode_response(response, request, started_at, attempt)
                last_error = AIHTTPError(response.status, response.body)
                transient = response.status in self._TRANSIENT_STATUSES
            if not transient or attempt == attempts_allowed:
                assert last_error is not None
                raise last_error
            self._sleeper(self.retry_backoff_seconds * (2 ** (attempt - 1)))
        raise AssertionError("retry loop terminated unexpectedly")

    async def extract(self, request: AIRequest[T]) -> AICompletion[T]:
        return self.complete(request)

    async def validate(self, request: AIRequest[T]) -> AICompletion[T]:
        return self.complete(request)

    async def escalate(self, request: AIRequest[T]) -> AICompletion[T]:
        return self.complete(request)


def build_ai_provider(
    settings: Any,
    *,
    operation: Literal["extract", "validate", "escalate"],
    fixture_responses: Sequence[FixtureResponse | Mapping[str, Any]] = (),
    transport: HTTPTransport | None = None,
    budget_ledger: Any | None = None,
) -> AIProvider:
    """Build an operation-specific provider solely from validated settings.

    Real model identifiers have no fallback and must come from the environment-backed
    ``Settings`` object. The optional transport exists for network-free contract tests.
    """

    provider_value = getattr(settings.ai_provider, "value", settings.ai_provider)
    if provider_value == "fixture":
        return FixtureAIProvider(fixture_responses)
    if budget_ledger is None:
        raise ValueError("network AI provider requires a shared budget ledger")
    model_by_operation = {
        "extract": settings.ai_extract_model,
        "validate": settings.ai_validate_model,
        "escalate": settings.ai_escalate_model,
    }
    model = model_by_operation[operation]
    if not model:
        raise ValueError(f"configured model is required for {operation}")
    secret = settings.ai_api_key
    api_key = (
        secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret or "")
    )
    pricing = Pricing(
        settings.ai_input_per_million_aud,
        settings.ai_output_per_million_aud,
    )
    provider = OpenAICompatibleProvider(
        api_key=api_key,
        model=model,
        base_url=settings.ai_base_url,
        timeout_seconds=settings.ai_request_timeout_seconds,
        # Queue-level retries obtain a fresh budget reservation; one provider
        # invocation is deliberately limited to one paid-capable dispatch.
        max_retries=0,
        retry_backoff_seconds=settings.ai_retry_backoff_seconds,
        max_output_tokens=settings.ai_max_output_tokens,
        pricing=pricing,
        transport=transport,
    )
    from .budget import BudgetedAIProvider, BudgetLimits

    expected_limits = BudgetLimits(
        settings.ai_daily_budget_aud,
        settings.ai_monthly_soft_budget_aud,
    )
    if getattr(budget_ledger, "limits", None) != expected_limits:
        raise ValueError("budget ledger limits must match validated settings")
    return BudgetedAIProvider(
        provider=provider,
        ledger=budget_ledger,
        estimated_cost_aud=provider.estimated_max_cost,
    )
