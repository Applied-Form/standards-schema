#!/usr/bin/env python3
"""Local CLI for the scoped Standards agent workflow."""
import argparse
import json
import sys
from pathlib import Path

from .checker import check_artifact
from .engine import PACK_FILES, assemble_context, create_plan, prepare_repair

ROOT = Path(__file__).resolve().parents[1]


def _json_file(path, limit=2_100_000):
    data = Path(path).read_bytes()
    if len(data) > limit:
        raise ValueError(f"input exceeds {limit} bytes")
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON object key")
            value[key] = item
        return value

    def reject_constant(value):
        raise ValueError(f"non-finite JSON number {value}")

    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def _text_file(path, limit=2_000_000):
    data = Path(path).read_bytes()
    if len(data) > limit:
        raise ValueError(f"input exceeds {limit} bytes")
    return data.decode("utf-8")


def _reader(packs):
    root = packs.resolve()

    def read(system, filename):
        if system != "instrument" or filename not in PACK_FILES:
            raise ValueError("unsupported system or workflow source file")
        pack = (root / system).resolve()
        if not pack.is_relative_to(root):
            raise ValueError("installed pack is outside the catalogue")
        target = (pack / filename).resolve()
        if not target.is_relative_to(pack) or not target.is_file():
            raise ValueError("workflow source is missing or outside the installed pack")
        return target.read_text(encoding="utf-8")

    return read


def _write(value, output):
    rendered = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


def parser():
    top = argparse.ArgumentParser(description=__doc__)
    top.add_argument("--packs", type=Path, default=ROOT / "packs", help="installed pack directory")
    commands = top.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="create a validated plan from a fixed-content brief")
    plan.add_argument("--brief", required=True)
    plan.add_argument("--renderer-identity", required=True)
    plan.add_argument("--out")
    context = commands.add_parser("context", help="assemble selected context for a plan")
    context.add_argument("--plan", required=True)
    context.add_argument("--out")
    check = commands.add_parser("check", help="check static HTML and optional browser evidence")
    check.add_argument("--plan", required=True)
    check.add_argument("--html", required=True)
    check.add_argument("--evidence")
    check.add_argument("--out")
    repair = commands.add_parser("repair", help="prepare the next bounded repair decision")
    repair.add_argument("--plan", required=True)
    repair.add_argument("--html", required=True)
    repair.add_argument("--evidence")
    repair.add_argument("--history")
    repair.add_argument("--out")
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    read_pack = _reader(args.packs)
    if args.command == "plan":
        result = create_plan(_json_file(args.brief, 500_000), read_pack,
                             _json_file(args.renderer_identity, 50_000))
    elif args.command == "context":
        result = assemble_context(_json_file(args.plan, 500_000), read_pack)
    else:
        plan = _json_file(args.plan, 500_000)
        html = _text_file(args.html)
        evidence = _json_file(args.evidence, 3_500_000) if args.evidence else None
        if args.command == "check":
            result = check_artifact(plan, html, evidence)
        else:
            history = _json_file(args.history, 500_000) if args.history else []
            result = prepare_repair(plan, html, history, evidence, read_pack)
    _write(result, args.out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
