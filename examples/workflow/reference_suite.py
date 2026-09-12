#!/usr/bin/env python3
"""Regenerate the retained standard and 320px references for all six moves."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile


PUBLIC_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UI = PUBLIC_ROOT.parent / "standards-ui"
DEFAULT_OUT = Path(__file__).with_name("reference")
BRIEF_ROOT = Path(__file__).parent

if str(PUBLIC_ROOT) not in sys.path:
    sys.path.insert(0, str(PUBLIC_ROOT))

from workflow.checker import check_artifact  # noqa: E402
from workflow.engine import PACK_FILES, assemble_context, create_plan, digest  # noqa: E402
from workflow.schema import load_schema, validate  # noqa: E402


CASES = (
    ("reference", "schedule", Path("schedule-brief.json")),
    ("long-content", "schedule-long", Path("schedule-long-brief.json")),
    ("datum-standard", "datum-standard", Path("reference-briefs/datum-standard.json")),
    ("datum-320", "datum-320", Path("reference-briefs/datum-320.json")),
    ("matrix-standard", "matrix-standard", Path("reference-briefs/matrix-standard.json")),
    ("matrix-320", "matrix-320", Path("reference-briefs/matrix-320.json")),
    ("band-statement-standard", "band-statement-standard", Path("reference-briefs/band-statement-standard.json")),
    ("band-statement-320", "band-statement-320", Path("reference-briefs/band-statement-320.json")),
    ("series-standard", "series-standard", Path("reference-briefs/series-standard.json")),
    ("series-320", "series-320", Path("reference-briefs/series-320.json")),
    ("running-index-standard", "running-index-standard", Path("reference-briefs/running-index-standard.json")),
    ("running-index-320", "running-index-320", Path("reference-briefs/running-index-320.json")),
)


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path, limit: int = 8_000_000) -> object:
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ValueError(f"input exceeds {limit} bytes: {path.name}")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"non-finite JSON number: {value}")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def write_json(path: Path, value: object) -> bytes:
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()
    path.write_bytes(raw)
    return raw


def pack_reader(system: str, filename: str) -> str:
    if system != "instrument" or filename not in PACK_FILES:
        raise ValueError("reference suite only reads supported Instrument workflow sources")
    pack = (PUBLIC_ROOT / "packs" / system).resolve()
    target = (pack / filename).resolve()
    if not target.is_relative_to(pack) or not target.is_file():
        raise ValueError("workflow source is missing or outside the Instrument pack")
    return target.read_text(encoding="utf-8")


def run(command: list[str], cwd: Path, purpose: str, timeout: int = 180) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{purpose} failed ({result.returncode}): {detail[-4000:]}")
    return result.stdout.strip()


def png_dimensions(raw: bytes) -> tuple[int, int]:
    if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        raise ValueError("renderer output is not a PNG")
    return struct.unpack(">II", raw[16:24])


def regenerate(ui: Path, output: Path, recorded_date: str, build_ui: bool) -> dict:
    ui = ui.resolve()
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory must be new or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    node = shutil.which("node")
    npm = shutil.which("npm")
    renderer = ui / "scripts" / "workflow-render.mjs"
    if not node or not renderer.is_file():
        raise ValueError("a supported Node runtime and Standards UI renderer are required")
    if build_ui:
        if not npm:
            raise ValueError("npm is required unless --skip-build is used")
        run([npm, "run", "build"], ui, "Standards UI build")
    identity = json.loads(run([node, str(renderer), "--identity"], ui, "renderer identity"))
    validate(identity, load_schema("renderer-identity"))

    manifest_cases = []
    for name, prefix, brief_relative in CASES:
        brief_path = BRIEF_ROOT / brief_relative
        brief = read_json(brief_path, 500_000)
        validate(brief, load_schema("brief"))
        plan = create_plan(brief, pack_reader, identity)
        context = assemble_context(plan, pack_reader)
        plan_file = output / f"{prefix}-plan.json"
        context_file = output / f"{prefix}-context.json"
        plan_raw = write_json(plan_file, plan)
        context_raw = write_json(context_file, context)
        with tempfile.TemporaryDirectory(prefix=f"standards-{prefix}-") as temporary:
            stage = Path(temporary)
            run([node, str(renderer), "--plan", str(plan_file), "--out", str(stage)], ui,
                f"{name} render")
            artifact_raw = (stage / "artifact.html").read_bytes()
            evidence = read_json(stage / "render-evidence.json")
            screenshots = []
            for viewport, observed in zip(plan["artifact"]["viewports"], evidence["viewports"], strict=True):
                source = stage / observed["screenshot"]["file"]
                destination_name = f"{prefix}-{viewport['width']}x{viewport['height']}.png"
                destination = output / destination_name
                screenshot_raw = source.read_bytes()
                destination.write_bytes(screenshot_raw)
                observed["screenshot"]["file"] = destination_name
                width, height = png_dimensions(screenshot_raw)
                screenshots.append({"file": destination_name, "declaredViewport": viewport,
                                    "capturedPixels": {"width": width, "height": height},
                                    "sha256": sha256(screenshot_raw)})
        artifact_file = output / f"{prefix}.html"
        evidence_file = output / f"{prefix}-render-evidence.json"
        report_file = output / f"{prefix}-report.json"
        artifact_file.write_bytes(artifact_raw)
        evidence_raw = write_json(evidence_file, evidence)
        report = check_artifact(plan, artifact_raw.decode("utf-8"), evidence)
        if report["status"] != "pass":
            raise AssertionError(f"{name} retained reference failed: {canonical(report)}")
        report_raw = write_json(report_file, report)
        manifest_cases.append({
            "name": name,
            "brief": f"../{brief_relative.as_posix()}",
            "planSha256": digest(plan),
            "contextSha256": context["manifest"]["sha256"],
            "artifactSha256": sha256(artifact_raw),
            "baselineStatus": "pass",
            "records": {
                "plan": {"file": plan_file.name, "sha256": sha256(plan_raw)},
                "context": {"file": context_file.name, "sha256": sha256(context_raw)},
                "artifact": {"file": artifact_file.name, "sha256": sha256(artifact_raw)},
                "evidence": {"file": evidence_file.name, "sha256": sha256(evidence_raw)},
                "report": {"file": report_file.name, "sha256": sha256(report_raw)},
            },
            "screenshots": screenshots,
        })
    manifest = {
        "schemaVersion": "0.2.0", "recordedDate": recorded_date,
        "purpose": "Synthetic retained review records for all six workflow 0.2 moves at standard and 320px widths; they prove deterministic plan/render/check mechanics, not designer approval or comparative model performance.",
        "renderer": identity, "cases": manifest_cases,
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui", type=Path, default=DEFAULT_UI)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--recorded-date", default=date.today().isoformat())
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    date.fromisoformat(args.recorded_date)
    manifest = regenerate(args.ui, args.out, args.recorded_date, not args.skip_build)
    print(json.dumps({"output": str(args.out.resolve()), "cases": len(manifest["cases"])}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, RuntimeError, UnicodeError, ValueError,
            json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
