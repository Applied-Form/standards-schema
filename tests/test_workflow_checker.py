#!/usr/bin/env python3
"""Fact, semantics and browser-evidence checker regressions."""
import copy
import base64
import hashlib
from html import escape
import json
from pathlib import Path
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workflow.checker import check_artifact, normalize_text
from workflow.engine import create_plan, digest, sha256
from workflow.schema import load_schema, validate
from tests.test_workflow_engine import brief, html_for, read_pack, renderer_identity, six_briefs


def _png(width, height):
    def chunk(kind, payload):
        return (len(payload).to_bytes(4, "big") + kind + payload
                + (zlib.crc32(kind + payload) & 0xffffffff).to_bytes(4, "big"))
    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    row = b"\x00" + b"\xff\xff\xff" * width
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(row * height)) + chunk(b"IEND", b"")


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
    for viewport in plan["artifact"]["viewports"]:
        png = _png(viewport["width"], viewport["height"])
        viewports.append({**viewport,
            "document": {"clientWidth": viewport["width"], "clientHeight": viewport["height"],
                         "scrollWidth": viewport["width"], "scrollHeight": viewport["height"] + 100},
            "bodyTextLength": 100, "overflowingElements": [], "pageErrors": [], "blockedRequests": [],
            "facts": copy.deepcopy(facts), "unmarkedText": [],
            "semanticChecks": {"move": plan["move"], "oneVisibleH1": True,
                               "relationships": [{"id": identifier, "passed": True}
                                                 for identifier in plan["requiredRelationships"]]},
            "invariantBand": {"count": 1, "containsTitle": True,
                              "bounds": {"x": 0, "y": 0, "width": viewport["width"], "height": 32},
                              "backgroundColor": "rgb(17, 17, 17)",
                              "titleColor": "rgb(255, 255, 255)",
                              "borderWidths": {"top": 0, "right": 0, "bottom": 0, "left": 0}},
            "screenshot": {"file": f'schedule-{viewport["width"]}x{viewport["height"]}.png',
                           "sha256": hashlib.sha256(png).hexdigest(),
                           "dataBase64": base64.b64encode(png).decode("ascii")}})
    return {"schemaVersion": "0.2.0", "planSha256": digest(plan), "artifactSha256": sha256(html),
            "renderer": copy.deepcopy(plan["renderer"]), "viewports": viewports}


