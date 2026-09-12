#!/usr/bin/env python3
"""Run the real public-plan -> Standards UI -> check/repair reference loop.

The harness has no Python package dependencies. It invokes the sibling
``standards-ui`` renderer as a subprocess and retains each plan, context,
artifact, evidence file, report, decision and repair-history record.
"""
from __future__ import annotations

import argparse
from html import escape, unescape
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


PUBLIC_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BRIEF = Path(__file__).with_name("schedule-brief.json")
DEFAULT_UI = PUBLIC_ROOT.parent / "standards-ui"
TARGET_FACT = "schedule.total.amount"

if str(PUBLIC_ROOT) not in sys.path:
    sys.path.insert(0, str(PUBLIC_ROOT))

from workflow.checker import check_artifact  # noqa: E402
from workflow.engine import (  # noqa: E402
    PACK_FILES,
    assemble_context,
    create_plan,
    digest,
    prepare_repair,
)
from workflow.schema import load_schema, validate  # noqa: E402


def _parse_json(text: str):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"non-finite JSON number: {value}")

    return json.loads(text, object_pairs_hook=object_pairs, parse_constant=invalid_constant)


def _load_json(path: Path, limit: int = 8_000_000):
    data = path.read_bytes()
    if len(data) > limit:
        raise ValueError(f"{path} exceeds the {limit}-byte reference-loop limit")
    return _parse_json(data.decode("utf-8"))


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
                    encoding="utf-8")


def _pack_reader(system: str, filename: str) -> str:
    if system != "instrument" or filename not in PACK_FILES:
        raise ValueError("reference loop only reads supported Instrument workflow sources")
    pack = (PUBLIC_ROOT / "packs" / system).resolve()
    target = (pack / filename).resolve()
    if not target.is_relative_to(pack) or not target.is_file():
        raise ValueError("workflow source is missing or outside the Instrument pack")
    return target.read_text(encoding="utf-8")


def _run(command: list[str], cwd: Path, purpose: str) -> str:
    try:
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=180)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{purpose} exceeded the 180-second limit") from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{purpose} failed ({result.returncode}): {detail[-4000:]}")
    return result.stdout.strip()


def _renderer_command(ui: Path) -> list[str]:
    script = ui / "scripts" / "workflow-render.mjs"
    if not script.is_file():
        raise ValueError(f"Standards UI renderer not found at {script}")
    node = shutil.which("node")
    if not node:
        raise ValueError("node is required to run the Standards UI renderer")
    return [node, str(script)]


def _renderer_identity(ui: Path) -> dict:
    output = _run([*_renderer_command(ui), "--identity"], ui, "renderer identity")
    identity = _parse_json(output)
    if not isinstance(identity, dict):
        raise ValueError("renderer identity must be a JSON object")
    return identity


def _render(ui: Path, plan_path: Path, stage: Path, html_path: Path | None = None) -> tuple[str, dict]:
    command = [*_renderer_command(ui), "--plan", str(plan_path), "--out", str(stage)]
    if html_path is not None:
        command.extend(["--html", str(html_path)])
    _run(command, ui, f"render stage {stage.name}")
    artifact = (stage / "artifact.html").read_text(encoding="utf-8")
    evidence = _load_json(stage / "render-evidence.json", 3_500_000)
    return artifact, evidence


def _fact_pattern(identifier: str) -> re.Pattern[str]:
    quoted = re.escape(identifier)
    return re.compile(
        rf'(?P<open><(?P<tag>[a-z][a-z0-9:-]*)\b[^>]*\bdata-std-fact='
        rf'(?P<quote>["\']){quoted}(?P=quote)[^>]*>)(?P<body>.*?)(?P<close></(?P=tag)\s*>)',
        re.IGNORECASE | re.DOTALL,
    )


def replace_fact_text(html: str, identifier: str, expected: str, replacement: str) -> str:
    """Replace one plain-text fact marker while proving the expected value was present."""
    matches = list(_fact_pattern(identifier).finditer(html))
    if len(matches) != 1:
        raise ValueError(f"expected one {identifier} marker, found {len(matches)}")
    match = matches[0]
    if "<" in match.group("body") or unescape(match.group("body")) != expected:
        raise ValueError(f"{identifier} is not the expected plain-text marker")
    body = escape(replacement, quote=False)
    return html[:match.start("body")] + body + html[match.end("body"):]


def _require_status(report: dict, status: str, stage: str) -> None:
    validate(report, load_schema("report"))
    if report["status"] != status:
        failures = [f"{item['ruleId']}:{item['status']}" for item in report["findings"]
                    if item["status"] != "pass"]
        raise AssertionError(f"{stage} expected {status}, got {report['status']}: {failures[:20]}")


def _failed_rules(report: dict) -> list[str]:
    return sorted({item["ruleId"] for item in report["findings"] if item["status"] == "fail"})


