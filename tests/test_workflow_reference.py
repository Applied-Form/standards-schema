#!/usr/bin/env python3
"""Offline integrity regressions for the checked-in workflow reference receipt."""

import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workflow.reference import (REFERENCE_MANIFEST, validate_reference_manifest,
                                validate_reference_manifest_data)


class WorkflowReferenceTests(unittest.TestCase):
    def test_checked_in_reference_manifest_is_internally_consistent(self):
        manifest = validate_reference_manifest()
        self.assertEqual(len(manifest["cases"]), 12)
        plans = [json.loads((REFERENCE_MANIFEST.parent / case["records"]["plan"]["file"])
                            .read_text(encoding="utf-8")) for case in manifest["cases"]]
        by_move = {}
        for plan in plans:
            by_move.setdefault(plan["move"], []).append(plan["artifact"]["viewports"])
        self.assertEqual(set(by_move), {
            "Datum", "Matrix", "Band statement", "Series", "Schedule", "Running index",
        })
        for move, viewports in by_move.items():
            with self.subTest(move=move):
                self.assertEqual(len(viewports), 2)
                self.assertTrue(any(any(viewport["width"] >= 390 for viewport in case)
                                    for case in viewports))
                self.assertTrue(any(case == [{"width": 320, "height": 844}]
                                    for case in viewports))

    def test_renderer_paths_hashes_dimensions_and_derived_records_are_enforced(self):
        original = json.loads(REFERENCE_MANIFEST.read_text(encoding="utf-8"))
        validate_reference_manifest_data(original)
        cases = []

        unknown_shape = copy.deepcopy(original)
        unknown_shape["unexpected"] = True
        cases.append((unknown_shape, "unknown field unexpected"))

        missing_renderer_field = copy.deepcopy(original)
        missing_renderer_field["renderer"].pop("browserPayloadSha256")
        cases.append((missing_renderer_field, "missing required field browserPayloadSha256"))

        escaping_brief = copy.deepcopy(original)
        escaping_brief["cases"][0]["brief"] = "../../../README.md"
        cases.append((escaping_brief, "brief path leaves examples/workflow"))

        escaping_screenshot = copy.deepcopy(original)
        escaping_screenshot["cases"][0]["screenshots"][0]["file"] = "../../../README.md.png"
        cases.append((escaping_screenshot, "screenshot path leaves examples/workflow"))

        bad_screenshot_hash = copy.deepcopy(original)
        bad_screenshot_hash["cases"][0]["screenshots"][0]["sha256"] = "0" * 64
        cases.append((bad_screenshot_hash, "screenshot SHA-256 differs"))

        bad_dimensions = copy.deepcopy(original)
        bad_dimensions["cases"][0]["screenshots"][0]["capturedPixels"]["height"] += 1
        cases.append((bad_dimensions, "screenshot pixel dimensions differ"))

        bad_plan_hash = copy.deepcopy(original)
        bad_plan_hash["cases"][0]["planSha256"] = "0" * 64
        cases.append((bad_plan_hash, "planSha256 differs"))

        bad_context_hash = copy.deepcopy(original)
        bad_context_hash["cases"][0]["contextSha256"] = "0" * 64
        cases.append((bad_context_hash, "contextSha256 differs"))

        bad_record_hash = copy.deepcopy(original)
        bad_record_hash["cases"][0]["records"]["plan"]["sha256"] = "0" * 64
        cases.append((bad_record_hash, "plan record SHA-256 differs"))

        for manifest, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    validate_reference_manifest_data(manifest)


if __name__ == "__main__":
    unittest.main()