class WorkflowCheckerTests(unittest.TestCase):
    def setUp(self):
        self.plan = create_plan(brief(), read_pack, renderer_identity())
        self.html = html_for(self.plan)

    def test_complete_hash_bound_evidence_passes(self):
        report = check_artifact(self.plan, self.html, evidence_for(self.plan, self.html))
        self.assertEqual(report["status"], "pass")
        validate(report, load_schema("report"))
        self.assertTrue(all(finding["status"] == "pass" for finding in report["findings"]))
        self.assertLess(report["summary"]["total"], 30)

    def test_valid_schedule_without_total_accepts_matching_no_footer_evidence(self):
        plan = copy.deepcopy(self.plan)
        del plan["content"]["data"]["total"]
        del plan["binding"]["props"]["total"]
        plan["facts"] = [fact for fact in plan["facts"]
                         if not fact["id"].startswith("schedule.total.")]
        html = html_for(plan)
        self.assertNotIn("<tfoot>", html)
        evidence = evidence_for(plan, html)
        self.assertTrue(all(all(item["passed"] for item in viewport["semanticChecks"]["relationships"])
                            for viewport in evidence["viewports"]))
        report = check_artifact(plan, html, evidence)
        self.assertEqual(report["status"], "pass")
        with_empty_footer = html.replace("</table>", "<tfoot></tfoot></table>")
        report = check_artifact(plan, with_empty_footer, evidence_for(plan, with_empty_footer))
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(finding["ruleId"] == "move.semantics"
                            and finding["status"] == "fail" for finding in report["findings"]))
        with_hidden_footer = html.replace("</table>", "<tfoot hidden></tfoot></table>")
        self.assertEqual(check_artifact(
            plan, with_hidden_footer, evidence_for(plan, with_hidden_footer))["status"], "fail")

    def test_missing_or_stale_render_evidence_remains_unknown(self):
        missing = check_artifact(self.plan, self.html)
        self.assertEqual(missing["status"], "unknown")
        stale = evidence_for(self.plan, self.html)
        stale["artifactSha256"] = "0" * 64
        report = check_artifact(self.plan, self.html, stale)
        self.assertEqual(report["status"], "unknown")
        self.assertIn("stale", next(f["observed"] for f in report["findings"] if f["ruleId"] == "render.binding"))
        unknown_rules = {finding["ruleId"] for finding in missing["findings"]
                         if finding["status"] == "unknown"}
        self.assertTrue({"render.binding", "render.viewport_fit", "render.facts",
                         "render.semantics", "instrument.invariant_band",
                         "render.screenshot"}.issubset(unknown_rules))

    def test_changed_hidden_duplicate_and_invented_facts_fail(self):
        variants = {
            "changed": self.html.replace("£3,200", "£3,500"),
            "hidden": self.html.replace('data-std-fact="schedule.total.amount"',
                                        'data-std-fact="schedule.total.amount" hidden'),
            "duplicate": self.html.replace("</body>", '<p data-std-fact="schedule.total.amount">£3,200</p></body>'),
            "invented": self.html.replace("</body>", "<p>Valid for 30 days</p></body>"),
        }
        for name, html in variants.items():
            with self.subTest(name=name):
                report = check_artifact(self.plan, html, evidence_for(self.plan, html))
                self.assertEqual(report["status"], "fail")
                self.assertTrue(any(f["status"] == "fail" and f["severity"] == "critical"
                                    for f in report["findings"]))

    def test_unsafe_active_html_and_bad_semantics_fail(self):
        active = self.html.replace("</body>", "<script>alert(1)</script></body>")
        self.assertEqual(check_artifact(self.plan, active)["status"], "fail")
        interactive = self.html.replace("</body>", '<input type="button" value="Approve £9,999 now"></body>')
        self.assertEqual(check_artifact(self.plan, interactive)["status"], "fail")
        animated = self.html.replace("</style>", "@keyframes hide{to{opacity:0}}body{animation:hide 2s}</style>")
        self.assertEqual(check_artifact(self.plan, animated)["status"], "fail")
        alternate_text_fill = self.html.replace(
            "</style>",
            "[data-std-fact]{color:#111;-webkit-text-fill-color:#fff;background:#fff}</style>",
        )
        self.assertEqual(check_artifact(self.plan, alternate_text_fill)["status"], "fail")
        alternate_text_stroke = self.html.replace(
            "</style>",
            "[data-std-fact]{-webkit-text-stroke:12px #fff;text-shadow:0 0 8px #fff}</style>",
        )
        self.assertEqual(check_artifact(self.plan, alternate_text_stroke)["status"], "fail")
        gradient = self.html.replace("</style>", ".test-band{background:linear-gradient(#111,#fff)}</style>")
        self.assertEqual(check_artifact(self.plan, gradient)["status"], "fail")
        shadow = self.html.replace("</style>", ".test-band{box-shadow:0 0 20px #fff}</style>")
        self.assertEqual(check_artifact(self.plan, shadow)["status"], "fail")
        duplicate_ids = self.html.replace("<body>", '<body><span id="x" hidden>invented</span><span id="x" hidden>text</span>')
        self.assertEqual(check_artifact(self.plan, duplicate_ids)["status"], "fail")
        for bad_table in (self.html.replace('scope="col"', '', 1),
                          self.html.replace('scope="col"', 'scope="col" colspan="2"', 1),
                          self.html.replace('<th scope="row" colspan="2" data-std-fact="schedule.total.label"',
                                            '<td colspan="2" data-std-fact="schedule.total.label"')
                                   .replace('</th><td data-std-fact="schedule.total.duration"',
                                            '</td><td data-std-fact="schedule.total.duration"')):
            self.assertEqual(check_artifact(self.plan, bad_table)["status"], "fail")

    def test_misplaced_series_period_markers_are_bounded_semantic_failures(self):
        supplied = next(item for item in six_briefs() if item["move"] == "Series")
        plan = create_plan(supplied, read_pack, renderer_identity())
        markers = []
        for fact in plan["facts"]:
            if fact["id"] == "title":
                markers.append(f'<h1 data-std-fact="title">{escape(fact["text"])}</h1>')
            else:
                markers.append(
                    f'<p data-std-fact="{fact["id"]}">{escape(fact["text"])}</p>')
        html = ("<!doctype html><html><head><title>x</title></head><body><section>"
                + "".join(markers) + "<ol></ol></section></body></html>")
        report = check_artifact(plan, html)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(finding["ruleId"] == "move.semantics"
                            and finding["status"] == "fail" for finding in report["findings"]))

    def test_total_facts_must_remain_in_their_declared_footer_columns(self):
        swapped = (self.html
                   .replace('data-std-fact="schedule.total.duration"',
                            'data-std-fact="schedule.total.swap"', 1)
                   .replace('data-std-fact="schedule.total.amount"',
                            'data-std-fact="schedule.total.duration"', 1)
                   .replace('data-std-fact="schedule.total.swap"',
                            'data-std-fact="schedule.total.amount"', 1))
        report = check_artifact(self.plan, swapped, evidence_for(self.plan, swapped))
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(finding["ruleId"] == "move.semantics"
                            and finding["status"] == "fail" for finding in report["findings"]))
        extra_hidden_footer = self.html.replace("</table>", "<tfoot hidden></tfoot></table>")
        report = check_artifact(
            self.plan, extra_hidden_footer, evidence_for(self.plan, extra_hidden_footer))
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(finding["ruleId"] == "move.semantics"
                            and finding["status"] == "fail" for finding in report["findings"]))

    def test_render_overflow_and_clipped_fact_fail(self):
        evidence = evidence_for(self.plan, self.html)
        evidence["viewports"][0]["document"]["scrollWidth"] += 20
        evidence["viewports"][1]["facts"][0]["clipped"] = True
        report = check_artifact(self.plan, self.html, evidence)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(f["ruleId"] == "render.viewport_fit" and f["status"] == "fail"
                            for f in report["findings"]))
        self.assertTrue(any(f["ruleId"] == "render.facts" and f["status"] == "fail"
                            for f in report["findings"]))
        wrong_order = evidence_for(self.plan, self.html)
        next(item for item in wrong_order["viewports"][0]["semanticChecks"]["relationships"]
             if item["id"] == "schedule.numeric-order")["passed"] = False
        report = check_artifact(self.plan, self.html, wrong_order)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(f["ruleId"] == "render.semantics" and f["status"] == "fail"
                            for f in report["findings"]))

    def test_wrong_invariant_band_fails_even_when_other_render_checks_pass(self):
        evidence = evidence_for(self.plan, self.html)
        evidence["viewports"][0]["invariantBand"]["bounds"]["height"] = 24
        evidence["viewports"][1]["invariantBand"]["containsTitle"] = False
        report = check_artifact(self.plan, self.html, evidence)
        self.assertEqual(report["status"], "fail")
        failures = [finding for finding in report["findings"]
                    if finding["ruleId"] == "instrument.invariant_band"
                    and finding["status"] == "fail"]
        self.assertEqual(len(failures), 2)
        displaced = evidence_for(self.plan, self.html)
        displaced["viewports"][0]["invariantBand"]["bounds"]["y"] = 200
        displaced["viewports"][0]["facts"][0]["bounds"]["y"] = 100
        self.assertEqual(check_artifact(self.plan, self.html, displaced)["status"], "fail")
        bordered = evidence_for(self.plan, self.html)
        bordered["viewports"][0]["invariantBand"]["borderWidths"]["left"] = 16
        self.assertEqual(check_artifact(self.plan, self.html, bordered)["status"], "fail")

    def test_malformed_invariant_band_evidence_is_bounded_unknown(self):
        variants = []
        bad_colour = evidence_for(self.plan, self.html)
        bad_colour["viewports"][0]["invariantBand"]["backgroundColor"] = 7
        variants.append(bad_colour)
        bad_bounds = evidence_for(self.plan, self.html)
        bad_bounds["viewports"][0]["invariantBand"]["bounds"] = {}
        variants.append(bad_bounds)
        for evidence in variants:
            with self.subTest(evidence=evidence):
                report = check_artifact(self.plan, self.html, evidence)
                self.assertEqual(report["status"], "unknown")
                binding = next(finding for finding in report["findings"]
                               if finding["ruleId"] == "render.binding")
                self.assertEqual(binding["status"], "unknown")
                self.assertIn("schema", binding["observed"])

    def test_renderer_viewport_and_screenshot_provenance_are_bound(self):
        variants = []
        renderer = evidence_for(self.plan, self.html)
        renderer["renderer"]["sourceSha256"] = "0" * 64
        variants.append(renderer)
        viewport = evidence_for(self.plan, self.html)
        viewport["viewports"][0]["document"]["clientWidth"] = 1
        variants.append(viewport)
        screenshot = evidence_for(self.plan, self.html)
        screenshot["viewports"][0]["screenshot"]["sha256"] = "0" * 64
        variants.append(screenshot)
        for evidence in variants:
            with self.subTest(evidence=evidence):
                report = check_artifact(self.plan, self.html, evidence)
                self.assertNotEqual(report["status"], "pass")
                validate(report, load_schema("report"))

    def test_column_heading_allows_two_intact_lines_but_rejects_three(self):
        evidence = evidence_for(self.plan, self.html)
        heading = next(fact for fact in evidence["viewports"][0]["facts"]
                       if fact["id"] == "schedule.columns.duration")
        heading["lineCount"] = 2
        report = check_artifact(self.plan, self.html, evidence)
        self.assertEqual(report["status"], "pass")
        heading["lineCount"] = 3
        report = check_artifact(self.plan, self.html, evidence)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(f["location"].endswith("/schedule.columns.duration")
                            and f["status"] == "fail" for f in report["findings"]))

    def test_invalid_plan_and_html_size_are_bounded_failures(self):
        bad = copy.deepcopy(self.plan)
        bad["facts"].pop()
        report = check_artifact(bad, self.html)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["findings"][0]["ruleId"], "plan.valid")
        report = check_artifact(self.plan, "x" * 2_000_001)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["findings"][-1]["ruleId"], "html.structure")

    def test_compatibility_characters_are_not_collapsed_into_different_facts(self):
        self.assertNotEqual(normalize_text("Ⅰ"), normalize_text("I"))
        self.assertNotEqual(normalize_text("²"), normalize_text("2"))

    def test_report_stays_schema_valid_under_marker_flood(self):
        flooded = self.html.replace("</body>",
            "".join(f'<i data-std-fact="extra.{index}">x</i>' for index in range(1001)) + "</body>")
        report = check_artifact(self.plan, flooded)
        self.assertEqual(report["status"], "fail")
        self.assertLessEqual(len(report["findings"]), 1000)
        validate(report, load_schema("report"))


if __name__ == "__main__":
    unittest.main()