def run_reference_loop(brief_path: Path, ui: Path, output: Path, build_ui: bool = True) -> dict:
    ui = ui.resolve()
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory must be new or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    if build_ui:
        npm = shutil.which("npm")
        if not npm:
            raise ValueError("npm is required unless --skip-build is used")
        _run([npm, "run", "build"], ui, "Standards UI build")

    brief = _load_json(brief_path, 500_000)
    renderer = _renderer_identity(ui)
    _write_json(output / "brief.json", brief)
    _write_json(output / "renderer-identity.json", renderer)

    plan = create_plan(brief, _pack_reader, renderer)
    plan_path = output / "plan.json"
    _write_json(plan_path, plan)
    context = assemble_context(plan, _pack_reader)
    _write_json(output / "context.json", context)

    baseline_html, baseline_evidence = _render(ui, plan_path, output / "00-baseline")
    baseline_report = check_artifact(plan, baseline_html, baseline_evidence)
    _require_status(baseline_report, "pass", "baseline")
    _write_json(output / "00-baseline-report.json", baseline_report)

    expected = next(fact["text"] for fact in plan["facts"] if fact["id"] == TARGET_FACT)
    seeded = f"[seeded defect] {expected}"
    defective_html = replace_fact_text(baseline_html, TARGET_FACT, expected, seeded)
    defective_source = output / "01-defect-source.html"
    defective_source.write_text(defective_html, encoding="utf-8")
    defective_html, defective_evidence = _render(
        ui, plan_path, output / "01-defect", defective_source)
    defect_report = check_artifact(plan, defective_html, defective_evidence)
    _require_status(defect_report, "fail", "seeded defect")
    if "facts.exact" not in _failed_rules(defect_report):
        raise AssertionError("seeded defect did not fail the exact-fact source rule")
    _write_json(output / "01-defect-report.json", defect_report)

    first = prepare_repair(plan, defective_html, render_evidence=defective_evidence,
                           read_pack=_pack_reader)
    if first["action"] != "repair" or first["record"]["turn"] != 0:
        raise AssertionError("first failed artifact did not produce repair turn zero")
    _write_json(output / "01-repair-decision.json", first)
    success_history = [first["record"]]
    _write_json(output / "success-history.json", success_history)

    repaired_source_text = replace_fact_text(defective_html, TARGET_FACT, seeded, expected)
    if repaired_source_text != baseline_html:
        raise AssertionError("targeted repair changed bytes outside the seeded fact")
    repaired_source = output / "02-repaired-source.html"
    repaired_source.write_text(repaired_source_text, encoding="utf-8")
    repaired_html, repaired_evidence = _render(
        ui, plan_path, output / "02-repaired", repaired_source)
    repaired_report = check_artifact(plan, repaired_html, repaired_evidence)
    _require_status(repaired_report, "pass", "fresh repaired render")
    if repaired_report["artifactSha256"] == defect_report["artifactSha256"]:
        raise AssertionError("fresh repair evidence is still bound to the defective artifact")
    _write_json(output / "02-repaired-report.json", repaired_report)
    completed = prepare_repair(plan, repaired_html, history=success_history,
                               render_evidence=repaired_evidence, read_pack=_pack_reader)
    if completed["action"] != "complete":
        raise AssertionError("repaired artifact did not complete the workflow")
    _write_json(output / "02-complete-decision.json", completed)

    persistent_one_html, persistent_one_evidence = _render(
        ui, plan_path, output / "03-persistent-turn-1", defective_source)
    second = prepare_repair(plan, persistent_one_html, history=[first["record"]],
                            render_evidence=persistent_one_evidence, read_pack=_pack_reader)
    if second["action"] != "repair" or second["record"]["turn"] != 1:
        raise AssertionError("persistent defect did not consume the second repair decision")
    persistent_history = [first["record"], second["record"]]
    _write_json(output / "persistent-history.json", persistent_history)
    _write_json(output / "03-persistent-decision.json", second)

    persistent_two_html, persistent_two_evidence = _render(
        ui, plan_path, output / "04-persistent-turn-2", defective_source)
    stopped = prepare_repair(plan, persistent_two_html, history=persistent_history,
                             render_evidence=persistent_two_evidence, read_pack=_pack_reader)
    if (stopped["action"] != "stop" or stopped["remainingRepairs"] != 0
            or stopped["report"]["status"] != "fail"):
        raise AssertionError("persistent defect did not stop with an unresolved failure")
    _write_json(output / "04-stop-decision.json", stopped)

    summary = {
        "schemaVersion": "0.1.0",
        "planSha256": digest(plan),
        "contextSha256": context["manifest"]["sha256"],
        "renderer": renderer,
        "baseline": {"status": baseline_report["status"],
                     "artifactSha256": baseline_report["artifactSha256"]},
        "seededDefect": {"factId": TARGET_FACT, "expected": expected, "seeded": seeded,
                         "status": defect_report["status"], "failedRules": _failed_rules(defect_report),
                         "nextAction": first["action"]},
        "repaired": {"status": repaired_report["status"], "nextAction": completed["action"],
                     "artifactSha256": repaired_report["artifactSha256"]},
        "persistentFailure": {"actions": [first["action"], second["action"], stopped["action"]],
                              "status": stopped["report"]["status"],
                              "remainingRepairs": stopped["remainingRepairs"],
                              "failedRules": _failed_rules(stopped["report"])},
    }
    _write_json(output / "summary.json", summary)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, default=DEFAULT_BRIEF,
                        help="fixed-content Schedule brief (renderer identity is replaced locally)")
    parser.add_argument("--ui", type=Path, default=DEFAULT_UI,
                        help="standards-ui checkout containing the real renderer")
    parser.add_argument("--out", type=Path,
                        help="new or empty output directory; defaults to a temporary directory")
    parser.add_argument("--skip-build", action="store_true",
                        help="use an already-built standards-ui checkout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.out or Path(tempfile.mkdtemp(prefix="standards-reference-loop-"))
    summary = run_reference_loop(args.brief, args.ui, output, build_ui=not args.skip_build)
    print(json.dumps({"output": str(output.resolve()), "summary": summary}, ensure_ascii=False,
                     allow_nan=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, RuntimeError, UnicodeError, ValueError,
            json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
