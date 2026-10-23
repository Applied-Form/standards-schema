#!/usr/bin/env python3
"""Standards MCP server — serves installed packs and a local artifact workflow.

Turns the catalogue from a download into something an agent can query: list the
systems, pull one build, read the token and archetype contracts, and select a
move by the rhetorical job it does rather than by how it looks.

Standard library only, like the compiler. Speaks JSON-RPC 2.0 over stdio with
newline-delimited messages.

    python3 mcp/server.py                 # serve packs/ next to this repo
    python3 mcp/server.py --packs PATH    # serve a different catalogue
    python3 mcp/server.py --selftest      # exercise the protocol and exit

Client config (Claude Code, Claude Desktop and anything else reading MCP stdio):

    {"mcpServers": {"standards-schema": {
        "command": "python3",
        "args": ["/absolute/path/to/standards-schema/mcp/server.py"]}}}
"""
import argparse, importlib, json, os, sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

PROTOCOL_VERSION = "2025-06-18"
MAX_MESSAGE_CHARS = 4_000_000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS = os.path.join(ROOT, "packs")

BUILDS = {"compact": "SKILL-compact.md",   # compact instruction build
          "full": "SKILL.md",              # full instruction build
          "reference": "REFERENCE.md"}     # detailed reference


def workflow_module(name):
    """Load repository-local workflow code, independent of the launch directory."""
    if not sys.path or sys.path[0] != ROOT:
        sys.path.insert(0, ROOT)
    return importlib.import_module("workflow." + name)


# ---------------------------------------------------------------- catalogue

def resolved(path):
    try:
        return path.resolve()
    except RuntimeError as e:  # Older Python versions report symlink loops here.
        raise ValueError("cannot resolve pack resource path") from e


def pack_file(slug, filename):
    """Resolve a file inside one installed pack, never a sibling or host file."""
    if (not isinstance(slug, str) or not slug or slug in (".", "..")
            or any(c in slug for c in "/\\:") or any(ord(c) < 32 for c in slug)):
        raise ValueError("invalid system slug")
    if (not isinstance(filename, str) or not filename
            or any(c in filename for c in "\\:") or any(ord(c) < 32 for c in filename)
            or any(part in ("", ".", "..") for part in filename.split("/"))):
        raise ValueError("invalid pack resource path")
    root = resolved(Path(PACKS))
    pack = resolved(root / slug)
    if pack == root or not pack.is_relative_to(root):
        raise ValueError("system is outside the pack catalogue")
    marker = resolved(pack / "manifest.json")
    if not marker.is_relative_to(pack) or not marker.is_file():
        raise FileNotFoundError(f"unknown system {slug!r}")
    target = resolved(pack / filename)
    if target == pack or not target.is_relative_to(pack):
        raise ValueError("resource is outside the selected pack")
    if not target.is_file():
        raise FileNotFoundError(f"{slug} has no {filename}")
    return target


def slugs():
    if not os.path.isdir(PACKS):
        return []
    found = []
    for slug in os.listdir(PACKS):
        try:
            pack_file(slug, "manifest.json")
        except (OSError, ValueError):
            continue
        found.append(slug)
    return sorted(found)


def read(slug, filename):
    return pack_file(slug, filename).read_text(encoding="utf-8")


def manifest(slug):
    return json.loads(read(slug, "manifest.json"))


def licence_of(slug):
    try:
        first = [l for l in read(slug, "LICENSE").splitlines() if l.strip()]
        for line in first:
            if "CC BY" in line:
                return "CC BY 4.0"
            if "Proprietary" in line:
                return "proprietary"
    except FileNotFoundError:
        pass
    return "unstated"


# -------------------------------------------------------------------- tools

