"""Canonical workflow support declaration and exact binding lookup."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .schema import load_schema, validate


SUPPORT_MANIFEST = Path(__file__).with_name("support-manifest.json")


def _strict_json(raw: bytes) -> dict:
    def object_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate support-manifest key: {key}")
            value[key] = item
        return value

    def reject_constant(value):
        raise ValueError(f"non-finite support-manifest number: {value}")

    parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs,
                        parse_constant=reject_constant)
    if not isinstance(parsed, dict):
        raise ValueError("support manifest must be an object")
    return parsed


def support_manifest_bytes() -> bytes:
    raw = SUPPORT_MANIFEST.read_bytes()
    if len(raw) > 200_000:
        raise ValueError("support manifest exceeds its 200000-byte limit")
    return raw


def support_manifest_sha256() -> str:
    return hashlib.sha256(support_manifest_bytes()).hexdigest()


def load_support_manifest() -> dict:
    """Return a validated copy of the canonical public support declaration."""
    manifest = _strict_json(support_manifest_bytes())
    validate(manifest, load_schema("support-manifest"), path="supportManifest")
    supported = manifest["supported"]
    keys = [(item["job"], item["move"], item["format"], item["contentKind"])
            for item in supported]
    if len(keys) != len(set(keys)):
        raise ValueError("support manifest contains duplicate workflow tuples")
    expected = {
        ("E", "Evidence", "Plate", "html", "plate", "Plate", "plate", ("plate.rows", "plate.scales")),
        ("E", "Evidence", "Register", "html", "register", "Register", "register", ("register.figures",)),
        ("S", "Structure", "Key", "html", "key", "Key", "key", ("key.entries", "key.marks")),
        ("E", "Evidence", "Datum", "html", "datum", "Datum", "datum",
         ("datum.label-value",)),
        ("S", "Structure", "Matrix", "html", "matrix", "Matrix", "matrix",
         ("matrix.column-headers", "matrix.row-headers", "matrix.grid")),
        ("N", "Narrative", "Band statement", "html", "bandStatement", "BandStatement",
         "bandStatement", ("bandStatement.statement",)),
        ("C", "Change", "Series", "html", "series", "Series", "series",
         ("series.period-order", "series.value-association")),
        ("T", "Transaction", "Schedule", "html", "schedule", "Schedule", "schedule",
         ("schedule.named-table", "schedule.column-headers", "schedule.row-headers",
          "schedule.numeric-order", "schedule.footer")),
        ("W", "Wayfinding", "Running index", "html", "runningIndex", "RunningIndex",
         "runningIndex", ("runningIndex.section-order", "runningIndex.current-section")),
    }
    actual = {(item["job"], item["jobName"], item["move"], item["format"],
               item["contentKind"], item["binding"]["component"],
               item["binding"]["factPrefix"], tuple(item["requiredRelationships"]))
              for item in supported}
    if actual != expected:
        raise ValueError("support manifest differs from the nine admitted workflow bindings")
    for item in supported:
        if (item["binding"]["package"] != manifest["packages"]["instrument"]["name"]
                or item["binding"]["packageVersion"]
                != manifest["packages"]["instrument"]["version"]):
            raise ValueError("support binding differs from the declared Instrument package")
        relationships = item["requiredRelationships"]
        if len(relationships) != len(set(relationships)):
            raise ValueError("support binding contains duplicate relationship identifiers")
    return copy.deepcopy(manifest)


def support_for(job: str, move: str, format_name: str, content_kind: str) -> dict:
    manifest = load_support_manifest()
    matches = [item for item in manifest["supported"]
               if (item["job"], item["move"], item["format"], item["contentKind"])
               == (job, move, format_name, content_kind)]
    if len(matches) != 1:
        raise ValueError("unsupported workflow tuple; call get_workflow_capabilities for exact support")
    return matches[0]
