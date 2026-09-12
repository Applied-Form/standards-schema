#!/usr/bin/env python3
import base64
import copy
from html import escape
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import zlib

from evaluation.cli import main as cli_main
from evaluation.harness import (AGENT_NATIVE_CONDITIONS, BASELINE_CONDITIONS, CONDITIONS,
    MINIMAL_BASELINE_CONDITIONS, REFERENCE_CONDITION,
    SCAFFOLDED_CONDITION, EvaluationError, agent_contract_fact_metric, brief_fulfilment,
    extract_html, generic_scaffold_context, load_fixtures, messages_for, parse_json_bytes,
    plan_for, run_experiment, source_task_payload, summarize_designer_review)
from evaluation.openrouter import OpenRouterProvider, discover_free_models
from evaluation.provider import CompletionResult
from workflow.engine import digest, sha256
from workflow.checker import check_artifact


def identity():
    value = {"name": "standards-ui-workflow-render", "version": "0.1.0",
             "packageVersion": "1.0.0", "browserRevision": "test",
             "browser": "Chromium test", "platform": "test-x64", "nodeVersion": "v20.0.0"}
    for field in ("sourceSha256", "packageEntrySha256", "tokensSha256", "fontAssetsSha256",
                  "runtimeModulesSha256", "lockfileSha256", "browserLauncherSha256",
                  "nodeExecutableSha256", "browserPayloadSha256"):
        value[field] = hashlib.sha256(field.encode()).hexdigest()
    return value


def html_for(plan):
    props = plan["binding"]["props"]
    out = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>x</title>",
           "<style>body{margin:0}</style></head><body>",
           f'<h1 data-std-fact="title">{escape(plan["artifact"]["title"])}</h1><table>',
           f'<caption data-std-fact="schedule.label">{escape(props["label"])}</caption><thead><tr>']
    for field in ("ref", "description", "duration", "amount"):
        out.append(f'<th scope="col" data-std-fact="schedule.columns.{field}">{escape(props["columns"][field])}</th>')
    out.append("</tr></thead><tbody>")
    for index, line in enumerate(props["lines"]):
        out.append(f'<tr><th scope="row" data-std-fact="schedule.lines.{index}.ref">{escape(line["ref"])}</th><td>')
        out.append(f'<span data-std-fact="schedule.lines.{index}.description">{escape(line["description"])}</span>')
        if "standard" in line:
            out.append(f'<span data-std-fact="schedule.lines.{index}.standard">{escape(line["standard"])}</span>')
        out.append(f'</td><td data-std-fact="schedule.lines.{index}.duration">{escape(line["duration"])}</td>')
        out.append(f'<td data-std-fact="schedule.lines.{index}.amount">{escape(line["amount"])}</td></tr>')
    out.append("</tbody>")
    if "total" in props:
        total = props["total"]
        out.append(f'<tfoot><tr><th scope="row" colspan="2" data-std-fact="schedule.total.label">{escape(total["label"])}</th>')
        out.append(f'<td data-std-fact="schedule.total.duration">{escape(total["duration"])}</td>')
        out.append(f'<td data-std-fact="schedule.total.amount">{escape(total["amount"])}</td></tr></tfoot>')
    out.append("</table>")
    if "note" in props:
        out.append(f'<p data-std-fact="schedule.note">{escape(props["note"])}</p>')
    out.append("</body></html>")
    return "".join(out)


def png(width, height, colour=(255, 255, 255)):
    def chunk(kind, payload):
        return len(payload).to_bytes(4, "big") + kind + payload \
            + (zlib.crc32(kind + payload) & 0xffffffff).to_bytes(4, "big")
    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    row = b"\x00" + bytes(colour) * width
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) \
        + chunk(b"IDAT", zlib.compress(row * height)) + chunk(b"IEND", b"")


