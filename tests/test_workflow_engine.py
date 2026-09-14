#!/usr/bin/env python3
"""Six-move planning, selected-context and safe bounded-repair regressions."""
import copy
import hashlib
from html import escape
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workflow.engine import (LIMITATIONS, RULES, assemble_context, create_plan, digest,
                             prepare_repair, validate_plan)
from workflow.schema import load_schema, validate
from workflow.support import load_support_manifest, support_manifest_sha256


def read_pack(system, filename):
    return (ROOT / "packs" / system / filename).read_text(encoding="utf-8")


def brief():
    return json.loads((ROOT / "examples/workflow/schedule-brief.json").read_text())


def renderer_identity():
    return {"name": "standards-ui-workflow-render", "version": "0.2.0",
            "supportManifestSha256": support_manifest_sha256(),
            "sourceSha256": "1" * 64, "packageVersion": "2.0.0",
            "packageEntrySha256": "2" * 64, "tokensSha256": "3" * 64,
            "fontAssetsSha256": "4" * 64, "runtimeModulesSha256": "5" * 64,
            "lockfileSha256": "6" * 64, "browserLauncherSha256": "7" * 64,
            "browserPayloadSha256": "8" * 64, "nodeExecutableSha256": "9" * 64,
            "browserRevision": "1234", "browser": "Chromium 140.0",
            "platform": "test-x64", "nodeVersion": "v22.0.0"}


def six_briefs():
    common = {"schemaVersion": "0.2.0", "system": "instrument", "format": "html",
              "instructionBuild": "full", "title": "Synthetic workflow fixture",
              "viewports": [{"width": 1280, "height": 960}, {"width": 390, "height": 844}]}
    items = {
        ("E", "Datum", "datum"): {"label": "Verified total", "value": "42", "unit": "%",
                                      "supporting": [{"term": "Prior", "value": "38%"}],
                                      "note": "Synthetic data"},
        ("S", "Matrix", "matrix"): {"label": "Decision matrix", "columns": ["Low", "High"],
                                        "rows": [{"label": "Effort", "values": ["1", "4"]},
                                                 {"label": "Impact", "values": ["2", "5"]}],
                                        "emphasis": [1, 1], "note": "Synthetic data"},
        ("N", "Band statement", "bandStatement"): {"label": "Position",
                                                        "statement": "Clarity precedes scale.",
                                                        "figures": [{"term": "Teams", "value": "6"}],
                                                        "note": "Synthetic statement"},
        ("C", "Series", "series"): {"label": "Cases", "periods": [
            {"period": "Q1", "value": 12, "display": "12"},
            {"period": "Q2", "value": 18, "display": "18"}],
            "summary": [{"term": "Change", "value": "+6"}], "note": "Synthetic data"},
        ("W", "Running index", "runningIndex"): {"document": "Field report", "folio": "03/08",
                                                     "sections": ["Context", "Evidence", "Decision"],
                                                     "current": 2, "note": "Synthetic navigation"},
    }
    result = [brief()]
    for (job, move, kind), data in items.items():
        result.append({**common, "job": job, "move": move,
                       "content": {"kind": kind, "data": data}})
    return result


def html_for(plan):
    if plan["move"] != "Schedule":
        raise ValueError("test HTML helper covers the Schedule fixture")
    props = plan["binding"]["props"]
    parts = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>x</title>",
             "<style>body{margin:0}.test-band{width:100%;height:32px;background:#111;color:#fff}</style></head><body>",
             f'<header class="test-band"><h1 data-std-fact="title">{escape(plan["artifact"]["title"])}</h1></header><table>',
             f'<caption data-std-fact="schedule.label">{escape(props["label"])}</caption><thead><tr>']
    for field in ("ref", "description", "duration", "amount"):
        parts.append(f'<th scope="col" data-std-fact="schedule.columns.{field}">{escape(props["columns"][field])}</th>')
    parts.append("</tr></thead><tbody>")
    for index, line in enumerate(props["lines"]):
        parts.append(f'<tr><th scope="row" data-std-fact="schedule.lines.{index}.ref">{escape(line["ref"])}</th><td>')
        parts.append(f'<span data-std-fact="schedule.lines.{index}.description">{escape(line["description"])}</span>')
        if "standard" in line:
            parts.append(f'<span data-std-fact="schedule.lines.{index}.standard">{escape(line["standard"])}</span>')
        parts.append(f'</td><td data-std-fact="schedule.lines.{index}.duration">{escape(line["duration"])}</td>')
        parts.append(f'<td data-std-fact="schedule.lines.{index}.amount">{escape(line["amount"])}</td></tr>')
    parts.append("</tbody>")
    if "total" in props:
        total = props["total"]
        parts.append(f'<tfoot><tr><th scope="row" colspan="2" data-std-fact="schedule.total.label">{escape(total["label"])}</th>')
        parts.append(f'<td data-std-fact="schedule.total.duration">{escape(total["duration"])}</td>')
        parts.append(f'<td data-std-fact="schedule.total.amount">{escape(total["amount"])}</td></tr></tfoot>')
    parts.append("</table>")
    if "note" in props:
        parts.append(f'<p data-std-fact="schedule.note">{escape(props["note"])}</p>')
    parts.append("</body></html>")
    return "".join(parts)


