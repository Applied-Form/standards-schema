"""Offline integrity checks for the checked-in workflow reference receipt."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import struct
import zlib

from .checker import check_artifact
from .engine import PACK_FILES, assemble_context, canonical, create_plan, digest
from .schema import load_schema, validate


PUBLIC_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_EXAMPLES = PUBLIC_ROOT / "examples" / "workflow"
REFERENCE_MANIFEST = WORKFLOW_EXAMPLES / "reference-catalogue-r3" / "manifest.json"
MANIFEST_SCHEMA = Path(__file__).with_name("schemas") / "reference-manifest.schema.json"


def _read_bounded(path: Path, limit: int, kind: str) -> bytes:
    if path.stat().st_size > limit:
        raise ValueError(f"{kind} exceeds the {limit}-byte limit: {path.name}")
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ValueError(f"{kind} exceeds the {limit}-byte limit: {path.name}")
    return raw


def _parse_json(raw: bytes, path: Path) -> object:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"{path}: non-finite JSON number {value}")

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: invalid UTF-8 JSON: {error}") from error


def _strict_json(path: Path, limit: int) -> object:
    return _parse_json(_read_bounded(path, limit, "JSON file"), path)


def _inside(path_text: str, manifest_path: Path, workflow_root: Path, kind: str) -> Path:
    if any(ord(character) < 32 for character in path_text) or "\\" in path_text:
        raise ValueError(f"{kind} path contains unsupported characters")
    relative = Path(path_text)
    if relative.is_absolute():
        raise ValueError(f"{kind} path must be relative")
    root = workflow_root.resolve()
    target = (manifest_path.parent / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"{kind} path leaves examples/workflow: {path_text}")
    if not target.is_file():
        raise ValueError(f"{kind} file is missing: {path_text}")
    return target


def _png(path: Path) -> tuple[bytes, tuple[int, int]]:
    raw = _read_bounded(path, 2_000_000, "screenshot")
    if (len(raw) < 33 or raw[:8] != b"\x89PNG\r\n\x1a\n"
            or raw[8:12] != b"\x00\x00\x00\r" or raw[12:16] != b"IHDR"):
        raise ValueError(f"screenshot is not a PNG with a leading IHDR chunk: {path.name}")
    expected_crc = struct.unpack(">I", raw[29:33])[0]
    if zlib.crc32(raw[12:29]) & 0xffffffff != expected_crc:
        raise ValueError(f"screenshot has an invalid IHDR checksum: {path.name}")
    width, height = struct.unpack(">II", raw[16:24])
    if width <= 0 or height <= 0 or width * height > 40_000_000:
        raise ValueError(f"screenshot dimensions exceed the renderer limits: {path.name}")
    return raw, (width, height)


def _pack_reader(system: str, filename: str) -> str:
    if system != "instrument" or filename not in PACK_FILES:
        raise ValueError("reference manifest uses an unsupported pack source")
    pack = (PUBLIC_ROOT / "packs" / system).resolve()
    target = (pack / filename).resolve()
    if not target.is_relative_to(pack) or not target.is_file():
        raise ValueError(f"workflow source is missing or outside the pack: {filename}")
    return target.read_text(encoding="utf-8")


def _record(case: dict, name: str, manifest_path: Path,
            workflow_root: Path, limit: int) -> tuple[Path, bytes]:
    location = f"case {case['name']} {name} record"
    declaration = case["records"][name]
    path = _inside(declaration["file"], manifest_path, workflow_root, location)
    raw = _read_bounded(path, limit, location)
    if hashlib.sha256(raw).hexdigest() != declaration["sha256"]:
        raise ValueError(f"{location} SHA-256 differs: {declaration['file']}")
    return path, raw


def validate_reference_manifest_data(manifest: dict, path: Path = REFERENCE_MANIFEST,
                                     workflow_root: Path = WORKFLOW_EXAMPLES) -> dict:
    """Validate parsed receipt data against its public files and reproducible inputs."""
    path = Path(path).resolve()
    workflow_root = Path(workflow_root).resolve()
    manifest_schema = _strict_json(MANIFEST_SCHEMA, 500_000)
    validate(manifest, manifest_schema, path="manifest")
    validate(manifest["renderer"], load_schema("renderer-identity"), path="manifest.renderer")
    try:
        date.fromisoformat(manifest["recordedDate"])
    except ValueError as error:
        raise ValueError("manifest.recordedDate is not a calendar date") from error

    names = [case["name"] for case in manifest["cases"]]
    if len(names) != len(set(names)):
        raise ValueError("reference case names must be unique")
    screenshot_paths: set[Path] = set()

    for case in manifest["cases"]:
        location = f"case {case['name']}"
        brief_path = _inside(case["brief"], path, workflow_root, f"{location} brief")
        brief = _strict_json(brief_path, 500_000)
        validate(brief, load_schema("brief"), path=f"{location}.brief")

        plan = create_plan(brief, _pack_reader, manifest["renderer"])
        if digest(plan) != case["planSha256"]:
            raise ValueError(f"{location} planSha256 differs from the reproducible public plan")
        context = assemble_context(plan, _pack_reader)
        if context["manifest"]["sha256"] != case["contextSha256"]:
            raise ValueError(f"{location} contextSha256 differs from the reproducible public context")

        plan_path, plan_raw = _record(case, "plan", path, workflow_root, 500_000)
        retained_plan = _parse_json(plan_raw, plan_path)
        validate(retained_plan, load_schema("plan"), path=f"{location}.plan")
        if canonical(retained_plan) != canonical(plan):
            raise ValueError(f"{location} retained plan differs from the reproducible public plan")

        context_path, context_raw = _record(case, "context", path, workflow_root, 2_000_000)
        retained_context = _parse_json(context_raw, context_path)
        validate(retained_context, load_schema("context"), path=f"{location}.context")
        if canonical(retained_context) != canonical(context):
            raise ValueError(f"{location} retained context differs from the reproducible public context")

        _, artifact_raw = _record(case, "artifact", path, workflow_root, 2_000_000)
        try:
            artifact = artifact_raw.decode("utf-8")
        except UnicodeError as error:
            raise ValueError(f"{location} retained artifact is not UTF-8") from error
        if hashlib.sha256(artifact_raw).hexdigest() != case["artifactSha256"]:
            raise ValueError(f"{location} artifactSha256 differs from the retained artifact")

        evidence_path, evidence_raw = _record(case, "evidence", path, workflow_root, 5_000_000)
        evidence = _parse_json(evidence_raw, evidence_path)
        validate(evidence, load_schema("render-evidence"), path=f"{location}.evidence")
        if (evidence["planSha256"] != case["planSha256"]
                or evidence["artifactSha256"] != case["artifactSha256"]
                or canonical(evidence["renderer"]) != canonical(manifest["renderer"])):
            raise ValueError(f"{location} retained render evidence is not bound to the case")

        report_path, report_raw = _record(case, "report", path, workflow_root, 2_000_000)
        retained_report = _parse_json(report_raw, report_path)
        validate(retained_report, load_schema("report"), path=f"{location}.report")
        reproduced_report = check_artifact(plan, artifact, evidence)
        if canonical(retained_report) != canonical(reproduced_report):
            raise ValueError(f"{location} retained report differs from the offline public checker")
        if reproduced_report["status"] != case["baselineStatus"]:
            raise ValueError(f"{location} baselineStatus differs from the offline public checker")

        declared = [shot["declaredViewport"] for shot in case["screenshots"]]
        if declared != plan["artifact"]["viewports"]:
            raise ValueError(f"{location} screenshot viewports differ from the reproducible public plan")
        evidence_by_viewport = {(item["width"], item["height"]): item
                                for item in evidence["viewports"]}
        for screenshot in case["screenshots"]:
            screenshot_path = _inside(screenshot["file"], path, workflow_root,
                                      f"{location} screenshot")
            if screenshot_path in screenshot_paths:
                raise ValueError(f"screenshot file is declared more than once: {screenshot['file']}")
            screenshot_paths.add(screenshot_path)
            raw, actual = _png(screenshot_path)
            if hashlib.sha256(raw).hexdigest() != screenshot["sha256"]:
                raise ValueError(f"{location} screenshot SHA-256 differs: {screenshot['file']}")
            captured = screenshot["capturedPixels"]
            if actual != (captured["width"], captured["height"]):
                raise ValueError(f"{location} screenshot pixel dimensions differ: {screenshot['file']}")
            viewport = screenshot["declaredViewport"]
            if actual[0] != viewport["width"] or actual[1] < viewport["height"]:
                raise ValueError(f"{location} screenshot does not cover its declared viewport: {screenshot['file']}")
            observed = evidence_by_viewport.get((viewport["width"], viewport["height"]))
            if (observed is None or observed["screenshot"]["sha256"] != screenshot["sha256"]
                    or observed["screenshot"]["file"] != Path(screenshot["file"]).name):
                raise ValueError(f"{location} screenshot differs from retained render evidence: {screenshot['file']}")

    return manifest


def validate_reference_manifest(path: Path = REFERENCE_MANIFEST,
                                workflow_root: Path = WORKFLOW_EXAMPLES) -> dict:
    """Validate the public reference receipt without a browser, sibling repo or network."""
    path = Path(path).resolve()
    return validate_reference_manifest_data(_strict_json(path, 500_000), path, workflow_root)
