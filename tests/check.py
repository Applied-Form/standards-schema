#!/usr/bin/env python3
"""Standards repository checks. Run from anywhere: python3 tests/check.py

Six checks, in the order they are cheapest to fix:

  1. every Python file parses
  2. every pack carries a licence
     and Claude bundles contain their current referenced files and notices
  3. the packs recompile byte-identically  - enforces "never edit the builds"
  4. no build exceeds the constraint budget - enforces schema v0.4 rule 2
  5. every shipped brief regenerates its proof grid byte for byte
  6. every grid is generated from a brief, or listed as legacy
  7. the proof grids meet the Layer 0 contrast floor
  8. the MCP server answers the protocol
     and rejects unsafe resource paths and malformed requests
  9. the study harnesses parse, if node is available
"""
import os, subprocess, sys, glob, py_compile, shutil, tempfile, filecmp
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILED = []


def check(name):
    def deco(fn):
        sys.stdout.write(f"  {name:44s}")
        sys.stdout.flush()
        try:
            detail = fn()
            print("ok" + (f"  ({detail})" if detail else ""))
        except AssertionError as e:
            print("FAIL")
            FAILED.append(f"{name}: {e}")
        except Exception as e:                       # noqa: BLE001
            print("ERROR")
            FAILED.append(f"{name}: {type(e).__name__}: {e}")
        return fn
    return deco


def run(*args, cwd=ROOT):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


@check("python files parse")
def _():
    files = [p for p in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True)
             if ".git" not in p]
    for f in files:
        py_compile.compile(f, doraise=True, cfile=os.path.join(tempfile.gettempdir(), "c.pyc"))
    return f"{len(files)} files"


@check("every pack carries a licence")
def _():
    packs = sorted(glob.glob(os.path.join(ROOT, "packs", "*", "SOURCE.md")))
    assert packs, "no packs found"
    missing = [os.path.basename(os.path.dirname(p)) for p in packs
               if not os.path.exists(os.path.join(os.path.dirname(p), "LICENSE"))]
    assert not missing, f"no LICENSE in {', '.join(missing)}"
    return f"{len(packs)} packs"


def build_files():
    # Generated: the top-level builds, and everything under dist/. Not
    # assets/, which is hand-maintained source alongside SOURCE.md.
    return sorted(
        [f for f in glob.glob(os.path.join(ROOT, "packs", "*", "*"))
         if os.path.basename(f) != "SOURCE.md" and f.endswith((".md", ".json"))]
        + [f for f in glob.glob(os.path.join(ROOT, "packs", "*", "dist", "**", "*"),
                                recursive=True) if os.path.isfile(f)]
    )


@check("Claude bundles contain canonical references")
def _():
    # Check BEFORE recompilation, which would otherwise repair a missing file
    # and hide a broken shipped bundle from CI.
    import importlib.util
    spec = importlib.util.spec_from_file_location("standards_compiler", os.path.join(ROOT, "schema", "compile.py"))
    compiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    count = 0
    for source in sorted(Path(ROOT).glob("packs/*/SOURCE.md")):
        pack = source.parent
        bundle = pack / "dist/claude" / pack.name
        expected = compiler.claude_bundle_sources(pack)
        actual = {path.relative_to(bundle).as_posix(): path for path in bundle.rglob("*") if path.is_file()}
        missing, extra = set(expected) - set(actual), set(actual) - set(expected)
        assert not missing, f"{pack.name}: missing bundle files {', '.join(sorted(missing))}"
        assert not extra, f"{pack.name}: stale bundle files {', '.join(sorted(extra))}"
        for name, canonical in expected.items():
            assert actual[name].resolve().is_relative_to(bundle.resolve()), f"{pack.name}: escaping bundled file {name}"
            assert actual[name].read_bytes() == canonical.read_bytes(), f"{pack.name}: bundle file differs from canonical source: {name}"
        count += len(expected)
    return f"{count} bundled files match sources"


@check("Claude bundle generation regressions")
def _():
    r = run(sys.executable, "tests/test_distribution.py")
    assert r.returncode == 0, r.stderr.strip()[-2000:] or r.stdout.strip()[-2000:]
    return "references, notices and stale-file cleanup"