class WorkflowEngineTests(unittest.TestCase):
    def test_manifest_and_all_six_plans_are_closed_versioned_and_reproducible(self):
        manifest = load_support_manifest()
        self.assertEqual(manifest["workflow"]["version"], "0.2.0")
        self.assertEqual(manifest["system"]["contentVersion"], "1.0.0")
        self.assertEqual(manifest["packages"]["instrument"]["version"], "2.0.0")
        self.assertEqual(manifest["packages"]["core"]["version"], "0.2.0")
        self.assertEqual(len(manifest["supported"]), 6)
        self.assertEqual(
            [(item["job"], item["jobName"], item["move"], item["contentKind"],
              item["binding"]["component"], tuple(item["requiredRelationships"]))
             for item in manifest["supported"]],
            [("E", "Evidence", "Datum", "datum", "Datum", ("datum.label-value",)),
             ("S", "Structure", "Matrix", "matrix", "Matrix",
              ("matrix.column-headers", "matrix.row-headers", "matrix.grid")),
             ("N", "Narrative", "Band statement", "bandStatement", "BandStatement",
              ("bandStatement.statement",)),
             ("C", "Change", "Series", "series", "Series",
              ("series.period-order", "series.value-association")),
             ("T", "Transaction", "Schedule", "schedule", "Schedule",
              ("schedule.named-table", "schedule.column-headers", "schedule.row-headers",
               "schedule.numeric-order", "schedule.footer")),
             ("W", "Wayfinding", "Running index", "runningIndex", "RunningIndex",
              ("runningIndex.section-order", "runningIndex.current-section"))],
        )
        for supplied in six_briefs():
            with self.subTest(move=supplied["move"]):
                plan = create_plan(supplied, read_pack, renderer_identity())
                self.assertEqual(plan["move"], supplied["move"])
                self.assertEqual(plan["content"]["kind"], supplied["content"]["kind"])
                self.assertEqual(plan["binding"]["packageVersion"], "2.0.0")
                self.assertEqual(plan["source"]["systemVersion"], "1.0.0")
                self.assertEqual(plan["source"]["supportManifestSha256"], support_manifest_sha256())
                self.assertEqual(plan["rules"], RULES)
                self.assertEqual(plan["limitations"], LIMITATIONS)
                if supplied["move"] == "Series":
                    self.assertIn({"id": "series.zero", "text": "0"}, plan["facts"])
                    self.assertIn({"id": "series.current", "text": "Current"}, plan["facts"])
                if supplied["move"] == "Running index":
                    self.assertIn({"id": "runningIndex.numbers.1", "text": "2"}, plan["facts"])
                self.assertIs(validate_plan(plan, read_pack), plan)
                validate(plan, load_schema("plan"))

    def test_plan_rejects_tuple_content_and_binding_drift(self):
        bad = brief(); bad["job"] = "E"
        with self.assertRaisesRegex(ValueError, "unsupported workflow tuple"):
            create_plan(bad, read_pack, renderer_identity())
        bad = brief(); bad["content"]["kind"] = "datum"
        with self.assertRaises(ValueError):
            create_plan(bad, read_pack, renderer_identity())
        duplicate = brief()
        duplicate["content"]["data"]["lines"][1]["ref"] = duplicate["content"]["data"]["lines"][0]["ref"]
        with self.assertRaisesRegex(ValueError, "unique"):
            create_plan(duplicate, read_pack, renderer_identity())
        # The component owns an empty-state label, so workflow 0.2 excludes empty Series
        # rather than allowing visible text outside the authoritative fact ledger.
        series = next(item for item in six_briefs() if item["move"] == "Series")
        series["content"]["data"]["periods"] = []
        with self.assertRaises(ValueError):
            create_plan(series, read_pack, renderer_identity())
        series = next(item for item in six_briefs() if item["move"] == "Series")
        series["content"]["data"]["emphasiseLast"] = False
        series_plan = create_plan(series, read_pack, renderer_identity())
        self.assertNotIn("series.current", {fact["id"] for fact in series_plan["facts"]})
        wrong_renderer = renderer_identity()
        wrong_renderer["supportManifestSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "different workflow capability bytes"):
            create_plan(brief(), read_pack, wrong_renderer)
        plan = create_plan(brief(), read_pack, renderer_identity())
        plan["binding"]["props"]["label"] = "Drifted"
        with self.assertRaisesRegex(ValueError, "binding"):
            validate_plan(plan)

    def test_context_records_selection_support_bytes_and_omissions(self):
        plan = create_plan(brief(), read_pack, renderer_identity())
        context = assemble_context(plan, read_pack)
        self.assertEqual(context["planSha256"], digest(plan))
        self.assertEqual(context["manifest"]["bytes"], len(context["content"].encode()))
        self.assertEqual(len(context["manifest"]["inputs"]), 4)
        self.assertEqual(context["manifest"]["inputs"][2]["path"], "workflow/support-manifest.json")
        self.assertIn("## Selected move", context["content"])
        self.assertIn("data-std-fact set to its exact id", context["content"])
        self.assertIn('data-standards-pack="instrument"', context["content"])
        self.assertIn("class instrument-band", context["content"])
        self.assertIn("start at x=0", context["content"])
        self.assertNotIn("| Evidence | **Datum**", context["content"])
        self.assertIn("eight unused move definitions", context["manifest"]["omitted"])

    def test_repair_retains_best_stops_identical_ties_regressions_and_stale_evidence(self):
        from tests.test_workflow_checker import evidence_for
        plan = create_plan(brief(), read_pack, renderer_identity())
        fixed = html_for(plan)
        broken = fixed.replace("£3,200", "£3,500").replace(
            "Total · excluding VAT", "Sum · excluding VAT")
        first = prepare_repair(plan, broken, render_evidence=evidence_for(plan, broken), read_pack=read_pack)
        self.assertEqual((first["action"], first["disposition"]), ("repair", "baseline"))
        self.assertTrue(first["record"]["accepted"])
        self.assertIsNone(first["record"]["baseArtifactSha256"])
        self.assertEqual(first["record"]["bestArtifactSha256"], first["record"]["artifactSha256"])
        self.assertEqual(len(first["record"]["snapshot"]["selectionKey"]), 9)
        self.assertEqual(
            list(first["record"]["snapshot"]["acceptanceMetrics"]),
            ["contractPass", "briefPass", "visibleFactCoverage",
             "minimumVisibleFactCoverageBps", "staticCoverageBps",
             "contractFactCoverageBps", "severityCounts"],
        )
        self.assertTrue(all("repairable" not in finding for finding in first["report"]["findings"]))
        self.assertTrue({finding["classification"] for finding in first["report"]["findings"]}
                        <= {"safe-model-repair", "renderer-or-configuration",
                            "human-decision", "non-repairable"})
        unchanged = prepare_repair(plan, broken, [first["record"]], evidence_for(plan, broken), read_pack)
        self.assertEqual(unchanged["disposition"], "rejected-oscillation")
        self.assertEqual(unchanged["bestArtifactSha256"], first["record"]["artifactSha256"])
        self.assertFalse(unchanged["record"]["accepted"])
        self.assertEqual(unchanged["record"]["baseArtifactSha256"], first["record"]["artifactSha256"])
        self.assertEqual(unchanged["record"]["bestArtifactSha256"], first["record"]["artifactSha256"])

        repeated_html = broken.replace("</html>", "<!-- byte-distinct --> </html>")
        repeated = prepare_repair(plan, repeated_html, [first["record"]],
                                  evidence_for(plan, repeated_html), read_pack)
        self.assertEqual(repeated["disposition"], "rejected-repeated-findings")
        self.assertEqual(repeated["rollbackArtifactSha256"], first["record"]["artifactSha256"])
        with self.assertRaisesRegex(ValueError, "cannot authorize another"):
            prepare_repair(plan, fixed, [first["record"], repeated["record"]],
                           evidence_for(plan, fixed), read_pack)
        impossible = copy.deepcopy(first["record"])
        impossible["accepted"] = False
        impossible["bestArtifactSha256"] = None
        body = {key: value for key, value in impossible.items() if key != "recordSha256"}
        impossible["recordSha256"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")).hexdigest()
        with self.assertRaisesRegex(ValueError, "acceptance and disposition"):
            prepare_repair(plan, fixed, [impossible], evidence_for(plan, fixed), read_pack)
        tied_html = broken.replace("£3,500", "£3,600").replace(
            "Sum · excluding VAT", "Subtotal · excluding VAT")
        tie = prepare_repair(plan, tied_html, [first["record"]],
                             evidence_for(plan, tied_html), read_pack)
        self.assertEqual(tie["disposition"], "rejected-tie")
        self.assertFalse(tie["record"]["accepted"])
        self.assertEqual(tie["bestArtifactSha256"], first["record"]["artifactSha256"])

        partial = fixed.replace("£3,200", "£3,500")
        second = prepare_repair(plan, partial, [first["record"]], evidence_for(plan, partial), read_pack)
        self.assertEqual((second["action"], second["disposition"]), ("repair", "accepted-improvement"))
        self.assertEqual(second["record"]["baseArtifactSha256"], first["record"]["artifactSha256"])
        self.assertEqual(second["record"]["bestArtifactSha256"], second["record"]["artifactSha256"])
        oscillation = prepare_repair(plan, broken, [first["record"], second["record"]],
                                     evidence_for(plan, broken), read_pack)
        self.assertEqual(oscillation["disposition"], "rejected-oscillation")
        self.assertEqual(oscillation["rollbackArtifactSha256"], second["record"]["artifactSha256"])

        regressive = fixed.replace(
            "Catalogue and condition assessment", "Missing catalogue assessment")
        regression = prepare_repair(plan, regressive, [first["record"], second["record"]],
                                    evidence_for(plan, regressive), read_pack)
        self.assertEqual(regression["disposition"], "rejected-regression")
        self.assertEqual(regression["record"]["snapshot"]["selectionKey"],
                         second["record"]["snapshot"]["selectionKey"])
        self.assertTrue(any("critical/error finding" in reason for reason in regression["reasons"]))

        stale = evidence_for(plan, partial); stale["artifactSha256"] = "0" * 64
        needs_evidence = prepare_repair(plan, partial, [first["record"]], stale, read_pack)
        self.assertEqual(needs_evidence["action"], "stop")
        self.assertEqual(needs_evidence["disposition"], "stopped-stale-evidence")
        self.assertEqual(needs_evidence["rollbackArtifactSha256"], first["record"]["artifactSha256"])

        complete = prepare_repair(plan, fixed, [first["record"]], evidence_for(plan, fixed), read_pack)
        self.assertEqual((complete["action"], complete["disposition"]), ("complete", "complete"))
        validate(complete, load_schema("repair"))

    def test_schema_rejects_boolean_integer_unknown_fields_and_nonfinite_numbers(self):
        schema = {"type": "object", "properties": {"count": {"type": "integer"}},
                  "required": ["count"], "additionalProperties": False}
        for value in ({"count": True}, {"count": 1, "extra": 2}):
            with self.assertRaises(ValueError): validate(value, schema)
        with self.assertRaises(ValueError): validate(float("nan"), {"type": "number"})

    def test_cli_runs_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plan.json"; renderer = Path(directory) / "renderer.json"
            renderer.write_text(json.dumps(renderer_identity()))
            result = subprocess.run([sys.executable, "-B", "-m", "workflow.cli", "plan",
                                     "--brief", str(ROOT / "examples/workflow/schedule-brief.json"),
                                     "--renderer-identity", str(renderer), "--out", str(output)],
                                    cwd=ROOT, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["move"], "Schedule")


if __name__ == "__main__":
    unittest.main()
