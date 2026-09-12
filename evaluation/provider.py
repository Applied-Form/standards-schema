"""Small provider contract used by the evaluation runner.

Adapters return their complete, scrubbed response separately from normalized fields.
This keeps provider-specific evidence available without coupling the experiment logic
to one API.
"""
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class CompletionResult:
    ok: bool
    text: str = ""
    requested_model: str = ""
    resolved_model: str | None = None
    provider_name: str | None = None
    response_id: str | None = None
    finish_reason: str | None = None
    service_tier: str | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost: float | None = None
    system_fingerprint: str | None = None
    routing: dict[str, Any] | None = None
    model_integrity: dict[str, Any] | None = None
    raw: Any = None
    error: dict[str, Any] | None = None
    request_parameters: dict[str, Any] = field(default_factory=dict)


class ModelProvider(Protocol):
    """A provider adapter that can execute the same message list for a model."""

    name: str

    def complete(self, model: str, messages: list[dict[str, str]], *,
                 max_tokens: int, temperature: float,
                 trace: dict[str, str] | None = None) -> CompletionResult:
        ...