@check("Instrument chart semantics stay consistent")
def _():
    r = run(sys.executable, "tests/test_instrument_chart_semantics.py")
    assert r.returncode == 0, r.stderr.strip()[-2000:] or r.stdout.strip()[-2000:]
    return "neutral series in source and distribution"


@check("packs recompile byte-identically")
def _():
    """Drift is "recompiling changes a build", independent of git state."""
    builds = build_files()
    assert builds, "no build outputs found"
    before = {f: open(f, "rb").read() for f in builds}
    r = run(sys.executable, "schema/compile.py", "--all", "packs")
    assert r.returncode == 0, r.stderr.strip()[:300]
    after = {f: open(f, "rb").read() for f in build_files()}
    changed = [os.path.relpath(f, ROOT) for f in sorted(set(before) | set(after))
               if before.get(f) != after.get(f)]
    assert not changed, ("recompiling changed these, so a build no longer matches its "
                         "source - edit SOURCE.md and recompile, never edit a build:\n      "
                         + "\n      ".join(changed[:8]))
    return f"{len(builds)} build files"


@check("no build exceeds the constraint budget")
def _():
    r = run(sys.executable, "schema/compile.py", "--all", "packs", "--strict")
    assert r.returncode == 0, "a build is over budget:\n" + "\n".join(
        l for l in r.stdout.splitlines() if "OVER" in l)
    return "all under 20"


@check("shipped briefs regenerate their grids")
def _():
    if not os.path.isdir(os.path.join(ROOT, "proof")):
        return "skipped, no proof/ in this repository"
    briefs = sorted(glob.glob(os.path.join(ROOT, "proof", "briefs", "*.json")))
    assert briefs, "no briefs shipped - the proof grids cannot be rebuilt"
    tmp = tempfile.mkdtemp()
    bad = []
    for b in briefs:
        name = os.path.splitext(os.path.basename(b))[0]
        grid = os.path.join(ROOT, "proof", f"proof-grid-{name}.html")
        if not os.path.exists(grid):
            continue
        out = os.path.join(tmp, name + ".html")
        r = run(sys.executable, "proof/proofgen.py", b, out)
        if r.returncode != 0 or not filecmp.cmp(out, grid, shallow=False):
            bad.append(name)
    shutil.rmtree(tmp, ignore_errors=True)
    assert not bad, f"regenerated output differs for: {', '.join(bad)}"
    return f"{len(briefs)} briefs"


@check("every grid is generated or listed as legacy")
def _():
    """A grid with no brief cannot be corrected by editing data. Three predate the
    generator and are listed in proof/LEGACY.md; this fails if a fourth appears, so
    the set cannot grow by accident."""
    if not os.path.isdir(os.path.join(ROOT, "proof")):
        return "skipped, no proof/ in this repository"
    legacy_doc = os.path.join(ROOT, "proof", "LEGACY.md")
    assert os.path.exists(legacy_doc), "proof/LEGACY.md is missing"
    listed = open(legacy_doc, encoding="utf-8").read()
    orphans = []
    for path in sorted(glob.glob(os.path.join(ROOT, "proof", "proof-grid*.html"))):
        name = os.path.basename(path)
        stem = name[len("proof-grid-"):-len(".html")] if name.startswith("proof-grid-") else None
        has_brief = stem and os.path.exists(os.path.join(ROOT, "proof", "briefs", stem + ".json"))
        if not has_brief and name not in listed:
            orphans.append(name)
    assert not orphans, ("no brief and not listed in proof/LEGACY.md: "
                         + ", ".join(orphans))
    return "set is closed"