def evidence_for(plan, html):
    facts = []
    for index, fact in enumerate(plan["facts"]):
        bounds = ({"x": 16, "y": 8, "width": 120, "height": 16}
                  if fact["id"] == "title"
                  else {"x": 16, "y": 64 + index * 24, "width": 120, "height": 20})
        facts.append({"id": fact["id"], "text": fact["text"], "visible": True,
                      "clipped": False, "occluded": False, "contrastRatio": 7,
                      "lineCount": 1, "bounds": bounds})
    viewports = []
    colour = tuple(hashlib.sha256(html.encode()).digest()[:3])
    for viewport in plan["artifact"]["viewports"]:
        image = png(viewport["width"], viewport["height"], colour)
        viewports.append({**viewport,
            "document": {"clientWidth": viewport["width"], "clientHeight": viewport["height"],
                         "scrollWidth": viewport["width"], "scrollHeight": viewport["height"]},
            "bodyTextLength": 100, "overflowingElements": [], "pageErrors": [],
            "blockedRequests": [], "facts": copy.deepcopy(facts), "unmarkedText": [],
            "semanticChecks": {"oneVisibleH1": True, "tableCount": 1,
                               "namedTable": True, "captionOrLabel": True,
                               "columnHeaders": True, "rowHeaders": True, "bodyGrid": True,
                               "numericColumnOrder": True,
                               "footerStructure": True},
            "invariantBand": {"count": 1, "containsTitle": True,
                              "bounds": {"x": 0, "y": 0, "width": viewport["width"], "height": 32},
                              "backgroundColor": "rgb(17, 17, 17)",
                              "titleColor": "rgb(255, 255, 255)",
                              "borderWidths": {"top": 0, "right": 0, "bottom": 0, "left": 0}},
            "screenshot": {"file": f'schedule-{viewport["width"]}x{viewport["height"]}.png',
                           "sha256": hashlib.sha256(image).hexdigest(),
                           "dataBase64": base64.b64encode(image).decode("ascii")}})
    return {"schemaVersion": "0.1.0", "planSha256": digest(plan),
            "artifactSha256": sha256(html), "renderer": copy.deepcopy(plan["renderer"]),
            "viewports": viewports}


class FakeRenderer:
    def identity(self):
        return identity()

    def render(self, plan, directory, html=None):
        directory.mkdir(parents=True, exist_ok=True)
        artifact = html if html is not None else html_for(plan)
        render_dir = directory / "render"
        render_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = render_dir / "artifact.html"
        artifact_path.write_text(artifact)
        evidence = evidence_for(plan, artifact)
        for viewport in evidence["viewports"]:
            (render_dir / viewport["screenshot"]["file"]).write_bytes(
                base64.b64decode(viewport["screenshot"]["dataBase64"]))
        evidence_path = render_dir / "render-evidence.json"
        evidence_path.write_text(json.dumps(evidence))
        return {"summary": {"artifact": str(artifact_path), "evidence": str(evidence_path)},
                "artifact": artifact, "artifactPath": artifact_path,
                "evidence": evidence, "evidencePath": evidence_path}


class FakeProvider:
    name = "fixture-provider"

    def __init__(self, outputs):
        self.outputs = list(outputs)

    def complete(self, model, messages, *, max_tokens, temperature, trace=None):
        text = self.outputs.pop(0)
        return CompletionResult(ok=True, text=text, requested_model=model,
            resolved_model="fixture/model-v1", provider_name="Fixture Provider",
            response_id=f"fixture-{len(self.outputs)}", finish_reason="stop",
            latency_ms=5, prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.0, routing={"strategy": "direct"}, raw={"output": text},
            model_integrity={"status": "exact-request-match", "accepted": True},
            request_parameters={"maxTokens": max_tokens, "temperature": temperature})