TOOLS = [
    {"name": "list_systems",
     "description": "List every Standards system available, with its territory, constraint "
                    "counts and licence. Call this first.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},

    {"name": "get_system",
     "description": "Fetch one system's compact or full instruction build, or its detailed "
                    "reference. Choose the context appropriate to the task; comparative "
                    "quality and efficiency of these formats remain evaluation questions.",
     "inputSchema": {"type": "object",
                     "properties": {"system": {"type": "string",
                                               "description": "system slug, e.g. instrument"},
                                    "build": {"type": "string", "enum": list(BUILDS),
                                              "default": "full"}},
                     "required": ["system"], "additionalProperties": False}},

    {"name": "get_tokens",
     "description": "The system's token contract as JSON: colour, type and system tokens, "
                    "available without extracting values from the prose build.",
     "inputSchema": {"type": "object",
                     "properties": {"system": {"type": "string"}},
                     "required": ["system"], "additionalProperties": False}},

    {"name": "get_archetypes",
     "description": "The system's compositional moves as JSON, indexed by rhetorical job.",
     "inputSchema": {"type": "object",
                     "properties": {"system": {"type": "string"}},
                     "required": ["system"], "additionalProperties": False}},

    {"name": "select_move",
     "description": "Return candidate compositional moves for a rhetorical job; a job may "
                    "have several matches. Jobs are E evidence, S structure, N narrative, "
                    "C change, T transaction, W wayfinding. Choose one applicable move "
                    "for the artefact; this retrieval call does not make a complete plan.",
     "inputSchema": {"type": "object",
                     "properties": {"system": {"type": "string"},
                                    "job": {"type": "string",
                                            "description": "job code or name, e.g. E or evidence"}},
                     "required": ["system", "job"], "additionalProperties": False}},
]

READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def tool_definitions():
    """Advertise the same nested input contracts used by the local workflow."""
    load_schema = workflow_module("schema").load_schema
    brief = load_schema("brief")
    plan = load_schema("plan")
    renderer = load_schema("renderer-identity")
    evidence = load_schema("render-evidence")
    history = load_schema("history")
    context_output = load_schema("context")
    report_output = load_schema("report")
    repair_output = load_schema("repair")
    support_output = load_schema("support-manifest")
    html = {"type": "string", "minLength": 1,
            "maxLength": 2000000,
            "description": "HTML source to inspect; the server does not execute it."}

    def arguments(properties, required):
        return {"type": "object", "properties": properties, "required": required,
                "additionalProperties": False}

    tools = TOOLS + [
        {"name": "get_workflow_capabilities",
         "description": "Return the canonical versioned support manifest before planning. "
                        "It declares exact job/move/format tuples, package bindings, runtime "
                        "requirements, tested clients and unsupported surfaces.",
         "inputSchema": arguments({}, []),
         "outputSchema": support_output},
        {"name": "plan_artifact",
         "description": "Validate a supported fixed-content brief and create a versioned "
                        "artifact plan with selected move and source provenance. Unsupported "
                        "workflows return an error; no model call or rendering occurs.",
         "inputSchema": arguments({"brief": brief, "renderer": renderer}, ["brief", "renderer"]),
         "outputSchema": plan},
        {"name": "assemble_context",
         "description": "Assemble context for a validated artifact plan from installed pack "
                        "sources and record exactly what was supplied. This does not prove "
                        "that less context produces better output.",
         "inputSchema": arguments({"plan": plan}, ["plan"]),
         "outputSchema": context_output},
        {"name": "check_artifact",
         "description": "Check supplied HTML against a supported artifact plan. Return "
                        "rule-linked findings and explicit unknowns; source checks are not "
                        "a browser audit or a human design-quality judgement.",
         "inputSchema": arguments({"plan": plan, "html": html,
                                    "render_evidence": evidence}, ["plan", "html"]),
         "outputSchema": report_output},
        {"name": "prepare_repair",
         "description": "Prepare a bounded repair packet from artifact findings and prior "
                        "records. Preserve protected content and report stop conditions. "
                        "This returns instructions and a record; it does not call a model "
                        "or apply an edit.",
         "inputSchema": arguments({"plan": plan, "html": html, "history": history,
                                    "render_evidence": evidence}, ["plan", "html"]),
         "outputSchema": repair_output},
    ]
    return [{**tool, "annotations": dict(READ_ONLY_ANNOTATIONS)} for tool in tools]

JOBS = {"e": "evidence", "s": "structure", "n": "narrative",
        "c": "change", "t": "transaction", "w": "wayfinding"}


def tool_list_systems():
    out = []
    for s in slugs():
        m = manifest(s)
        c = m.get("constraints", {})
        out.append({"system": s, "name": m.get("system", s),
                    "coreConstraints": c.get("coreCount"),
                    "compactConstraints": c.get("compactCount"),
                    "budget": c.get("budget"),
                    "typeLicence": m.get("typeLicence"),
                    "licence": licence_of(s)})
    if not out:
        return "No packs found. Point --packs at a directory of Standards packs."
    return json.dumps({"systems": out, "builds": list(BUILDS),
                       "note": "Load exactly one build per call."}, indent=2)


def tool_get_system(system, build="full"):
    if build not in BUILDS:
        raise ValueError(f"unknown build {build!r}; expected one of {', '.join(BUILDS)}")
    return read(system, BUILDS[build])


def tool_get_tokens(system):
    return read(system, "tokens.json")


def tool_get_archetypes(system):
    return read(system, "archetypes.json")


def tool_select_move(system, job):
    data = json.loads(read(system, "archetypes.json"))
    moves = data.get("moves", [])
    key = job.strip().lower()
    # accept a code ("E"), a name ("evidence") or the name the pack uses ("Evidence")
    want = JOBS.get(key, key)
    hits = [m for m in moves
            if str(m.get("job", "")).strip().lower() == key
            or str(m.get("jobName", "")).strip().lower() == want]
    if not hits:
        have = sorted({f'{m.get("job")} · {m.get("jobName")}' for m in moves})
        return json.dumps({"matches": [], "job": job, "availableJobs": have,
                           "note": "No move for that job in this system. Its refusals may "
                                   "make the job out of scope, which is a finding rather "
                                   "than a gap."}, indent=2)
    return json.dumps({"job": job, "matches": hits,
                       "selection": data.get("selection"),
                       "note": "One move is active per artefact."}, indent=2)


def tool_get_workflow_capabilities():
    return workflow_module("support").load_support_manifest()


def workflow_text(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)


def tool_plan_artifact(brief, renderer):
    return workflow_module("engine").create_plan(brief, read, renderer)


def tool_assemble_context(plan):
    return workflow_module("engine").assemble_context(plan, read)


def tool_check_artifact(plan, html, render_evidence=None):
    return workflow_module("checker").check_artifact(plan, html, render_evidence=render_evidence)


def tool_prepare_repair(plan, html, history=None, render_evidence=None):
    return workflow_module("engine").prepare_repair(
        plan, html, history=history, render_evidence=render_evidence, read_pack=read)


DISPATCH = {"list_systems": tool_list_systems, "get_system": tool_get_system,
            "get_tokens": tool_get_tokens, "get_archetypes": tool_get_archetypes,
            "select_move": tool_select_move,
            "get_workflow_capabilities": tool_get_workflow_capabilities,
            "plan_artifact": tool_plan_artifact,
            "assemble_context": tool_assemble_context,
            "check_artifact": tool_check_artifact, "prepare_repair": tool_prepare_repair}


# ---------------------------------------------------------------- resources

def resources():
    out = []
    for s in slugs():
        for f in ("SKILL.md", "SKILL-compact.md", "REFERENCE.md",
                  "tokens.json", "archetypes.json", "manifest.json", "AGENTS.md"):
            try:
                pack_file(s, f)
            except (OSError, ValueError):
                continue
            out.append({"uri": f"standards://{s}/{f}",
                        "name": f"{s} · {f}",
                        "mimeType": "application/json" if f.endswith(".json")
                                    else "text/markdown"})
    return out


def resource_path(uri):
    if (not isinstance(uri, str) or not uri.startswith("standards://")
            or any(ord(c) < 32 for c in uri)):
        raise ValueError("expected a standards:// resource URI")
    parsed = urlsplit(uri)
    if parsed.query or parsed.fragment or not parsed.path.startswith("/"):
        raise ValueError("invalid Standards resource URI")
    # Decode once before path checks. Encoded separators and dot segments receive
    # the same containment checks as literal ones; no later decoding is performed.
    return unquote(parsed.netloc, errors="strict"), unquote(parsed.path[1:], errors="strict")


# ---------------------------------------------------------------- transport

def result(rid, payload):
    return {"jsonrpc": "2.0", "id": rid, "result": payload}


def error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def tool_error(rid, message):
    return result(rid, {"isError": True,
                        "content": [{"type": "text", "text": message}]})


def validate_arguments(name, arguments):
    """Validate recursively against the exact advertised argument schema."""
    schema = next(tool["inputSchema"] for tool in tool_definitions() if tool["name"] == name)
    workflow_module("schema").validate(arguments, schema, path="arguments")


def handle(msg):
    """Return a response dict, or None for a notification."""
    if not isinstance(msg, dict):
        return error(None, -32600, "request must be an object")
    method, rid = msg.get("method"), msg.get("id")
    if (msg.get("jsonrpc") != "2.0" or not isinstance(method, str) or not method
            or (rid is not None and (isinstance(rid, bool) or not isinstance(rid, (str, int))))):
        return error(None, -32600, "invalid JSON-RPC request")
    # JSON-RPC notifications do not receive replies, including unknown methods.
    if "id" not in msg:
        return None
    params = msg.get("params", {})
    if not isinstance(params, dict):
        return error(rid, -32602, "params must be an object")

    if method == "initialize":
        return result(rid, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": "standards", "version": "0.2.0"},
            "instructions": "Open design rules, contracts and a scoped local artifact "
                            "workflow. Call list_systems to discover installed packs. "
                            "Call get_workflow_capabilities before plan_artifact. Check and repair "
                            "tools report findings without generating or executing HTML."})
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return result(rid, {})
    if method == "tools/list":
        return result(rid, {"tools": tool_definitions()})
    if method == "resources/list":
        return result(rid, {"resources": resources()})
    if method == "resources/read":
        uri = params.get("uri")
        try:
            slug, fname = resource_path(uri)
            text = read(slug, fname)
        except (OSError, ValueError, UnicodeError) as e:
            return error(rid, -32602, str(e))
        return result(rid, {"contents": [{"uri": uri, "text": text}]})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(args, dict):
            return error(rid, -32602, "tool name must be a string and arguments must be an object")
        fn = DISPATCH.get(name)
        if not fn:
            return error(rid, -32601, f"unknown tool {name!r}")
        try:
            validate_arguments(name, args)
            payload = fn(**args)
        except TypeError as e:
            return tool_error(rid, f"bad arguments: {e}")
        except RecursionError:
            return tool_error(rid, "input nesting is too deep")
        except (OSError, ValueError, KeyError, UnicodeError) as e:
            return tool_error(rid, str(e))
        if isinstance(payload, (dict, list)):
            return result(rid, {"content": [{"type": "text", "text": workflow_text(payload)}],
                                "structuredContent": payload})
        return result(rid, {"content": [{"type": "text", "text": payload}]})
    return error(rid, -32601, f"unknown method {method!r}")


