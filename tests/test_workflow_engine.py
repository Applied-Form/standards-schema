#!/usr/bin/env python3
"""Plan, selective-context and bounded-repair regressions."""
import copy
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


def read_pack(system, filename):
    return (ROOT / "packs" / system / filename).read_text(encoding="utf-8")


def brief():
    return json.loads((ROOT / "examples/workflow/schedule-brief.json").read_text())


def renderer_identity():
    return {"name": "standards-ui-workflow-render", "version": "0.1.0",
            "sourceSha256": "1" * 64, "packageVersion": "1.0.0",
            "packageEntrySha256": "2" * 64, "tokensSha256": "3" * 64,
            "fontAssetsSha256": "4" * 64, "runtimeModulesSha256": "5" * 64,
            "lockfileSha256": "6" * 64, "browserLauncherSha256": "7" * 64,
            "browserPayloadSha256": "8" * 64, "nodeExecutableSha256": "9" * 64,
            "browserRevision": "1234", "browser": "Chromium 140.0",
            "platform": "test-x64", "nodeVersion": "v22.0.0"}


def html_for(plan):
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
    def test_plan_is_closed_versioned_and_reproducible(self):
        plan = create_plan(brief(), read_pack, renderer_identity())
        self.assertEqual(plan["move"], "Schedule")
        self.assertEqual(plan["rules"], RULES)
        self.assertEqual(plan["limitations"], LIMITATIONS)
        self.assertEqual(plan["binding"]["props"]["columns"]["ref"], "REF")
        self.assertEqual(plan["binding"]["props"]["columns"]["description"], "DESCRIPTION")
        self.assertEqual(len(plan["source"]["files"]), 7)
        self.assertEqual(len(plan["source"]["implementation"]), 13)
        self.assertEqual(plan["binding"]["packageVersion"], plan["source"]["systemVersion"])
        self.assertEqual(plan["source"]["schemaVersion"], "v0.4")
        self.assertIs(validate_plan(plan, read_pack), plan)

        changed = copy.deepcopy(plan)
        changed["source"]["files"]["tokens.json"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "installed source differs"):
            validate_plan(changed, read_pack)

    def test_plan_rejects_bad_brief_and_duplicate_references(self):
        bad = brief()
        bad["job"] = "E"
        with self.assertRaises(ValueError):
            create_plan(bad, read_pack, renderer_identity())
        duplicate = brief()
        duplicate["schedule"]["lines"][1]["ref"] = duplicate["schedule"]["lines"][0]["ref"]
        with self.assertRaisesRegex(ValueError, "references must be unique"):
            create_plan(duplicate, read_pack, renderer_identity())
        normalized_duplicate = brief()
        normalized_duplicate["schedule"]["lines"][1]["ref"] = "  01  "
        with self.assertRaisesRegex(ValueError, "references must be unique"):
            create_plan(normalized_duplicate, read_pack, renderer_identity())

    def test_context_records_selection_bytes_and_omissions(self):
        plan = create_plan(brief(), read_pack, renderer_identity())
        context = assemble_context(plan, read_pack)
        self.assertEqual(context["planSha256"], digest(plan))
        self.assertEqual(context["manifest"]["bytes"], len(context["content"].encode()))
        self.assertIsNone(context["manifest"]["tokens"])
        self.assertIn("## Selected move", context["content"])
        self.assertNotIn("| Evidence | **Datum**", context["content"])
        self.assertIn("eight unused move definitions", context["manifest"]["omitted"])
        compact_brief = brief()
        compact_brief["instructionBuild"] = "compact"
        compact_plan = create_plan(compact_brief, read_pack, renderer_identity())
        compact = assemble_context(compact_plan, read_pack)
        self.assertEqual(compact["manifest"]["inputs"][0]["path"], "SKILL-compact.md")
        self.assertIn("## 3 · Conflict register", compact["content"])

    def test_repair_history_is_hash_chained_and_stops_after_two_attempts(self):
        plan = create_plan(brief(), read_pack, renderer_identity())
        broken = html_for(plan).replace("£3,200", "£3,500")
        first = prepare_repair(plan, broken, read_pack=read_pack)
        self.assertEqual(first["action"], "repair")
        second = prepare_repair(plan, broken, [first["record"]], read_pack=read_pack)
        self.assertEqual(second["action"], "repair")
        third = prepare_repair(plan, broken, [first["record"], second["record"]], read_pack=read_pack)
        self.assertEqual(third["action"], "stop")
        self.assertEqual(third["remainingRepairs"], 0)
        damaged = copy.deepcopy(first["record"])
        damaged["artifactSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "valid chain"):
            prepare_repair(plan, broken, [damaged], read_pack=read_pack)

        fixed = html_for(plan)
        from tests.test_workflow_checker import evidence_for
        complete = prepare_repair(plan, fixed, [first["record"]],
                                  evidence_for(plan, fixed), read_pack)
        self.assertEqual(complete["action"], "complete")
        validate(complete, load_schema("repair"))

    def test_schema_rejects_boolean_integer_unknown_fields_and_nonfinite_numbers(self):
        schema = {"type": "object", "properties": {"count": {"type": "integer"}},
                  "required": ["count"], "additionalProperties": False}
        for value in ({"count": True}, {"count": 1, "extra": 2}):
            with self.assertRaises(ValueError):
                validate(value, schema)
        with self.assertRaises(ValueError):
            validate(float("nan"), {"type": "number"})
        validate(create_plan(brief(), read_pack, renderer_identity()), load_schema("plan"))

    def test_cli_runs_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plan.json"
            renderer = Path(directory) / "renderer.json"
            renderer.write_text(json.dumps(renderer_identity()))
            result = subprocess.run([sys.executable, "-B", "-m", "workflow.cli", "plan",
                                     "--brief", str(ROOT / "examples/workflow/schedule-brief.json"),
                                     "--renderer-identity", str(renderer),
                                     "--out", str(output)], cwd=ROOT, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["move"], "Schedule")


if __name__ == "__main__":
    unittest.main()
