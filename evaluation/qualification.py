"""Fail-closed, resumable route qualification for protocol 0.5."""
from __future__ import annotations

from dataclasses import asdict, fields
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from typing import Any

from .provider import CompletionResult, ModelProvider
from .study import (HEX64, IDENTIFIER, SpendLedger, StudyError, VERSION, canonical,
                    digest, read_json, validate_route_qualification)

CALLS_PER_BLOCK = 5
BLOCKS = 2
EXPECTED_TEXT = "ROUTE_OK"
RESULT_KEYS = {field.name for field in fields(CompletionResult)} | {"checks"}
CHECK_KEYS = {
    "providerOk", "acceptedIdentity", "textOutput", "providerPinned",
    "parametersAccepted", "success",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _write(path: Path, value: Any, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive and path.exists():
        raise StudyError(f"qualification record already exists: {path.name}")
    temporary = path.with_name(path.name + ".tmp")
    if path.is_symlink() or temporary.is_symlink():
        raise StudyError("qualification records must not use symlinks")
    temporary.unlink(missing_ok=True)
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _read(path: Path) -> Any:
    if path.is_symlink():
        raise StudyError(f"retained qualification record must not be a symlink: {path.name}")
    try:
        return read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError, StudyError) as error:
        raise StudyError(f"invalid retained qualification JSON: {path.name}") from error


def _ledger_identity(value: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    header = {key: value[key] for key in (
        "schemaVersion", "ledgerId", "currency", "capGbp", "automaticTopUp",
        "scope", "createdAt",
    )}
    if any(entry["status"] == "actual-exceeded-reservation" for entry in value["entries"]):
        raise StudyError("route qualification cannot use a spend ledger with a reservation overrun")
    return digest(header), header


def _snapshot_identity(model_snapshot: Any, model_id: str) -> list[str]:
    if not isinstance(model_snapshot, dict) or not isinstance(model_snapshot.get("models"), list):
        raise StudyError("route qualification requires a frozen OpenRouter model snapshot")
    entries = [entry for entry in model_snapshot["models"]
               if isinstance(entry, dict) and entry.get("id") == model_id]
    if len(entries) != 1:
        raise StudyError("qualification model must occur exactly once in the frozen snapshot")
    canonical_slug = entries[0].get("canonicalSlug")
    if canonical_slug is not None and (not isinstance(canonical_slug, str)
                                       or not canonical_slug.strip()):
        raise StudyError("frozen canonical model identity must be a nonblank string")
    return list(dict.fromkeys([model_id] + ([canonical_slug] if canonical_slug else [])))


def _validate_inputs(*, route_id: str, model_id: str, model_family: str,
                     provider_endpoint: str, max_tokens: int, temperature: float,
                     worst_case_call_cost_gbp: float, usd_to_gbp_rate: float) -> None:
    if not isinstance(route_id, str) or not IDENTIFIER.fullmatch(route_id):
        raise StudyError("qualification route ID must be a stable lowercase identifier")
    if not isinstance(model_family, str) or not IDENTIFIER.fullmatch(model_family):
        raise StudyError("qualification model family must be a stable lowercase identifier")
    if (not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 240
            or not isinstance(provider_endpoint, str) or not provider_endpoint.strip()
            or len(provider_endpoint) > 240):
        raise StudyError("qualification model and provider endpoint must be nonblank")
    if type(max_tokens) is not int or not 1 <= max_tokens <= 32_000:
        raise StudyError("qualification max tokens must be an integer between 1 and 32000")
    if (isinstance(temperature, bool) or not isinstance(temperature, (int, float))
            or not math.isfinite(temperature) or not 0 <= temperature <= 2):
        raise StudyError("qualification temperature must be between 0 and 2")
    if (isinstance(worst_case_call_cost_gbp, bool)
            or not isinstance(worst_case_call_cost_gbp, (int, float))
            or not math.isfinite(worst_case_call_cost_gbp)
            or not 0 <= worst_case_call_cost_gbp <= 500):
        raise StudyError("qualification worst-case call cost must be between £0 and £500")
    if (isinstance(usd_to_gbp_rate, bool) or not isinstance(usd_to_gbp_rate, (int, float))
            or not math.isfinite(usd_to_gbp_rate) or not .000001 <= usd_to_gbp_rate <= 100):
        raise StudyError("qualification USD-to-GBP rate is invalid")


def _precommit(*, route_id: str, model_id: str, model_family: str,
               provider_endpoint: str, snapshot_sha256: str, expires_at: str,
               accepted_resolved_models: list[str], require_zero_price: bool,
               ledger_header: dict[str, Any], ledger_identity_sha256: str,
               max_tokens: int, temperature: float, worst_case_call_cost_gbp: float,
               usd_to_gbp_rate: float) -> dict[str, Any]:
    return {
        "schemaVersion": VERSION, "routeId": route_id, "modelId": model_id,
        "modelFamily": model_family, "provider": "openrouter",
        "providerEndpoint": provider_endpoint, "modelSnapshotSha256": snapshot_sha256,
        "expiresAt": expires_at,
        "settings": {"maxTokens": max_tokens, "temperature": temperature,
                     "reasoningEffort": "none", "expectedText": EXPECTED_TEXT,
                     "providerOnly": [provider_endpoint], "allowFallbacks": False,
                     "requireParameters": True, "requireZeroPrice": require_zero_price,
                     "acceptedResolvedModels": accepted_resolved_models},
        "budget": {"worstCaseCallCostGbp": worst_case_call_cost_gbp,
                   "usdToGbpRate": usd_to_gbp_rate, "automaticTopUp": False,
                   "ledgerId": ledger_header["ledgerId"],
                   "ledgerCapGbp": ledger_header["capGbp"],
                   "ledgerIdentitySha256": ledger_identity_sha256},
        "design": {"blocks": BLOCKS, "callsPerBlock": CALLS_PER_BLOCK,
                   "successRateMinimum": .9, "acceptedIdentityRate": 1},
    }


def _new_journal(precommit: dict[str, Any]) -> dict[str, Any]:
    return {"schemaVersion": VERSION, "routeId": precommit["routeId"],
            "precommitSha256": digest(precommit), "createdAt": utc_now(),
            "blocks": [{"blockIndex": index, "status": "pending", "startedAt": None,
                        "completedAt": None, "calls": []}
                       for index in range(1, BLOCKS + 1)]}


def _reservation_id(precommit: dict[str, Any], block_index: int, call_index: int) -> str:
    return "qual-" + digest([
        precommit["routeId"], block_index, call_index, digest(precommit),
    ])[:24]


def _result_relative(block_index: int, call_index: int) -> str:
    return f"block-{block_index}/call-{call_index}/provider-result.json"


def _retained_path(output: Path, relative: str) -> Path:
    path = output
    for part in Path(relative).parts:
        path = path / part
        if path.is_symlink():
            raise StudyError("qualification result path must not traverse a symlink")
    return path


def _utc(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise StudyError(f"{name} must be an RFC 3339 UTC timestamp")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise StudyError(f"{name} must be an RFC 3339 UTC timestamp") from error


def _validate_journal(value: Any, precommit: dict[str, Any], *, output: Path,
                      ledger: SpendLedger) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
            "schemaVersion", "routeId", "precommitSha256", "createdAt", "blocks"}:
        raise StudyError("qualification journal has an invalid shape")
    if (value["schemaVersion"] != VERSION or value["routeId"] != precommit["routeId"]
            or value["precommitSha256"] != digest(precommit)):
        raise StudyError("qualification journal differs from its frozen precommit")
    _utc(value["createdAt"], "qualification journal.createdAt")
    blocks = value["blocks"]
    if not isinstance(blocks, list) or len(blocks) != BLOCKS:
        raise StudyError("qualification journal must contain exactly two blocks")
    seen_reservations: set[str] = set()
    for expected, block in enumerate(blocks, 1):
        if not isinstance(block, dict) or set(block) != {
                "blockIndex", "status", "startedAt", "completedAt", "calls"}:
            raise StudyError("qualification journal block has an invalid shape")
        if block["blockIndex"] != expected or block["status"] not in {
                "pending", "in-flight", "complete"}:
            raise StudyError("qualification journal block identity or status is invalid")
        if not isinstance(block["calls"], list) or len(block["calls"]) > CALLS_PER_BLOCK:
            raise StudyError("qualification block exceeds five calls")
        if block["status"] == "pending":
            if block["calls"] or block["startedAt"] is not None or block["completedAt"] is not None:
                raise StudyError("a pending qualification block cannot contain calls or timestamps")
        else:
            _utc(block["startedAt"], "qualification block.startedAt")
            if block["status"] == "complete":
                _utc(block["completedAt"], "qualification block.completedAt")
            elif block["completedAt"] is not None:
                raise StudyError("an in-flight qualification block cannot be completed")
        for call_index, call in enumerate(block["calls"]):
            if not isinstance(call, dict) or set(call) != {
                    "callIndex", "status", "reservationId", "startedAt", "completedAt",
                    "resultFile", "resultSha256", "checks"}:
                raise StudyError("qualification journal call has an invalid shape")
            if call["callIndex"] != call_index or call["status"] not in {
                    "in-flight", "complete", "indeterminate"}:
                raise StudyError("qualification call order or status is invalid")
            if call["reservationId"] != _reservation_id(precommit, expected, call_index):
                raise StudyError("qualification reservation identity differs from its frozen cell")
            if call["resultFile"] != _result_relative(expected, call_index):
                raise StudyError("qualification result path differs from its frozen cell")
            if call["reservationId"] in seen_reservations:
                raise StudyError("qualification reservation IDs must be unique")
            seen_reservations.add(call["reservationId"])
            _utc(call["startedAt"], "qualification call.startedAt")
            if call["status"] == "in-flight":
                if (call["completedAt"] is not None or call["resultSha256"] is not None
                        or call["checks"] is not None or call_index != len(block["calls"]) - 1):
                    raise StudyError("only the final call may be in flight without retained checks")
            if call["status"] in {"complete", "indeterminate"}:
                if not isinstance(call["resultFile"], str) or not isinstance(call["checks"], dict):
                    raise StudyError("completed qualification calls require retained checks")
                if not isinstance(call["resultSha256"], str) or len(call["resultSha256"]) != 64:
                    raise StudyError("completed qualification calls require a result digest")
                if not HEX64.fullmatch(call["resultSha256"]):
                    raise StudyError("qualification result digest must be lowercase SHA-256")
                _utc(call["completedAt"], "qualification call.completedAt")
                result = _validated_result(
                    _retained_path(output, call["resultFile"]),
                    precommit, expected, call_index)
                if digest(result) != call["resultSha256"]:
                    raise StudyError("retained qualification result differs from its journal digest")
                if result["checks"] != call["checks"]:
                    raise StudyError("retained qualification checks differ from the journal")
                if call["status"] == "indeterminate" \
                        and (result.get("error") or {}).get("code") != "execution-indeterminate":
                    raise StudyError("indeterminate qualification call lacks retained stop evidence")
                _verify_call_ledger(ledger, call, result, precommit)
        if block["status"] == "complete" and len(block["calls"]) != CALLS_PER_BLOCK:
            raise StudyError("a complete qualification block must retain exactly five calls")
    if blocks[1]["status"] != "pending" and blocks[0]["status"] != "complete":
        raise StudyError("qualification block 2 cannot precede completion of block 1")
    if blocks[1]["status"] != "pending" and (
            _utc(blocks[1]["startedAt"], "qualification block 2.startedAt")
            <= _utc(blocks[0]["completedAt"], "qualification block 1.completedAt")):
        raise StudyError("qualification blocks must have distinct sequential start times")
    return value


def _parameter_check(parameters: Any, error: Any, *, precommit: dict[str, Any],
                     block_index: int, call_index: int) -> bool:
    provider = parameters.get("provider") if isinstance(parameters, dict) else None
    error_text = canonical(error or {}).casefold()
    expected_provider_keys = {"only", "allow_fallbacks", "require_parameters"}
    if precommit["settings"]["requireZeroPrice"]:
        expected_provider_keys.add("max_price")
    return (isinstance(provider, dict)
            and set(provider) == expected_provider_keys
            and provider.get("only") == precommit["settings"]["providerOnly"]
            and provider.get("allow_fallbacks") is False
            and provider.get("require_parameters") is True
            and (not precommit["settings"]["requireZeroPrice"]
                 or provider.get("max_price") == {"prompt": 0, "completion": 0})
            and set(parameters) == {"maxTokens", "temperature", "provider", "trace",
                                    "reasoning", "frozenModelSnapshotSha256"}
            and parameters.get("maxTokens") == precommit["settings"]["maxTokens"]
            and parameters.get("temperature") == precommit["settings"]["temperature"]
            and parameters.get("reasoning") == {"effort": "none"}
            and parameters.get("frozenModelSnapshotSha256")
            == precommit["modelSnapshotSha256"]
            and parameters.get("trace") == {
                "trace_id": precommit["routeId"],
                "generation_name": f"qualification:block-{block_index}:call-{call_index}",
            }
            and "unsupported_parameter" not in error_text
            and "unsupported parameter" not in error_text)


def _checks(record: dict[str, Any], *, precommit: dict[str, Any],
            block_index: int, call_index: int) -> dict[str, bool]:
    integrity = record.get("model_integrity")
    integrity = integrity if isinstance(integrity, dict) else {}
    resolved = record.get("resolved_model")
    accepted_models = precommit["settings"]["acceptedResolvedModels"]
    checks = {
        "providerOk": record.get("ok") is True and record.get("error") is None,
        "acceptedIdentity": (
            record.get("requested_model") == precommit["modelId"]
            and integrity.get("requestedModel") == precommit["modelId"]
            and integrity.get("resolvedModel") == resolved
            and integrity.get("acceptedResolvedModels") == accepted_models
            and resolved in accepted_models
            and integrity.get("accepted") is True),
        "textOutput": (isinstance(record.get("text"), str)
                       and record["text"].strip() == EXPECTED_TEXT),
        "providerPinned": (
            record.get("provider_endpoint") == precommit["providerEndpoint"]
            and record.get("provider_name") == precommit["providerEndpoint"]),
        "parametersAccepted": _parameter_check(
            record.get("request_parameters"), record.get("error"),
            precommit=precommit, block_index=block_index, call_index=call_index),
    }
    checks["success"] = all(checks.values())
    return checks


def _result_record(result: CompletionResult, *, precommit: dict[str, Any],
                   block_index: int, call_index: int) -> dict[str, Any]:
    retained = asdict(result)
    retained["text"] = result.text[:1000]
    retained["checks"] = _checks(
        retained, precommit=precommit, block_index=block_index, call_index=call_index)
    return retained


def _indeterminate_record(precommit: dict[str, Any], block_index: int,
                          call_index: int) -> dict[str, Any]:
    record = asdict(CompletionResult(
        ok=False, requested_model=precommit["modelId"],
        error={"code": "execution-indeterminate",
               "message": "Process stopped after scheduling this call; it was not retried."},
    ))
    record["checks"] = _checks(
        record, precommit=precommit, block_index=block_index, call_index=call_index)
    return record


def _validated_result(path: Path, precommit: dict[str, Any], block_index: int,
                      call_index: int) -> dict[str, Any]:
    record = _read(path)
    if not isinstance(record, dict) or set(record) != RESULT_KEYS:
        raise StudyError("retained qualification provider result has an invalid shape")
    checks = record.get("checks")
    if (not isinstance(checks, dict) or set(checks) != CHECK_KEYS
            or any(type(value) is not bool for value in checks.values())):
        raise StudyError("retained qualification checks have an invalid shape")
    expected = _checks(
        record, precommit=precommit, block_index=block_index, call_index=call_index)
    if checks != expected:
        raise StudyError("retained qualification checks do not match the provider result")
    return record


def _ledger_entry(ledger: SpendLedger, reservation_id: str) -> dict[str, Any] | None:
    return next((entry for entry in ledger.value["entries"]
                 if entry["reservationId"] == reservation_id), None)


def _reload_ledger(ledger: SpendLedger, precommit: dict[str, Any] | None = None) -> None:
    ledger.value = SpendLedger.load(ledger.path).value
    identity, header = _ledger_identity(ledger.value)
    if precommit is not None and (
            identity != precommit["budget"]["ledgerIdentitySha256"]
            or header["ledgerId"] != precommit["budget"]["ledgerId"]
            or header["capGbp"] != precommit["budget"]["ledgerCapGbp"]):
        raise StudyError("qualification resume requires the frozen cumulative spend ledger")


def _verify_call_ledger(ledger: SpendLedger, call: dict[str, Any], result: dict[str, Any],
                        precommit: dict[str, Any]) -> None:
    _reload_ledger(ledger, precommit)
    entry = _ledger_entry(ledger, call["reservationId"])
    if entry is None or entry["stage"] != "qualification":
        raise StudyError("retained qualification result has no qualification spend reservation")
    if entry["status"] == "actual-exceeded-reservation":
        raise StudyError("qualification call exceeded its frozen worst-case spend reservation")
    if entry["status"] not in {"settled", "usage-missing-reservation-retained"}:
        raise StudyError("retained qualification spend reservation is not finalized")
    if (entry["reservedGbp"] != round(precommit["budget"]["worstCaseCallCostGbp"], 6)
            or entry["usdToGbpRate"] != precommit["budget"]["usdToGbpRate"]):
        raise StudyError("qualification spend reservation differs from its frozen budget")
    if result.get("cost") is None:
        if entry["status"] != "usage-missing-reservation-retained":
            raise StudyError("missing qualification usage did not retain its reservation")
    elif (entry["status"] != "settled"
          or entry["providerReportedCostUsd"] != result.get("cost")):
        raise StudyError("qualification result cost differs from its spend settlement")


def _complete_retained_call(output: Path, journal: dict[str, Any], block: dict[str, Any],
                            call: dict[str, Any], ledger: SpendLedger,
                            precommit: dict[str, Any]) -> None:
    result_path = _retained_path(output, call["resultFile"])
    block_index = block["blockIndex"]
    call_index = call["callIndex"]
    _reload_ledger(ledger, precommit)
    entry = _ledger_entry(ledger, call["reservationId"])
    if result_path.is_file():
        result = _validated_result(result_path, precommit, block_index, call_index)
        if entry is None:
            raise StudyError("retained provider result has no spend reservation")
        if entry["status"] == "actual-exceeded-reservation":
            raise StudyError("qualification call exceeded its frozen worst-case spend reservation")
        if entry["status"] == "reserved":
            ledger.settle(call["reservationId"], result.get("cost"))
        _verify_call_ledger(ledger, call, result, precommit)
        status = "complete"
    else:
        if entry is None:
            ledger.reserve(call["reservationId"], stage="qualification",
                           worst_case_gbp=precommit["budget"]["worstCaseCallCostGbp"],
                           usd_to_gbp_rate=precommit["budget"]["usdToGbpRate"])
            ledger.settle(call["reservationId"], None)
        elif entry["status"] == "reserved":
            ledger.settle(call["reservationId"], None)
        elif entry["status"] != "usage-missing-reservation-retained":
            raise StudyError("interrupted qualification call has an inconsistent reservation")
        result = _indeterminate_record(precommit, block_index, call_index)
        _write(result_path, result, exclusive=True)
        _verify_call_ledger(ledger, call, result, precommit)
        status = "indeterminate"
    call.update(status=status, completedAt=utc_now(), resultSha256=digest(result),
                checks=result["checks"])
    _write(output / "qualification-journal.json", journal)


def _summarize(output: Path, journal: dict[str, Any], precommit: dict[str, Any]) -> dict[str, Any]:
    calls = [call for block in journal["blocks"] for call in block["calls"]]
    checks = [call["checks"] for call in calls]
    successes = sum(item["success"] is True for item in checks)
    identities = sum(item["acceptedIdentity"] is True for item in checks)
    text_outputs = sum(item["textOutput"] is True for item in checks)
    pins = sum(item["providerPinned"] is True for item in checks)
    parameters = sum(item["parametersAccepted"] is True for item in checks)
    observations = {
        "calls": len(calls), "timeBlocks": sum(block["status"] == "complete"
                                                for block in journal["blocks"]),
        "successes": successes, "successRate": successes / len(calls) if calls else 0,
        "acceptedIdentities": identities,
        "acceptedIdentityRate": identities / len(calls) if calls else 0,
        "textOutputs": text_outputs, "textOutput": text_outputs >= 9,
        "providerPinMatches": pins, "providerPinned": pins == 10,
        "parameterAcceptances": parameters, "parametersAccepted": parameters == 10,
        "reservationIds": [call["reservationId"] for call in calls],
    }
    evidence = {"schemaVersion": VERSION, "routeId": precommit["routeId"],
                "modelId": precommit["modelId"], "modelFamily": precommit["modelFamily"],
                "provider": precommit["provider"],
                "providerEndpoint": precommit["providerEndpoint"],
                "modelSnapshotSha256": precommit["modelSnapshotSha256"],
                "precommitSha256": digest(precommit), "journalSha256": digest(journal),
                "blocks": journal["blocks"], "observations": observations}
    _write(output / "qualification-evidence.json", evidence)
    return evidence


def run_route_qualification(*, output: Path, provider: ModelProvider,
                            model_snapshot: dict[str, Any], spend_ledger: SpendLedger,
                            route_id: str, model_id: str, model_family: str,
                            provider_endpoint: str, block_index: int, expires_at: str,
                            max_tokens: int = 64, temperature: float = 0,
                            worst_case_call_cost_gbp: float = 0,
                            usd_to_gbp_rate: float = 1,
                            resume: bool = False) -> dict[str, Any]:
    """Run exactly one five-call block and issue a receipt only after both blocks qualify."""
    if block_index not in {1, 2}:
        raise StudyError("qualification block must be 1 or 2")
    _validate_inputs(
        route_id=route_id, model_id=model_id, model_family=model_family,
        provider_endpoint=provider_endpoint, max_tokens=max_tokens,
        temperature=temperature, worst_case_call_cost_gbp=worst_case_call_cost_gbp,
        usd_to_gbp_rate=usd_to_gbp_rate)
    if output.is_symlink():
        raise StudyError("qualification output directory must not be a symlink")
    if getattr(provider, "name", None) != "openrouter":
        raise StudyError("route qualification requires the OpenRouter provider adapter")
    if not isinstance(getattr(provider, "provider_pins", None), dict) \
            or provider.provider_pins != {model_id: provider_endpoint}:
        raise StudyError("route qualification requires one exact pinned provider endpoint")
    if getattr(provider, "model_snapshot_sha256", None) != digest(model_snapshot):
        raise StudyError("qualification provider and frozen snapshot differ")
    expiry = _utc(expires_at, "qualification expiry")
    if expiry <= datetime.now(timezone.utc):
        raise StudyError("qualification expiry must be a future RFC 3339 UTC timestamp")
    accepted_resolved_models = _snapshot_identity(model_snapshot, model_id)
    require_zero_price = getattr(provider, "require_zero_price", None)
    if type(require_zero_price) is not bool:
        raise StudyError("qualification provider must declare its frozen zero-price policy")
    _reload_ledger(spend_ledger)
    ledger_identity_sha256, ledger_header = _ledger_identity(spend_ledger.value)
    precommit = _precommit(
        route_id=route_id, model_id=model_id, model_family=model_family,
        provider_endpoint=provider_endpoint, snapshot_sha256=digest(model_snapshot),
        accepted_resolved_models=accepted_resolved_models,
        require_zero_price=require_zero_price, ledger_header=ledger_header,
        ledger_identity_sha256=ledger_identity_sha256,
        expires_at=expires_at, max_tokens=max_tokens, temperature=temperature,
        worst_case_call_cost_gbp=worst_case_call_cost_gbp,
        usd_to_gbp_rate=usd_to_gbp_rate)
    if resume:
        if not output.is_dir():
            raise StudyError("qualification resume requires an existing output directory")
        retained = _read(output / "qualification-precommit.json")
        if retained != precommit:
            raise StudyError("qualification resume inputs differ from the frozen precommit")
        if digest(_read(output / "model-snapshot.json")) != precommit["modelSnapshotSha256"]:
            raise StudyError("retained qualification model snapshot differs from its precommit")
        journal = _validate_journal(
            _read(output / "qualification-journal.json"), precommit,
            output=output, ledger=spend_ledger)
    else:
        if output.exists():
            if not output.is_dir() or any(output.iterdir()):
                raise StudyError("qualification output directory must be an empty directory")
        output.mkdir(parents=True, exist_ok=True)
        _write(output / "model-snapshot.json", model_snapshot, exclusive=True)
        _write(output / "qualification-precommit.json", precommit, exclusive=True)
        journal = _new_journal(precommit)
        _write(output / "qualification-journal.json", journal, exclusive=True)
    if block_index == 2 and journal["blocks"][0]["status"] != "complete":
        raise StudyError("qualification block 2 cannot begin before block 1 completes")
    if block_index == 1 and journal["blocks"][1]["status"] != "pending":
        raise StudyError("qualification block 1 cannot run after block 2 starts")
    block = journal["blocks"][block_index - 1]
    for call in block["calls"]:
        if call["status"] == "in-flight":
            _complete_retained_call(output, journal, block, call, spend_ledger, precommit)
    if block["status"] == "complete":
        pass
    else:
        if block["status"] == "pending":
            block.update(status="in-flight", startedAt=utc_now())
            _write(output / "qualification-journal.json", journal)
        while len(block["calls"]) < CALLS_PER_BLOCK:
            call_index = len(block["calls"])
            reservation_id = _reservation_id(precommit, block_index, call_index)
            result_relative = _result_relative(block_index, call_index)
            call = {"callIndex": call_index, "status": "in-flight",
                    "reservationId": reservation_id, "startedAt": utc_now(),
                    "completedAt": None, "resultFile": result_relative,
                    "resultSha256": None, "checks": None}
            block["calls"].append(call)
            _write(output / "qualification-journal.json", journal)
            spend_ledger.reserve(
                reservation_id, stage="qualification",
                worst_case_gbp=worst_case_call_cost_gbp,
                usd_to_gbp_rate=usd_to_gbp_rate)
            result = None
            try:
                result = provider.complete(
                    model_id,
                    [{"role": "system", "content": "Return plain text only."},
                     {"role": "user", "content": f"Reply exactly {EXPECTED_TEXT}."}],
                    max_tokens=max_tokens, temperature=temperature,
                    trace={"trace_id": route_id,
                           "generation_name": f"qualification:block-{block_index}:call-{call_index}"})
            finally:
                if result is None:
                    spend_ledger.settle(reservation_id, None)
            record = _result_record(
                result, precommit=precommit, block_index=block_index,
                call_index=call_index)
            result_path = _retained_path(output, result_relative)
            _write(result_path, record, exclusive=True)
            spend_ledger.settle(reservation_id, result.cost)
            call.update(status="complete", completedAt=utc_now(),
                        resultSha256=digest(record), checks=record["checks"])
            _write(output / "qualification-journal.json", journal)
        block.update(status="complete", completedAt=utc_now())
        _write(output / "qualification-journal.json", journal)
    journal = _validate_journal(
        journal, precommit, output=output, ledger=spend_ledger)
    if block_index == 1:
        return {"schemaVersion": VERSION, "routeId": route_id,
                "status": "block-complete", "block": 1, "calls": CALLS_PER_BLOCK,
                "next": "resume the identical output with block 2"}
    evidence = _summarize(output, journal, precommit)
    observations = evidence["observations"]
    qualified = (observations["calls"] == 10 and observations["timeBlocks"] == 2
                 and observations["successRate"] >= .9
                 and observations["acceptedIdentityRate"] == 1
                 and observations["textOutput"] is True
                 and observations["providerPinned"] is True
                 and observations["parametersAccepted"] is True)
    if not qualified:
        failure = {"schemaVersion": VERSION, "routeId": route_id,
                   "status": "not-qualified", "observations": observations,
                   "reason": "The retained ten-call evidence did not meet every frozen threshold."}
        _write(output / "qualification-failure.json", failure)
        (output / "route-qualification.json").unlink(missing_ok=True)
        return failure
    receipt = {"schemaVersion": VERSION, "routeId": route_id,
               "qualifiedAt": journal["blocks"][1]["completedAt"],
               "expiresAt": expires_at, "receiptSha256": digest(evidence),
               "observations": observations}
    validate_route_qualification(receipt)
    _write(output / "route-qualification.json", receipt)
    return receipt
