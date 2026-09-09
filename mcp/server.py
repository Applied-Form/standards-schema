#!/usr/bin/env python3
"""Standards MCP server — serves the six packs to any MCP client.

Turns the catalogue from a download into something an agent can query: list the
systems, pull one build, read the token and archetype contracts, and select a
move by the rhetorical job it does rather than by how it looks.

Standard library only, like the compiler. Speaks JSON-RPC 2.0 over stdio with
newline-delimited messages.

    python3 mcp/server.py                 # serve packs/ next to this repo
    python3 mcp/server.py --packs PATH    # serve a different catalogue
    python3 mcp/server.py --selftest      # exercise the protocol and exit

Client config (Claude Code, Claude Desktop and anything else reading MCP stdio):

    {"mcpServers": {"standards": {
        "command": "python3",
        "args": ["/absolute/path/to/standards/mcp/server.py"]}}}
"""
import argparse, json, os, sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

PROTOCOL_VERSION = "2025-06-18"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS = os.path.join(ROOT, "packs")

BUILDS = {"compact": "SKILL-compact.md",   # small and fast models
          "full": "SKILL.md",              # frontier models
          "reference": "REFERENCE.md"}     # on demand, either


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
     "description": "Fetch one system's instruction build. Use 'compact' for small and fast "
                    "models, 'full' for frontier models, 'reference' when you need a specific "
                    "detail. Load one build, never two - loading the reference alongside a "
                    "core costs compliance on the core.",
     "inputSchema": {"type": "object",
                     "properties": {"system": {"type": "string",
                                               "description": "system slug, e.g. instrument"},
                                    "build": {"type": "string", "enum": list(BUILDS),
                                              "default": "full"}},
                     "required": ["system"], "additionalProperties": False}},

    {"name": "get_tokens",
     "description": "The system's token contract as JSON: colour, type and system tokens. "
                    "Cheaper and more accurate than parsing them out of the prose build.",
     "inputSchema": {"type": "object",
                     "properties": {"system": {"type": "string"}},
                     "required": ["system"], "additionalProperties": False}},

    {"name": "get_archetypes",
     "description": "The system's compositional moves as JSON, indexed by rhetorical job.",
     "inputSchema": {"type": "object",
                     "properties": {"system": {"type": "string"}},
                     "required": ["system"], "additionalProperties": False}},

    {"name": "select_move",
     "description": "Pick the compositional move for a rhetorical job. Jobs are E evidence, "
                    "S structure, N narrative, C change, T transaction, W wayfinding. One move "
                    "is active per artefact; the others are not in force, so select rather "
                    "than trying to satisfy the whole table.",
     "inputSchema": {"type": "object",
                     "properties": {"system": {"type": "string"},
                                    "job": {"type": "string",
                                            "description": "job code or name, e.g. E or evidence"}},
                     "required": ["system", "job"], "additionalProperties": False}},
]

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


DISPATCH = {"list_systems": tool_list_systems, "get_system": tool_get_system,
            "get_tokens": tool_get_tokens, "get_archetypes": tool_get_archetypes,
            "select_move": tool_select_move}


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
    """Enforce the small string-only schemas advertised by this server."""
    schema = next(tool["inputSchema"] for tool in TOOLS if tool["name"] == name)
    for field in schema.get("required", []):
        if field not in arguments:
            raise ValueError(f"missing required argument {field!r}")
    for field, value in arguments.items():
        spec = schema["properties"].get(field)
        if spec is None:
            raise ValueError(f"unknown argument {field!r}")
        if not isinstance(value, str):
            raise ValueError(f"argument {field!r} must be a string")
        if "enum" in spec and value not in spec["enum"]:
            raise ValueError(f"argument {field!r} must be one of {', '.join(spec['enum'])}")


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
            "serverInfo": {"name": "standards", "version": "1.0.0"},
            "instructions": "Six design systems written as rulesets a model can execute. "
                            "Call list_systems first, then get_system with one build."})
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return result(rid, {})
    if method == "tools/list":
        return result(rid, {"tools": TOOLS})
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
            text = fn(**args)
        except TypeError as e:
            return tool_error(rid, f"bad arguments: {e}")
        except (OSError, ValueError, KeyError, UnicodeError) as e:
            return tool_error(rid, str(e))
        return result(rid, {"content": [{"type": "text", "text": text}]})
    return error(rid, -32601, f"unknown method {method!r}")


def serve(stdin=sys.stdin, stdout=sys.stdout):
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
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
