#!/usr/bin/env python3
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.openrouter import OpenRouterProvider
from evaluation.study import (
    CellJournal, SpendLedger, StudyError, analyze_confirmatory, canonical,
    confirmatory_blockers, create_publication_bundle, digest, holm_adjust,
    development_plan_blockers,
    exploratory_h3_gate, krippendorff_alpha_ordinal, paired_binary_analysis,
    plan_paired_power,
    seal_review_set, validate_analysis_result, validate_declaration,
    validate_development_plan, validate_spend_ledger, verify_publication_safe,
)


def declaration_and_receipt():
    snapshot = {"provider": "openrouter", "count": 6, "models": [
        {"id": f"maker/model-{index}", "canonicalSlug": f"maker/model-{index}-v1",
         "pricing": {"prompt": ".000001", "completion": ".000002"},
         "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}}
        for index in range(6)
    ]}
    snapshot_sha = digest(snapshot)
    routes = []
    qualification_hashes = {}
    ledger_entries = []
    for index in range(6):
        route_id = f"route-{index}"
        receipt_sha = str(index + 1) * 64
        qualification_hashes[route_id] = receipt_sha
        reservation_ids = [f"qual-{index}-{call}" for call in range(10)]
        for reservation_id in reservation_ids:
            ledger_entries.append({
                "reservationId": reservation_id, "stage": "qualification",
                "reservedGbp": .01, "chargedGbp": 0, "status": "settled",
                "providerReportedCostUsd": 0, "usdToGbpRate": .8,
                "reservedAt": "2026-09-12T09:00:00Z",
                "settledAt": "2026-09-12T09:01:00Z",
            })
        routes.append({
            "routeId": route_id, "modelId": f"maker/model-{index}",
            "modelFamily": f"family-{index // 2}",
            "provider": "openrouter", "endpointPolicy": "pinned",
            "underlyingProvider": f"provider-{index}",
            "providerDisplayName": f"Provider {index}", "snapshotSha256": snapshot_sha,
            "qualification": {"schemaVersion": "0.5.0", "routeId": route_id,
                              "qualifiedAt": "2026-09-12T10:00:00Z",
                              "expiresAt": "2099-09-12T10:00:00Z",
                              "receiptSha256": receipt_sha,
                              "observations": {"calls": 10, "timeBlocks": 2,
                                  "successes": 10, "successRate": 1,
                                  "acceptedIdentities": 10, "acceptedIdentityRate": 1,
                                  "textOutputs": 10, "textOutput": True,
                                  "providerPinMatches": 10, "providerPinned": True,
                                  "parameterAcceptances": 10, "parametersAccepted": True,
                                  "reservationIds": reservation_ids}},
        })
    ledger = {"schemaVersion": "0.5.0", "ledgerId": "evaluation-ledger",
              "currency": "GBP", "capGbp": 500, "automaticTopUp": False,
              "scope": ["qualification", "development", "confirmatory"],
              "createdAt": "2026-09-12T08:00:00Z", "entries": ledger_entries}
    power = plan_paired_power(
        baseline_rate=.55, treatment_rate=.70, within_pair_correlation=.4,
        alpha=.05, power=.9, routes=6, fixtures=8, minimum_repetitions=5,
        maximum_repetitions=50, estimated_cost_per_cell_gbp=.1,
        conditions=5, maximum_budget_gbp=500, simulations=10000, seed=7)
    declaration = {
        "schemaVersion": "0.5.0", "studyId": "schedule-rc-1",
        "protocolVersion": "0.5.0", "studyMode": "confirmatory",
        "createdAt": "2026-09-12T11:00:00Z", "releaseCommit": "a" * 40,
        "split": "held-out",
        "conditions": ["raw_brief", "brand_bible", "scaffolded_html",
                       "selected_context", "full_rules"],
        "fixtures": [{"id": f"held-case-{index}", "sha256": "f" * 64}
                     for index in range(8)],
        "routes": routes, "repetitions": power["repetitionsPerRouteFixture"],
        "generation": {"maxTokens": 6000, "temperature": 0,
                       "reasoningEffort": "none", "maxRepairs": 0,
                       "worstCaseCallCostGbp": .1, "usdToGbpRate": .8,
                       "automaticTopUp": False},
        "randomization": {"strategy": "blocked-case-repetition-shuffle-v1", "seed": 91},
        "analysis": {
            "primary": {"hypothesis": "H1", "treatment": "selected_context",
                        "comparator": "scaffolded_html",
                        "outcome": "firstPassBriefFulfilment",
                        "minimumEffect": .1, "alpha": .05, "power": .9},
            "secondaryComparators": ["raw_brief", "brand_bible"],
            "h2": {"treatment": "selected_context", "comparator": "full_rules",
                   "tokenOutcome": "firstCallPromptTokens", "briefMargin": .05,
                   "contractMargin": .05, "sourceFactMargin": .02, "designMargin": .25,
                   "maximumTokenRatio": .8},
            "bootstrap": {"method": "paired-stratified-model-case-v1",
                          "replicates": 20000, "seed": 92, "confidenceLevel": .95},
            "powerPlan": {"method": power["method"], "baselineRate": .55,
                          "treatmentRate": .70, "withinPairCorrelation": .4,
                          "estimatedCostPerCellGbp": .1,
                          "requiredPairs": power["requiredPairs"],
                          "selectedRepetitions": power["repetitionsPerRouteFixture"],
                          "estimatedBudgetGbp": power["estimatedBudgetGbp"],
                          "estimatedPower": power["estimatedPower"],
                          "simulationCount": 10000, "simulationSeed": 7},
            "multiplicity": "holm-secondary-h1",
            "missingData": "scheduled-failure-zero; missing-cell-blocks-analysis",
        },
        "review": {"attemptPolicy": "first-pass-for-H1",
                   "reviewerIds": ["designer-a", "designer-b", "designer-c"],
                   "minimumReviewers": 3,
                   "agreementStatistic": "krippendorff-alpha-ordinal",
                   "agreementThreshold": .67, "missingArtifactScore": 1,
                   "missingRatingPolicy": "block-analysis",
                   "reviewerSelection": "Independent practising designers selected before unblinding.",
                   "conflicts": [], "independentReviewers": True,
                   "selectedRepetition": 0},
        "budget": {"currency": "GBP", "maximum": 500},
        "renderer": {"identitySha256": "e" * 64},
        "protocolFiles": {"evaluation/harness.py": "d" * 64},
    }
    receipt = {
        "schemaVersion": "0.5.0", "receiptId": "freeze-1",
        "studyId": declaration["studyId"], "declarationSha256": digest(declaration),
        "frozenAt": "2026-09-12T12:00:00Z",
        "custodian": {"name": "External protocol custodian",
                      "organization": "Independent methods office", "independent": True},
        "timestamp": {"method": "human-countersignature",
                      "url": "https://example.test/immutable/freeze-1",
                      "evidenceSha256": "b" * 64},
        "signature": {"method": "human-countersignature-sha256", "keyId": "custodian-1",
                      "value": "retained-countersignature", "signedBytesSha256": digest(declaration),
                      "locallyVerified": True},
        "releaseCommit": declaration["releaseCommit"],
        "modelSnapshotSha256": snapshot_sha,
        "routeQualificationSha256": qualification_hashes,
        "reviewerCommitments": declaration["review"]["reviewerIds"],
        "budgetApproved": True, "budgetMaximum": 500, "executionAuthorized": True,
        "spendLedgerPreRunSha256": digest(ledger),
    }
    return declaration, receipt, snapshot, ledger


def binary_trials():
    trials = []
    values = {
        ("m1", "c1"): (True, False),
        ("m1", "c2"): (True, True),
        ("m2", "c1"): (False, False),
        ("m2", "c2"): (True, False),
    }
    for (model, case), (selected, scaffold) in values.items():
        for condition, value in (("selected_context", selected),
                                 ("scaffolded_html", scaffold)):
            trials.append({"condition": condition, "requestedModel": model,
                           "caseId": case, "repetition": 0,
                           "metrics": {"firstPassBriefFulfilment": value}})
    return trials


def development_plan(declaration):
    return {
        "schemaVersion": "0.5.0", "planId": "schedule-development-1",
        "protocolVersion": "0.5.0", "studyMode": "development",
        "createdAt": "2026-09-12T11:00:00Z",
        "releaseCommit": declaration["releaseCommit"], "split": "dev",
        "conditions": ["raw_brief", "brand_bible", "scaffolded_html",
                       "selected_context", "full_rules"],
        "fixtures": declaration["fixtures"][:6], "routes": declaration["routes"],
        "repetitions": 1,
        "generation": {**declaration["generation"], "maxRepairs": 0},
        "randomization": declaration["randomization"],
        "budget": declaration["budget"], "renderer": declaration["renderer"],
        "protocolFiles": declaration["protocolFiles"],
        "claims": {"status": "disabled",
                   "interpretation": "exploratory-development-only"},
    }


class StudyProtocolTests(unittest.TestCase):
    def test_pinned_development_plan_is_qualified_and_claim_disabled(self):
        declaration, _, snapshot, ledger = declaration_and_receipt()
        plan = development_plan(declaration)
        self.assertEqual(validate_development_plan(plan), plan)
        identity = {"releaseCommit": plan["releaseCommit"],
                    "rendererIdentitySha256": plan["renderer"]["identitySha256"],
                    "protocolFiles": plan["protocolFiles"]}
        self.assertEqual(development_plan_blockers(
            plan, snapshot=snapshot, spend_ledger=ledger, current_identity=identity), [])
        self.assertIn("frozen model snapshot", development_plan_blockers(plan)[0])
        changed = copy.deepcopy(plan)
        changed["claims"]["status"] = "enabled"
        with self.assertRaisesRegex(StudyError, "claims disabled"):
            validate_development_plan(changed)

    def test_declaration_requires_endpoint_slug_and_display_name(self):
        declaration, _, _, _ = declaration_and_receipt()
        changed = copy.deepcopy(declaration)
        del changed["routes"][0]["providerDisplayName"]
        with self.assertRaisesRegex(StudyError, "missing"):
            validate_declaration(changed)

    def test_strict_declaration_and_external_freeze_are_fail_closed(self):
        declaration, receipt, snapshot, ledger = declaration_and_receipt()
        self.assertEqual(validate_declaration(declaration), declaration)
        self.assertEqual(confirmatory_blockers(declaration, receipt, snapshot=snapshot, spend_ledger=ledger), [])
        self.assertIn("externally timestamped", confirmatory_blockers(declaration, None)[0])
        tampered = copy.deepcopy(declaration)
        tampered["unexpected"] = True
        with self.assertRaisesRegex(StudyError, "unexpected"):
            validate_declaration(tampered)
        changed = copy.deepcopy(snapshot)
        changed["count"] = 2
        self.assertTrue(any("snapshot differs" in item
                            for item in confirmatory_blockers(declaration, receipt, snapshot=changed, spend_ledger=ledger)))
        overrun = copy.deepcopy(ledger)
        overrun["entries"][0].update(
            status="actual-exceeded-reservation", providerReportedCostUsd=.02,
            chargedGbp=.016)
        overrun_receipt = copy.deepcopy(receipt)
        overrun_receipt["spendLedgerPreRunSha256"] = digest(overrun)
        self.assertTrue(any("above its frozen reservation" in item for item in
                            confirmatory_blockers(declaration, overrun_receipt,
                                                 snapshot=snapshot, spend_ledger=overrun)))

    def test_route_pin_is_sent_and_wrong_endpoint_fails_integrity(self):
        declaration, _, snapshot, _ = declaration_and_receipt()
        route = declaration["routes"][0]
        provider = OpenRouterProvider(snapshot, key="test-key", reasoning_effort="none",
                                      provider_pins={route["modelId"]: route["underlyingProvider"]},
                                      provider_display_names={
                                          route["modelId"]: route["providerDisplayName"]},
                                      require_zero_price=False)
        response = {"id": "provider-uuid", "model": "maker/model-0-v1",
                    "openrouter_metadata": {"attempts": [{"status": 200,
                                                            "provider": "Provider 0"}]},
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 1,
                              "total_tokens": 3, "cost": 0}}
        with patch("evaluation.openrouter._http_json", return_value=(200, response, 3)) as request:
            result = provider.complete(route["modelId"], [{"role": "user", "content": "x"}],
                                       max_tokens=256, temperature=0)
        self.assertTrue(result.ok)
        sent = request.call_args.args[2]
        self.assertEqual(sent["provider"]["only"], ["provider-0"])
        self.assertFalse(sent["provider"]["allow_fallbacks"])
        self.assertTrue(sent["provider"]["require_parameters"])
        self.assertNotIn("order", sent["provider"])
        self.assertNotIn("models", sent)
        self.assertEqual(result.provider_endpoint, "provider-0")
        wrong = copy.deepcopy(response)
        wrong["openrouter_metadata"]["attempts"][0]["provider"] = "Provider other"
        with patch("evaluation.openrouter._http_json", return_value=(200, wrong, 3)):
            result = provider.complete(route["modelId"], [{"role": "user", "content": "x"}],
                                       max_tokens=256, temperature=0)
        self.assertFalse(result.ok)
        self.assertEqual(result.error["code"], "provider_endpoint_integrity_failure")

    def test_paired_bootstrap_is_deterministic_and_failure_aware(self):
        arguments = dict(treatment="selected_context", comparator="scaffolded_html",
                         outcome="firstPassBriefFulfilment",
                         model_families={"m1": "family-a", "m2": "family-b"},
                         replicates=500, seed=17, confidence_level=.95)
        first = paired_binary_analysis(binary_trials(), **arguments)
        second = paired_binary_analysis(binary_trials(), **arguments)
        self.assertEqual(first, second)
        self.assertEqual(first["pairs"], 4)
        self.assertEqual(first["estimate"], .5)
        incomplete = binary_trials()[:-1]
        with self.assertRaisesRegex(StudyError, "exactly one observation"):
            paired_binary_analysis(incomplete, **arguments)

    def test_power_holm_and_ordinal_agreement_interfaces(self):
        plan = plan_paired_power(baseline_rate=.55, treatment_rate=.7,
                                 within_pair_correlation=.4, alpha=.05, power=.9,
                                 routes=6, fixtures=8, maximum_repetitions=50)
        self.assertTrue(plan["feasible"])
        self.assertGreaterEqual(plan["repetitionsPerRouteFixture"], 1)
        self.assertEqual(holm_adjust({"b": .03, "a": .01}), {"a": .02, "b": .03})
        self.assertEqual(krippendorff_alpha_ordinal([[5, 5, 5], [3, 3, 3]]), 1)

    def test_cell_journal_recovers_without_retry_and_detects_tampering(self):
        matrix = [{"caseId": "case-a", "condition": "raw_brief",
                   "requestedModel": "model-a", "repetition": 0}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cell-journal.json"
            journal = CellJournal.create(path, "run-a", matrix)
            cell = journal.next_pending()
            journal.begin(cell["cellId"])
            recovered = CellJournal.load(path, "run-a", matrix).recover_in_flight()
            self.assertEqual([item["status"] for item in recovered], ["indeterminate"])
            trial = {"trialId": "trial-a", "metrics": {"firstPassBriefFulfilment": False}}
            journal = CellJournal.load(path, "run-a", matrix)
            journal.complete(cell["cellId"], "trial-a", trial)
            journal.verify_trial(cell["cellId"], trial)
            with self.assertRaisesRegex(StudyError, "differs"):
                journal.verify_trial(cell["cellId"], {**trial, "changed": True})

    def test_spend_ledger_reserves_before_calls_and_keeps_missing_usage_charged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spend.json"
            ledger = SpendLedger.create(path, "budget-ledger", cap_gbp=1)
            reserved = ledger.reserve("call-one", stage="development", worst_case_gbp=.6,
                                      usd_to_gbp_rate=.8)
            self.assertEqual(reserved["status"], "reserved")
            with self.assertRaisesRegex(StudyError, "refused"):
                ledger.reserve("call-two", stage="development", worst_case_gbp=.5,
                               usd_to_gbp_rate=.8)
            settled = ledger.settle("call-one", None)
            self.assertEqual(settled["status"], "usage-missing-reservation-retained")
            self.assertEqual(SpendLedger.load(path).charged_gbp, .6)
            self.assertFalse(validate_spend_ledger(SpendLedger.load(path).value)["automaticTopUp"])

    def test_exploratory_h3_gate_requires_volume_recovery_bound_and_no_regression(self):
        trials = []
        for index in range(30):
            recovered = index < 18
            trials.append({"metrics": {"repairEligible": True, "repairSuccess": recovered,
                                        "firstPassBriefFulfilment": False,
                                        "finalBriefFulfilment": recovered,
                                        "firstPassSourceFactCoverage": {"rate": 1},
                                        "finalSourceFactCoverage": {"rate": 1}}})
        result = exploratory_h3_gate(trials, replicates=2000, seed=7)
        self.assertTrue(result["gatePassed"])
        self.assertFalse(result["entersPrimaryConfirmatoryClaims"])
        trials[0]["metrics"]["finalSourceFactCoverage"] = {"rate": .9}
        self.assertFalse(exploratory_h3_gate(trials, replicates=2000, seed=7)["gatePassed"])

    def test_multi_reviewer_seal_binds_cards_and_reports_agreement(self):
        declaration, _, _, _ = declaration_and_receipt()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "precommit.json").write_text(json.dumps({
                "schemaVersion": "0.5.0", "runId": "run-a",
                "reviewAttemptPolicy": "first-pass-for-H1"}))
            blind_ids = ["blind-a", "blind-b", "blind-c"]
            mapping = {}
            master_cards = []
            for index, blind_id in enumerate(blind_ids):
                image = root / "designer-review-assets" / blind_id / "desktop.png"
                image.parent.mkdir(parents=True)
                image.write_bytes(b"png-" + str(index).encode())
                master_cards.append({"blindId": blind_id,
                                     "screenshots": [str(image.relative_to(root))],
                                     "scores": {field: None for field in
                                                ("visualHierarchy", "systemFidelity", "legibility",
                                                 "rhetoricalFit", "overall")},
                                     "notes": None})
                mapping[blind_id] = {"trialId": f"trial-{index}",
                                     "condition": "selected_context",
                                     "requestedModel": f"maker/model-{index}",
                                     "caseId": f"held-case-{index}", "repetition": 0,
                                     "attemptIndex": 0, "repaired": False}
            (root / "designer-review.json").write_text(json.dumps({
                "schemaVersion": "0.5.0", "reviewerId": None, "status": "pending",
                "attemptPolicy": "first-pass-for-H1", "cards": master_cards}))
            (root / "designer-review-key.json").write_text(json.dumps({
                "schemaVersion": "0.5.0", "runId": "run-a", "mapping": mapping}))
            paths = []
            for reviewer_index, reviewer in enumerate(("designer-a", "designer-b", "designer-c")):
                review_dir = root / "designer-review-sets" / reviewer
                review_dir.mkdir(parents=True)
                ordered = blind_ids[reviewer_index:] + blind_ids[:reviewer_index]
                cards = []
                for blind_id in ordered:
                    source = root / next(card["screenshots"][0] for card in master_cards
                                         if card["blindId"] == blind_id)
                    target = review_dir / "assets" / blind_id / "desktop.png"
                    target.parent.mkdir(parents=True)
                    target.write_bytes(source.read_bytes())
                    cards.append({"blindId": blind_id,
                                  "screenshots": [str(target.relative_to(root))],
                                  "scores": {field: 4 for field in
                                             ("visualHierarchy", "systemFidelity", "legibility",
                                              "rhetoricalFit", "overall")},
                                  "notes": None})
                path = review_dir / "review.json"
                path.write_text(json.dumps({
                    "schemaVersion": "0.5.0", "reviewerId": reviewer,
                    "status": "complete", "attemptPolicy": "first-pass-for-H1",
                    "cards": cards}))
                paths.append(path)
            sealed = seal_review_set(root, declaration, paths, root / "review-set.json")
            self.assertTrue(sealed["agreementGatePassed"])
            self.assertEqual(sealed["cards"], 3)

    def test_publication_bundle_redacts_response_identifiers_and_verifies_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "publication"
            trial_dir = source / "trials" / "trial-a" / "attempt-0"
            trial_dir.mkdir(parents=True)
            trial = {"trialId": "trial-a", "responseId": "private-response-uuid",
                     "metrics": {"firstPassBriefFulfilment": True}}
            (source / "precommit.json").write_text(json.dumps({"runId": "run-a"}))
            (source / "results.json").write_text(json.dumps({"runId": "run-a"}))
            (source / "trials.jsonl").write_text(canonical(trial) + "\n")
            (source / "trials" / "trial-a" / "trial.json").write_text(json.dumps(trial))
            (trial_dir / "provider-response.json").write_text(json.dumps({
                "id": "private-provider-uuid", "user_id": "private-account"}))
            manifest = create_publication_bundle(source, destination)
            self.assertGreater(len(manifest["files"]), 0)
            retained = json.loads((destination / "trials" / "trial-a" / "trial.json").read_text())
            self.assertEqual(retained["responseId"], "[REDACTED]")
            provider = json.loads((destination / "trials" / "trial-a" / "attempt-0" /
                                   "provider-response.json").read_text())
            self.assertEqual(provider["id"], "[REDACTED]")
            self.assertEqual(provider["user_id"], "[REDACTED]")
            self.assertEqual(verify_publication_safe(destination)["status"], "safe")
            (destination / "precommit.json").write_text("{}")
            with self.assertRaisesRegex(StudyError, "manifest differs"):
                verify_publication_safe(destination)

    def test_analysis_result_schema_rejects_extra_top_level_fields(self):
        primary = paired_binary_analysis(
            binary_trials(), treatment="selected_context", comparator="scaffolded_html",
            outcome="firstPassBriefFulfilment", model_families={"m1": "f1", "m2": "f2"},
            replicates=20000, seed=1, confidence_level=.95)
        primary.update(minimumEffect=.1, gatePassed=False)
        interval = {"level": .95, "lower": -.1, "upper": .1}
        value = {"schemaVersion": "0.5.0", "studyId": "study-a", "runId": "run-a",
                 "declarationSha256": "a" * 64, "status": "mechanical-analysis-complete",
                 "primary": primary, "secondary": [],
                 "h2": {"tokenEfficiency": {"outcome": "firstCallPromptTokens", "pairs": 4,
                                               "meanDifference": -10, "meanRatio": .8,
                                               "maximumRatio": .8, "gatePassed": True},
                        "nonInferiority": {
                            "briefFulfilment": {"estimate": 0, "confidenceInterval": interval,
                                                 "oneSided95Lower": -.1,
                                                 "margin": .05, "passed": False},
                            "agentContractConformance": {"estimate": 0,
                                                          "confidenceInterval": interval,
                                                          "oneSided95Lower": -.1,
                                                          "margin": .05, "passed": False},
                            "sourceFactCoverage": {"estimate": 0, "confidenceInterval": interval,
                                                   "oneSided95Lower": -.1,
                                                   "margin": .02, "passed": False},
                            "designerOverall": None},
                        "mechanicalGatePassed": False, "fullGatePassed": None},
                 "reviewStatus": "not-sealed",
                 "claimGatePassed": False, "limitations": ["Scoped evidence."]}
        validate_analysis_result(value)
        with self.assertRaisesRegex(StudyError, "unexpected"):
            validate_analysis_result({**value, "peeked": True})

    def test_confirmatory_analysis_consumes_complete_declared_matrix(self):
        declaration, _, _, _ = declaration_and_receipt()
        trials = []
        for fixture in declaration["fixtures"]:
            for repetition in range(declaration["repetitions"]):
                for route in declaration["routes"]:
                    for condition in declaration["conditions"]:
                        brief = condition in {"selected_context", "full_rules"}
                        contract = brief if condition in {"selected_context", "full_rules"} else None
                        trial = {"condition": condition, "requestedModel": route["modelId"],
                                 "caseId": fixture["id"], "repetition": repetition,
                                 "metrics": {"firstPassBriefFulfilment": brief,
                                             "firstPassAgentContractConformance": contract,
                                             "firstPassSourceFactCoverage": {
                                                 "rate": 1.0 if brief else .8}},
                                 "calls": [{"usage": {"promptTokens":
                                                       100 if condition == "selected_context"
                                                       else 150 if condition == "full_rules" else 50}}]}
                        trials.append(trial)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "precommit.json").write_text(json.dumps({
                "schemaVersion": "0.5.0", "studyMode": "confirmatory", "runId": "run-a"}))
            (root / "results.json").write_text(json.dumps({"status": "complete", "runId": "run-a"}))
            (root / "trials.jsonl").write_text("".join(canonical(item) + "\n" for item in trials))
            result = analyze_confirmatory(root, declaration)
        self.assertEqual(result["primary"]["estimate"], 1)
        self.assertTrue(result["primary"]["gatePassed"])
        self.assertLess(result["h2"]["tokenEfficiency"]["meanRatio"], 1)
        self.assertTrue(result["h2"]["mechanicalGatePassed"])
        self.assertIsNone(result["h2"]["fullGatePassed"])
        self.assertFalse(result["claimGatePassed"])


if __name__ == "__main__":
    unittest.main()
