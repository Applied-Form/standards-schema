#!/usr/bin/env python3
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from evaluation.cli import main as cli_main
from evaluation.openrouter import OpenRouterProvider
from evaluation.provider import CompletionResult
from evaluation.qualification import EXPECTED_TEXT, run_route_qualification
from evaluation.study import SpendLedger, StudyError, digest


def snapshot():
    return {"provider": "openrouter", "count": 1, "models": [{
        "id": "maker/model-a", "canonicalSlug": "maker/model-a-v1",
        "pricing": {"prompt": ".000001", "completion": ".000002"},
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
    }]}


class FakeQualificationProvider:
    name = "openrouter"

    def __init__(self, model_snapshot, ledger, outputs=None, raise_at=None,
                 failure_modes=None, cost=0):
        self.model_snapshot_sha256 = digest(model_snapshot)
        self.provider_pins = {"maker/model-a": "pinned-provider"}
        self.provider_display_names = {"maker/model-a": "Pinned Provider"}
        self.require_zero_price = False
        self.ledger = ledger
        self.outputs = list(outputs or [EXPECTED_TEXT] * 10)
        self.raise_at = raise_at
        self.failure_modes = dict(failure_modes or {})
        self.cost = cost
        self.calls = 0
        self.saw_reservations = []

    def complete(self, model, messages, *, max_tokens, temperature, trace=None):
        current = SpendLedger.load(self.ledger.path)
        self.saw_reservations.append(current.value["entries"][-1]["status"] == "reserved")
        call = self.calls
        self.calls += 1
        if self.raise_at == call:
            raise RuntimeError("simulated process stop")
        text = self.outputs.pop(0)
        mode = self.failure_modes.get(call)
        resolved_model = "maker/model-a-v1"
        endpoint = "other-provider" if mode == "pin" else "pinned-provider"
        provider_name = "Other Provider" if mode == "pin" else "Pinned Provider"
        accepted = mode != "identity"
        error = ({"code": "model_integrity_failure"} if mode == "identity" else
                 {"code": "provider_endpoint_integrity_failure"} if mode == "pin" else
                 {"code": "unsupported_parameter"} if mode == "parameter" else None)
        provider_parameters = {"only": ["pinned-provider"],
                               "allow_fallbacks": mode == "parameter",
                               "require_parameters": True}
        return CompletionResult(
            ok=error is None, text=text, requested_model=model,
            resolved_model=resolved_model, provider_name=provider_name,
            provider_endpoint=endpoint, prompt_tokens=3, completion_tokens=1,
            total_tokens=4, cost=self.cost,
            raw={"model": resolved_model, "text": text}, error=error,
            model_integrity={"accepted": accepted, "status": "frozen-canonical-match",
                             "requestedModel": model, "resolvedModel": resolved_model,
                             "acceptedResolvedModels": [model, resolved_model]},
            request_parameters={"maxTokens": max_tokens, "temperature": temperature,
                                "provider": provider_parameters,
                                "trace": trace, "reasoning": {"effort": "none"},
                                "frozenModelSnapshotSha256": self.model_snapshot_sha256},
        )