def serve(stdin=sys.stdin, stdout=sys.stdout):
    for line in stdin:
        if len(line) > MAX_MESSAGE_CHARS:
            stdout.write(json.dumps(error(None, -32600, "request exceeds the message size limit")) + "\n")
            stdout.flush()
            continue
        line = line.strip()
        if not line:
            continue
        try:
            def unique_object(pairs):
                value = {}
                for key, item in pairs:
                    if key in value:
                        raise ValueError("duplicate JSON object key")
                    value[key] = item
                return value

            def reject_constant(value):
                raise ValueError(f"non-finite JSON number {value}")

            msg = json.loads(line, object_pairs_hook=unique_object, parse_constant=reject_constant)
        except (json.JSONDecodeError, RecursionError, ValueError):
            resp = error(None, -32700, "invalid JSON")
        else:
            resp = handle(msg)
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()


# ---------------------------------------------------------------- self test

def selftest():
    calls = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "list_systems", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "get_system", "arguments": {"system": "instrument",
                                                        "build": "compact"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "select_move", "arguments": {"system": "instrument", "job": "E"}}},
        {"jsonrpc": "2.0", "id": 6, "method": "resources/list"},
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
         "params": {"name": "get_system", "arguments": {"system": "nope"}}},
    ]
    ok = True
    for c in calls:
        r = handle(c)
        label = c.get("method") + (f" · {c['params']['name']}"
                                   if c.get("params", {}).get("name") else "")
        if r is None:
            print(f"  {label:38s} notification, no reply")
            continue
        if "error" in r:
            print(f"  {label:38s} error: {r['error']['message']}")
            ok = False
            continue
        res = r["result"]
        if "tools" in res:
            names = [tool["name"] for tool in res["tools"]]
            if len(names) != len(set(names)) or set(names) != set(DISPATCH):
                print("  tool definitions do not match the dispatch table")
                ok = False
            print(f"  {label:38s} {len(res['tools'])} tools")
        elif "resources" in res:
            print(f"  {label:38s} {len(res['resources'])} resources")
        elif "serverInfo" in res:
            print(f"  {label:38s} {res['serverInfo']['name']} {res['protocolVersion']}")
        elif res.get("isError"):
            print(f"  {label:38s} handled error: {res['content'][0]['text'][:48]}")
        else:
            print(f"  {label:38s} {len(res['content'][0]['text'])} chars")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--packs", help="directory of packs (default: packs/ beside this repo)")
    ap.add_argument("--selftest", action="store_true", help="exercise the protocol and exit")
    a = ap.parse_args()
    if a.packs:
        PACKS = os.path.abspath(a.packs)
    if a.selftest:
        print("Standards MCP server — self test\n")
        sys.exit(selftest())
    serve()
