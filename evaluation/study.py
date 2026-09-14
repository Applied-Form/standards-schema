"""Protocol 0.5 study declarations, analysis, review sealing, and evidence controls.

This module is deliberately dependency-free.  The JSON schemas are the exchange
contracts; the validators below enforce the confirmatory subset before any provider
adapter is constructed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
from statistics import NormalDist
from typing import Any, Iterable


VERSION = "0.5.0"
SCHEMA_ROOT = Path(__file__).resolve().parent / "schemas"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{1,119}$")
REVIEW_FIELDS = ("visualHierarchy", "systemFidelity", "legibility", "rhetoricalFit", "overall")
CELL_STATES = {"pending", "in-flight", "complete", "indeterminate"}
SPEND_STAGES = {"qualification", "development", "confirmatory"}
SPEND_STATUSES = {
    "reserved", "settled", "usage-missing-reservation-retained",
    "actual-exceeded-reservation",
}
PRIVATE_JSON_KEYS = {
    "authorization", "api_key", "apikey", "token", "secret", "password",
    "user_id", "account_id", "organization_id", "org_id", "customer_id",
    "email", "email_address", "response_id", "request_id", "responseid", "requestid",
}
SECRET_PATTERNS = (
    re.compile(rb"sk-or-v1-[A-Za-z0-9_-]{16,}"),
    re.compile(rb"OPENROUTER_API_KEY\s*[=:]\s*[^\s\"']+", re.I),
)
ABSOLUTE_PATH_PATTERNS = (
    re.compile(rb"/Users/[A-Za-z0-9._-]+/"),
    re.compile(rb"/private/(?:tmp|var)/"),
    re.compile(rb"[A-Za-z]:\\\\Users\\\\[^\\\\]+\\\\"),
)


class StudyError(RuntimeError):
    """A declaration, retained run, review, or analysis violates protocol 0.5."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    if not isinstance(value, (str, bytes)):
        value = canonical(value)
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path, maximum: int = 10_000_000) -> Any:
    data = path.read_bytes()
    if len(data) > maximum:
        raise StudyError(f"JSON input exceeds {maximum} bytes: {path.name}")
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_float=_finite_float,
            parse_constant=lambda value: (_ for _ in ()).throw(
                StudyError(f"non-finite number in {path.name}: {value}")),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise StudyError(f"invalid JSON: {path.name}") from error


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StudyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise StudyError(f"non-finite JSON number: {value}")
    return result