@check("proof grids meet the Layer 0 contrast floor")
def _():
    """Layer 0 is the catalogue-level quality claim: body text at or above 4.5:1,
    large display at or above 3:1. The proof grids are the artefacts that claim it
    in public, so the claim is checked rather than asserted.

    A colour is judged against the nearest declared background above it: its own
    rule first, then the nearest ancestor selector, then the system's ground. An
    ink band sets its own ground and its text is measured against that."""
    import re

    def lum(h):
        h = h.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    def ratio(a, b):
        hi, lo = sorted([lum(a), lum(b)], reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    HEX = r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b"
    fails = []

    # chart series are marks, so the 3:1 graphical floor applies to them
    import json as _json
    for theme in sorted(glob.glob(os.path.join(ROOT, "packs", "*", "assets",
                                               "chart-theme.json"))):
        d = _json.load(open(theme, encoding="utf-8"))
        bg = d.get("background")
        for h in d.get("seriesOrder", []):
            if bg and ratio(h, bg) < 3.0:
                fails.append(f"{os.path.relpath(theme, ROOT)}: series {h} on {bg} "
                             f"= {ratio(h, bg):.2f}:1, floor 3.0")

    for path in sorted(glob.glob(os.path.join(ROOT, "proof", "proof-grid*.html"))):
        css = open(path, encoding="utf-8").read()
        rules = {}
        for m in re.finditer(r"([^{}]+)\{([^}]*)\}", css):
            for sel in m.group(1).split(","):
                rules.setdefault(sel.strip(), "")
                rules[sel.strip()] += m.group(2)

        def background_for(sel):
            parts = sel.split()
            while parts:
                body = rules.get(" ".join(parts), "")
                bg = re.search(r"background(?:-color)?:\s*(" + HEX + ")", body)
                if bg:
                    return bg.group(1)
                parts.pop()
            return None

        for sel, body in rules.items():
            col = re.search(r"(?<!-)\bcolor:\s*(" + HEX + ")", body)
            if not col or not sel.startswith("."):
                continue
            bg = background_for(sel)
            if not bg:
                continue
            size = re.search(r"font-size:\s*([0-9.]+)px", body)
            weight = re.search(r"font-weight:\s*([0-9]+)", body)
            px = float(size.group(1)) if size else None
            if px is None:                    # inherited: take the nearest ancestor's size
                parts = sel.split()
                while parts and px is None:
                    parts.pop()
                    anc = re.search(r"font-size:\s*([0-9.]+)px", rules.get(" ".join(parts), ""))
                    px = float(anc.group(1)) if anc else None
            bold = weight and int(weight.group(1)) >= 700
            large = px is not None and (px >= 24 or (px >= 18.66 and bold))
            floor = 3.0 if large else 4.5
            r = ratio(col.group(1), bg)
            if r < floor:
                fails.append(f"{os.path.basename(path)} · {sel}: {col.group(1)} on {bg} "
                             f"= {r:.2f}:1, floor {floor}")
    assert not fails, "below the Layer 0 floor:\n      " + "\n      ".join(fails[:10])
    return "all declared colours pass"


@check("mcp server answers the protocol")
def _():
    r = run(sys.executable, "mcp/server.py", "--selftest")
    assert r.returncode == 0, r.stdout.strip()[-300:] or r.stderr.strip()[-300:]
    assert "5 tools" in r.stdout, "tool list did not come back"
    return "self test clean"


@check("mcp input and resource boundaries")
def _():
    r = run(sys.executable, "tests/test_mcp.py")
    assert r.returncode == 0, r.stderr.strip()[-2000:] or r.stdout.strip()[-2000:]
    return "boundary regressions clean"


@check("study harnesses parse")
def _():
    if not shutil.which("node"):
        return "skipped, no node"
    import re
    for f in ("schema/study.html", "schema/harness.html"):
        src = open(os.path.join(ROOT, f), encoding="utf-8").read()
        js = "\n;\n".join(re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', src, re.S))
        p = os.path.join(tempfile.gettempdir(), "chk.js")
        open(p, "w", encoding="utf-8").write(js)
        r = run("node", "--check", p)
        assert r.returncode == 0, f"{f}: {r.stderr.strip()[:200]}"
    return "2 files"


if __name__ == "__main__":
    print("Standards checks\n")
    if FAILED:
        print("\n" + "\n".join(f"  ✗ {f}" for f in FAILED))
        print(f"\n{len(FAILED)} check(s) failed.")
        sys.exit(1)
    print("\nAll checks passed.")
