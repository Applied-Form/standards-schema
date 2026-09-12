"""OpenRouter adapter for the public evaluation runner.

Only fixed OpenRouter API paths can receive the credential. The key is loaded from
``OPENROUTER_API_KEY`` or, on macOS, a generic-password Keychain entry. It is never
included in returned records or diagnostic messages.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import getpass
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .provider import CompletionResult


BASE_URL = "https://openrouter.ai/api/v1"
ADAPTER_VERSION = "0.2.0"
MAX_RESPONSE_BYTES = 12_000_000
ALLOWED_PATHS = {"/models", "/chat/completions"}
PRIVATE_FIELDS = {
    "authorization", "api_key", "apikey", "token", "secret", "password",
    "user_id", "account_id", "organization_id", "org_id", "customer_id",
    "email", "email_address",
}


class OpenRouterError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        """Reject redirects so an Authorization header never reaches another host."""
        return None


def _safe_json(data: bytes) -> Any:
    if len(data) > MAX_RESPONSE_BYTES:
        raise OpenRouterError("OpenRouter response exceeds the configured size limit")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise OpenRouterError("OpenRouter returned JSON with a duplicate key")
            value[key] = item
        return value

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise OpenRouterError(f"OpenRouter returned a non-finite JSON number: {value}")
        return parsed

    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=unique,
            parse_float=finite_float,
            parse_constant=lambda value: (_ for _ in ()).throw(
                OpenRouterError(f"OpenRouter returned a non-finite JSON number: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise OpenRouterError("OpenRouter returned an invalid JSON response") from error


def _scrub(value: Any, secret: str) -> Any:
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]") if secret else value
    if isinstance(value, list):
        return [_scrub(item, secret) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            clean_key = _scrub(str(key), secret)
            normalized_key = clean_key.casefold().replace("-", "_")
            private_identifier = normalized_key in PRIVATE_FIELDS or normalized_key.endswith(
                ("_user_id", "_account_id", "_organization_id", "_customer_id")
            )
            result[clean_key] = "[REDACTED]" if private_identifier else _scrub(item, secret)
        return result
    return value


def credential() -> tuple[str, str]:
    """Return ``(key, source)`` without logging either lookup's output."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        source = "environment"
    elif sys.platform == "darwin":
        account = os.environ.get("OPENROUTER_KEYCHAIN_ACCOUNT", "").strip() or getpass.getuser()
        service = os.environ.get("OPENROUTER_KEYCHAIN_SERVICE", "").strip() or "standards-openrouter"
        try:
            lookup = subprocess.run(
                ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
                capture_output=True, text=True, check=False, timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            lookup = None
        key = lookup.stdout.strip() if lookup is not None and lookup.returncode == 0 else ""
        source = "macos-keychain" if key else "unavailable"
    else:
        source = "unavailable"
    if not key:
        raise OpenRouterError(
            "OpenRouter credential unavailable. Set OPENROUTER_API_KEY or configure the "
            "macOS Keychain service selected by OPENROUTER_KEYCHAIN_SERVICE."
        )
    if len(key) > 4096 or any(ord(character) < 33 or ord(character) > 126 for character in key):
        raise OpenRouterError("OpenRouter credential contains invalid header characters")
    return key, source


def credential_status() -> dict[str, Any]:
    try:
        _, source = credential()
    except OpenRouterError:
        return {"available": False, "source": "unavailable"}
    return {"available": True, "source": source}


def _http_json(path: str, key: str, payload: dict[str, Any] | None = None,
               timeout: float = 120) -> tuple[int, Any, int]:
    if path not in ALLOWED_PATHS:
        raise OpenRouterError("unsupported OpenRouter API path")
    body = None if payload is None else json.dumps(
        payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {key}",
        "User-Agent": f"standards-public-evaluation/{ADAPTER_VERSION}",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["X-OpenRouter-Metadata"] = "enabled"
    request = Request(BASE_URL + path, data=body, headers=headers,
                      method="POST" if body is not None else "GET")
    started = time.monotonic_ns()
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            status = response.status
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        status = error.code
        data = error.read(MAX_RESPONSE_BYTES + 1)
    except (URLError, TimeoutError, OSError) as error:
        elapsed = round((time.monotonic_ns() - started) / 1_000_000)
        return 0, {"error": {"code": "transport_error", "message": str(error)}}, elapsed
    elapsed = round((time.monotonic_ns() - started) / 1_000_000)
    return status, _safe_json(data), elapsed


def _all_known_prices_are_zero(pricing: Any) -> bool:
    if not isinstance(pricing, dict) or not {"prompt", "completion"}.issubset(pricing) or not pricing:
        return False
    try:
        values = [Decimal(str(value)) for value in pricing.values()]
    except (InvalidOperation, ValueError):
        return False
    return all(value.is_finite() and value == 0 for value in values)


def _text_model(model: dict[str, Any]) -> bool:
    architecture = model.get("architecture") if isinstance(model.get("architecture"), dict) else {}
    inputs = architecture.get("input_modalities")
    outputs = architecture.get("output_modalities")
    modality = architecture.get("modality")
    input_text = isinstance(inputs, list) and "text" in inputs
    output_text = isinstance(outputs, list) and "text" in outputs
    if isinstance(modality, str) and "->" in modality:
        source, target = modality.split("->", 1)
        input_text = input_text or "text" in source.split("+")
        output_text = output_text or "text" in target.split("+")
    return input_text and output_text


def discover_free_models(key: str | None = None) -> dict[str, Any]:
    """Fetch a current snapshot and keep exact zero-price text routes only."""
    if key is None:
        key, source = credential()
    else:
        source = "supplied"
    status, raw, latency = _http_json("/models", key, timeout=45)
    clean = _scrub(raw, key)
    if status != 200 or not isinstance(clean, dict) or not isinstance(clean.get("data"), list):
        raise OpenRouterError(f"OpenRouter model discovery failed with HTTP {status or 'transport'}")
    models = []
    for item in clean["data"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        pricing = item.get("pricing")
        if not (_all_known_prices_are_zero(pricing) and _text_model(item)):
            continue
        models.append({
            "id": item["id"],
            "canonicalSlug": item.get("canonical_slug"),
            "name": item.get("name"),
            "created": item.get("created"),
            "contextLength": item.get("context_length"),
            "pricing": dict(pricing),
            "architecture": item.get("architecture"),
            "supportedParameters": item.get("supported_parameters"),
            "topProvider": item.get("top_provider"),
            "freeVariant": item["id"].endswith(":free") or item["id"] == "openrouter/free",
        })
    models.sort(key=lambda item: item["id"])
    return {
        "schemaVersion": "0.1.0",
        "provider": "openrouter",
        "endpoint": "/api/v1/models",
        "retrievedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "latencyMs": latency,
        "credentialSource": source,
        "filter": "text input/output, prompt and completion prices present, and every published price field exactly zero",
        "count": len(models),
        "models": models,
    }


def snapshot_sha256(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _catalogue_index(snapshot: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(snapshot, dict) or snapshot.get("provider") != "openrouter":
        raise OpenRouterError("a frozen OpenRouter model snapshot is required")
    rows = snapshot.get("models")
    if not isinstance(rows, list) or snapshot.get("count") != len(rows):
        raise OpenRouterError("the frozen OpenRouter model snapshot is malformed")
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        identifier = row.get("id") if isinstance(row, dict) else None
        if not isinstance(identifier, str) or not identifier or identifier in index:
            raise OpenRouterError("the frozen OpenRouter model snapshot has an invalid model ID")
        if not _all_known_prices_are_zero(row.get("pricing")) or not _text_model(row):
            raise OpenRouterError(
                f"the frozen catalogue does not prove an exact zero-price text route: {identifier}"
            )
        canonical_slug = row.get("canonicalSlug")
        if canonical_slug is not None and (not isinstance(canonical_slug, str) or not canonical_slug):
            raise OpenRouterError(f"the frozen catalogue has an invalid canonical slug: {identifier}")
        index[identifier] = row
    return index


def validate_frozen_models(snapshot: Any, models: list[str]) -> dict[str, dict[str, Any]]:
    """Fail closed unless every exact requested route is free in this snapshot."""
    index = _catalogue_index(snapshot)
    selected: dict[str, dict[str, Any]] = {}
    for model in models:
        if not isinstance(model, str) or not model or model in {"openrouter/auto", "openrouter/free"} \
                or "," in model:
            raise OpenRouterError(f"automatic or invalid model route is not permitted: {model}")
        if model not in index:
            raise OpenRouterError(f"model is absent from the frozen zero-price catalogue: {model}")
        selected[model] = index[model]
    return selected


def _model_integrity(requested: str, resolved: Any,
                     entry: dict[str, Any]) -> dict[str, Any]:
    canonical_slug = entry.get("canonicalSlug")
    accepted = [requested]
    if isinstance(canonical_slug, str) and canonical_slug not in accepted:
        accepted.append(canonical_slug)
    if not isinstance(resolved, str) or not resolved:
        status = "unobserved"
        matches = False
    elif resolved == requested:
        status = "exact-request-match"
        matches = True
    elif resolved == canonical_slug:
        # OpenRouter's frozen catalogue can map a route ID to a release-dated
        # canonical_slug. No other suffix, alias, or substitution is accepted.
        status = "frozen-canonical-match"
        matches = True
    else:
        status = "mismatch"
        matches = False
    return {
        "status": status,
        "accepted": matches,
        "requestedModel": requested,
        "resolvedModel": resolved if isinstance(resolved, str) else None,
        "acceptedResolvedModels": accepted,
        "catalogueCanonicalSlug": canonical_slug,
        "rule": "Accept only the exact request ID or its release-dated canonical_slug from the frozen catalogue.",
    }


def _number(value: Any, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if integer else float(value)


def _message_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(part.get("text", "")) for part in content
                         if isinstance(part, dict) and part.get("type") == "text")
    return ""


def _selected_provider(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    endpoints = metadata.get("endpoints")
    available = endpoints.get("available") if isinstance(endpoints, dict) else None
    if isinstance(available, list):
        for endpoint in available:
            if isinstance(endpoint, dict) and endpoint.get("selected") is True \
                    and isinstance(endpoint.get("provider"), str):
                return endpoint["provider"]
    attempts = metadata.get("attempts")
    if isinstance(attempts, list):
        for attempt in reversed(attempts):
            if isinstance(attempt, dict) and attempt.get("status") == 200 \
                    and isinstance(attempt.get("provider"), str):
                return attempt["provider"]
    return None


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, model_snapshot: dict[str, Any], key: str | None = None,
                 timeout: float = 120, reasoning_effort: str | None = None):
        if reasoning_effort not in {None, "none"}:
            raise OpenRouterError("reasoning effort must be omitted or none")
        self._catalogue = _catalogue_index(model_snapshot)
        self.model_snapshot_sha256 = snapshot_sha256(model_snapshot)
        self.reasoning_effort = reasoning_effort
        self.experiment_metadata = {
            "adapter": f"evaluation.openrouter/{ADAPTER_VERSION}",
            "environment": environment_metadata(),
            "frozenModelSnapshotSha256": self.model_snapshot_sha256,
            "zeroPriceCatalogueGuard": True,
            "automaticModelRouting": False,
            "providerFallbacks": False,
            "underlyingProviderPinned": False,
            "routingCaveat": "OpenRouter selects the initial eligible provider endpoint for each request; fallback is disabled, and the resolved provider is recorded when supplied.",
            "reasoningEffort": reasoning_effort if reasoning_effort is not None else "provider-default",
            "modelIdentityRule": "exact request ID or its frozen catalogue canonical_slug",
        }
        if key is None:
            key, source = credential()
        else:
            source = "supplied"
        self._key = key
        self.credential_source = source
        self.timeout = timeout

    def complete(self, model: str, messages: list[dict[str, str]], *,
                 max_tokens: int, temperature: float,
                 trace: dict[str, str] | None = None) -> CompletionResult:
        try:
            entry = validate_frozen_models(
                {"provider": "openrouter", "count": len(self._catalogue),
                 "models": list(self._catalogue.values())},
                [model],
            )[model]
        except OpenRouterError as error:
            detail = {"code": "frozen_catalogue_guard", "message": str(error)}
            return CompletionResult(
                ok=False, requested_model=model, raw={"error": detail}, error=detail,
                model_integrity={"status": "not-called", "accepted": False,
                                 "requestedModel": model, "resolvedModel": None,
                                 "acceptedResolvedModels": []},
            )
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "provider": {"allow_fallbacks": False,
                         "max_price": {"prompt": 0, "completion": 0}},
        }
        if self.reasoning_effort is not None:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        if trace:
            payload["trace"] = {str(key): str(value) for key, value in trace.items()}
        request_parameters = {"maxTokens": max_tokens, "temperature": temperature,
                              "provider": payload["provider"], "trace": payload.get("trace"),
                              "reasoning": payload.get("reasoning"),
                              "frozenModelSnapshotSha256": self.model_snapshot_sha256}
        try:
            status, raw, latency = _http_json(
                "/chat/completions", self._key, payload, self.timeout
            )
        except OpenRouterError as error:
            detail = {"code": "invalid_provider_response", "message": str(error)}
            return CompletionResult(
                ok=False, requested_model=model, model_integrity=_model_integrity(model, None, entry),
                raw={"error": detail}, error=detail, request_parameters=request_parameters,
            )
        clean = _scrub(raw, self._key)
        if status != 200 or not isinstance(clean, dict):
            error = clean.get("error") if isinstance(clean, dict) else {"message": "invalid response"}
            return CompletionResult(ok=False, requested_model=model, latency_ms=latency,
                                    routing=clean.get("openrouter_metadata") if isinstance(clean, dict) else None,
                                    raw=clean, error={"httpStatus": status, "detail": error},
                                    model_integrity=_model_integrity(model, None, entry),
                                    request_parameters=request_parameters)
        usage = clean.get("usage") if isinstance(clean.get("usage"), dict) else {}
        choices = clean.get("choices") if isinstance(clean.get("choices"), list) else []
        first = choices[0] if choices and isinstance(choices[0], dict) else {}
        routing = clean.get("openrouter_metadata") if isinstance(clean.get("openrouter_metadata"), dict) else None
        text = _message_text(clean)
        resolved_model = clean.get("model") if isinstance(clean.get("model"), str) else None
        integrity = _model_integrity(model, resolved_model, entry)
        reported_cost = _number(usage.get("cost"))
        if not integrity["accepted"]:
            error = {"httpStatus": status, "code": "model_integrity_failure",
                     "detail": "resolved model is absent or differs from the frozen exact model identity"}
        elif reported_cost is not None and reported_cost != 0:
            error = {"httpStatus": status, "code": "zero_price_guard_failure",
                     "detail": "provider reported nonzero cost for a frozen zero-price route"}
        elif not text:
            error = {"httpStatus": status, "code": "empty_response",
                     "detail": "successful response contained no text"}
        else:
            error = None
        return CompletionResult(
            ok=bool(text) and error is None, text=text, requested_model=model,
            resolved_model=resolved_model,
            provider_name=_selected_provider(routing),
            response_id=clean.get("id") if isinstance(clean.get("id"), str) else None,
            finish_reason=first.get("finish_reason") if isinstance(first.get("finish_reason"), str) else None,
            service_tier=clean.get("service_tier") if isinstance(clean.get("service_tier"), str) else None,
            latency_ms=latency,
            prompt_tokens=_number(usage.get("prompt_tokens"), True),
            completion_tokens=_number(usage.get("completion_tokens"), True),
            total_tokens=_number(usage.get("total_tokens"), True),
            cost=reported_cost,
            system_fingerprint=clean.get("system_fingerprint") if isinstance(clean.get("system_fingerprint"), str) else None,
            routing=routing, model_integrity=integrity, raw=clean, error=error,
            request_parameters=request_parameters,
        )


def environment_metadata() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "platform": f"{sys.platform}-{platform.machine().lower()}",
        "adapter": f"evaluation.openrouter/{ADAPTER_VERSION}",
    }
