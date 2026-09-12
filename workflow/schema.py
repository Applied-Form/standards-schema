"""Validate the JSON Schema subset used by the local workflow, without dependencies.

This is not a general-purpose JSON Schema implementation. Schemas shipped here
are also usable with a complete Draft 2020-12 validator.
"""
import json
import math
import re
from pathlib import Path


def load_schema(name):
    if name not in {"brief", "plan", "report", "history", "render-evidence", "renderer-identity",
                    "context", "repair"}:
        raise ValueError("unknown workflow schema")
    return json.loads((Path(__file__).parent / "schemas" / f"{name}.schema.json").read_text())


def validate(value, schema, path="$", root=None):
    root = schema if root is None else root
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise ValueError("only local $defs references are supported")
        target = root
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        return validate(value, target, path, root)
    if "anyOf" in schema:
        for alternative in schema["anyOf"]:
            try:
                validate(value, alternative, path, root)
                return
            except ValueError:
                pass
        raise ValueError(f"{path}: does not match an allowed shape")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ValueError(f"{path}: unexpected constant")
    if "enum" in schema and not any(type(value) is type(v) and value == v for v in schema["enum"]):
        raise ValueError(f"{path}: outside the allowed values")
    kinds = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
             "string": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool),
             "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
             "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v),
             "null": lambda v: v is None}
    kind = schema.get("type")
    if kind and not kinds[kind](value):
        raise ValueError(f"{path}: must be {kind}")
    if isinstance(value, dict):
        if len(value) < schema.get("minProperties", 0) or len(value) > schema.get("maxProperties", float("inf")):
            raise ValueError(f"{path}: object field count outside limits")
        if any(not isinstance(k, str) for k in value):
            raise ValueError(f"{path}: keys must be strings")
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(f"{path}: missing required field {key}")
        props = schema.get("properties", {})
        for key, item in value.items():
            spec = props.get(key, schema.get("additionalProperties", {}))
            if spec is False:
                raise ValueError(f"{path}: unknown field {key}")
            if isinstance(spec, dict):
                validate(item, spec, f"{path}.{key}", root)
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            raise ValueError(f"{path}: array length outside limits")
        for i, item in enumerate(value):
            validate(item, schema.get("items", {}), f"{path}[{i}]", root)
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", float("inf")):
            raise ValueError(f"{path}: string length outside limits")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise ValueError(f"{path}: string does not match required pattern")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value) or value < schema.get("minimum", -float("inf")) or value > schema.get("maximum", float("inf")):
            raise ValueError(f"{path}: number outside limits")