class QualificationTests(unittest.TestCase):
    def arguments(self, root, provider, ledger, block, resume=False):
        return dict(output=root / "qualification", provider=provider,
                    model_snapshot=snapshot(), spend_ledger=ledger,
                    route_id="route-a", model_id="maker/model-a",
                    model_family="family-a", provider_endpoint="pinned-provider",
                    provider_display_name="Pinned Provider",
                    block_index=block, expires_at="2099-09-12T00:00:00Z",
                    max_tokens=64, temperature=0, worst_case_call_cost_gbp=.1,
                    usd_to_gbp_rate=.8, resume=resume)

    def test_two_blocks_reserve_before_each_call_and_emit_receipt_after_ten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = SpendLedger.create(root / "ledger.json", "qualification-ledger")
            provider = FakeQualificationProvider(snapshot(), ledger)
            first = run_route_qualification(**self.arguments(root, provider, ledger, 1))
            self.assertEqual(first["status"], "block-complete")
            self.assertFalse((root / "qualification" / "route-qualification.json").exists())
            receipt = run_route_qualification(**self.arguments(root, provider, ledger, 2, True))
            self.assertEqual(receipt["observations"]["calls"], 10)
            self.assertEqual(receipt["observations"]["timeBlocks"], 2)
            self.assertEqual(receipt["observations"]["successRate"], 1)
            self.assertTrue(all(provider.saw_reservations))
            self.assertEqual(len(SpendLedger.load(ledger.path).value["entries"]), 10)
            self.assertTrue((root / "qualification" / "route-qualification.json").is_file())

    def test_failed_threshold_retains_all_calls_and_emits_no_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = SpendLedger.create(root / "ledger.json", "qualification-ledger")
            provider = FakeQualificationProvider(
                snapshot(), ledger, outputs=["WRONG", "WRONG"] + [EXPECTED_TEXT] * 8)
            run_route_qualification(**self.arguments(root, provider, ledger, 1))
            result = run_route_qualification(**self.arguments(root, provider, ledger, 2, True))
            self.assertEqual(result["status"], "not-qualified")
            self.assertEqual(result["observations"]["successes"], 8)
            self.assertFalse((root / "qualification" / "route-qualification.json").exists())
            self.assertTrue((root / "qualification" / "qualification-evidence.json").is_file())
            self.assertEqual(len(SpendLedger.load(ledger.path).value["entries"]), 10)
            evidence_schema = json.loads((Path(__file__).parents[1] / "schemas" /
                                          "qualification-evidence.schema.json").read_text())
            receipt_schema = json.loads((Path(__file__).parents[1] / "schemas" /
                                         "route-qualification.schema.json").read_text())
            self.assertEqual(evidence_schema["properties"]["observations"]
                             ["properties"]["successes"]["minimum"], 0)
            self.assertEqual(receipt_schema["properties"]["observations"]
                             ["properties"]["successes"]["minimum"], 9)

    def test_exactly_nine_successes_meets_the_frozen_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = SpendLedger.create(root / "ledger.json", "qualification-ledger")
            provider = FakeQualificationProvider(
                snapshot(), ledger, outputs=["WRONG"] + [EXPECTED_TEXT] * 9)
            run_route_qualification(**self.arguments(root, provider, ledger, 1))
            receipt = run_route_qualification(
                **self.arguments(root, provider, ledger, 2, True))
            self.assertEqual(receipt["observations"]["successes"], 9)
            self.assertEqual(receipt["observations"]["successRate"], .9)
            self.assertEqual(receipt["observations"]["acceptedIdentities"], 10)

    def test_identity_pin_and_parameter_failures_each_block_receipt(self):
        expected = {"identity": "acceptedIdentities", "pin": "providerPinMatches",
                    "parameter": "parameterAcceptances"}
        for mode, observation in expected.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                ledger = SpendLedger.create(root / "ledger.json", "qualification-ledger")
                provider = FakeQualificationProvider(
                    snapshot(), ledger, failure_modes={0: mode})
                run_route_qualification(**self.arguments(root, provider, ledger, 1))
                result = run_route_qualification(
                    **self.arguments(root, provider, ledger, 2, True))
                self.assertEqual(result["status"], "not-qualified")
                self.assertEqual(result["observations"][observation], 9)
                self.assertFalse((root / "qualification" / "route-qualification.json").exists())

    def test_interrupted_call_is_not_retried_on_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = SpendLedger.create(root / "ledger.json", "qualification-ledger")
            interrupted = FakeQualificationProvider(snapshot(), ledger, raise_at=2)
            with self.assertRaisesRegex(RuntimeError, "process stop"):
                run_route_qualification(**self.arguments(root, interrupted, ledger, 1))
            resumed = FakeQualificationProvider(snapshot(), ledger)
            first = run_route_qualification(**self.arguments(root, resumed, ledger, 1, True))
            self.assertEqual(first["status"], "block-complete")
            self.assertEqual(resumed.calls, 2)
            journal = (root / "qualification" / "qualification-journal.json").read_text()
            self.assertIn('"status": "indeterminate"', journal)

    def test_resume_rejects_tampered_result_and_journal_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = SpendLedger.create(root / "ledger.json", "qualification-ledger")
            provider = FakeQualificationProvider(snapshot(), ledger)
            run_route_qualification(**self.arguments(root, provider, ledger, 1))
            journal_path = root / "qualification" / "qualification-journal.json"
            journal = json.loads(journal_path.read_text())
            journal["blocks"][0]["calls"][0]["checks"]["success"] = False
            journal_path.write_text(json.dumps(journal))
            with self.assertRaisesRegex(StudyError, "checks differ"):
                run_route_qualification(**self.arguments(root, provider, ledger, 2, True))
            self.assertEqual(provider.calls, 5)

    def test_resume_rejects_changed_ledger_and_spend_overrun(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = SpendLedger.create(root / "ledger.json", "qualification-ledger")
            provider = FakeQualificationProvider(snapshot(), ledger)
            run_route_qualification(**self.arguments(root, provider, ledger, 1))
            replacement = SpendLedger.create(root / "other-ledger.json", "other-ledger")
            changed_provider = FakeQualificationProvider(snapshot(), replacement)
            with self.assertRaisesRegex(StudyError, "frozen precommit"):
                run_route_qualification(
                    **self.arguments(root, changed_provider, replacement, 2, True))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = SpendLedger.create(root / "ledger.json", "qualification-ledger")
            provider = FakeQualificationProvider(snapshot(), ledger, cost=1)
            args = self.arguments(root, provider, ledger, 1)
            args["usd_to_gbp_rate"] = 1
            with self.assertRaisesRegex(StudyError, "exceeded"):
                run_route_qualification(**args)
            resumed = FakeQualificationProvider(snapshot(), ledger)
            args = self.arguments(root, resumed, ledger, 1, True)
            args["usd_to_gbp_rate"] = 1
            with self.assertRaisesRegex(StudyError, "overrun"):
                run_route_qualification(**args)
            self.assertFalse((root / "qualification" / "route-qualification.json").exists())

    def test_cli_runs_offline_with_a_fake_pinned_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snap = root / "snapshot.json"
            snap.write_text(json.dumps(snapshot()))
            ledger = SpendLedger.create(root / "ledger.json", "qualification-ledger")
            provider = FakeQualificationProvider(snapshot(), ledger)
            common = ["route-qualify", "--route-id", "route-a", "--model", "maker/model-a",
                      "--model-family", "family-a", "--provider-endpoint", "pinned-provider",
                      "--provider-display-name", "Pinned Provider",
                      "--snapshot", str(snap), "--spend-ledger", str(ledger.path),
                      "--out", str(root / "qualification"), "--expires-at",
                      "2099-09-12T00:00:00Z", "--worst-case-call-cost-gbp", ".1",
                      "--usd-to-gbp-rate", ".8"]
            with patch("evaluation.cli.OpenRouterProvider", return_value=provider), \
                    patch("evaluation.cli._print"):
                self.assertEqual(cli_main([*common, "--block", "1"]), 0)
                self.assertEqual(cli_main([*common, "--block", "2", "--resume"]), 0)
            self.assertEqual(provider.calls, 10)

    def test_real_openrouter_adapter_contract_qualifies_with_offline_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = SpendLedger.create(root / "ledger.json", "qualification-ledger")
            provider = OpenRouterProvider(
                snapshot(), key="test-key", reasoning_effort="none",
                provider_pins={"maker/model-a": "pinned-provider"},
                provider_display_names={"maker/model-a": "Pinned Provider"},
                require_zero_price=False)

            def response(_path, _key, payload, _timeout):
                return 200, {
                    "id": "offline-response", "model": "maker/model-a-v1",
                    "openrouter_metadata": {
                        "attempts": [{"status": 200, "provider": "Pinned Provider"}]},
                    "choices": [{"message": {"content": EXPECTED_TEXT},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 1,
                              "total_tokens": 4, "cost": 0},
                }, 2

            with patch("evaluation.openrouter._http_json", side_effect=response) as transport:
                run_route_qualification(**self.arguments(root, provider, ledger, 1))
                receipt = run_route_qualification(
                    **self.arguments(root, provider, ledger, 2, True))
            self.assertEqual(receipt["observations"]["successes"], 10)
            self.assertEqual(transport.call_count, 10)
            for call in transport.call_args_list:
                payload = call.args[2]
                self.assertEqual(payload["provider"]["only"], ["pinned-provider"])
                self.assertFalse(payload["provider"]["allow_fallbacks"])
                self.assertTrue(payload["provider"]["require_parameters"])
                self.assertEqual(payload["reasoning"], {"effort": "none"})


if __name__ == "__main__":
    unittest.main()