class EvaluationTests(unittest.TestCase):
    def test_fixed_fixture_splits_and_all_condition_prompts(self):
        fixtures = load_fixtures("all")
        self.assertEqual({item["split"] for item in fixtures}, {"dev", "held-out"})
        fixture = fixtures[0]
        lengths = {}
        minimal_user_messages = set()
        scaffold_user_messages = set()
        systems = {}
        for condition in CONDITIONS:
            brief, plan = plan_for(fixture, condition, identity())
            if condition != REFERENCE_CONDITION:
                messages = messages_for(condition, brief, plan)
                systems[condition] = messages[0]["content"]
                lengths[condition] = len(json.dumps(messages))
                self.assertEqual([message["role"] for message in messages], ["system", "user"])
                if condition in MINIMAL_BASELINE_CONDITIONS:
                    minimal_user_messages.add(messages[1]["content"])
                    self.assertIn("ORIGINAL BRIEF", messages[1]["content"])
                    self.assertNotIn("data-std-fact", messages[1]["content"])
                    self.assertNotIn('"binding"', messages[1]["content"])
                    public_brief = json.loads(messages[1]["content"].split("ORIGINAL BRIEF\n", 1)[1])
                    self.assertEqual(set(public_brief), {"format", "title", "schedule", "viewports"})
                else:
                    scaffold_user_messages.add(messages[1]["content"])
                    self.assertIn("SOURCE TASK DATA", messages[1]["content"])
                    self.assertIn("data-std-fact", messages[0]["content"])
                    self.assertIn('"factSlots"', messages[1]["content"])
        self.assertLess(lengths["selected_context"], lengths["full_rules"])
        self.assertEqual(len(minimal_user_messages), 1)
        self.assertEqual(len(scaffold_user_messages), 1)
        self.assertNotEqual(minimal_user_messages, scaffold_user_messages)
        self.assertEqual(systems["raw_brief"], "You produce static design artifacts.")
        self.assertTrue(all(value.startswith("You produce static design artifacts.")
                            for value in systems.values()))
        for demand_word in ("baseline", "experiment", "evaluation", "comparison condition"):
            self.assertNotIn(demand_word, systems["brand_bible"].lower())
        self.assertTrue(all(set(item["brief"]["schedule"]["columns"])
                            == {"ref", "description", "duration", "amount"}
                            for item in fixtures))
        self.assertNotIn("## Authoritative task data", messages_for(
            "selected_context", *plan_for(fixture, "selected_context", identity()))[0]["content"])

    def test_scaffold_and_selected_share_generic_contract_and_source_payload(self):
        fixture = load_fixtures("dev", {"dev-archive-digitisation"})[0]
        scaffold_brief, scaffold_plan = plan_for(fixture, SCAFFOLDED_CONDITION, identity())
        selected_brief, selected_plan = plan_for(fixture, "selected_context", identity())
        scaffold_messages = messages_for(SCAFFOLDED_CONDITION, scaffold_brief, scaffold_plan)
        selected_messages = messages_for("selected_context", selected_brief, selected_plan)

        self.assertEqual(scaffold_messages[1], selected_messages[1])
        separator = "\n\n# Additional design-system context\n\n"
        self.assertTrue(selected_messages[0]["content"].startswith(
            scaffold_messages[0]["content"] + separator))
        self.assertEqual(scaffold_messages[0]["content"],
                         "You produce static design artifacts.\n\n"
                         + generic_scaffold_context().rstrip())
        self.assertIn(SCAFFOLDED_CONDITION, BASELINE_CONDITIONS)
        self.assertNotIn(SCAFFOLDED_CONDITION, AGENT_NATIVE_CONDITIONS)

        payload = json.loads(scaffold_messages[1]["content"].split("SOURCE TASK DATA\n", 1)[1])
        self.assertEqual(payload, source_task_payload(scaffold_brief))
        self.assertEqual(set(payload), {"format", "title", "schedule", "viewports", "factSlots"})
        self.assertEqual({item["id"] for item in payload["factSlots"]},
                         {fact["id"] for fact in scaffold_plan["facts"]})
        self.assertTrue(all(set(item) == {"id", "text", "slot"}
                            for item in payload["factSlots"]))
        self.assertNotIn("binding", payload)

        generic_prompt = json.dumps(scaffold_messages, ensure_ascii=False).lower()
        generic_context = scaffold_messages[0]["content"].lower()
        for leaked in ("instrument", "@standards", "public sans", "dm mono", "#c8102e",
                       "selected move", "ruleid", '"binding"', '"package"'):
            self.assertNotIn(leaked, generic_prompt)
        for visual_recipe in ("color", "colour", "typography", "spacing", "signature",
                              " band", "token", "rule id", "package", "binding"):
            self.assertNotIn(visual_recipe, generic_context)
        for required in ('scope=\\"col\\"', 'scope=\\"row\\"', "data-std-fact",
                         "horizontal overflow", "supplied viewport", "accessible"):
            self.assertIn(required, generic_prompt)

        future_fixture = copy.deepcopy(fixture)
        future_fixture["brief"]["instructionBuild"] = "compact"
        baseline_brief, _ = plan_for(future_fixture, "raw_brief", identity())
        self.assertEqual(baseline_brief["instructionBuild"], "compact")

    def test_scaffold_and_selected_first_calls_share_generation_budget(self):
        fixture = load_fixtures("dev", {"dev-archive-digitisation"})[0]
        _, plan = plan_for(fixture, SCAFFOLDED_CONDITION, identity())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            run_experiment(
                output=output, provider=FakeProvider([html_for(plan), html_for(plan)]),
                models=["fixture/model"], renderer=FakeRenderer(),
                conditions=[SCAFFOLDED_CONDITION, "selected_context"], split="dev",
                case_ids={fixture["id"]}, repetitions=1, max_repairs=2,
                max_tokens=1234, temperature=0.25, model_snapshot={"models": []},
                label="scaffold-budget-parity-test",
            )
            requests = []
            for trial_directory in (output / "trials").iterdir():
                trial = json.loads((trial_directory / "trial.json").read_text())
                request = json.loads((trial_directory / "attempt-0" / "request.json").read_text())
                requests.append((trial["condition"], request))
                self.assertEqual(len(trial["calls"]), 1)
            self.assertEqual({condition for condition, _ in requests},
                             {SCAFFOLDED_CONDITION, "selected_context"})
            self.assertEqual({request["maxTokens"] for _, request in requests}, {1234})
            self.assertEqual({request["temperature"] for _, request in requests}, {0.25})
            self.assertEqual({request["attempt"] for _, request in requests}, {0})
            self.assertEqual(len({request["messages"][1]["content"]
                                  for _, request in requests}), 1)

    def test_brief_fulfilment_and_source_facts_ignore_private_marker_attributes(self):
        fixture = load_fixtures("dev", {"dev-archive-digitisation"})[0]
        brief, plan = plan_for(fixture, "full_rules", identity())
        marked = html_for(plan)
        unmarked = re.sub(r' data-std-fact="[^"]+"', "", marked)
        outcomes = []
        checker_statuses = []
        with tempfile.TemporaryDirectory() as directory:
            for index, html in enumerate((marked, unmarked)):
                rendered = FakeRenderer().render(plan, Path(directory) / str(index), html)
                if html == unmarked:
                    for viewport in rendered["evidence"]["viewports"]:
                        viewport["facts"] = []
                        viewport["unmarkedText"] = [fact["text"] for fact in plan["facts"]]
                report = check_artifact(plan, html, rendered["evidence"])
                outcomes.append(brief_fulfilment(brief, html, report, rendered["evidence"]))
                checker_statuses.append(report["status"])
        self.assertEqual(checker_statuses, ["pass", "fail"])
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertTrue(outcomes[0]["passed"])
        self.assertTrue(outcomes[0]["sourceFactCoverage"]["allPreserved"])

        changed = unmarked.replace("£3,200", "£3,500")
        with tempfile.TemporaryDirectory() as directory:
            rendered = FakeRenderer().render(plan, Path(directory), changed)
            changed_outcome = brief_fulfilment(
                brief, changed, check_artifact(plan, changed, rendered["evidence"]),
                rendered["evidence"]
            )
        self.assertFalse(changed_outcome["passed"])
        self.assertIn("schedule.total.amount",
                      changed_outcome["sourceFactCoverage"]["missingOrChanged"])

    def test_brief_fulfilment_requires_every_fact_visible_at_every_viewport(self):
        fixture = load_fixtures("dev", {"dev-archive-digitisation"})[0]
        brief, plan = plan_for(fixture, "full_rules", identity())
        html = html_for(plan)
        evidence = evidence_for(plan, html)
        for viewport in evidence["viewports"]:
            amount = next(fact for fact in viewport["facts"]
                          if fact["id"] == "schedule.total.amount")
            amount["contrastRatio"] = 1
        report = check_artifact(plan, html, evidence)
        outcome = brief_fulfilment(brief, html, report, evidence)
        self.assertTrue(outcome["sourceFactCoverage"]["allPreserved"])
        self.assertEqual(outcome["browserEvidence"]["status"], "fail")
        self.assertFalse(outcome["passed"])
        for viewport in outcome["browserEvidence"]["markerIndependentScheduleChecks"]:
            self.assertFalse(viewport["visibleSourceFacts"]["allVisible"])
            self.assertIn("schedule.total.amount",
                          viewport["visibleSourceFacts"]["missingOrNotVisible"])

    def test_html_extraction_and_fact_preservation_keep_symbols_distinct(self):
        fixture = load_fixtures("dev", {"dev-archive-digitisation"})[0]
        _, plan = plan_for(fixture, "raw_brief", identity())
        good = html_for(plan)
        extracted, record = extract_html(f"```html\n{good}\n```")
        self.assertEqual(extracted, good)
        self.assertTrue(record["changed"])
        self.assertTrue(agent_contract_fact_metric(plan, good)["allPreserved"])
        changed = good.replace("£3,200", "£3,500")
        self.assertFalse(agent_contract_fact_metric(plan, changed)["allPreserved"])

    def test_openrouter_discovery_requires_every_published_price_to_be_zero(self):
        catalogue = {"data": [
            {"id": "maker/free:free", "pricing": {"prompt": "0", "completion": "0"},
             "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}},
            {"id": "maker/request-fee", "pricing": {"prompt": "0", "completion": "0", "request": "0.01"},
             "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}},
            {"id": "maker/image", "pricing": {"prompt": "0", "completion": "0"},
             "architecture": {"input_modalities": ["text"], "output_modalities": ["image"]}},
        ]}
        with patch("evaluation.openrouter._http_json", return_value=(200, catalogue, 12)):
            snapshot = discover_free_models("secret-value")
        self.assertEqual([item["id"] for item in snapshot["models"]], ["maker/free:free"])
        self.assertNotIn("secret-value", json.dumps(snapshot))

    def test_openrouter_accepts_only_frozen_exact_or_canonical_identity(self):
        snapshot = {"provider": "openrouter", "count": 1, "models": [{
            "id": "maker/model:free", "canonicalSlug": "maker/model-20260912",
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
            "supportedParameters": ["reasoning", "tool_choice"],
        }]}
        provider = OpenRouterProvider(snapshot, key="test-key", reasoning_effort="none")
        self.assertIn("python", provider.experiment_metadata["environment"])
        self.assertFalse(provider.experiment_metadata["underlyingProviderPinned"])
        response = {"id": "one", "model": "maker/model-20260912",
                    "user_id": "private-account-id",
                    "metadata": {"billing_account_id": "private-billing-id"},
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                              "total_tokens": 2, "cost": 0}}
        with patch("evaluation.openrouter._http_json", return_value=(200, response, 4)) as transport:
            accepted = provider.complete("maker/model:free", [{"role": "user", "content": "x"}],
                                         max_tokens=256, temperature=0)
        self.assertTrue(accepted.ok)
        self.assertEqual(accepted.model_integrity["status"], "frozen-canonical-match")
        self.assertEqual(accepted.raw["user_id"], "[REDACTED]")
        self.assertEqual(accepted.raw["metadata"]["billing_account_id"], "[REDACTED]")
        self.assertNotIn("private-account-id", json.dumps(accepted.raw))
        payload = transport.call_args.args[2]
        self.assertEqual(payload["reasoning"], {"effort": "none"})
        self.assertNotIn("tool_choice", payload)
        self.assertFalse(payload["provider"]["allow_fallbacks"])
        substituted = copy.deepcopy(response)
        substituted["model"] = "maker/other-model"
        with patch("evaluation.openrouter._http_json", return_value=(200, substituted, 4)):
            rejected = provider.complete("maker/model:free", [{"role": "user", "content": "x"}],
                                         max_tokens=256, temperature=0)
        self.assertFalse(rejected.ok)
        self.assertEqual(rejected.error["code"], "model_integrity_failure")

    def test_json_parser_rejects_duplicate_keys_and_non_finite_numbers(self):
        with self.assertRaisesRegex(Exception, "duplicate JSON key"):
            parse_json_bytes(b'{"a":1,"a":2}', "test")
        with self.assertRaisesRegex(Exception, "non-finite"):
            parse_json_bytes(b'{"a":NaN}', "test")
        with self.assertRaisesRegex(Exception, "non-finite"):
            parse_json_bytes(b'{"a":1e999}', "test")

    def test_runner_retains_failures_and_measures_successful_repair(self):
        fixture = load_fixtures("dev", {"dev-archive-digitisation"})[0]
        _, plan = plan_for(fixture, "full_rules", identity())
        good = html_for(plan)
        broken = good.replace("£3,200", "£3,500")
        provider = FakeProvider([broken, good])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            result = run_experiment(output=output, provider=provider, models=["fixture/model"],
                renderer=FakeRenderer(), conditions=["full_rules"], split="dev",
                case_ids={fixture["id"]}, repetitions=1, max_repairs=1,
                max_tokens=1000, temperature=0, model_snapshot={"models": []}, label="test")
            row = result["summary"][0]
            self.assertEqual(row["firstPassBriefFulfilment"]["passed"], 0)
            self.assertEqual(row["firstPassAgentContractConformance"]["passed"], 0)
            self.assertEqual(row["repair"]["succeeded"], 1)
            self.assertEqual(row["finalBriefFulfilment"]["passed"], 1)
            self.assertEqual(row["finalAgentContractConformance"]["passed"], 1)
            self.assertEqual(
                row["promptTokensPerFinalAgentContractConformingArtifact"]["value"], 200
            )
            trial = json.loads((next((output / "trials").iterdir()) / "trial.json").read_text())
            self.assertEqual(len(trial["calls"]), 2)
            self.assertTrue(all(not Path(call["rawResponse"]).is_absolute() for call in trial["calls"]))
            self.assertTrue(all((output / call["rawResponse"]).is_file() for call in trial["calls"]))
            self.assertNotIn(str(output.resolve()), json.dumps(trial))
            review = json.loads((output / "designer-review.json").read_text())
            key = json.loads((output / "designer-review-key.json").read_text())
            self.assertEqual(review["attemptPolicy"], "first-pass-for-H1")
            self.assertNotIn("condition", review["cards"][0])
            self.assertEqual(set(review["rubric"]["visualHierarchy"]), {"1", "3", "5"})
            self.assertNotIn("artifact", review["cards"][0])
            self.assertTrue(review["cards"][0]["screenshots"])
            self.assertTrue(all((output / path).is_file()
                                for path in review["cards"][0]["screenshots"]))
            mapping = key["mapping"][review["cards"][0]["blindId"]]
            self.assertEqual(mapping["attemptIndex"], 0)
            self.assertFalse(mapping["repaired"])
            first_evidence = json.loads((output / trial["attempts"][0]["render"]["evidence"]).read_text())
            final_evidence = json.loads((output / trial["attempts"][-1]["render"]["evidence"]).read_text())
            review_image = (output / review["cards"][0]["screenshots"][0]).read_bytes()
            first_image = (output / Path(trial["attempts"][0]["render"]["evidence"]).parent
                           / first_evidence["viewports"][0]["screenshot"]["file"]).read_bytes()
            final_image = (output / Path(trial["attempts"][-1]["render"]["evidence"]).parent
                           / final_evidence["viewports"][0]["screenshot"]["file"]).read_bytes()
            self.assertEqual(review_image, first_image)
            self.assertNotEqual(review_image, final_image)
            self.assertTrue((output / "precommit.json").is_file())
            precommit = json.loads((output / "precommit.json").read_text())
            self.assertEqual(precommit["studyMode"], "exploratory")
            self.assertIn("python", precommit["runnerEnvironment"])
            condition = next(item for item in precommit["conditions"]
                             if item["id"] == "full_rules")
            self.assertEqual(condition["treatmentClass"], "agent-native")
            self.assertTrue(condition["repairAllowed"])
            self.assertTrue(condition["agentContractMeasured"])
            self.assertEqual(precommit["reviewAttemptPolicy"], "first-pass-for-H1")
            self.assertIn("workflow/schemas/render-evidence.schema.json",
                          precommit["protocolFiles"])

    def test_baselines_receive_no_repair_assistance(self):
        fixture = load_fixtures("dev", {"dev-archive-digitisation"})[0]
        _, plan = plan_for(fixture, "raw_brief", identity())
        good = html_for(plan)
        broken = good.replace("£3,200", "£3,500")
        provider = FakeProvider([broken, good])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            run_experiment(
                output=output, provider=provider, models=["fixture/model"],
                renderer=FakeRenderer(), conditions=["raw_brief"], split="dev",
                case_ids={fixture["id"]}, repetitions=1, max_repairs=2,
                max_tokens=1000, temperature=0, model_snapshot={"models": []},
                label="baseline-test",
            )
            trial = json.loads((next((output / "trials").iterdir()) / "trial.json").read_text())
            self.assertEqual(len(trial["calls"]), 1)
            self.assertEqual(len(provider.outputs), 1)
            self.assertFalse(trial["metrics"]["repairEligible"])
            self.assertEqual(trial["metrics"]["repairAttempts"], 0)
            self.assertFalse(trial["metrics"]["finalBriefFulfilment"])
            self.assertIsNone(trial["metrics"]["firstPassAgentContractConformance"])
            self.assertIsNone(trial["metrics"]["finalAgentContractConformance"])
            row = json.loads((output / "results.json").read_text())["summary"][0]
            self.assertIsNone(row["firstPassAgentContractConformance"]["passed"])
            self.assertIsNone(row["firstPassAgentContractConformance"]["denominator"])
            self.assertIsNone(row["firstPassAgentContractConformance"]["rate"])

    def test_scaffold_uses_neutral_measurement_and_is_never_repaired(self):
        fixture = load_fixtures("dev", {"dev-archive-digitisation"})[0]
        _, plan = plan_for(fixture, SCAFFOLDED_CONDITION, identity())
        unmarked = re.sub(r' data-std-fact="[^"]+"', "", html_for(plan))
        provider = FakeProvider([unmarked, html_for(plan)])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            result = run_experiment(
                output=output, provider=provider, models=["fixture/model"],
                renderer=FakeRenderer(), conditions=[SCAFFOLDED_CONDITION], split="dev",
                case_ids={fixture["id"]}, repetitions=1, max_repairs=2,
                max_tokens=1000, temperature=0, model_snapshot={"models": []},
                label="scaffold-no-repair-test",
            )
            trial = json.loads((next((output / "trials").iterdir()) / "trial.json").read_text())
            self.assertEqual(len(trial["calls"]), 1)
            self.assertEqual(len(provider.outputs), 1)
            self.assertTrue(trial["metrics"]["firstPassBriefFulfilment"])
            self.assertIsNone(trial["metrics"]["firstPassAgentContractConformance"])
            self.assertFalse(trial["metrics"]["repairEligible"])
            self.assertEqual(trial["metrics"]["repairAttempts"], 0)

            row = result["summary"][0]
            self.assertEqual(row["firstPassBriefFulfilment"],
                             {"passed": 1, "denominator": 1, "rate": 1.0})
            self.assertIsNone(row["firstPassAgentContractConformance"]["passed"])
            self.assertIsNone(row["firstPassAgentContractConformance"]["denominator"])
            self.assertIsNone(row["firstPassAgentContractConformance"]["rate"])
            precommit = json.loads((output / "precommit.json").read_text())
            condition = precommit["conditions"][0]
            self.assertEqual(condition["treatmentClass"], "scaffolded-baseline")
            self.assertTrue(condition["genericScaffoldSupplied"])
            self.assertFalse(condition["agentContractMeasured"])
            self.assertFalse(condition["repairAllowed"])
            self.assertEqual(condition["maxRepairTurns"], 0)
            self.assertIn("evaluation/conditions/scaffolded-html.md",
                          precommit["protocolFiles"])

    def test_failed_repair_call_is_counted_and_partial_usage_is_missing(self):
        fixture = load_fixtures("dev", {"dev-archive-digitisation"})[0]
        _, plan = plan_for(fixture, "full_rules", identity())
        broken = html_for(plan).replace("£3,200", "£3,500")

        class FailedRepairProvider(FakeProvider):
            def complete(self, model, messages, *, max_tokens, temperature, trace=None):
                if self.outputs:
                    return super().complete(model, messages, max_tokens=max_tokens,
                                            temperature=temperature, trace=trace)
                return CompletionResult(
                    ok=False, requested_model=model, error={"code": "repair-provider-failure"},
                    raw={"error": {"code": "repair-provider-failure"}},
                    model_integrity={"status": "exact-request-match", "accepted": True},
                )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            result = run_experiment(
                output=output, provider=FailedRepairProvider([broken]),
                models=["fixture/model"], renderer=FakeRenderer(),
                conditions=["full_rules"], split="dev", case_ids={fixture["id"]},
                repetitions=1, max_repairs=1, max_tokens=1000, temperature=0,
                model_snapshot={"models": []}, label="failed-repair-test",
            )
            trial = json.loads((next((output / "trials").iterdir()) / "trial.json").read_text())
            self.assertEqual(len(trial["calls"]), 2)
            self.assertEqual(len(trial["attempts"]), 1)
            self.assertTrue(trial["metrics"]["repairEligible"])
            self.assertEqual(trial["metrics"]["repairAttempts"], 1)
            self.assertIsNone(trial["metrics"]["promptTokens"])
            efficiency = result["summary"][0]["promptTokensPerFinalAgentContractConformingArtifact"]
            self.assertIsNone(efficiency["providerReportedPromptTokens"])
            self.assertIsNone(efficiency["value"])

    def test_group_prompt_total_is_null_when_any_trial_omits_usage(self):
        fixture = load_fixtures("dev", {"dev-archive-digitisation"})[0]
        _, plan = plan_for(fixture, "raw_brief", identity())
        good = html_for(plan)

        class PartialUsageProvider:
            name = "partial-usage-provider"

            def __init__(self):
                self.calls = 0

            def complete(self, model, messages, *, max_tokens, temperature, trace=None):
                self.calls += 1
                if self.calls == 1:
                    return CompletionResult(
                        ok=True, text=good, requested_model=model, resolved_model=model,
                        latency_ms=5, prompt_tokens=100, completion_tokens=50,
                        total_tokens=150, cost=0.0, raw={"output": good},
                        model_integrity={"status": "exact-request-match", "accepted": True},
                    )
                return CompletionResult(
                    ok=False, requested_model=model, error={"code": "missing-usage"},
                    raw={"error": {"code": "missing-usage"}},
                    model_integrity={"status": "unobserved", "accepted": False},
                )

        with tempfile.TemporaryDirectory() as directory:
            result = run_experiment(
                output=Path(directory) / "run", provider=PartialUsageProvider(),
                models=["fixture/model"], renderer=FakeRenderer(), conditions=["raw_brief"],
                split="dev", case_ids={fixture["id"]}, repetitions=2, max_repairs=0,
                max_tokens=1000, temperature=0, model_snapshot={"models": []},
                label="partial-usage-test",
            )
            efficiency = result["summary"][0]["promptTokensPerFinalAgentContractConformingArtifact"]
            self.assertEqual(efficiency["reportedTrialCount"], 1)
            self.assertEqual(efficiency["trialDenominator"], 2)
            self.assertIsNone(efficiency["providerReportedPromptTokens"])
            self.assertIsNone(efficiency["value"])

    def test_review_uses_opaque_ids_omits_treatment_metadata_and_deduplicates_reference(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch("evaluation.harness.secrets.token_hex", return_value="ab" * 12) as token_hex:
            output = Path(directory) / "run"
            run_experiment(
                output=output, provider=None, models=[], renderer=FakeRenderer(),
                conditions=[REFERENCE_CONDITION], split="dev",
                case_ids={"dev-archive-digitisation"}, repetitions=2, max_repairs=0,
                max_tokens=1000, temperature=0, model_snapshot=None,
                label="review-test",
            )
            review = json.loads((output / "designer-review.json").read_text())
            key = json.loads((output / "designer-review-key.json").read_text())
            self.assertNotIn("runId", review)
            self.assertEqual(len(review["cards"]), 1)
            card = review["cards"][0]
            self.assertEqual(card["blindId"], "ab" * 12)
            token_hex.assert_called_once_with(12)
            for field in ("caseId", "split", "repetition", "condition", "requestedModel", "artifact"):
                self.assertNotIn(field, card)
            self.assertEqual(key["eligibility"]["omittedDeterministicReferenceDuplicates"], 1)
            self.assertEqual(key["eligibility"]["reviewCards"], 1)
            self.assertEqual(key["reviewAttemptPolicy"], "first-pass-for-H1")
            self.assertEqual(key["eligibility"]["byConditionModel"], [{
                "condition": REFERENCE_CONDITION,
                "requestedModel": REFERENCE_CONDITION,
                "scheduledTrials": 2,
                "reviewCards": 1,
                "missingFirstPassArtifacts": 0,
                "omittedDeterministicReferenceDuplicates": 1,
            }])
            mapping = key["mapping"][card["blindId"]]
            self.assertEqual(mapping["attemptIndex"], 0)
            self.assertFalse(mapping["repaired"])

    def test_review_summary_rejects_removed_cards(self):
        fixture = load_fixtures("dev", {"dev-archive-digitisation"})[0]
        _, plan = plan_for(fixture, "full_rules", identity())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            run_experiment(
                output=output, provider=FakeProvider([html_for(plan), html_for(plan)]),
                models=["fixture/model"], renderer=FakeRenderer(), conditions=["full_rules"],
                split="dev", case_ids={fixture["id"]}, repetitions=2, max_repairs=0,
                max_tokens=1000, temperature=0, model_snapshot={"models": []},
                label="review-integrity-test",
            )
            review_path = output / "designer-review.json"
            review = json.loads(review_path.read_text())
            review["cards"] = review["cards"][:1]
            review["status"] = "complete"
            review_path.write_text(json.dumps(review))
            with self.assertRaisesRegex(EvaluationError, "added, removed or duplicated"):
                summarize_designer_review(output)

    def test_confirmatory_mode_fails_before_provider_discovery(self):
        with patch("evaluation.cli.discover_free_models") as discovery:
            with self.assertRaisesRegex(EvaluationError, "confirmatory execution is disabled"):
                cli_main(["run", "--models", "maker/model:free", "--mode", "confirmatory"])
            discovery.assert_not_called()

    def test_renderer_failure_is_counted_and_workspace_paths_are_scrubbed(self):
        fixture = load_fixtures("dev", {"dev-archive-digitisation"})[0]
        _, plan = plan_for(fixture, "raw_brief", identity())

        class FailingRenderer(FakeRenderer):
            root = Path.home() / "standards-ui"

            def render(self, plan, directory, html=None):
                raise EvaluationError(f"failed at {directory}/render and {self.root}/scripts")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            result = run_experiment(
                output=output, provider=FakeProvider([html_for(plan)]),
                models=["fixture/model"], renderer=FailingRenderer(),
                conditions=["raw_brief"], split="dev", case_ids={fixture["id"]},
                repetitions=1, max_repairs=0, max_tokens=1000, temperature=0,
                model_snapshot={"models": []}, label="test-renderer-failure",
            )
            row = result["summary"][0]
            self.assertEqual(row["failures"]["renderer"], {"failed": 1, "rate": 1.0})
            eligibility = result["designerReview"]["eligibility"]["byConditionModel"]
            self.assertEqual(eligibility, [{
                "condition": "raw_brief", "requestedModel": "fixture/model",
                "scheduledTrials": 1, "reviewCards": 0,
                "missingFirstPassArtifacts": 1,
                "omittedDeterministicReferenceDuplicates": 0,
            }])
            trial_text = (next((output / "trials").iterdir()) / "trial.json").read_text()
            self.assertNotIn(str(output.resolve()), trial_text)
            self.assertNotIn(str(Path.home()), trial_text)


if __name__ == "__main__":
    unittest.main()