def _utc(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise StudyError(f"{path} must be an RFC 3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise StudyError(f"{path} must be an RFC 3339 UTC timestamp") from error
    return parsed


def _exact(value: Any, keys: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StudyError(f"{path} must be an object")
    missing = sorted(keys - set(value))
    extra = sorted(set(value) - keys)
    if missing or extra:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise StudyError(f"{path} has " + "; ".join(details))
    return value


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise StudyError(f"{path} must be a stable lowercase identifier")
    return value


def _string(value: Any, path: str, maximum: int = 1000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise StudyError(f"{path} must be a nonblank string of at most {maximum} characters")
    return value


def _number(value: Any, path: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise StudyError(f"{path} must be a finite number")
    if not minimum <= float(value) <= maximum:
        raise StudyError(f"{path} must be between {minimum} and {maximum}")
    return float(value)


def _integer(value: Any, path: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise StudyError(f"{path} must be an integer between {minimum} and {maximum}")
    return value


def _unique_strings(value: Any, path: str, minimum: int = 1) -> list[str]:
    if (not isinstance(value, list) or len(value) < minimum
            or any(not isinstance(item, str) or not item.strip() for item in value)
            or len(value) != len(set(value))):
        raise StudyError(f"{path} must contain at least {minimum} unique nonblank strings")
    return value


def validate_declaration(value: Any) -> dict[str, Any]:
    """Strictly validate the frozen confirmatory study declaration."""
    top = _exact(value, {
        "schemaVersion", "studyId", "protocolVersion", "studyMode", "createdAt",
        "releaseCommit", "split", "conditions", "fixtures", "routes", "repetitions",
        "generation", "randomization", "analysis", "review", "budget", "renderer",
        "protocolFiles",
    }, "declaration")
    if top["schemaVersion"] != VERSION or top["protocolVersion"] != VERSION:
        raise StudyError(f"declaration must use protocol {VERSION}")
    _identifier(top["studyId"], "declaration.studyId")
    if top["studyMode"] != "confirmatory" or top["split"] != "held-out":
        raise StudyError("confirmatory declarations must use the held-out split")
    _utc(top["createdAt"], "declaration.createdAt")
    if not isinstance(top["releaseCommit"], str) or not COMMIT.fullmatch(top["releaseCommit"]):
        raise StudyError("declaration.releaseCommit must be a full lowercase Git commit")
    conditions = _unique_strings(top["conditions"], "declaration.conditions", 3)
    allowed_conditions = {
        "raw_brief", "brand_bible", "scaffolded_html", "full_rules",
        "compact_rules", "selected_context", "deterministic_component",
    }
    if set(conditions) - allowed_conditions:
        raise StudyError("declaration.conditions contains an unknown condition")

    fixtures = top["fixtures"]
    if not isinstance(fixtures, list) or len(fixtures) != 8:
        raise StudyError("declaration.fixtures must contain exactly eight held-out fixtures")
    fixture_ids: list[str] = []
    for index, row in enumerate(fixtures):
        row = _exact(row, {"id", "sha256"}, f"declaration.fixtures[{index}]")
        fixture_ids.append(_identifier(row["id"], f"declaration.fixtures[{index}].id"))
        if not isinstance(row["sha256"], str) or not HEX64.fullmatch(row["sha256"]):
            raise StudyError(f"declaration.fixtures[{index}].sha256 must be lowercase SHA-256")
    if len(fixture_ids) != len(set(fixture_ids)):
        raise StudyError("declaration fixture IDs must be unique")

    routes = top["routes"]
    if not isinstance(routes, list) or len(routes) != 6:
        raise StudyError("declaration.routes must contain exactly six pinned routes")
    route_ids: list[str] = []
    model_ids: list[str] = []
    families: set[str] = set()
    qualification_reservations: list[str] = []
    for index, route in enumerate(routes):
        route = _exact(route, {
            "routeId", "modelId", "modelFamily", "provider", "endpointPolicy",
            "underlyingProvider", "providerDisplayName", "snapshotSha256", "qualification",
        }, f"declaration.routes[{index}]")
        route_ids.append(_identifier(route["routeId"], f"declaration.routes[{index}].routeId"))
        model_ids.append(_string(route["modelId"], f"declaration.routes[{index}].modelId", 240))
        families.add(_identifier(route["modelFamily"], f"declaration.routes[{index}].modelFamily"))
        if route["provider"] != "openrouter" or route["endpointPolicy"] != "pinned":
            raise StudyError("confirmatory routes must use pinned OpenRouter endpoints")
        _string(route["underlyingProvider"], f"declaration.routes[{index}].underlyingProvider", 240)
        _string(route["providerDisplayName"],
                f"declaration.routes[{index}].providerDisplayName", 240)
        if not isinstance(route["snapshotSha256"], str) or not HEX64.fullmatch(route["snapshotSha256"]):
            raise StudyError(f"declaration.routes[{index}].snapshotSha256 must be SHA-256")
        validate_route_qualification(route["qualification"], route)
        qualification_reservations.extend(
            route["qualification"]["observations"]["reservationIds"])
    if len(route_ids) != len(set(route_ids)) or len(model_ids) != len(set(model_ids)):
        raise StudyError("route and model IDs must be unique")
    if len(families) < 3:
        raise StudyError("confirmatory routes must span at least three model families")
    if len(qualification_reservations) != len(set(qualification_reservations)):
        raise StudyError("route qualification spend reservations must be unique across routes")

    _integer(top["repetitions"], "declaration.repetitions", 5, 50)
    generation = _exact(top["generation"], {
        "maxTokens", "temperature", "reasoningEffort", "maxRepairs",
        "worstCaseCallCostGbp", "usdToGbpRate", "automaticTopUp",
    }, "declaration.generation")
    _integer(generation["maxTokens"], "declaration.generation.maxTokens", 256, 32000)
    _number(generation["temperature"], "declaration.generation.temperature", 0, 2)
    if generation["reasoningEffort"] not in {"none", "provider-default"}:
        raise StudyError("generation.reasoningEffort must be none or provider-default")
    if generation["maxRepairs"] != 0:
        raise StudyError("confirmatory generation must freeze maxRepairs at 0")
    _number(generation["worstCaseCallCostGbp"],
            "declaration.generation.worstCaseCallCostGbp", 0, 500)
    _number(generation["usdToGbpRate"], "declaration.generation.usdToGbpRate", .000001, 100)
    if generation["automaticTopUp"] is not False:
        raise StudyError("confirmatory execution must disable automatic budget top-up")

    randomization = _exact(top["randomization"], {"strategy", "seed"},
                           "declaration.randomization")
    if randomization["strategy"] != "blocked-case-repetition-shuffle-v1":
        raise StudyError("unsupported randomization strategy")
    _integer(randomization["seed"], "declaration.randomization.seed", 0, 2**63 - 1)
    _validate_analysis_plan(top["analysis"], conditions)
    _validate_review_plan(top["review"], top["repetitions"])
    budget = _exact(top["budget"], {"currency", "maximum"}, "declaration.budget")
    if budget["currency"] != "GBP":
        raise StudyError("declaration.budget.currency must be GBP")
    _number(budget["maximum"], "declaration.budget.maximum", 0, 500)
    _validate_power_plan(top["analysis"]["powerPlan"], top["repetitions"],
                         len([name for name in conditions if name != "deterministic_component"]),
                         budget["maximum"])
    if top["analysis"]["powerPlan"]["estimatedCostPerCellGbp"] \
            != generation["worstCaseCallCostGbp"]:
        raise StudyError("power-plan cell cost must equal the runtime worst-case call reservation")
    renderer = _exact(top["renderer"], {"identitySha256"}, "declaration.renderer")
    if not isinstance(renderer["identitySha256"], str) or not HEX64.fullmatch(renderer["identitySha256"]):
        raise StudyError("declaration.renderer.identitySha256 must be SHA-256")
    protocol_files = top["protocolFiles"]
    if (not isinstance(protocol_files, dict) or not protocol_files
            or any(not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts
                   or not isinstance(checksum, str) or not HEX64.fullmatch(checksum)
                   for path, checksum in protocol_files.items())):
        raise StudyError("declaration.protocolFiles must map safe relative paths to SHA-256 values")
    return top


def validate_route_qualification(value: Any, route: dict[str, Any] | None = None) -> dict[str, Any]:
    qualification = _exact(value, {
        "schemaVersion", "routeId", "qualifiedAt", "expiresAt", "receiptSha256", "observations",
    }, "route qualification")
    if qualification["schemaVersion"] != VERSION:
        raise StudyError(f"route qualification must use schema {VERSION}")
    _identifier(qualification["routeId"], "route qualification.routeId")
    qualified = _utc(qualification["qualifiedAt"], "route qualification.qualifiedAt")
    expires = _utc(qualification["expiresAt"], "route qualification.expiresAt")
    if expires <= qualified:
        raise StudyError("route qualification must expire after it was qualified")
    if not isinstance(qualification["receiptSha256"], str) or not HEX64.fullmatch(
            qualification["receiptSha256"]):
        raise StudyError("route qualification.receiptSha256 must be SHA-256")
    observations = _exact(qualification["observations"], {
        "calls", "timeBlocks", "successes", "successRate", "acceptedIdentities",
        "acceptedIdentityRate", "textOutput", "providerPinned", "parametersAccepted",
        "textOutputs", "providerPinMatches", "parameterAcceptances", "reservationIds",
    }, "route qualification.observations")
    if observations["calls"] != 10 or observations["timeBlocks"] != 2:
        raise StudyError("route qualification requires exactly ten calls in two time blocks")
    successes = _integer(observations["successes"], "route qualification.successes", 0, 10)
    success_rate = _number(observations["successRate"], "route qualification.successRate", 0, 1)
    if successes / 10 != success_rate or success_rate < .9:
        raise StudyError("route qualification success must be at least 90% with an exact rate")
    if observations["acceptedIdentities"] != 10 or observations["acceptedIdentityRate"] != 1:
        raise StudyError("route qualification requires 100% accepted model identity")
    text_outputs = _integer(observations["textOutputs"],
                            "route qualification.textOutputs", 0, 10)
    pin_matches = _integer(observations["providerPinMatches"],
                           "route qualification.providerPinMatches", 0, 10)
    parameter_acceptances = _integer(observations["parameterAcceptances"],
                                     "route qualification.parameterAcceptances", 0, 10)
    if (observations["textOutput"] is not (text_outputs >= 9)
            or observations["providerPinned"] is not (pin_matches == 10)
            or observations["parametersAccepted"] is not (parameter_acceptances == 10)
            or any(observations[key] is not True for key in
                   ("textOutput", "providerPinned", "parametersAccepted"))):
        raise StudyError("route qualification output, pin and parameter checks must pass")
    reservation_ids = _unique_strings(observations["reservationIds"],
                                      "route qualification.reservationIds", 10)
    if len(reservation_ids) != 10:
        raise StudyError("route qualification must bind one spend reservation per call")
    if route is not None and qualification["routeId"] != route["routeId"]:
        raise StudyError("route qualification ID differs from its route")
    return qualification


def validate_development_plan(value: Any) -> dict[str, Any]:
    """Validate a pinned, claim-disabled development comparison plan."""
    top = _exact(value, {
        "schemaVersion", "planId", "protocolVersion", "studyMode", "createdAt",
        "releaseCommit", "split", "conditions", "fixtures", "routes", "repetitions",
        "generation", "randomization", "budget", "renderer", "protocolFiles", "claims",
    }, "development plan")
    if top["schemaVersion"] != VERSION or top["protocolVersion"] != VERSION:
        raise StudyError(f"development plan must use protocol {VERSION}")
    _identifier(top["planId"], "development plan.planId")
    if top["studyMode"] != "development" or top["split"] != "dev":
        raise StudyError("development plans must use the development split")
    _utc(top["createdAt"], "development plan.createdAt")
    if not isinstance(top["releaseCommit"], str) or not COMMIT.fullmatch(top["releaseCommit"]):
        raise StudyError("development plan.releaseCommit must be a full lowercase Git commit")
    expected_conditions = [
        "raw_brief", "brand_bible", "scaffolded_html", "selected_context", "full_rules"]
    if top["conditions"] != expected_conditions:
        raise StudyError("development plan must freeze the five declared comparison conditions")
    fixtures = top["fixtures"]
    if not isinstance(fixtures, list) or len(fixtures) != 6:
        raise StudyError("development plan.fixtures must contain exactly six development fixtures")
    fixture_ids: list[str] = []
    for index, row in enumerate(fixtures):
        row = _exact(row, {"id", "sha256"}, f"development plan.fixtures[{index}]")
        fixture_ids.append(_identifier(row["id"], f"development plan.fixtures[{index}].id"))
        if not isinstance(row["sha256"], str) or not HEX64.fullmatch(row["sha256"]):
            raise StudyError(f"development plan.fixtures[{index}].sha256 must be SHA-256")
    if len(fixture_ids) != len(set(fixture_ids)):
        raise StudyError("development fixture IDs must be unique")
    routes = top["routes"]
    if not isinstance(routes, list) or len(routes) != 6:
        raise StudyError("development plan.routes must contain exactly six pinned routes")
    route_ids: list[str] = []
    model_ids: list[str] = []
    families: set[str] = set()
    reservations: list[str] = []
    for index, route in enumerate(routes):
        route = _exact(route, {
            "routeId", "modelId", "modelFamily", "provider", "endpointPolicy",
            "underlyingProvider", "providerDisplayName", "snapshotSha256", "qualification",
        }, f"development plan.routes[{index}]")
        route_ids.append(_identifier(route["routeId"], f"development plan.routes[{index}].routeId"))
        model_ids.append(_string(route["modelId"], f"development plan.routes[{index}].modelId", 240))
        families.add(_identifier(route["modelFamily"], f"development plan.routes[{index}].modelFamily"))
        if route["provider"] != "openrouter" or route["endpointPolicy"] != "pinned":
            raise StudyError("development routes must use pinned OpenRouter endpoints")
        _string(route["underlyingProvider"],
                f"development plan.routes[{index}].underlyingProvider", 240)
        _string(route["providerDisplayName"],
                f"development plan.routes[{index}].providerDisplayName", 240)
        if not isinstance(route["snapshotSha256"], str) or not HEX64.fullmatch(route["snapshotSha256"]):
            raise StudyError(f"development plan.routes[{index}].snapshotSha256 must be SHA-256")
        validate_route_qualification(route["qualification"], route)
        reservations.extend(route["qualification"]["observations"]["reservationIds"])
    if len(route_ids) != len(set(route_ids)) or len(model_ids) != len(set(model_ids)):
        raise StudyError("development route and model IDs must be unique")
    if len(families) < 3:
        raise StudyError("development routes must span at least three model families")
    if len(reservations) != len(set(reservations)):
        raise StudyError("development qualification reservations must be unique across routes")
    _integer(top["repetitions"], "development plan.repetitions", 1, 10)
    generation = _exact(top["generation"], {
        "maxTokens", "temperature", "reasoningEffort", "maxRepairs",
        "worstCaseCallCostGbp", "usdToGbpRate", "automaticTopUp",
    }, "development plan.generation")
    _integer(generation["maxTokens"], "development plan.generation.maxTokens", 256, 32000)
    _number(generation["temperature"], "development plan.generation.temperature", 0, 2)
    if generation["reasoningEffort"] != "none" or generation["maxRepairs"] != 0:
        raise StudyError("development comparison must be reasoning-off and repair-free")
    _number(generation["worstCaseCallCostGbp"],
            "development plan.generation.worstCaseCallCostGbp", 0, 500)
    _number(generation["usdToGbpRate"], "development plan.generation.usdToGbpRate", .000001, 100)
    if generation["automaticTopUp"] is not False:
        raise StudyError("development execution must disable automatic budget top-up")
    randomization = _exact(top["randomization"], {"strategy", "seed"},
                           "development plan.randomization")
    if randomization["strategy"] != "blocked-case-repetition-shuffle-v1":
        raise StudyError("unsupported development randomization strategy")
    _integer(randomization["seed"], "development plan.randomization.seed", 0, 2**63 - 1)
    budget = _exact(top["budget"], {"currency", "maximum"}, "development plan.budget")
    if budget["currency"] != "GBP":
        raise StudyError("development plan budget must use GBP")
    _number(budget["maximum"], "development plan.budget.maximum", 0, 500)
    renderer = _exact(top["renderer"], {"identitySha256"}, "development plan.renderer")
    if not isinstance(renderer["identitySha256"], str) or not HEX64.fullmatch(renderer["identitySha256"]):
        raise StudyError("development plan renderer identity must be SHA-256")
    files = top["protocolFiles"]
    if (not isinstance(files, dict) or not files
            or any(not isinstance(path, str) or not path or path.startswith("/")
                   or ".." in Path(path).parts or not isinstance(checksum, str)
                   or not HEX64.fullmatch(checksum) for path, checksum in files.items())):
        raise StudyError("development plan.protocolFiles must map safe relative paths to SHA-256 values")
    if top["claims"] != {"status": "disabled", "interpretation": "exploratory-development-only"}:
        raise StudyError("development plan must keep comparative claims disabled")
    return top


def development_plan_blockers(plan: Any, *, snapshot: Any | None = None,
                              spend_ledger: Any | None = None,
                              current_identity: dict[str, Any] | None = None,
                              now: datetime | None = None) -> list[str]:
    """Return every local entry blocker for a pinned development comparison."""
    try:
        plan = validate_development_plan(plan)
    except StudyError as error:
        return [str(error)]
    blockers: list[str] = []
    current_time = now or datetime.now(timezone.utc)
    for route in plan["routes"]:
        if _utc(route["qualification"]["expiresAt"], "route qualification.expiresAt") <= current_time:
            blockers.append(f"route qualification expired before execution: {route['routeId']}")
    snapshot_hashes = {route["snapshotSha256"] for route in plan["routes"]}
    if len(snapshot_hashes) != 1:
        blockers.append("development routes do not bind one model snapshot")
    if snapshot is None:
        blockers.append("the frozen model snapshot is required")
    elif digest(snapshot) not in snapshot_hashes:
        blockers.append("model snapshot differs from the development route plan")
    if spend_ledger is None:
        blockers.append("the cumulative spend ledger is required")
    else:
        try:
            validate_spend_ledger(spend_ledger)
        except StudyError as error:
            blockers.append(str(error))
        else:
            if spend_ledger["capGbp"] != plan["budget"]["maximum"]:
                blockers.append("spend ledger cap differs from the development plan")
            retained = {entry["reservationId"]: entry for entry in spend_ledger["entries"]}
            qualification_ids = {
                reservation_id for route in plan["routes"]
                for reservation_id in route["qualification"]["observations"]["reservationIds"]}
            if qualification_ids - set(retained):
                blockers.append("spend ledger lacks route-qualification reservations")
            elif any(retained[item]["stage"] != "qualification"
                     or retained[item]["status"] == "reserved" for item in qualification_ids):
                blockers.append("route-qualification spend reservations are not finalized")
            charged = sum(float(entry["chargedGbp"]) for entry in spend_ledger["entries"])
            reservation = (len(plan["routes"]) * len(plan["fixtures"])
                           * plan["repetitions"] * len(plan["conditions"])
                           * plan["generation"]["worstCaseCallCostGbp"])
            if charged + reservation > spend_ledger["capGbp"] + 1e-9:
                blockers.append("cumulative ledger lacks budget for the development matrix")
    if current_identity is not None:
        if current_identity.get("releaseCommit") != plan["releaseCommit"]:
            blockers.append("current release commit differs from the development plan")
        if current_identity.get("rendererIdentitySha256") != plan["renderer"]["identitySha256"]:
            blockers.append("current renderer identity differs from the development plan")
        if current_identity.get("protocolFiles") != plan["protocolFiles"]:
            blockers.append("current protocol files differ from the development plan")
    return blockers


def _validate_analysis_plan(value: Any, conditions: list[str]) -> None:
    analysis = _exact(value, {
        "primary", "secondaryComparators", "h2", "bootstrap", "powerPlan",
        "multiplicity", "missingData",
    }, "declaration.analysis")
    primary = _exact(analysis["primary"], {
        "hypothesis", "treatment", "comparator", "outcome", "minimumEffect", "alpha", "power",
    }, "declaration.analysis.primary")
    if (primary["hypothesis"] != "H1" or primary["treatment"] != "selected_context"
            or primary["comparator"] != "scaffolded_html"
            or primary["outcome"] != "firstPassBriefFulfilment"):
        raise StudyError("H1 primary must be selected_context versus scaffolded_html first-pass brief fulfilment")
    if primary["treatment"] not in conditions or primary["comparator"] not in conditions:
        raise StudyError("H1 primary conditions are absent from the declared matrix")
    if (primary["minimumEffect"] != .10 or primary["alpha"] != .05
            or primary["power"] != .90):
        raise StudyError("H1 must freeze minimumEffect .10, alpha .05 and power .90")
    secondary = _unique_strings(analysis["secondaryComparators"],
                                "analysis.secondaryComparators", 0)
    if any(item not in {"raw_brief", "brand_bible"} or item not in conditions for item in secondary):
        raise StudyError("secondary H1 comparators must be declared raw_brief or brand_bible conditions")
    h2 = _exact(analysis["h2"], {
        "treatment", "comparator", "tokenOutcome", "briefMargin", "contractMargin",
        "sourceFactMargin", "designMargin", "maximumTokenRatio",
    }, "declaration.analysis.h2")
    if h2["treatment"] != "selected_context" or h2["comparator"] != "full_rules":
        raise StudyError("H2 must compare selected_context with full_rules")
    if any(item not in conditions for item in (h2["treatment"], h2["comparator"])):
        raise StudyError("H2 conditions are absent from the declared matrix")
    if h2["tokenOutcome"] != "firstCallPromptTokens":
        raise StudyError("H2 token outcome must be firstCallPromptTokens")
    for key, maximum in (("briefMargin", .5), ("contractMargin", .5),
                         ("sourceFactMargin", .5), ("designMargin", 2.0)):
        _number(h2[key], f"analysis.h2.{key}", 0, maximum)
    expected_h2 = {"briefMargin": .05, "contractMargin": .05,
                   "sourceFactMargin": .02, "designMargin": .25,
                   "maximumTokenRatio": .80}
    if any(h2[key] != expected for key, expected in expected_h2.items()):
        raise StudyError("H2 must freeze .05/.05/.02/.25 margins and token ratio .80")
    bootstrap = _exact(analysis["bootstrap"], {
        "method", "replicates", "seed", "confidenceLevel",
    }, "declaration.analysis.bootstrap")
    if bootstrap["method"] != "paired-stratified-model-case-v1":
        raise StudyError("unsupported bootstrap method")
    if bootstrap["replicates"] != 20000 or bootstrap["confidenceLevel"] != .95:
        raise StudyError("confirmatory bootstrap must freeze 20,000 resamples and 95% confidence")
    _integer(bootstrap["seed"], "analysis.bootstrap.seed", 0, 2**63 - 1)
    _number(bootstrap["confidenceLevel"], "analysis.bootstrap.confidenceLevel", .8, .999)
    if analysis["multiplicity"] != "holm-secondary-h1":
        raise StudyError("multiplicity must use Holm adjustment for secondary H1 contrasts")
    if analysis["missingData"] != "scheduled-failure-zero; missing-cell-blocks-analysis":
        raise StudyError("unsupported missing-data rule")


def _validate_review_plan(value: Any, repetitions: int) -> None:
    review = _exact(value, {
        "attemptPolicy", "reviewerIds", "minimumReviewers", "agreementStatistic",
        "agreementThreshold", "missingArtifactScore", "missingRatingPolicy",
        "reviewerSelection", "conflicts", "independentReviewers", "selectedRepetition",
    }, "declaration.review")
    if review["attemptPolicy"] != "first-pass-for-H1":
        raise StudyError("review attempt policy must be first-pass-for-H1")
    reviewers = _unique_strings(review["reviewerIds"], "review.reviewerIds", 3)
    if len(reviewers) != 3 or review["minimumReviewers"] != 3:
        raise StudyError("confirmatory review requires exactly three declared reviewers")
    if review["independentReviewers"] is not True:
        raise StudyError("confirmatory reviewers must be declared independent")
    _integer(review["selectedRepetition"], "review.selectedRepetition", 0, repetitions - 1)
    if review["agreementStatistic"] != "krippendorff-alpha-ordinal":
        raise StudyError("unsupported agreement statistic")
    if review["agreementThreshold"] != .67:
        raise StudyError("review agreement threshold must be .67")
    if review["missingArtifactScore"] != 1 or review["missingRatingPolicy"] != "block-analysis":
        raise StudyError("review must score missing artifacts as 1 and block on missing ratings")
    _string(review["reviewerSelection"], "review.reviewerSelection", 2000)
    if not isinstance(review["conflicts"], list) or any(not isinstance(item, str) for item in review["conflicts"]):
        raise StudyError("review.conflicts must be a list of disclosures")


def _validate_power_plan(value: Any, repetitions: int, conditions: int,
                         maximum_budget_gbp: float) -> None:
    power = _exact(value, {
        "method", "baselineRate", "treatmentRate", "withinPairCorrelation",
        "estimatedCostPerCellGbp", "requiredPairs", "selectedRepetitions",
        "estimatedBudgetGbp", "estimatedPower", "simulationCount", "simulationSeed",
    }, "declaration.analysis.powerPlan")
    if power["method"] != "paired-binary-seeded-simulation-v1":
        raise StudyError("unsupported frozen power method")
    expected = plan_paired_power(
        baseline_rate=power["baselineRate"], treatment_rate=power["treatmentRate"],
        within_pair_correlation=power["withinPairCorrelation"], alpha=.05, power=.9,
        routes=6, fixtures=8, minimum_repetitions=5, maximum_repetitions=50,
        estimated_cost_per_cell_gbp=power["estimatedCostPerCellGbp"],
        conditions=conditions, maximum_budget_gbp=maximum_budget_gbp,
        simulations=power["simulationCount"], seed=power["simulationSeed"])
    if (power["requiredPairs"] != expected["requiredPairs"]
            or power["selectedRepetitions"] != expected["repetitionsPerRouteFixture"]
            or power["estimatedBudgetGbp"] != expected["estimatedBudgetGbp"]
            or power["estimatedPower"] != expected["estimatedPower"]
            or repetitions != power["selectedRepetitions"]):
        raise StudyError("declared repetitions or budget differ from the frozen 90% power plan")


def validate_freeze_receipt(value: Any) -> dict[str, Any]:
    receipt = _exact(value, {
        "schemaVersion", "receiptId", "studyId", "declarationSha256", "frozenAt",
        "custodian", "timestamp", "signature", "releaseCommit", "modelSnapshotSha256",
        "routeQualificationSha256", "reviewerCommitments", "budgetApproved",
        "budgetMaximum", "executionAuthorized", "spendLedgerPreRunSha256",
    }, "freeze receipt")
    if receipt["schemaVersion"] != VERSION:
        raise StudyError(f"freeze receipt must use schema {VERSION}")
    _identifier(receipt["receiptId"], "freeze receipt.receiptId")
    _identifier(receipt["studyId"], "freeze receipt.studyId")
    for key in ("declarationSha256", "modelSnapshotSha256", "spendLedgerPreRunSha256"):
        if not isinstance(receipt[key], str) or not HEX64.fullmatch(receipt[key]):
            raise StudyError(f"freeze receipt.{key} must be SHA-256")
    _utc(receipt["frozenAt"], "freeze receipt.frozenAt")
    custodian = _exact(receipt["custodian"], {"name", "organization", "independent"},
                       "freeze receipt.custodian")
    _string(custodian["name"], "freeze receipt.custodian.name", 240)
    _string(custodian["organization"], "freeze receipt.custodian.organization", 240)
    if custodian["independent"] is not True:
        raise StudyError("freeze receipt requires an independent custodian")
    timestamp = _exact(receipt["timestamp"], {"method", "url", "evidenceSha256"},
                       "freeze receipt.timestamp")
    if timestamp["method"] not in {"rfc3161", "git-commit", "human-countersignature"}:
        raise StudyError("freeze receipt timestamp method is unsupported")
    if not _string(timestamp["url"], "freeze receipt.timestamp.url", 2000).startswith("https://"):
        raise StudyError("freeze receipt timestamp URL must use HTTPS")
    if not isinstance(timestamp["evidenceSha256"], str) or not HEX64.fullmatch(
            timestamp["evidenceSha256"]):
        raise StudyError("freeze receipt timestamp evidence must be SHA-256 bound")
    signature = _exact(receipt["signature"], {
        "method", "keyId", "value", "signedBytesSha256", "locallyVerified",
    }, "freeze receipt.signature")
    if signature["method"] not in {"minisign-ed25519", "human-countersignature-sha256"}:
        raise StudyError("freeze receipt signature method is unsupported")
    _string(signature["keyId"], "freeze receipt.signature.keyId", 500)
    _string(signature["value"], "freeze receipt.signature.value", 5000)
    if (signature["signedBytesSha256"] != receipt["declarationSha256"]
            or signature["locallyVerified"] is not True):
        raise StudyError("freeze receipt signature must bind the declaration and verify locally")
    if not isinstance(receipt["releaseCommit"], str) or not COMMIT.fullmatch(receipt["releaseCommit"]):
        raise StudyError("freeze receipt.releaseCommit must be a full Git commit")
    qualifications = receipt["routeQualificationSha256"]
    if (not isinstance(qualifications, dict) or not qualifications
            or any(not IDENTIFIER.fullmatch(key) or not isinstance(value, str)
                   or not HEX64.fullmatch(value) for key, value in qualifications.items())):
        raise StudyError("freeze receipt.routeQualificationSha256 must map route IDs to SHA-256 values")
    reviewers = _unique_strings(receipt["reviewerCommitments"],
                                "freeze receipt.reviewerCommitments", 3)
    if len(reviewers) != 3:
        raise StudyError("freeze receipt must bind exactly three reviewer commitments")
    if receipt["budgetApproved"] is not True or receipt["executionAuthorized"] is not True:
        raise StudyError("freeze receipt must explicitly approve budget and execution")
    _number(receipt["budgetMaximum"], "freeze receipt.budgetMaximum", 0, 500)
    return receipt


def confirmatory_blockers(declaration: Any, receipt: Any | None, *,
                          snapshot: Any | None = None,
                          spend_ledger: Any | None = None,
                          current_identity: dict[str, Any] | None = None,
                          now: datetime | None = None) -> list[str]:
    """Return every fail-closed entry blocker without performing network I/O."""
    blockers: list[str] = []
    try:
        declaration = validate_declaration(declaration)
    except StudyError as error:
        return [str(error)]
    if receipt is None:
        return ["an externally timestamped freeze receipt is required"]
    try:
        receipt = validate_freeze_receipt(receipt)
    except StudyError as error:
        return [str(error)]
    if receipt["studyId"] != declaration["studyId"]:
        blockers.append("freeze receipt study ID differs from the declaration")
    if receipt["declarationSha256"] != digest(declaration):
        blockers.append("freeze receipt does not bind the canonical declaration")
    if receipt["releaseCommit"] != declaration["releaseCommit"]:
        blockers.append("freeze receipt release commit differs from the declaration")
    if receipt["budgetMaximum"] < declaration["budget"]["maximum"]:
        blockers.append("approved budget is below the declared maximum")
    if not set(declaration["review"]["reviewerIds"]).issubset(receipt["reviewerCommitments"]):
        blockers.append("freeze receipt lacks every declared reviewer commitment")
    qualification_hashes = receipt["routeQualificationSha256"]
    if set(qualification_hashes) != {route["routeId"] for route in declaration["routes"]}:
        blockers.append("freeze receipt qualification map differs from the six declared routes")
    current_time = now or datetime.now(timezone.utc)
    for route in declaration["routes"]:
        expected = route["qualification"]["receiptSha256"]
        if qualification_hashes.get(route["routeId"]) != expected:
            blockers.append(f"route qualification receipt is absent or changed: {route['routeId']}")
        if _utc(route["qualification"]["expiresAt"], "route qualification.expiresAt") <= current_time:
            blockers.append(f"route qualification expired before execution: {route['routeId']}")
    route_snapshot_hashes = {route["snapshotSha256"] for route in declaration["routes"]}
    if len(route_snapshot_hashes) != 1 or receipt["modelSnapshotSha256"] not in route_snapshot_hashes:
        blockers.append("routes and freeze receipt do not bind one model snapshot")
    if snapshot is None:
        blockers.append("the frozen model snapshot is required")
    elif digest(snapshot) != receipt["modelSnapshotSha256"]:
        blockers.append("model snapshot differs from the externally frozen digest")
    if spend_ledger is None:
        blockers.append("the cumulative spend ledger is required")
    else:
        try:
            validate_spend_ledger(spend_ledger)
        except StudyError as error:
            blockers.append(str(error))
        else:
            if spend_ledger["capGbp"] != declaration["budget"]["maximum"]:
                blockers.append("spend ledger cap differs from the declared GBP budget")
            if any(entry["status"] == "actual-exceeded-reservation"
                   for entry in spend_ledger["entries"]):
                blockers.append("spend ledger contains a provider cost above its frozen reservation")
            if digest(spend_ledger) != receipt["spendLedgerPreRunSha256"]:
                blockers.append("spend ledger differs from the externally frozen pre-run digest")
            qualification_reservations = {
                reservation_id
                for route in declaration["routes"]
                for reservation_id in route["qualification"]["observations"]["reservationIds"]
            }
            retained = {entry["reservationId"]: entry for entry in spend_ledger["entries"]}
            missing = sorted(qualification_reservations - set(retained))
            if missing:
                blockers.append("spend ledger lacks route-qualification reservations")
            elif any(retained[item]["stage"] != "qualification"
                     or retained[item]["status"] == "reserved"
                     for item in qualification_reservations):
                blockers.append("route-qualification spend reservations are not finalized")
            charged = sum(float(entry["chargedGbp"]) for entry in spend_ledger["entries"])
            generative_conditions = sum(
                condition != "deterministic_component" for condition in declaration["conditions"])
            confirmatory_reservation = (
                len(declaration["routes"]) * len(declaration["fixtures"])
                * declaration["repetitions"] * generative_conditions
                * declaration["generation"]["worstCaseCallCostGbp"])
            if charged + confirmatory_reservation > spend_ledger["capGbp"] + 1e-9:
                blockers.append("cumulative ledger lacks budget for every frozen confirmatory call")
    if current_identity is not None:
        if current_identity.get("releaseCommit") != declaration["releaseCommit"]:
            blockers.append("current release commit differs from the declaration")
        if current_identity.get("rendererIdentitySha256") != declaration["renderer"]["identitySha256"]:
            blockers.append("current renderer identity differs from the declaration")
        if current_identity.get("protocolFiles") != declaration["protocolFiles"]:
            blockers.append("current protocol files differ from the declaration")
    return blockers


def assert_confirmatory_ready(*args: Any, **kwargs: Any) -> dict[str, Any]:
    declaration = args[0] if args else kwargs.get("declaration")
    blockers = confirmatory_blockers(*args, **kwargs)
    if blockers:
        raise StudyError("confirmatory execution blocked: " + " | ".join(blockers))
    return declaration


class CellJournal:
    """Atomically record each deterministic matrix cell for safe crash recovery."""

    def __init__(self, path: Path, value: dict[str, Any]):
        self.path = path
        self.value = value
        self._validate()

    @classmethod
    def create(cls, path: Path, run_id: str, matrix: list[dict[str, Any]]) -> "CellJournal":
        cells = []
        for index, cell in enumerate(matrix):
            identifier = digest({"runId": run_id, "index": index, "cell": cell})[:24]
            cells.append({"cellId": identifier, "index": index, "cell": cell,
                          "status": "pending", "trialId": None, "trialSha256": None})
        value = {"schemaVersion": VERSION, "runId": run_id,
                 "matrixSha256": digest(matrix), "cells": cells}
        journal = cls(path, value)
        journal.save(exclusive=True)
        return journal

    @classmethod
    def load(cls, path: Path, run_id: str, matrix: list[dict[str, Any]]) -> "CellJournal":
        journal = cls(path, read_json(path))
        if journal.value["runId"] != run_id or journal.value["matrixSha256"] != digest(matrix):
            raise StudyError("cell journal differs from the frozen matrix")
        return journal

    def _validate(self) -> None:
        value = _exact(self.value, {"schemaVersion", "runId", "matrixSha256", "cells"},
                       "cell journal")
        if value["schemaVersion"] != VERSION or not isinstance(value["runId"], str):
            raise StudyError("invalid cell journal identity")
        if not isinstance(value["matrixSha256"], str) or not HEX64.fullmatch(value["matrixSha256"]):
            raise StudyError("invalid cell journal matrix digest")
        if not isinstance(value["cells"], list):
            raise StudyError("cell journal cells must be an array")
        seen: set[str] = set()
        for index, entry in enumerate(value["cells"]):
            entry = _exact(entry, {"cellId", "index", "cell", "status", "trialId", "trialSha256"},
                           f"cell journal.cells[{index}]")
            if entry["index"] != index or entry["status"] not in CELL_STATES:
                raise StudyError("cell journal order or status is invalid")
            if (not isinstance(entry["cellId"], str)
                    or not re.fullmatch(r"[0-9a-f]{24}", entry["cellId"])
                    or entry["cellId"] in seen):
                raise StudyError("cell journal cell IDs must be unique")
            seen.add(entry["cellId"])
            if entry["status"] == "complete":
                if (not isinstance(entry["trialId"], str) or not isinstance(entry["trialSha256"], str)
                        or not HEX64.fullmatch(entry["trialSha256"])):
                    raise StudyError("complete journal cells require a trial ID and digest")

    def save(self, *, exclusive: bool = False) -> None:
        self._validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if exclusive and self.path.exists():
            raise StudyError("cell journal already exists")
        temporary = self.path.with_name(self.path.name + ".tmp")
        if temporary.is_symlink():
            raise StudyError("cell journal temporary path must not be a symlink")
        temporary.unlink(missing_ok=True)
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(self.value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)

    def next_pending(self) -> dict[str, Any] | None:
        return next((entry for entry in self.value["cells"] if entry["status"] == "pending"), None)

    def begin(self, cell_id: str) -> None:
        entry = self._entry(cell_id)
        if entry["status"] != "pending":
            raise StudyError("only a pending cell can begin")
        entry["status"] = "in-flight"
        self.save()

    def complete(self, cell_id: str, trial_id: str, trial: dict[str, Any]) -> None:
        entry = self._entry(cell_id)
        if entry["status"] not in {"in-flight", "indeterminate"}:
            raise StudyError("only an active cell can complete")
        entry.update(status="complete", trialId=trial_id, trialSha256=digest(trial))
        self.save()

    def recover_in_flight(self) -> list[dict[str, Any]]:
        recovered = []
        for entry in self.value["cells"]:
            if entry["status"] == "in-flight":
                entry["status"] = "indeterminate"
                recovered.append(entry)
        if recovered:
            self.save()
        return recovered

    def verify_trial(self, cell_id: str, trial: dict[str, Any]) -> None:
        entry = self._entry(cell_id)
        if entry["status"] != "complete" or entry["trialSha256"] != digest(trial):
            raise StudyError(f"retained trial differs from journal cell {cell_id}")

    def _entry(self, cell_id: str) -> dict[str, Any]:
        for entry in self.value["cells"]:
            if entry["cellId"] == cell_id:
                return entry
        raise StudyError(f"unknown journal cell: {cell_id}")


def validate_spend_ledger(value: Any) -> dict[str, Any]:
    """Validate the cumulative, append-only budget ledger used before every call."""
    ledger = _exact(value, {
        "schemaVersion", "ledgerId", "currency", "capGbp", "automaticTopUp",
        "scope", "createdAt", "entries",
    }, "spend ledger")
    if ledger["schemaVersion"] != VERSION or ledger["currency"] != "GBP":
        raise StudyError("spend ledger must use protocol 0.5 and GBP")
    _identifier(ledger["ledgerId"], "spend ledger.ledgerId")
    cap = _number(ledger["capGbp"], "spend ledger.capGbp", 0, 500)
    if ledger["automaticTopUp"] is not False:
        raise StudyError("spend ledger automaticTopUp must be false")
    if ledger["scope"] != ["qualification", "development", "confirmatory"]:
        raise StudyError("spend ledger must cumulatively cover qualification, development, and confirmatory calls")
    _utc(ledger["createdAt"], "spend ledger.createdAt")
    if not isinstance(ledger["entries"], list):
        raise StudyError("spend ledger entries must be an array")
    seen: set[str] = set()
    total = 0.0
    overrun = False
    for index, entry in enumerate(ledger["entries"]):
        entry = _exact(entry, {
            "reservationId", "stage", "reservedGbp", "chargedGbp", "status",
            "providerReportedCostUsd", "usdToGbpRate", "reservedAt", "settledAt",
        }, f"spend ledger.entries[{index}]")
        identifier = _identifier(entry["reservationId"],
                                 f"spend ledger.entries[{index}].reservationId")
        if identifier in seen:
            raise StudyError("spend ledger reservation IDs must be unique")
        seen.add(identifier)
        if entry["stage"] not in SPEND_STAGES or entry["status"] not in SPEND_STATUSES:
            raise StudyError("spend ledger stage or status is invalid")
        reserved = _number(entry["reservedGbp"], "spend ledger reserved GBP", 0, 500)
        charged = _number(entry["chargedGbp"], "spend ledger charged GBP", 0, 1_000_000)
        rate = _number(entry["usdToGbpRate"], "spend ledger USD/GBP rate", .000001, 100)
        _utc(entry["reservedAt"], "spend ledger reservedAt")
        reported = entry["providerReportedCostUsd"]
        if entry["status"] == "reserved":
            if entry["settledAt"] is not None or reported is not None or charged != reserved:
                raise StudyError("an open reservation must keep its full charge and have no usage settlement")
        else:
            _utc(entry["settledAt"], "spend ledger settledAt")
            if entry["status"] == "usage-missing-reservation-retained":
                if reported is not None or charged != reserved:
                    raise StudyError("missing usage must retain the full reservation")
            else:
                cost = _number(reported, "spend ledger provider-reported USD", 0, 1_000_000)
                expected = round(cost * rate, 6)
                if charged != expected:
                    raise StudyError("settled GBP charge must equal retained provider cost at the frozen rate")
                if entry["status"] == "settled" and charged > reserved:
                    raise StudyError("a normal settlement cannot exceed its reservation")
                if entry["status"] == "actual-exceeded-reservation" and charged <= reserved:
                    raise StudyError("an overrun settlement must exceed its reservation")
                overrun = overrun or entry["status"] == "actual-exceeded-reservation"
        total += charged
    if total > cap and not overrun:
        raise StudyError("spend ledger charges exceed the fixed GBP cap")
    return ledger


class SpendLedger:
    """Atomic cumulative reservation ledger; reservations are charged before provider I/O."""

    def __init__(self, path: Path, value: dict[str, Any]):
        self.path = path
        self.value = validate_spend_ledger(value)

    @classmethod
    def create(cls, path: Path, ledger_id: str, *, cap_gbp: float = 500) -> "SpendLedger":
        value = {"schemaVersion": VERSION, "ledgerId": ledger_id, "currency": "GBP",
                 "capGbp": cap_gbp, "automaticTopUp": False,
                 "scope": ["qualification", "development", "confirmatory"],
                 "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                 "entries": []}
        ledger = cls(path, value)
        ledger._write(exclusive=True)
        return ledger

    @classmethod
    def load(cls, path: Path) -> "SpendLedger":
        if path.is_symlink():
            raise StudyError("spend ledger must not be a symlink")
        return cls(path, read_json(path))

    @property
    def charged_gbp(self) -> float:
        return round(sum(float(entry["chargedGbp"]) for entry in self.value["entries"]), 6)

    @property
    def remaining_gbp(self) -> float:
        return round(max(0.0, float(self.value["capGbp"]) - self.charged_gbp), 6)

    def snapshot(self) -> dict[str, Any]:
        return json.loads(canonical(self.value))

    def reserve(self, reservation_id: str, *, stage: str, worst_case_gbp: float,
                usd_to_gbp_rate: float) -> dict[str, Any]:
        _identifier(reservation_id, "reservationId")
        if stage not in SPEND_STAGES:
            raise StudyError("spend reservation stage is invalid")
        amount = _number(worst_case_gbp, "worstCaseGbp", 0, 500)
        rate = _number(usd_to_gbp_rate, "usdToGbpRate", .000001, 100)

        def update(value: dict[str, Any]) -> dict[str, Any]:
            if any(entry["reservationId"] == reservation_id for entry in value["entries"]):
                raise StudyError(f"duplicate spend reservation: {reservation_id}")
            charged = sum(float(entry["chargedGbp"]) for entry in value["entries"])
            if charged + amount > float(value["capGbp"]) + 1e-9:
                raise StudyError("provider call refused: worst-case reservation exceeds the remaining GBP budget")
            entry = {"reservationId": reservation_id, "stage": stage,
                     "reservedGbp": round(amount, 6), "chargedGbp": round(amount, 6),
                     "status": "reserved", "providerReportedCostUsd": None,
                     "usdToGbpRate": rate,
                     "reservedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                     "settledAt": None}
            value["entries"].append(entry)
            return entry

        return self._locked_update(update)

    def settle(self, reservation_id: str, provider_reported_cost_usd: float | None) -> dict[str, Any]:
        def update(value: dict[str, Any]) -> dict[str, Any]:
            entry = next((row for row in value["entries"]
                          if row["reservationId"] == reservation_id), None)
            if entry is None or entry["status"] != "reserved":
                raise StudyError("only an existing open spend reservation can be settled")
            entry["settledAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            if provider_reported_cost_usd is None:
                entry["status"] = "usage-missing-reservation-retained"
                return entry
            cost = _number(provider_reported_cost_usd, "providerReportedCostUsd", 0, 1_000_000)
            charged = round(cost * float(entry["usdToGbpRate"]), 6)
            entry["providerReportedCostUsd"] = cost
            entry["chargedGbp"] = charged
            entry["status"] = ("settled" if charged <= float(entry["reservedGbp"])
                               else "actual-exceeded-reservation")
            return entry

        entry = self._locked_update(update)
        if entry["status"] == "actual-exceeded-reservation":
            raise StudyError("provider-reported cost exceeded the declared worst-case reservation")
        return entry

    def _locked_update(self, callback: Any) -> dict[str, Any]:
        lock = self.path.with_name(self.path.name + ".lock")
        descriptor = None
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            os.fsync(descriptor)
            current = read_json(self.path)
            validate_spend_ledger(current)
            result = callback(current)
            validate_spend_ledger(current)
            self.value = current
            self._write()
            return json.loads(canonical(result))
        except FileExistsError as error:
            raise StudyError("spend ledger is locked by another process") from error
        finally:
            if descriptor is not None:
                os.close(descriptor)
                lock.unlink(missing_ok=True)

    def _write(self, *, exclusive: bool = False) -> None:
        validate_spend_ledger(self.value)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink() or (exclusive and self.path.exists()):
            raise StudyError("spend ledger path is unsafe or already exists")
        temporary = self.path.with_name(self.path.name + ".tmp")
        if temporary.is_symlink():
            raise StudyError("spend ledger temporary path must not be a symlink")
        temporary.unlink(missing_ok=True)
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(self.value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive and self.path.exists():
            temporary.unlink(missing_ok=True)
            raise StudyError("spend ledger already exists")
        os.replace(temporary, self.path)


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise StudyError("cannot calculate a percentile without values")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def paired_binary_analysis(trials: list[dict[str, Any]], *, treatment: str,
                           comparator: str, outcome: str, model_families: dict[str, str],
                           replicates: int, seed: int, confidence_level: float) -> dict[str, Any]:
    """Deterministic failure-aware paired risk difference and stratified bootstrap."""
    if outcome not in {"firstPassBriefFulfilment", "firstPassAgentContractConformance"}:
        raise StudyError("unsupported paired binary outcome")
    if not 100 <= replicates <= 200000:
        raise StudyError("bootstrap replicates must be between 100 and 200000")
    observations: dict[tuple[str, str, int], dict[str, bool]] = {}
    for trial in trials:
        condition = trial.get("condition")
        if condition not in {treatment, comparator}:
            continue
        model = trial.get("requestedModel")
        key = (model, trial.get("caseId"), trial.get("repetition"))
        value = (trial.get("metrics") or {}).get(outcome)
        if type(value) is not bool:
            raise StudyError(f"paired outcome is missing for scheduled cell {key} {condition}")
        if model not in model_families:
            raise StudyError(f"undeclared model in paired analysis: {model}")
        bucket = observations.setdefault(key, {})
        if condition in bucket:
            raise StudyError(f"duplicate paired cell: {key} {condition}")
        bucket[condition] = value
    incomplete = [key for key, pair in observations.items()
                  if set(pair) != {treatment, comparator}]
    if incomplete or not observations:
        raise StudyError("paired analysis requires exactly one observation per declared condition and cell")
    pairs = [(key, int(pair[treatment]) - int(pair[comparator]))
             for key, pair in sorted(observations.items())]
    estimate = sum(value for _, value in pairs) / len(pairs)
    by_model: dict[str, list[tuple[tuple[str, str, int], int]]] = {}
    for pair in pairs:
        by_model.setdefault(pair[0][0], []).append(pair)
    rng = random.Random(seed)
    samples: list[float] = []
    model_ids = sorted(by_model)
    for _ in range(replicates):
        selected_models = [rng.choice(model_ids) for _ in model_ids]
        values: list[int] = []
        for model in selected_models:
            rows = by_model[model]
            cases = sorted({row[0][1] for row in rows})
            sampled_cases = [rng.choice(cases) for _ in cases]
            for case in sampled_cases:
                case_rows = [row for row in rows if row[0][1] == case]
                values.extend(rng.choice(case_rows)[1] for _ in case_rows)
        samples.append(sum(values) / len(values))
    tail = (1 - confidence_level) / 2
    return {
        "treatment": treatment, "comparator": comparator, "outcome": outcome,
        "pairs": len(pairs), "estimate": estimate,
        "confidenceInterval": {"level": confidence_level,
                               "lower": _percentile(samples, tail),
                               "upper": _percentile(samples, 1 - tail)},
        "oneSided95Lower": _percentile(samples, .05),
        "bootstrap": {"method": "paired-stratified-model-case-v1",
                      "replicates": replicates, "seed": seed},
        "oneSidedPValueAtZero": (1 + sum(value <= 0 for value in samples)) / (replicates + 1),
        "strata": {
            "models": [{"modelId": model, "modelFamily": model_families[model],
                        "pairs": len(rows), "estimate": sum(value for _, value in rows) / len(rows)}
                       for model, rows in sorted(by_model.items())],
            "families": _family_rows(pairs, model_families),
        },
    }


def paired_numeric_analysis(trials: list[dict[str, Any]], *, treatment: str,
                            comparator: str, metric: str,
                            model_families: dict[str, str], replicates: int,
                            seed: int, confidence_level: float) -> dict[str, Any]:
    """Paired difference for a failure-aware numeric trial metric."""
    observations: dict[tuple[str, str, int], dict[str, float]] = {}
    for trial in trials:
        condition = trial.get("condition")
        if condition not in {treatment, comparator}:
            continue
        model = trial.get("requestedModel")
        if model not in model_families:
            raise StudyError(f"undeclared model in paired analysis: {model}")
        if metric == "firstPassSourceFactCoverage":
            record = (trial.get("metrics") or {}).get(metric)
            value = record.get("rate") if isinstance(record, dict) else 0.0
        else:
            value = (trial.get("metrics") or {}).get(metric)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise StudyError(f"paired numeric metric is invalid: {metric}")
        key = (model, trial.get("caseId"), trial.get("repetition"))
        bucket = observations.setdefault(key, {})
        if condition in bucket:
            raise StudyError("duplicate paired numeric cell")
        bucket[condition] = float(value)
    if not observations or any(set(pair) != {treatment, comparator}
                               for pair in observations.values()):
        raise StudyError("paired numeric analysis requires a complete matrix")
    pairs = [(key, pair[treatment] - pair[comparator])
             for key, pair in sorted(observations.items())]
    estimate = sum(value for _, value in pairs) / len(pairs)
    by_model: dict[str, list[tuple[tuple[str, str, int], float]]] = {}
    for pair in pairs:
        by_model.setdefault(pair[0][0], []).append(pair)
    rng = random.Random(seed)
    samples = []
    model_ids = sorted(by_model)
    for _ in range(replicates):
        values = []
        for model in [rng.choice(model_ids) for _ in model_ids]:
            rows = by_model[model]
            cases = sorted({row[0][1] for row in rows})
            for case in [rng.choice(cases) for _ in cases]:
                case_rows = [row for row in rows if row[0][1] == case]
                values.extend(rng.choice(case_rows)[1] for _ in case_rows)
        samples.append(sum(values) / len(values))
    tail = (1 - confidence_level) / 2
    return {"treatment": treatment, "comparator": comparator, "outcome": metric,
            "pairs": len(pairs), "estimate": estimate,
            "confidenceInterval": {"level": confidence_level,
                                   "lower": _percentile(samples, tail),
                                   "upper": _percentile(samples, 1 - tail)},
            "oneSided95Lower": _percentile(samples, .05),
            "bootstrap": {"method": "paired-stratified-model-case-v1",
                          "replicates": replicates, "seed": seed}}


def _family_rows(pairs: list[tuple[tuple[str, str, int], int]],
                 model_families: dict[str, str]) -> list[dict[str, Any]]:
    groups: dict[str, list[int]] = {}
    for (model, _, _), value in pairs:
        groups.setdefault(model_families[model], []).append(value)
    return [{"modelFamily": family, "pairs": len(values),
             "estimate": sum(values) / len(values)} for family, values in sorted(groups.items())]


def first_call_prompt_token_analysis(trials: list[dict[str, Any]], *, treatment: str,
                                     comparator: str) -> dict[str, Any]:
    cells: dict[tuple[str, str, int], dict[str, int]] = {}
    for trial in trials:
        condition = trial.get("condition")
        if condition not in {treatment, comparator}:
            continue
        calls = trial.get("calls")
        tokens = ((calls[0].get("usage") or {}).get("promptTokens")
                  if isinstance(calls, list) and calls else None)
        if type(tokens) is not int or tokens < 0:
            raise StudyError("H2 requires provider-reported first-call prompt tokens for every pair")
        key = (trial.get("requestedModel"), trial.get("caseId"), trial.get("repetition"))
        bucket = cells.setdefault(key, {})
        if condition in bucket:
            raise StudyError("duplicate H2 token cell")
        bucket[condition] = tokens
    if not cells or any(set(pair) != {treatment, comparator} for pair in cells.values()):
        raise StudyError("H2 requires complete selected/full token pairs")
    differences = [pair[treatment] - pair[comparator] for pair in cells.values()]
    ratios = [pair[treatment] / pair[comparator] for pair in cells.values()
              if pair[comparator] > 0]
    if len(ratios) != len(cells):
        raise StudyError("H2 comparator prompt-token values must be positive")
    return {"outcome": "firstCallPromptTokens", "pairs": len(cells),
            "meanDifference": sum(differences) / len(differences),
            "meanRatio": sum(ratios) / len(ratios)}


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for rank, (name, value) in enumerate(ordered):
        _number(value, f"pValues.{name}", 0, 1)
        running = max(running, min(1.0, value * (total - rank)))
        adjusted[name] = running
    return {name: adjusted[name] for name in sorted(adjusted)}


def plan_paired_power(*, baseline_rate: float, treatment_rate: float,
                      within_pair_correlation: float, alpha: float, power: float,
                      routes: int, fixtures: int, minimum_repetitions: int = 5,
                      maximum_repetitions: int = 50,
                      estimated_cost_per_cell_gbp: float = 0,
                      conditions: int = 5, maximum_budget_gbp: float = 500,
                      simulations: int = 10_000, seed: int = 20260912,
                      minimum_effect: float = .10) -> dict[str, Any]:
    """Choose 5–50 repetitions with a seeded simulation of paired binary trials."""
    p0 = _number(baseline_rate, "baselineRate", .001, .999)
    p1 = _number(treatment_rate, "treatmentRate", .001, .999)
    correlation = _number(within_pair_correlation, "withinPairCorrelation", -.99, .99)
    if p1 <= p0:
        raise StudyError("power planning requires treatmentRate greater than baselineRate")
    _integer(routes, "routes", 1, 100)
    _integer(fixtures, "fixtures", 1, 100)
    _integer(minimum_repetitions, "minimumRepetitions", 5, 50)
    _integer(maximum_repetitions, "maximumRepetitions", minimum_repetitions, 50)
    cost_per_cell = _number(estimated_cost_per_cell_gbp, "estimatedCostPerCellGbp", 0, 500)
    _integer(conditions, "conditions", 1, 7)
    budget = _number(maximum_budget_gbp, "maximumBudgetGbp", 0, 500)
    simulation_count = _integer(simulations, "simulations", 10_000, 200_000)
    simulation_seed = _integer(seed, "simulationSeed", 0, 2**63 - 1)
    alpha_value = _number(alpha, "alpha", .001, .2)
    target_power = _number(power, "power", .5, .999)
    effect_floor = _number(minimum_effect, "minimumEffect", 0, 1)

    variance0 = p0 * (1 - p0)
    variance1 = p1 * (1 - p1)
    p11 = p0 * p1 + correlation * math.sqrt(variance0 * variance1)
    feasible_lower = max(0.0, p0 + p1 - 1)
    feasible_upper = min(p0, p1)
    if not feasible_lower <= p11 <= feasible_upper:
        raise StudyError("within-pair correlation is incompatible with the declared binary rates")
    probabilities = (p11, p1 - p11, p0 - p11)
    z_one_sided = NormalDist().inv_cdf(1 - alpha_value)
    selected: tuple[int, float, float] | None = None
    for repetitions in range(minimum_repetitions, maximum_repetitions + 1):
        pairs = routes * fixtures * repetitions
        estimated_budget = round(pairs * conditions * cost_per_cell, 6)
        if estimated_budget > budget:
            continue
        rng = random.Random(simulation_seed + repetitions)
        successes = 0
        for _ in range(simulation_count):
            treatment_only = 0
            comparator_only = 0
            for _pair in range(pairs):
                draw = rng.random()
                if draw < probabilities[0]:
                    continue
                if draw < probabilities[0] + probabilities[1]:
                    treatment_only += 1
                elif draw < sum(probabilities):
                    comparator_only += 1
            estimate = (treatment_only - comparator_only) / pairs
            discordant = treatment_only + comparator_only
            sample_variance = max(0.0, (discordant - pairs * estimate**2) / (pairs - 1))
            standard_error = math.sqrt(sample_variance / pairs)
            one_sided_lower = estimate - z_one_sided * standard_error
            if estimate >= effect_floor and one_sided_lower > 0:
                successes += 1
        estimated_power = successes / simulation_count
        if estimated_power >= target_power:
            selected = (repetitions, estimated_power, estimated_budget)
            break
    if selected is None:
        raise StudyError("the seeded simulation cannot reach 90% power within 5–50 repetitions and the GBP budget cap")
    repetitions, estimated_power, estimated_budget = selected
    required_pairs = routes * fixtures * repetitions
    return {"method": "paired-binary-seeded-simulation-v1",
            "assumptions": {"baselineRate": p0, "treatmentRate": p1,
                            "withinPairCorrelation": correlation, "alpha": alpha,
                            "power": power, "minimumEffect": effect_floor,
                            "routes": routes, "fixtures": fixtures},
            "simulationCount": simulation_count, "simulationSeed": simulation_seed,
            "estimatedPower": round(estimated_power, 6),
            "requiredPairs": required_pairs,
            "repetitionsPerRouteFixture": repetitions,
            "maximumRepetitions": maximum_repetitions,
            "estimatedCostPerCellGbp": cost_per_cell,
            "estimatedBudgetGbp": estimated_budget,
            "maximumBudgetGbp": budget, "feasible": True}


def exploratory_h3_gate(trials: list[dict[str, Any]], *, replicates: int = 20_000,
                        seed: int = 503) -> dict[str, Any]:
    """Report the predeclared exploratory repair gate without entering H1/H2 claims."""
    _integer(replicates, "H3 bootstrap replicates", 1000, 200_000)
    _integer(seed, "H3 bootstrap seed", 0, 2**63 - 1)
    eligible = [trial for trial in trials
                if (trial.get("metrics") or {}).get("repairEligible") is True]
    recoveries = sum((trial.get("metrics") or {}).get("repairSuccess") is True
                     for trial in eligible)
    regressions = 0
    for trial in trials:
        metrics = trial.get("metrics") or {}
        first = metrics.get("firstPassSourceFactCoverage")
        final = metrics.get("finalSourceFactCoverage")
        first_rate = first.get("rate") if isinstance(first, dict) else None
        final_rate = final.get("rate") if isinstance(final, dict) else None
        source_regressed = (isinstance(first_rate, (int, float))
                            and (not isinstance(final_rate, (int, float))
                                 or final_rate < first_rate))
        brief_regressed = (metrics.get("firstPassBriefFulfilment") is True
                           and metrics.get("finalBriefFulfilment") is not True)
        if source_regressed or brief_regressed:
            regressions += 1
    estimate = recoveries / len(eligible) if eligible else None
    lower = None
    if eligible:
        population = [1] * recoveries + [0] * (len(eligible) - recoveries)
        rng = random.Random(seed)
        samples = [sum(rng.choice(population) for _ in population) / len(population)
                   for _ in range(replicates)]
        lower = _percentile(samples, .05)
    passed = (len(eligible) >= 30 and estimate is not None and estimate >= .30
              and lower is not None and lower > .10 and regressions == 0)
    return {
        "scope": "exploratory-only", "entersPrimaryConfirmatoryClaims": False,
        "eligibleFailures": len(eligible), "minimumEligibleFailures": 30,
        "recoveries": recoveries, "recoveryEstimate": estimate,
        "minimumRecoveryEstimate": .30, "oneSided95Lower": lower,
        "minimumOneSided95Lower": .10,
        "selectedContentRegressions": regressions,
        "maximumSelectedContentRegressions": 0,
        "bootstrap": {"method": "eligible-failure-resample-v1",
                      "replicates": replicates, "seed": seed},
        "gatePassed": passed,
    }


def krippendorff_alpha_ordinal(ratings_by_item: list[list[int]]) -> float:
    if not ratings_by_item or any(len(row) < 2 for row in ratings_by_item):
        raise StudyError("agreement requires at least two ratings for every item")
    if any(type(score) is not int or not 1 <= score <= 5
           for row in ratings_by_item for score in row):
        raise StudyError("agreement ratings must be integers from 1 to 5")
    observed_terms = [(left - right) ** 2 / 16
                      for row in ratings_by_item
                      for index, left in enumerate(row)
                      for right in row[index + 1:]]
    flat = [score for row in ratings_by_item for score in row]
    expected_terms = [(left - right) ** 2 / 16
                      for index, left in enumerate(flat)
                      for right in flat[index + 1:]]
    observed = sum(observed_terms) / len(observed_terms)
    expected = sum(expected_terms) / len(expected_terms) if expected_terms else 0
    if expected == 0:
        return 1.0 if observed == 0 else 0.0
    return 1 - observed / expected


def seal_review_set(run_directory: Path, declaration: dict[str, Any],
                    review_files: list[Path], output: Path) -> dict[str, Any]:
    declaration = validate_declaration(declaration)
    precommit = read_json(run_directory / "precommit.json")
    key = read_json(run_directory / "designer-review-key.json")
    if precommit.get("runId") != key.get("runId") or precommit.get("schemaVersion") != VERSION:
        raise StudyError("run records do not bind one protocol 0.5 run")
    if precommit.get("reviewAttemptPolicy") != declaration["review"]["attemptPolicy"]:
        raise StudyError("run review policy differs from the declaration")
    declared = declaration["review"]["reviewerIds"]
    if len(review_files) != 3:
        raise StudyError("confirmatory sealing requires exactly three completed reviewer files")
    records = []
    reviewer_ids: list[str] = []
    common_ids: list[str] | None = None
    card_orders: list[tuple[str, ...]] = []
    master = read_json(run_directory / "designer-review.json")
    master_cards = {card.get("blindId"): card for card in master.get("cards", [])
                    if isinstance(card, dict)}
    for path in review_files:
        record = read_json(path, 5_000_000)
        reviewer_id = record.get("reviewerId") if isinstance(record, dict) else None
        if reviewer_id not in declared or reviewer_id in reviewer_ids:
            raise StudyError("reviewer files must use unique declared reviewer IDs")
        if record.get("schemaVersion") != VERSION or record.get("status") != "complete" \
                or record.get("attemptPolicy") != "first-pass-for-H1":
            raise StudyError("reviewer file is incomplete or uses a different protocol")
        cards = record.get("cards")
        if not isinstance(cards, list) or not cards:
            raise StudyError("reviewer file has no cards")
        ids = [card.get("blindId") for card in cards if isinstance(card, dict)]
        if len(ids) != len(cards) or len(ids) != len(set(ids)) or set(ids) != set(key.get("mapping", {})):
            raise StudyError("reviewer cards differ from the sealed blind set")
        card_orders.append(tuple(ids))
        for card in cards:
            scores = card.get("scores")
            if not isinstance(scores, dict) or set(scores) != set(REVIEW_FIELDS) \
                    or any(type(scores[field]) is not int or not 1 <= scores[field] <= 5
                           for field in REVIEW_FIELDS):
                raise StudyError("every reviewer score must be an integer from 1 to 5")
            screenshots = card.get("screenshots")
            master_card = master_cards.get(card.get("blindId"))
            if (not isinstance(screenshots, list) or not screenshots
                    or not isinstance(master_card, dict)):
                raise StudyError("reviewer screenshot set differs from the sealed PNG cards")
            reviewer_hashes = []
            for screenshot in screenshots:
                target = (run_directory / screenshot).resolve()
                if (Path(screenshot).suffix.lower() != ".png"
                        or not target.is_relative_to(path.parent.resolve()) or not target.is_file()):
                    raise StudyError("reviewer material must contain existing run-relative PNGs only")
                reviewer_hashes.append(digest(target.read_bytes()))
            master_screenshots = master_card.get("screenshots")
            if not isinstance(master_screenshots, list) or len(master_screenshots) != len(screenshots):
                raise StudyError("reviewer screenshot set differs from the sealed PNG cards")
            master_hashes = []
            for screenshot in master_screenshots:
                target = (run_directory / screenshot).resolve()
                if (Path(screenshot).suffix.lower() != ".png"
                        or not target.is_relative_to(run_directory.resolve()) or not target.is_file()):
                    raise StudyError("master review material must contain retained PNGs only")
                master_hashes.append(digest(target.read_bytes()))
            if reviewer_hashes != master_hashes:
                raise StudyError("reviewer screenshot bytes differ from the sealed blind set")
        if common_ids is None:
            common_ids = ids
        records.append({card["blindId"]: card for card in cards})
        reviewer_ids.append(reviewer_id)
    if set(reviewer_ids) != set(declared) or len(set(card_orders)) != 3:
        raise StudyError("all three declared reviewers need separately shuffled card orders")
    ordered_ids = sorted(common_ids or [])
    agreement = {}
    for field in REVIEW_FIELDS:
        rows = [[record[blind_id]["scores"][field] for record in records]
                for blind_id in ordered_ids]
        agreement[field] = krippendorff_alpha_ordinal(rows)
    artifact_scores = []
    mapped_trial_ids = set()
    for blind_id in ordered_ids:
        identity = key["mapping"][blind_id]
        required_identity = ("trialId", "condition", "requestedModel", "caseId", "repetition")
        if any(identity.get(field) is None for field in required_identity):
            raise StudyError("unblinding key lacks the declared pairing identity")
        if identity.get("attemptIndex") != 0 or identity.get("repaired") is not False:
            raise StudyError("confirmatory review must contain first-pass artifacts only")
        if identity["repetition"] != declaration["review"]["selectedRepetition"]:
            raise StudyError("confirmatory review contains an undeclared repetition")
        mapped_trial_ids.add(identity["trialId"])
        artifact_scores.append({
            **{field: identity[field] for field in required_identity},
            "missingArtifact": False,
            "meanScores": {field: sum(record[blind_id]["scores"][field] for record in records)
                           / len(records) for field in REVIEW_FIELDS},
        })
    trials_path = run_directory / "trials.jsonl"
    if trials_path.is_file():
        for trial in _read_jsonl(trials_path):
            if (trial.get("repetition") != declaration["review"]["selectedRepetition"]
                    or trial.get("condition") == "deterministic_component"
                    or trial.get("trialId") in mapped_trial_ids):
                continue
            artifact_scores.append({"trialId": trial["trialId"],
                                    "condition": trial["condition"],
                                    "requestedModel": trial["requestedModel"],
                                    "caseId": trial["caseId"],
                                    "repetition": trial["repetition"],
                                    "missingArtifact": True,
                                    "meanScores": {field: declaration["review"]["missingArtifactScore"]
                                                   for field in REVIEW_FIELDS}})
    artifact_scores.sort(key=lambda row: (row["condition"], row["requestedModel"],
                                          row["caseId"], row["trialId"]))
    score_groups: dict[tuple[str, str], dict[str, list[float]]] = {}
    for artifact in artifact_scores:
        group = score_groups.setdefault((artifact["condition"], artifact["requestedModel"]),
                                        {field: [] for field in REVIEW_FIELDS})
        for field in REVIEW_FIELDS:
            group[field].append(artifact["meanScores"][field])
    condition_scores = []
    for (condition, model), values in sorted(score_groups.items()):
        ratings = len(values["overall"])
        condition_scores.append({"condition": condition, "requestedModel": model,
                                 "ratings": ratings,
                                 "meanScores": {field: sum(scores) / len(scores)
                                                for field, scores in values.items()}})
    threshold = declaration["review"]["agreementThreshold"]
    result = {
        "schemaVersion": VERSION, "runId": precommit["runId"],
        "studyId": declaration["studyId"], "declarationSha256": digest(declaration),
        "attemptPolicy": "first-pass-for-H1", "cardSetSha256": digest(ordered_ids),
        "reviewers": [{"reviewerId": reviewer_id,
                       "fileSha256": digest(path.read_bytes())}
                      for reviewer_id, path in zip(reviewer_ids, review_files)],
        "cards": len(ordered_ids), "agreementStatistic": "krippendorff-alpha-ordinal",
        "agreement": agreement, "agreementThreshold": threshold,
        "agreementGatePassed": all(value >= threshold for value in agreement.values()),
        "conditionScores": condition_scores,
        "artifactScores": artifact_scores,
        "status": "sealed",
    }
    validate_review_set(result)
    _write_json(output, result, exclusive=True)
    return result


def validate_review_set(value: Any) -> dict[str, Any]:
    review = _exact(value, {
        "schemaVersion", "runId", "studyId", "declarationSha256", "attemptPolicy",
        "cardSetSha256", "reviewers", "cards", "agreementStatistic", "agreement",
        "agreementThreshold", "agreementGatePassed", "conditionScores", "artifactScores", "status",
    }, "review set")
    if review["schemaVersion"] != VERSION or review["status"] != "sealed" \
            or review["attemptPolicy"] != "first-pass-for-H1":
        raise StudyError("invalid review-set identity")
    _identifier(review["studyId"], "review set.studyId")
    for field in ("declarationSha256", "cardSetSha256"):
        if not isinstance(review[field], str) or not HEX64.fullmatch(review[field]):
            raise StudyError(f"review set.{field} must be SHA-256")
    _integer(review["cards"], "review set.cards", 1, 1_000_000)
    reviewers = review["reviewers"]
    if not isinstance(reviewers, list) or len(reviewers) != 3:
        raise StudyError("confirmatory review set requires exactly three reviewers")
    ids = []
    for index, reviewer in enumerate(reviewers):
        reviewer = _exact(reviewer, {"reviewerId", "fileSha256"}, f"reviewers[{index}]")
        ids.append(_string(reviewer["reviewerId"], f"reviewers[{index}].reviewerId", 120))
        if not isinstance(reviewer["fileSha256"], str) or not HEX64.fullmatch(reviewer["fileSha256"]):
            raise StudyError("reviewer file digest must be SHA-256")
    if len(ids) != len(set(ids)):
        raise StudyError("reviewer IDs must be unique")
    if review["agreementStatistic"] != "krippendorff-alpha-ordinal":
        raise StudyError("unsupported review agreement statistic")
    if not isinstance(review["agreement"], dict) or set(review["agreement"]) != set(REVIEW_FIELDS):
        raise StudyError("review-set agreement fields are incomplete")
    for field, value in review["agreement"].items():
        _number(value, f"review set.agreement.{field}", -1, 1)
    _number(review["agreementThreshold"], "review set.agreementThreshold", -1, 1)
    if type(review["agreementGatePassed"]) is not bool:
        raise StudyError("review set agreement gate must be boolean")
    scores = review["conditionScores"]
    if not isinstance(scores, list) or not scores:
        raise StudyError("review set condition scores are required")
    identities = set()
    for index, row in enumerate(scores):
        row = _exact(row, {"condition", "requestedModel", "ratings", "meanScores"},
                     f"review set.conditionScores[{index}]")
        identity = (_string(row["condition"], "condition score condition", 120),
                    _string(row["requestedModel"], "condition score model", 240))
        if identity in identities:
            raise StudyError("review condition/model groups must be unique")
        identities.add(identity)
        _integer(row["ratings"], "condition score ratings", 1, 10_000_000)
        if not isinstance(row["meanScores"], dict) or set(row["meanScores"]) != set(REVIEW_FIELDS):
            raise StudyError("review condition score dimensions are incomplete")
        for field, value in row["meanScores"].items():
            _number(value, f"condition score {field}", 1, 5)
    artifacts = review["artifactScores"]
    if not isinstance(artifacts, list) or not artifacts:
        raise StudyError("review-set artifact scores are required")
    trial_ids = set()
    for index, row in enumerate(artifacts):
        row = _exact(row, {"trialId", "condition", "requestedModel", "caseId", "repetition",
                           "missingArtifact", "meanScores"},
                     f"review set.artifactScores[{index}]")
        if row["trialId"] in trial_ids or type(row["missingArtifact"]) is not bool:
            raise StudyError("review artifact identities must be unique and explicit")
        trial_ids.add(_string(row["trialId"], "review artifact trial ID", 240))
        for field in ("condition", "requestedModel", "caseId"):
            _string(row[field], f"review artifact {field}", 240)
        _integer(row["repetition"], "review artifact repetition", 0, 49)
        if not isinstance(row["meanScores"], dict) or set(row["meanScores"]) != set(REVIEW_FIELDS):
            raise StudyError("review artifact score dimensions are incomplete")
        for field, value in row["meanScores"].items():
            _number(value, f"review artifact {field}", 1, 5)
    return review


def analyze_confirmatory(run_directory: Path, declaration: dict[str, Any],
                         review_set: dict[str, Any] | None = None) -> dict[str, Any]:
    declaration = validate_declaration(declaration)
    precommit = read_json(run_directory / "precommit.json")
    results = read_json(run_directory / "results.json")
    trials = _read_jsonl(run_directory / "trials.jsonl")
    if precommit.get("studyMode") != "confirmatory" or precommit.get("schemaVersion") != VERSION:
        raise StudyError("analysis requires a completed confirmatory protocol 0.5 run")
    if results.get("status") != "complete" or results.get("runId") != precommit.get("runId"):
        raise StudyError("confirmatory run is incomplete or internally inconsistent")
    expected_cells = len(declaration["fixtures"]) * len(declaration["routes"]) \
        * len([condition for condition in declaration["conditions"]
               if condition != "deterministic_component"]) * declaration["repetitions"]
    if "deterministic_component" in declaration["conditions"]:
        expected_cells += len(declaration["fixtures"]) * declaration["repetitions"]
    if len(trials) != expected_cells:
        raise StudyError("retained trials do not cover the complete declared matrix")
    _assert_declared_trials(trials, declaration)
    analysis = declaration["analysis"]
    bootstrap = analysis["bootstrap"]
    families = {route["modelId"]: route["modelFamily"] for route in declaration["routes"]}
    primary = paired_binary_analysis(
        trials, treatment=analysis["primary"]["treatment"],
        comparator=analysis["primary"]["comparator"],
        outcome=analysis["primary"]["outcome"], model_families=families,
        replicates=bootstrap["replicates"], seed=bootstrap["seed"],
        confidence_level=bootstrap["confidenceLevel"],
    )
    primary["minimumEffect"] = analysis["primary"]["minimumEffect"]
    primary["gatePassed"] = (primary["estimate"] >= analysis["primary"]["minimumEffect"]
                             and primary["oneSided95Lower"] > 0)
    secondary = []
    for index, comparator in enumerate(analysis["secondaryComparators"]):
        row = paired_binary_analysis(
            trials, treatment="selected_context", comparator=comparator,
            outcome="firstPassBriefFulfilment", model_families=families,
            replicates=bootstrap["replicates"], seed=bootstrap["seed"] + index + 1,
            confidence_level=bootstrap["confidenceLevel"],
        )
        secondary.append(row)
    adjusted = holm_adjust({row["comparator"]: row["oneSidedPValueAtZero"]
                            for row in secondary}) if secondary else {}
    for row in secondary:
        row["holmAdjustedPValue"] = adjusted[row["comparator"]]
        row["holmSignificant"] = row["holmAdjustedPValue"] <= analysis["primary"]["alpha"]
    token_efficiency = first_call_prompt_token_analysis(
        trials, treatment=analysis["h2"]["treatment"], comparator=analysis["h2"]["comparator"])
    h2_plan = analysis["h2"]
    h2_brief = paired_binary_analysis(
        trials, treatment=h2_plan["treatment"], comparator=h2_plan["comparator"],
        outcome="firstPassBriefFulfilment", model_families=families,
        replicates=bootstrap["replicates"], seed=bootstrap["seed"] + 101,
        confidence_level=bootstrap["confidenceLevel"])
    h2_contract = paired_binary_analysis(
        trials, treatment=h2_plan["treatment"], comparator=h2_plan["comparator"],
        outcome="firstPassAgentContractConformance", model_families=families,
        replicates=bootstrap["replicates"], seed=bootstrap["seed"] + 102,
        confidence_level=bootstrap["confidenceLevel"])
    h2_source = paired_numeric_analysis(
        trials, treatment=h2_plan["treatment"], comparator=h2_plan["comparator"],
        metric="firstPassSourceFactCoverage", model_families=families,
        replicates=bootstrap["replicates"], seed=bootstrap["seed"] + 103,
        confidence_level=bootstrap["confidenceLevel"])
    noninferiority = {}
    for name, row, margin in (
            ("briefFulfilment", h2_brief, h2_plan["briefMargin"]),
            ("agentContractConformance", h2_contract, h2_plan["contractMargin"]),
            ("sourceFactCoverage", h2_source, h2_plan["sourceFactMargin"])):
        noninferiority[name] = {"estimate": row["estimate"],
                                "confidenceInterval": row["confidenceInterval"],
                                "oneSided95Lower": row["oneSided95Lower"],
                                "margin": margin,
                                "passed": row["oneSided95Lower"] >= -margin}
    design_result = None
    review_status = "not-sealed"
    if review_set is not None:
        review_set = validate_review_set(review_set)
        if review_set["declarationSha256"] != digest(declaration) \
                or review_set["runId"] != precommit["runId"]:
            raise StudyError("review set differs from this run or declaration")
        review_status = "passed" if review_set["agreementGatePassed"] else "agreement-below-threshold"
        design_trials = [{"condition": row["condition"],
                          "requestedModel": row["requestedModel"],
                          "caseId": row["caseId"], "repetition": row["repetition"],
                          "metrics": {"reviewOverall": row["meanScores"]["overall"]}}
                         for row in review_set["artifactScores"]
                         if row["condition"] in {h2_plan["treatment"], h2_plan["comparator"]}]
        design_pair = paired_numeric_analysis(
            design_trials, treatment=h2_plan["treatment"], comparator=h2_plan["comparator"],
            metric="reviewOverall", model_families=families,
            replicates=bootstrap["replicates"], seed=bootstrap["seed"] + 104,
            confidence_level=bootstrap["confidenceLevel"])
        design_result = {"estimate": design_pair["estimate"],
                         "confidenceInterval": design_pair["confidenceInterval"],
                         "oneSided95Lower": design_pair["oneSided95Lower"],
                         "margin": h2_plan["designMargin"],
                         "passed": design_pair["oneSided95Lower"] >= -h2_plan["designMargin"],
                         "method": "paired failure-aware artifact mean across three reviewers"}
    noninferiority["designerOverall"] = design_result
    token_gate = token_efficiency["meanRatio"] <= h2_plan["maximumTokenRatio"]
    token_efficiency["maximumRatio"] = h2_plan["maximumTokenRatio"]
    token_efficiency["gatePassed"] = token_gate
    mechanical_h2_gate = token_gate and all(noninferiority[name]["passed"] for name in
                                            ("briefFulfilment", "agentContractConformance",
                                             "sourceFactCoverage"))
    h2 = {"tokenEfficiency": token_efficiency, "nonInferiority": noninferiority,
          "mechanicalGatePassed": mechanical_h2_gate,
          "fullGatePassed": (mechanical_h2_gate and design_result["passed"]
                             if design_result is not None else None)}
    result = {
        "schemaVersion": VERSION, "studyId": declaration["studyId"],
        "runId": precommit["runId"], "declarationSha256": digest(declaration),
        "status": "complete" if review_status == "passed" else "mechanical-analysis-complete",
        "primary": primary, "secondary": secondary, "h2": h2,
        "reviewStatus": review_status,
        "claimGatePassed": primary["gatePassed"] and review_status == "passed",
        "limitations": [
            "Inference is limited to the declared routes, held-out Schedule fixtures, release, and dates.",
            "Provider and renderer failures remain scored as failures in the scheduled denominator.",
        ],
    }
    validate_analysis_result(result)
    return result


def validate_analysis_result(value: Any) -> dict[str, Any]:
    result = _exact(value, {
        "schemaVersion", "studyId", "runId", "declarationSha256", "status", "primary",
        "secondary", "h2", "reviewStatus", "claimGatePassed", "limitations",
    }, "analysis result")
    if result["schemaVersion"] != VERSION or result["status"] not in {
            "complete", "mechanical-analysis-complete"}:
        raise StudyError("invalid analysis-result identity")
    _identifier(result["studyId"], "analysis result.studyId")
    if not isinstance(result["declarationSha256"], str) \
            or not HEX64.fullmatch(result["declarationSha256"]):
        raise StudyError("analysis result declaration digest must be SHA-256")
    if type(result["claimGatePassed"]) is not bool:
        raise StudyError("analysis result claim gate must be boolean")
    if result["reviewStatus"] not in {"passed", "not-sealed", "agreement-below-threshold"}:
        raise StudyError("invalid analysis review status")
    _validate_paired_result(result["primary"], primary=True)
    if not isinstance(result["secondary"], list):
        raise StudyError("analysis result secondary contrasts must be an array")
    for row in result["secondary"]:
        _validate_paired_result(row, secondary=True)
    h2 = _exact(result["h2"], {"tokenEfficiency", "nonInferiority",
                                          "mechanicalGatePassed", "fullGatePassed"},
                "analysis result.h2")
    token = _exact(h2["tokenEfficiency"], {"outcome", "pairs", "meanDifference", "meanRatio",
                                                 "maximumRatio", "gatePassed"},
                   "analysis result.h2.tokenEfficiency")
    if token["outcome"] != "firstCallPromptTokens":
        raise StudyError("analysis H2 token outcome is invalid")
    _integer(token["pairs"], "analysis H2 token pairs", 1, 10_000_000)
    _number(token["meanDifference"], "analysis H2 token difference", -1e12, 1e12)
    _number(token["meanRatio"], "analysis H2 token ratio", 0, 1e12)
    if token["maximumRatio"] != .80:
        raise StudyError("analysis H2 maximum token ratio must remain .80")
    if type(token["gatePassed"]) is not bool:
        raise StudyError("analysis H2 token gate must be boolean")
    ni = _exact(h2["nonInferiority"], {"briefFulfilment", "agentContractConformance",
                                      "sourceFactCoverage", "designerOverall"},
                "analysis result.h2.nonInferiority")
    expected_margins = {"briefFulfilment": .05, "agentContractConformance": .05,
                        "sourceFactCoverage": .02}
    for name in ("briefFulfilment", "agentContractConformance", "sourceFactCoverage"):
        row = _exact(ni[name], {"estimate", "confidenceInterval", "oneSided95Lower",
                                "margin", "passed"},
                     f"analysis result.h2.nonInferiority.{name}")
        _number(row["estimate"], f"H2 {name} estimate", -1, 1)
        _validate_interval(row["confidenceInterval"], f"H2 {name} interval")
        _number(row["oneSided95Lower"], f"H2 {name} one-sided lower", -1, 1)
        if row["margin"] != expected_margins[name]:
            raise StudyError(f"H2 {name} margin differs from the frozen declaration")
        if type(row["passed"]) is not bool:
            raise StudyError(f"H2 {name} gate must be boolean")
    design = ni["designerOverall"]
    if design is not None:
        design = _exact(design, {"estimate", "confidenceInterval", "oneSided95Lower",
                                 "margin", "passed", "method"},
                        "analysis result.h2.nonInferiority.designerOverall")
        _number(design["estimate"], "H2 design estimate", -4, 4)
        _validate_interval(design["confidenceInterval"], "H2 design interval")
        _number(design["oneSided95Lower"], "H2 design one-sided lower", -4, 4)
        if design["margin"] != .25:
            raise StudyError("H2 design margin must remain .25")
        if type(design["passed"]) is not bool:
            raise StudyError("H2 design gate must be boolean")
        _string(design["method"], "H2 design method", 1000)
    if type(h2["mechanicalGatePassed"]) is not bool \
            or h2["fullGatePassed"] is not None and type(h2["fullGatePassed"]) is not bool:
        raise StudyError("H2 gate fields are invalid")
    expected_mechanical = token["gatePassed"] and all(
        ni[name]["passed"] for name in
        ("briefFulfilment", "agentContractConformance", "sourceFactCoverage"))
    if h2["mechanicalGatePassed"] != expected_mechanical:
        raise StudyError("H2 mechanical gate is inconsistent with its frozen component gates")
    expected_full = (expected_mechanical and design["passed"] if design is not None else None)
    if h2["fullGatePassed"] != expected_full:
        raise StudyError("H2 full gate is inconsistent with the sealed design result")
    if result["claimGatePassed"] != (result["primary"]["gatePassed"]
                                     and result["reviewStatus"] == "passed"):
        raise StudyError("confirmatory claim gate is inconsistent with H1 and review sealing")
    if not isinstance(result["limitations"], list) or not result["limitations"]:
        raise StudyError("analysis result must state limitations")
    return result


def _validate_interval(value: Any, path: str) -> None:
    interval = _exact(value, {"level", "lower", "upper"}, path)
    if interval["level"] != .95:
        raise StudyError(f"{path}.level must remain .95")
    lower = _number(interval["lower"], f"{path}.lower", -1e12, 1e12)
    upper = _number(interval["upper"], f"{path}.upper", -1e12, 1e12)
    if lower > upper:
        raise StudyError(f"{path} lower bound exceeds its upper bound")


def _validate_paired_result(value: Any, *, primary: bool = False,
                            secondary: bool = False) -> None:
    keys = {"treatment", "comparator", "outcome", "pairs", "estimate",
            "confidenceInterval", "oneSided95Lower", "bootstrap",
            "oneSidedPValueAtZero", "strata"}
    if primary:
        keys.update({"minimumEffect", "gatePassed"})
    if secondary:
        keys.update({"holmAdjustedPValue", "holmSignificant"})
    row = _exact(value, keys, "analysis paired result")
    for field in ("treatment", "comparator", "outcome"):
        _string(row[field], f"analysis paired result.{field}", 240)
    _integer(row["pairs"], "analysis paired result.pairs", 1, 10_000_000)
    _number(row["estimate"], "analysis paired result.estimate", -1, 1)
    _validate_interval(row["confidenceInterval"], "analysis paired result.confidenceInterval")
    _number(row["oneSided95Lower"], "analysis paired result.oneSided95Lower", -1, 1)
    bootstrap = _exact(row["bootstrap"], {"method", "replicates", "seed"},
                       "analysis paired result.bootstrap")
    if bootstrap["method"] != "paired-stratified-model-case-v1":
        raise StudyError("analysis result uses an unsupported bootstrap")
    if bootstrap["replicates"] != 20_000:
        raise StudyError("confirmatory analysis must retain exactly 20,000 bootstrap resamples")
    _integer(bootstrap["seed"], "analysis bootstrap seed", 0, 2**63 - 1)
    _number(row["oneSidedPValueAtZero"], "analysis paired p value", 0, 1)
    strata = _exact(row["strata"], {"models", "families"}, "analysis paired result.strata")
    for kind, identity_fields in (("models", ("modelId", "modelFamily")),
                                  ("families", ("modelFamily",))):
        if not isinstance(strata[kind], list) or not strata[kind]:
            raise StudyError(f"analysis {kind} strata are required")
        for item in strata[kind]:
            expected = {*identity_fields, "pairs", "estimate"}
            item = _exact(item, expected, f"analysis {kind} stratum")
            for field in identity_fields:
                _string(item[field], f"analysis {kind} {field}", 240)
            _integer(item["pairs"], f"analysis {kind} pairs", 1, 10_000_000)
            _number(item["estimate"], f"analysis {kind} estimate", -1, 1)
    if primary:
        if row["minimumEffect"] != .10:
            raise StudyError("analysis primary minimum effect must remain .10")
        if type(row["gatePassed"]) is not bool:
            raise StudyError("analysis primary gate must be boolean")
    if secondary:
        _number(row["holmAdjustedPValue"], "analysis Holm p value", 0, 1)
        if type(row["holmSignificant"]) is not bool:
            raise StudyError("analysis Holm gate must be boolean")


def _assert_declared_trials(trials: list[dict[str, Any]], declaration: dict[str, Any]) -> None:
    conditions = set(declaration["conditions"])
    fixtures = {fixture["id"] for fixture in declaration["fixtures"]}
    models = {route["modelId"] for route in declaration["routes"]}
    seen: set[tuple[str, str, str, int]] = set()
    for trial in trials:
        condition = trial.get("condition")
        model = trial.get("requestedModel")
        case = trial.get("caseId")
        repetition = trial.get("repetition")
        if condition not in conditions or case not in fixtures or type(repetition) is not int \
                or not 0 <= repetition < declaration["repetitions"]:
            raise StudyError("trial contains an undeclared condition, fixture, or repetition")
        if condition == "deterministic_component":
            if model != "deterministic_component":
                raise StudyError("deterministic reference has an invalid model identity")
        elif model not in models:
            raise StudyError("trial contains an undeclared model route")
        identity = (condition, model, case, repetition)
        if identity in seen:
            raise StudyError("duplicate trial identity in retained run")
        seen.add(identity)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise StudyError(f"blank JSONL record at line {line_number}")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise StudyError(f"invalid JSONL record at line {line_number}") from error
        if not isinstance(value, dict):
            raise StudyError(f"JSONL record {line_number} is not an object")
        records.append(value)
    return records


def verify_publication_safe(directory: Path) -> dict[str, Any]:
    """Fail on links, secrets, account fields, absolute private paths, or manifest drift."""
    root = directory.resolve()
    if not root.is_dir():
        raise StudyError("publication bundle must be a directory")
    files = []
    findings = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            findings.append({"file": str(path.relative_to(directory)), "code": "symlink"})
            continue
        if not path.is_file():
            continue
        relative = path.relative_to(directory)
        data = path.read_bytes()
        for pattern in SECRET_PATTERNS:
            if pattern.search(data):
                findings.append({"file": str(relative), "code": "credential-pattern"})
        for pattern in ABSOLUTE_PATH_PATTERNS:
            if pattern.search(data):
                findings.append({"file": str(relative), "code": "absolute-private-path"})
        if path.suffix in {".json", ".jsonl"}:
            _scan_private_json_fields(path, data, findings, relative)
        files.append({"path": str(relative), "sha256": digest(data), "bytes": len(data)})
    if findings:
        raise StudyError("publication bundle contains unsafe retained data: "
                         + canonical(findings[:20]))
    manifest_path = directory / "publication-manifest.json"
    if manifest_path.exists():
        manifest = validate_publication_manifest(read_json(manifest_path))
        actual = [item for item in files if item["path"] != "publication-manifest.json"]
        actual.sort(key=lambda item: item["path"])
        if manifest["files"] != actual:
            raise StudyError("publication manifest differs from retained files")
    return {"schemaVersion": VERSION, "status": "safe", "files": len(files),
            "bytes": sum(item["bytes"] for item in files), "findings": []}


def _scan_private_json_fields(path: Path, data: bytes, findings: list[dict[str, str]],
                              relative: Path) -> None:
    records: Iterable[Any]
    try:
        if path.suffix == ".jsonl":
            records = [json.loads(line) for line in data.decode("utf-8").splitlines() if line]
        else:
            records = [json.loads(data)]
    except (UnicodeError, json.JSONDecodeError):
        findings.append({"file": str(relative), "code": "invalid-json"})
        return
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = str(key).casefold().replace("-", "_")
                private = normalized in PRIVATE_JSON_KEYS or normalized.endswith(
                    ("_user_id", "_account_id", "_organization_id", "_customer_id"))
                if private and item is not None and item != "[REDACTED]":
                    findings.append({"file": str(relative), "code": "private-json-field"})
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for record in records:
        if (path.name == "provider-response.json" and isinstance(record, dict)
                and record.get("id") not in {None, "[REDACTED]"}):
            findings.append({"file": str(relative), "code": "provider-response-id"})
        visit(record)


def create_publication_bundle(source: Path, destination: Path, *,
                              include_unblinding_key: bool = False) -> dict[str, Any]:
    if destination.exists():
        raise StudyError("publication destination already exists")
    if not (source / "results.json").is_file() or not (source / "precommit.json").is_file():
        raise StudyError("source is not a completed evaluation run")
    excluded_names = {"publication-manifest.json"}
    if not include_unblinding_key:
        excluded_names.add("designer-review-key.json")
    destination.mkdir(parents=True)
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise StudyError("publication source contains a symlink")
        if not path.is_file() or path.name in excluded_names:
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        if path.suffix in {".json", ".jsonl"}:
            data = _sanitized_retained_json(relative, data)
        target.write_bytes(data)
    journal_path = destination / "cell-journal.json"
    if journal_path.is_file():
        journal = read_json(journal_path)
        ordered_trials = []
        for entry in journal.get("cells", []):
            if entry.get("status") != "complete":
                continue
            trial_path = destination / "trials" / entry["trialId"] / "trial.json"
            trial = read_json(trial_path)
            entry["trialSha256"] = digest(trial)
            ordered_trials.append(trial)
        _write_json(journal_path, journal)
        trials_path = destination / "trials.jsonl"
        with trials_path.open("w", encoding="utf-8") as stream:
            for trial in ordered_trials:
                stream.write(canonical(trial) + "\n")
    copied = [{"path": str(path.relative_to(destination)),
               "sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}
              for path in sorted(destination.rglob("*")) if path.is_file()]
    copied.sort(key=lambda item: item["path"])
    manifest = {"schemaVersion": VERSION, "sourceRunId": read_json(source / "results.json")["runId"],
                "unblindingKeyIncluded": include_unblinding_key, "files": copied}
    validate_publication_manifest(manifest)
    _write_json(destination / "publication-manifest.json", manifest, exclusive=True)
    verify_publication_safe(destination)
    return manifest


def _sanitized_retained_json(relative: Path, data: bytes) -> bytes:
    def clean(value: Any, *, provider_root: bool = False) -> Any:
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                normalized = str(key).casefold().replace("-", "_")
                private = normalized in PRIVATE_JSON_KEYS or normalized.endswith(
                    ("_user_id", "_account_id", "_organization_id", "_customer_id"))
                if private or (provider_root and key == "id"):
                    result[key] = None if item is None else "[REDACTED]"
                else:
                    result[key] = clean(item)
            return result
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value
    try:
        if relative.suffix == ".jsonl":
            records = [json.loads(line) for line in data.decode("utf-8").splitlines() if line]
            return ("".join(canonical(clean(record)) + "\n" for record in records)).encode("utf-8")
        record = json.loads(data)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise StudyError(f"cannot sanitize invalid retained JSON: {relative}") from error
    cleaned = clean(record, provider_root=relative.name == "provider-response.json")
    return (json.dumps(cleaned, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")


def validate_publication_manifest(value: Any) -> dict[str, Any]:
    manifest = _exact(value, {"schemaVersion", "sourceRunId", "unblindingKeyIncluded", "files"},
                      "publication manifest")
    if manifest["schemaVersion"] != VERSION or type(manifest["unblindingKeyIncluded"]) is not bool:
        raise StudyError("invalid publication manifest identity")
    _string(manifest["sourceRunId"], "publication manifest.sourceRunId", 240)
    if not isinstance(manifest["files"], list):
        raise StudyError("publication manifest files must be an array")
    paths = []
    for index, item in enumerate(manifest["files"]):
        item = _exact(item, {"path", "sha256", "bytes"}, f"publication files[{index}]")
        path = item["path"]
        if not isinstance(path, str) or path.startswith("/") or ".." in Path(path).parts:
            raise StudyError("publication manifest contains an unsafe path")
        if not isinstance(item["sha256"], str) or not HEX64.fullmatch(item["sha256"]):
            raise StudyError("publication file digest must be SHA-256")
        _integer(item["bytes"], "publication file bytes", 0, 1_000_000_000)
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise StudyError("publication manifest paths must be sorted and unique")
    return manifest


def _write_json(path: Path, value: Any, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    with path.open(mode, encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
