"""Shared best-so-far acceptance policy for bounded artifact repair."""
from __future__ import annotations

import hashlib
import json

from .schema import load_schema, validate


VERSION = "0.2.0"
CONTRACT_RULES = {"plan.valid", "html.structure", "html.self_contained", "move.semantics",
                  "render.binding", "render.viewport_fit", "render.semantics",
                  "instrument.invariant_band", "render.screenshot"}
BRIEF_RULES = {"facts.unique", "facts.exact", "facts.approved_text", "render.facts"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finding_id(finding):
    return _digest({key: finding[key] for key in
                    ("ruleId", "severity", "status", "location", "expected", "observed",
                     "classification")})


def _critical_error_identity(finding):
    return f"{finding['severity']}:{finding['ruleId']}:{finding['location']}"


def classified_finding(finding):
    """Add a cited observable instruction to one already-classified finding."""
    classification = finding["classification"]
    expected = _canonical(finding["expected"])[:500]
    if classification == "safe-model-repair":
        instruction = (f"Fix [{finding['ruleId']}] at {finding['location']}; the expected "
                       f"observable is {expected}. Preserve every other checked fact and relationship.")
    elif classification == "renderer-or-configuration":
        instruction = (f"Resolve renderer or evidence configuration for [{finding['ruleId']}] at "
                       f"{finding['location']}; the expected observable is {expected}.")
    elif classification == "human-decision":
        instruction = (f"Route [{finding['ruleId']}] at {finding['location']} to a human decision; "
                       f"the expected decision target is {expected}.")
    else:
        instruction = (f"Stop automated repair for [{finding['ruleId']}] at {finding['location']}; "
                       f"the expected observable is {expected}.")
    return {"findingId": _finding_id(finding), "classification": classification,
            "ruleId": finding["ruleId"], "severity": finding["severity"],
            "status": finding["status"], "location": finding["location"],
            "expected": finding["expected"], "observed": finding["observed"],
            "instruction": instruction}


def _rule_pass(report, rule):
    findings = [item for item in report["findings"] if item["ruleId"] == rule]
    return bool(findings) and all(item["status"] == "pass" for item in findings)


def _fresh_evidence(report):
    return _rule_pass(report, "render.binding")


def _coverage_bps(preserved, total):
    return (10_000 * preserved) // total if total else 0


def snapshot_for(plan, report):
    """Create the frozen acceptance metrics and protected-state snapshot."""
    nonpassing = [item for item in report["findings"] if item["status"] != "pass"]
    source_failures = sorted({item["location"] for item in nonpassing
                              if item["status"] == "fail"
                              and item["ruleId"] in ("facts.unique", "facts.exact")
                              and item["location"] not in ("artifact", "body")})
    visible_failures = sorted({item["location"] for item in nonpassing
                               if item["status"] == "fail" and item["ruleId"] == "render.facts"})
    relationship_failures = sorted({f"{item['ruleId']}:{item['location']}"
                                    for item in nonpassing
                                    if item["ruleId"] in ("move.semantics", "render.semantics")})
    critical_error = sorted({_critical_error_identity(item) for item in nonpassing
                             if item["status"] == "fail"
                             and item["severity"] in ("critical", "error")})
    planned = len(plan["facts"])
    source_lost = {location for location in source_failures
                   if any(fact["id"] == location for fact in plan["facts"])}
    source_preserved = max(0, planned - len(source_lost))
    visible = []
    for viewport in plan["artifact"]["viewports"]:
        location = f"viewport:{viewport['width']}x{viewport['height']}"
        observed = [item for item in report["findings"]
                    if item["ruleId"] == "render.facts"
                    and (item["location"] == location or item["location"].startswith(location + "/"))]
        lost = {item["location"].split("/", 1)[1] for item in observed
                if item["status"] == "fail" and "/" in item["location"]
                and any(fact["id"] == item["location"].split("/", 1)[1]
                        for fact in plan["facts"])}
        complete = bool(observed) and all(item["status"] != "unknown" for item in observed)
        preserved = max(0, planned - len(lost)) if complete else 0
        visible.append({"viewport": location, "preserved": preserved, "total": planned,
                        "basisPoints": _coverage_bps(preserved, planned)})
    minimum_visible = min(item["basisPoints"] for item in visible)
    static_coverage = _coverage_bps(source_preserved, planned)
    total_contract_facts = planned * (1 + len(visible))
    preserved_contract_facts = source_preserved + sum(item["preserved"] for item in visible)
    contract_fact_coverage = _coverage_bps(preserved_contract_facts, total_contract_facts)
    severity = {
        "critical": sum(item["status"] == "fail" and item["severity"] == "critical"
                        for item in nonpassing),
        "error": sum(item["status"] == "fail" and item["severity"] == "error"
                     for item in nonpassing),
        "warning": sum(item["status"] == "fail" and item["severity"] == "warning"
                       for item in nonpassing),
        "unknown": sum(item["status"] == "unknown" for item in nonpassing),
    }
    contract_pass = all(_rule_pass(report, rule) for rule in CONTRACT_RULES)
    brief_pass = all(_rule_pass(report, rule) for rule in BRIEF_RULES)
    # Lower is better. This is the frozen order; no hidden tiebreaker follows unknown count.
    key = [0 if contract_pass else 1, 0 if brief_pass else 1,
           10_000 - minimum_visible, 10_000 - static_coverage,
           10_000 - contract_fact_coverage, severity["critical"], severity["error"],
           severity["warning"], severity["unknown"]]
    return {"artifactSha256": report["artifactSha256"], "reportSha256": _digest(report),
            "status": report["status"], "freshEvidence": _fresh_evidence(report),
            "protected": {"plannedFacts": planned, "sourceFailures": source_failures,
                          "visibleFailures": visible_failures,
                          "requiredRelationships": len(plan["requiredRelationships"]),
                          "relationshipFailures": relationship_failures,
                          "criticalErrorFindings": critical_error},
            "acceptanceMetrics": {"contractPass": contract_pass, "briefPass": brief_pass,
                                  "visibleFactCoverage": visible,
                                  "minimumVisibleFactCoverageBps": minimum_visible,
                                  "staticCoverageBps": static_coverage,
                                  "contractFactCoverageBps": contract_fact_coverage,
                                  "severityCounts": severity},
            "findingFingerprints": sorted(_finding_id(item) for item in nonpassing),
            "selectionKey": key}


def strict_regressions(best, candidate):
    """Return every frozen safety regression versus the retained best snapshot."""
    reasons = []
    best_metrics, candidate_metrics = best["acceptanceMetrics"], candidate["acceptanceMetrics"]
    if best_metrics["contractPass"] and not candidate_metrics["contractPass"]:
        reasons.append("candidate loses contract pass")
    if best_metrics["briefPass"] and not candidate_metrics["briefPass"]:
        reasons.append("candidate loses brief pass")
    for field, label in (("sourceFailures", "source fact"),
                         ("visibleFailures", "visible fact"),
                         ("relationshipFailures", "relationship"),
                         ("criticalErrorFindings", "critical/error finding")):
        new = sorted(set(candidate["protected"][field]) - set(best["protected"][field]))
        for identifier in new:
            reasons.append(f"candidate introduces protected {label} failure: {identifier}")
    return reasons


def _validated_history(plan, history):
    history = [] if history is None else history
    validate(history, load_schema("history"))
    plan_hash = _digest(plan)
    parent = None
    best_record = None
    repair_attempt = 0
    fresh_artifacts = set()
    finding_sets = []
    previous_action = None
    accepted_dispositions = {"baseline", "accepted-improvement", "complete",
                             "stopped-budget", "stopped-non-repairable"}
    for attempt, record in enumerate(history):
        if attempt and previous_action != "repair":
            raise ValueError("repair history continues after a complete or stop decision")
        body = {key: value for key, value in record.items() if key != "recordSha256"}
        if (record["recordSha256"] != _digest(body) or record["planSha256"] != plan_hash
                or record["attempt"] != attempt or record["parentRecordSha256"] != parent
                or record["artifactSha256"] != record["snapshot"]["artifactSha256"]
                or record["reportSha256"] != record["snapshot"]["reportSha256"]
                or record["repairAttempt"] != repair_attempt
                or record["baseArtifactSha256"]
                != (best_record["artifactSha256"] if best_record else None)):
            raise ValueError("repair history is not a valid attempt chain for this immutable plan")
        if record["accepted"] != (record["disposition"] in accepted_dispositions):
            raise ValueError("repair history acceptance and disposition are inconsistent")
        if ((record["disposition"] == "baseline") != (attempt == 0)
                or record["disposition"] == "accepted-improvement" and best_record is None):
            raise ValueError("repair history disposition is impossible at this chain position")
        if record["accepted"]:
            if not record["snapshot"]["freshEvidence"]:
                raise ValueError("repair history cannot accept stale evidence")
            if (best_record is not None
                    and record["snapshot"]["selectionKey"] >= best_record["snapshot"]["selectionKey"]):
                raise ValueError("accepted repair history candidate does not improve the frozen key")
            best_record = record
        if record["bestArtifactSha256"] != (best_record["artifactSha256"] if best_record else None):
            raise ValueError("repair history best-artifact pointer is inconsistent")
        expected_action = ("repair" if record["disposition"] in ("baseline", "accepted-improvement")
                           else "complete" if record["disposition"] == "complete" else "stop")
        if record["nextAction"] != expected_action:
            raise ValueError("repair history action and disposition are inconsistent")
        if record["snapshot"]["freshEvidence"]:
            fresh_artifacts.add(record["artifactSha256"])
            if record["snapshot"]["findingFingerprints"]:
                finding_sets.append(record["snapshot"]["findingFingerprints"])
        if record["nextAction"] == "repair":
            repair_attempt += 1
        previous_action = record["nextAction"]
        parent = record["recordSha256"]
    if history and previous_action != "repair":
        raise ValueError("repair history cannot authorize another automated attempt")
    if repair_attempt > plan["maxRepairTurns"]:
        raise ValueError("repair history exceeds the immutable repair budget")
    return history, plan_hash, parent, best_record, repair_attempt, fresh_artifacts, finding_sets


def _record(plan_hash, parent, attempt, repair_attempt, base_hash, snapshot, disposition,
            accepted, best_hash, action):
    record = {"schemaVersion": VERSION, "planSha256": plan_hash,
              "artifactSha256": snapshot["artifactSha256"],
              "reportSha256": snapshot["reportSha256"],
              "parentRecordSha256": parent, "attempt": attempt,
              "repairAttempt": repair_attempt, "baseArtifactSha256": base_hash,
              "disposition": disposition, "accepted": accepted,
              "bestArtifactSha256": best_hash, "nextAction": action, "snapshot": snapshot}
    record["recordSha256"] = _digest(record)
    return record


def prepare_repair_decision(plan, html, report, history=None):
    """Evaluate and retain one attempt; another repair always starts from best accepted."""
    validate(report, load_schema("report"))
    if (not isinstance(html, str) or report["artifactSha256"] is None
            or hashlib.sha256(html.encode("utf-8")).hexdigest() != report["artifactSha256"]):
        raise ValueError("repair report is not bound to the supplied artifact bytes")
    (history, plan_hash, parent, best_record, repair_attempt,
     fresh_artifacts, finding_sets) = _validated_history(plan, history)
    snapshot = snapshot_for(plan, report)
    classified = [classified_finding(item) for item in report["findings"]
                  if item["status"] != "pass"]
    failed_classes = {item["classification"] for item in classified if item["status"] == "fail"}
    base_hash = best_record["artifactSha256"] if best_record else None
    best_hash = base_hash
    accepted = False
    rollback = None

    if not snapshot["freshEvidence"]:
        action, disposition = "stop", "stopped-stale-evidence"
        reasons = ["Fresh hash-bound render evidence is required; automated repair stops without accepting this attempt."]
        rollback = best_hash
    elif snapshot["artifactSha256"] in fresh_artifacts:
        action, disposition = "stop", "rejected-oscillation"
        reasons = ["The attempt repeats an earlier fresh artifact hash; repair has oscillated or made no byte change."]
        rollback = best_hash
    elif snapshot["findingFingerprints"] and snapshot["findingFingerprints"] in finding_sets:
        action, disposition = "stop", "rejected-repeated-findings"
        reasons = ["The attempt repeats an earlier complete finding fingerprint set; automated repair stops."]
        rollback = best_hash
    elif best_record is not None:
        regressions = strict_regressions(best_record["snapshot"], snapshot)
        if regressions:
            action, disposition, reasons = "stop", "rejected-regression", regressions
            rollback = best_hash
        elif snapshot["selectionKey"] == best_record["snapshot"]["selectionKey"]:
            action, disposition = "stop", "rejected-tie"
            reasons = ["The attempt ties the retained best on every frozen acceptance metric."]
            rollback = best_hash
        elif snapshot["selectionKey"] > best_record["snapshot"]["selectionKey"]:
            action, disposition = "stop", "rejected-non-improving"
            reasons = ["The attempt is lexicographically worse than the retained best artifact."]
            rollback = best_hash
        else:
            accepted = True; best_hash = snapshot["artifactSha256"]
            if report["status"] == "pass":
                action, disposition = "complete", "complete"
                reasons = ["All checks pass with fresh evidence and every frozen acceptance metric is safe."]
            elif failed_classes & {"non-repairable", "human-decision", "renderer-or-configuration"}:
                action, disposition = "stop", "stopped-non-repairable"
                reasons = ["At least one failed finding requires configuration, a human decision, or a non-automated remedy."]
            elif repair_attempt >= plan["maxRepairTurns"]:
                action, disposition = "stop", "stopped-budget"
                reasons = ["The accepted best attempt still fails after the two-attempt repair budget."]
            else:
                action, disposition = "repair", "accepted-improvement"
                reasons = ["The attempt improves the frozen key and preserves protected facts and relationships."]
    else:
        accepted = True; best_hash = snapshot["artifactSha256"]
        if report["status"] == "pass":
            action, disposition = "complete", "complete"
            reasons = ["The fresh baseline passes every check."]
        elif failed_classes & {"non-repairable", "human-decision", "renderer-or-configuration"}:
            action, disposition = "stop", "stopped-non-repairable"
            reasons = ["The fresh baseline contains a finding outside safe automated repair."]
        elif repair_attempt >= plan["maxRepairTurns"]:
            action, disposition = "stop", "stopped-budget"
            reasons = ["No repair budget remains."]
        else:
            action, disposition = "repair", "baseline"
            reasons = ["The fresh baseline is retained as the initial best artifact for bounded repair."]

    if action == "repair":
        safe = [item["instruction"] for item in classified
                if item["status"] == "fail" and item["classification"] == "safe-model-repair"]
        instructions = [
            "Start from bestArtifactSha256, never from the most recent rejected attempt.",
            "Keep the immutable plan, discriminated content, binding, facts and relationships unchanged.",
            *safe,
            "Archive the current artifact, evidence and record before editing; append every attempt to history.",
            "Re-render changed bytes and submit fresh hash-bound evidence; never reuse evidence after an edit.",
        ]
    else:
        instructions = []
    record = _record(plan_hash, parent, len(history), repair_attempt, base_hash, snapshot,
                     disposition, accepted, best_hash, action)
    result = {"schemaVersion": VERSION, "action": action, "disposition": disposition,
              "report": report, "record": record,
              "remainingRepairs": max(0, plan["maxRepairTurns"] - repair_attempt),
              "bestArtifactSha256": best_hash,
              "nextRepairBaseArtifactSha256": best_hash if action == "repair" else None,
              "rollbackArtifactSha256": rollback,
              "reasons": reasons, "classifiedFindings": classified,
              "instructions": instructions}
    validate(result, load_schema("repair"))
    return result
