#!/usr/bin/env python3
"""Standards pack compiler — schema v0.4.

One source, two delivery builds plus a reference.

    SOURCE.md          the system, authored once, full detail
      -> SKILL.md          frontier build: core only, flat, minimum constraints
      -> SKILL-compact.md  small-model build: clustered, precedence, checklist
      -> REFERENCE.md      on-demand detail: rationales, registers, failure modes

Why two builds. Published work on instruction stacking finds that a rewrite which
clusters constraints, merges them and inserts precedence notes recovers roughly +11
points of follow rate on the weakest model tested, +3.3 on the middle one, and
essentially nothing on the strongest (-1.2, not statistically robust). Structure that
helps a small model is dead weight on a frontier one. So we ship both.

Why a core/reference split. Follow rate falls from ~96% at one instruction to 20-60%
at twenty. Every pack in this catalogue stacked 30-37 constraints. Only fewer active
constraints fixes that.

Why floors appear twice. Instructions in the middle of a long prompt lose compliance
relative to those at the edges. Anything non-negotiable goes at both ends.

Usage:
    python3 compile.py ../packs/instrument
    python3 compile.py --all ../packs
"""
import argparse, os, re, shutil, sys, tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

# Section routing. Order within each build is deliberate.
CORE = [                      # always loaded, kept under the constraint budget
    "Before producing anything",
    "Materials",
    "The invariant element",
    "Archetypes",
]
# The gathered Prohibitions list duplicates the prohibitions already attached to the
# element they govern in Materials. v0.3 established that prohibitions belong with their
# element (the NASA manual's "don'ts" pattern); the core honours that and the gathered
# list moves to the reference as a checklist.
REFERENCE = [                 # loaded when a specific answer is needed
    "Archetypes",             # full table, with the Why column
    "Prohibitions",           # gathered list, as a checklist
    "State encoding",
    "Interaction",
    "Product register",
    "Density and attention",
    "Sequence",
    "Data treatment",
    "Deviation grammar",
    "Conflict register",
    "Failure mode",
    "Files",
]
# Compact build order follows the category ordering the literature found effective:
# reasoning-adjacent first (nearest "thinking"), format last (nearest token production).
#
# It carries the SAME rule set as the core, restructured — not a larger one. Schema v0.4
# rule 1 describes the compact build as "category-clustered, precedence note, numbered
# checklist, verification line", which is a change of structure. An earlier version of this
# list also added Product register, State encoding, Interaction, Prohibitions and Data
# treatment, so the build aimed at small models carried roughly twice the constraints of
# the build aimed at frontier models — backwards, since the collapse curve is steepest
# exactly where this build is used. Those sections are in REFERENCE.md.
# The conflict register is the one addition, because the v0.4 authoring checklist places it
# in the reference and the compact build by name.
COMPACT_ORDER = [
    "Before producing anything",
    "Archetypes",
    "Conflict register",
    "The invariant element",
    "Materials",
]

FLOOR_HEAD = "Floors"
# Words that mark a statement as constraint-bearing. Used to classify a statement,
# not to count: a statement carrying three of these is still one rule.
CONSTRAINT_WORDS = re.compile(
    r"\b(no|never|always|must|only|none|nothing|cannot|forbidden|required)\b", re.I)
TABLE_SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$")

# Schema v0.4 rule 2: no more than twenty active constraints in any single call.
# "Any single call" includes the compact build, which is loaded on its own.
BUDGET = 20


def parse(path):
    """Split a SOURCE.md into frontmatter, title block and ## sections."""
    raw = open(path, encoding="utf-8").read()
    fm = ""
    if raw.startswith("---"):
        end = raw.index("\n---", 3) + 4
        fm, raw = raw[:end], raw[end:]
    parts = re.split(r"^## ", raw, flags=re.M)
    head = parts[0].rstrip()
    sections = {}
    order = []
    for p in parts[1:]:
        title = p.splitlines()[0].strip()
        body = "\n".join(p.splitlines()[1:]).strip()
        sections[title] = body
        order.append(title)
    return fm, head, sections, order


def pick(sections, wanted):
    """Match wanted prefixes against actual section titles, preserving wanted order."""
    out = []
    for w in wanted:
        for title in sections:
            if title.lower().startswith(w.lower()) and title not in [t for t, _ in out]:
                out.append((title, sections[title]))
                break
    return out


def floors(sections):
    for t, b in sections.items():
        if t.lower().startswith(FLOOR_HEAD.lower()):
            return t, b
    return None, None


def constraint_units(text):
    """Split a build into statement units and classify them.

    Returns (unconditional, conditional). `unconditional` is a set of statements
    in force on every artefact; `conditional` is one count per archetype row,
    because a move's own prohibitions apply only when that move is selected.

    Three things this does that counting words did not. A statement counts once
    however many trigger words it carries, so "colour never the only signal" is
    one floor rather than two. Identical statements count once however often they
    repeat, so floors stated at both ends of a build are one set of rules. And the
    archetype `When` column is a selection trigger, not a rule to obey, so it is
    not counted at all.
    """
    uncond, cond, in_arch, in_conflict = set(), [], False, False
    para = []

    def flush():
        """Prose wraps across lines; a rule is a sentence, not a line."""
        if not para:
            return
        for sent in re.split(r"(?<=[.;])\s+", " ".join(para)):
            sent = sent.strip()
            if sent and CONSTRAINT_WORDS.search(sent):
                uncond.add(sent)
        para.clear()

    for ln in text.splitlines():
        st = ln.strip()
        if not st:
            flush(); in_arch = False
            continue
        if st.startswith("#") or st.startswith(">"):
            flush(); in_arch = in_conflict = False   # headings and callouts are not rules
            continue
        if st.startswith("|"):
            flush()
            if TABLE_SEP.match(ln):
                continue
            cells = [c.strip() for c in st.strip("|").split("|")]
            if cells and cells[0].lower().strip("* ") == "job":
                in_arch, in_conflict = True, False    # archetype table header
                continue
            if cells and cells[0].lower().strip("* ") == "collision":
                in_conflict, in_arch = True, False    # conflict register header
                continue
            if in_conflict:
                # A conflict-register row is a tiebreaker between two rules that are
                # already counted, not a third rule. "Measure wins" adds no obligation
                # the measure ceiling did not already impose; it says which of two
                # counted rules yields. Counting resolutions would count the same
                # constraint twice - once as a rule and again as its own tiebreak.
                continue
            if in_arch:                              # Job | Move | When | Why
                why = " ".join(cells[3:]) if len(cells) > 3 else ""
                cond.append(len(CONSTRAINT_WORDS.findall(why)))
                continue
            row = " ".join(cells)
            if CONSTRAINT_WORDS.search(row):
                uncond.add(row)
            continue
        in_arch = in_conflict = False
        para.append(st)
    flush()
    return uncond, cond


def count_constraints(text):
    """Active constraints in a single call.

    Every unconditional rule, plus the largest single archetype's own
    prohibitions. One move is active per artefact, so the other eight are not in
    force - which is the selection argument schema v0.4 rule 2 makes, applied to
    the measurement rather than only to the prose.
    """
    uncond, cond = constraint_units(text)
    return len(uncond) + (max(cond) if cond else 0)


def trim_archetypes(body, keep_why=False):
    """The core carries triggers; the reference carries rationales."""
    if keep_why or "|" not in body:
        return body
    lines, out = body.splitlines(), []
    for ln in lines:
        if ln.strip().startswith("|") and ln.count("|") >= 5:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            out.append("| " + " | ".join(cells[:-1]) + " |")   # drop the Why column
        else:
            out.append(ln)
    return "\n".join(out)


def build_skill(fm, head, sections):
    """Frontier build: flat, core only, floors at both ends."""
    ft, fb = floors(sections)
    parts = [fm, head, ""]
    if fb:
        parts += [f"## {ft}", fb, ""]
    for title, body in pick(sections, CORE):
        if title.lower().startswith("archetypes"):
            body = trim_archetypes(body)
            body += "\n\nFull rationales, data treatment and the conflict register are in `REFERENCE.md`."
        parts += [f"## {title}", body, ""]
    if fb:
        parts += ["---", "", f"## {ft} — restated", fb, ""]
    return "\n".join(parts).rstrip() + "\n"


def build_compact(fm, head, sections, name):
    """Small-model build: clustered, precedence, numbered checklist, verification line."""
    ft, fb = floors(sections)
    parts = [fm, head, ""]
    parts += ["> **Compact build.** Clustered by category with precedence made explicit, for",
              "> small and fast models. On a frontier model use `SKILL.md` instead — the extra",
              "> structure costs tokens and returns nothing there.", ""]
    if fb:
        parts += [f"## 0 · {ft} — these override everything below", fb, ""]
    n = 1
    for title, body in pick(sections, COMPACT_ORDER):
        if title.lower().startswith("archetypes"):
            body = trim_archetypes(body)
        parts += [f"## {n} · {title}", body, ""]
        n += 1
    parts += ["---", "",
              f"## {n} · Before finalising",
              "Verify every numbered section above is satisfied. Where two rules collide, the",
              "conflict register decides; where it is silent, the lower-numbered section wins.",
              ""]
    if fb:
        parts += [f"### {ft} — restated", fb, ""]
    return "\n".join(parts).rstrip() + "\n"


def build_reference(head, sections, name):
    title_line = head.splitlines()[0] if head else f"# {name}"
    parts = [f"{title_line} — reference", "",
             "Loaded on demand. The always-on rules are in `SKILL.md`; this file carries the",
             "detail behind them.", ""]
    for t, body in pick(sections, REFERENCE):
        parts += [f"## {t}", body, ""]
    return "\n".join(parts).rstrip() + "\n"


def local_markdown_files(text):
    """Explicit local file links and filename code spans, not prose guesses."""
    extensions = r"md|json|css|mplstyle|docx|pptx|xlsx|pdf|csv|txt|html|svg|png|jpe?g|webp|woff2?|ttf|otf|ya?ml|toml|[cm]?js|tsx?|py"
    targets = re.findall(r'\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)', text)
    targets += re.findall(r'^\s*\[[^\]\n]+\]:\s*(<[^>]+>|\S+)', text, re.M)
    for value in re.findall(r'(?<!`)`([^`\n]+)`(?!`)', text):
        value = value.strip()
        if value in ("LICENSE", "NOTICE") or re.search(rf'\.(?:{extensions})$', value, re.I):
            # A code span is often how installation docs name an adjacent file.
            # Spaces are valid filename characters; treating them as prose can
            # silently omit an advertised dependency from the bundle. Ambiguous
            # command-like spans now fail as missing paths instead of shipping an
            # incomplete installation, so commands belong in fenced code blocks.
            targets.append(value)
    for target in targets:
        target = target.strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme in ("http", "https", "mailto", "data") or target.startswith("#"):
            continue
        if parsed.netloc or parsed.scheme:
            raise ValueError(f"unsupported local bundle reference {target!r}")
        if parsed.path:
            yield unquote(parsed.path, errors="strict")


def claude_bundle_sources(d):
    """Map bundle paths to canonical files, including transitive Markdown refs.

    LICENSE is the pack's unmodified notice. Repository-context links and web
    links are not installed dependencies; local links in instruction/reference
    Markdown and all authored assets are copied into the standalone bundle.
    """
    root = Path(d).resolve()
    pending = [Path(name) for name in ("SKILL.md", "REFERENCE.md", "LICENSE")]
    assets = root / "assets"
    if assets.is_dir():
        pending.extend(path.relative_to(root) for path in sorted(assets.rglob("*")) if path.is_file())
    files = {}
    while pending:
        relative = pending.pop()
        if relative.is_absolute():
            raise ValueError(f"absolute bundle reference {relative}")
        relative = Path(os.path.normpath(relative))
        source = root / relative
        if not source.resolve().is_relative_to(root) or (relative.parts and relative.parts[0] == "dist"):
            raise ValueError(f"bundle reference escapes pack sources: {relative}")
        if not source.is_file():
            raise FileNotFoundError(f"bundle reference missing from {root.name}: {relative}")
        name = relative.as_posix()
        if name in files:
            continue
        files[name] = source
        if source.suffix.lower() == ".md":
            pending.extend(relative.parent / reference for reference in local_markdown_files(source.read_text(encoding="utf-8")))
    return dict(sorted(files.items()))


def emit_distribution(d, slug, skill, compact, fm):
    """Compile the pack to the two places a system is actually installed.

    Both are generated from the same builds as everything else, so a system
    cannot be correct in one target and stale in another. Nothing here is
    hand-written; `dist/` is regenerated on every run.

      dist/claude/<slug>/SKILL.md   an Agent Skill. SKILL.md already carries the
                                    name and description in its frontmatter, so
                                    the work is bundling its references, assets,
                                    advertised templates and pack licence.
      dist/cursor/<slug>.mdc        a Cursor rule. The compact build is used: a
                                    rule sits in context permanently, which is
                                    the case the compact build exists for.
    """
    dist = os.path.join(d, "dist")
    claude_dir = os.path.join(dist, "claude", slug)
    cursor_dir = os.path.join(dist, "cursor")
    sources = claude_bundle_sources(d)
    os.makedirs(os.path.dirname(claude_dir), exist_ok=True)
    os.makedirs(cursor_dir, exist_ok=True)

    # Stage a complete copy before replacing this generated target. Rebuilding
    # its inventory removes obsolete assets/references instead of shipping them
    # indefinitely, and a missing source cannot destroy the previous bundle.
    with tempfile.TemporaryDirectory(prefix=f".{slug}-", dir=os.path.dirname(claude_dir)) as staging:
        for relative, source in sources.items():
            target = Path(staging) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        if os.path.islink(claude_dir):
            os.unlink(claude_dir)
        elif os.path.exists(claude_dir):
            shutil.rmtree(claude_dir)
        os.replace(staging, claude_dir)

    # Cursor wants its own frontmatter. Take the description from the source's,
    # rather than restating it, so the two cannot drift.
    desc = ""
    m = re.search(r'^description:\s*"?(.*?)"?\s*$', fm, re.M)
    if m:
        desc = m.group(1)
    rule = (f"---\ndescription: {desc}\nglobs:\nalwaysApply: false\n---\n\n"
            + compact.split("---\n", 2)[-1].lstrip())
    (Path(cursor_dir) / f"{slug}.mdc").write_text(rule, encoding="utf-8")
    return 2


def compile_pack(d, quiet=False):
    src = os.path.join(d, "SOURCE.md")
    if not os.path.exists(src):
        legacy = os.path.join(d, "SKILL.md")
        if os.path.exists(legacy):
            os.rename(legacy, src)
        else:
            print(f"  ! {d}: no SOURCE.md", file=sys.stderr); return None
    name = os.path.basename(os.path.normpath(d)).capitalize()
    fm, head, sections, _ = parse(src)

    skill = build_skill(fm, head, sections)
    compact = build_compact(fm, head, sections, name)
    reference = build_reference(head, sections, name)

    open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8").write(skill)
    open(os.path.join(d, "SKILL-compact.md"), "w", encoding="utf-8").write(compact)
    open(os.path.join(d, "REFERENCE.md"), "w", encoding="utf-8").write(reference)

    slug_for_dist = os.path.basename(os.path.normpath(d))
    c_src = count_constraints(open(src, encoding="utf-8").read())
    c_core = count_constraints(skill)      # identical statements dedupe, so the
    c_comp = count_constraints(compact)    # floors restated at both ends count once
    n_arch, n_col = emit_machine_layer(d, name, sections, c_core, c_comp)
    # Referenced contracts/AGENTS must be current before packaging them.
    n_dist = emit_distribution(d, slug_for_dist, skill, compact, fm)
    over = max(c_core, c_comp) > BUDGET
    if not quiet:
        flag = "OVER" if over else "ok  "
        print(f"  {flag} {name:11s} source {c_src:3d} -> core {c_core:3d} · compact {c_comp:3d} "
              f"(budget {BUDGET})   json: {n_col} tokens, {n_arch} moves, "
              f"dist: {n_dist} targets")
    return c_core, c_comp, over





# ---------------------------------------------------------------------------
# v0.4.1 — machine-readable layer.
#
# Published benchmark evidence (Indeed, 1,056 prompts across 8 MCP configs):
# Markdown burned ~30,000 tokens per query at 82% coverage with hallucinations;
# JSON reached higher accuracy with 80% fewer tokens and 5x lower annual cost.
# Their rule, adopted here: JSON for MCP, Markdown for LLM. Structured data is a
# contract; instructions are natural language.
#
# Emits per pack:
#   tokens.json      the token contract
#   archetypes.json  the move index, machine-readable
#   manifest.json    what an importer reads first
#   AGENTS.md        orchestration entry point: always-on rules, retrieval, trust
# ---------------------------------------------------------------------------
import json

ROLE = {
    "ground": "The only permitted page ground",
    "ink": "Body text, display type, primary fills",
    "rule": "Hairlines and table rules",
    "muted": "Labels, secondary data, captions",
    "signal": "Identification and single-point emphasis. Never a data series",
    "accent": "Single accent. Never a field or background",
    "link": "Interaction. Default browser blue, honoured, not restyled",
    "visited": "Visited links, honoured",
    "yellow": "Highlight and primary action fill. Text stays ink",
    "red": "The axis bar, one emphasis, interaction",
    "cyan": "Interaction only. Links, buttons, controls",
    "pink": "Expression only. Never clickable",
    "brass": "Ornament and rule only. Never type, never interactive",
    "jade": "Single accent, once per artefact. Interaction",
    "ground-alt": "Secondary ground, posters only",
    "focus": "Focus ring. Always visible, never removed",
    "border": "Border weight. The weight is the identity",
    "offset": "Hard shadow offset. A solid, never a blur",
}

def parse_tokens_css(path):
    """tokens.css stays the single source; JSON is compiled from it."""
    if not os.path.exists(path):
        return {}, {}, {}
    css = open(path, encoding="utf-8").read()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)          # drop comments
    pairs = re.findall(r"--([a-z0-9-]+)\s*:\s*([^;]+);", css, re.I)
    colour, type_, system = {}, {}, {}
    for k, v in pairs:
        v = v.strip()
        if k.startswith("font-"):
            type_[k.replace("font-", "")] = v
        elif re.match(r"^#[0-9A-Fa-f]{3,8}$", v):
            entry = {"value": v}
            if k in ROLE:
                entry["role"] = ROLE[k]
            colour[k] = entry
        else:
            system[k] = v
    return colour, type_, system


JOB_CODE = {"evidence":"E","structure":"S","narrative":"N","change":"C",
            "transaction":"T","wayfinding":"W"}

def clean_md(t):
    """Strip markdown emphasis and code marks — JSON is a contract, not prose."""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"\*(.+?)\*", r"\1", t)
    t = re.sub(r"`(.+?)`", r"\1", t)
    return t.strip()


def parse_archetypes(sections):
    """Pull the archetype table out of SOURCE.md into a machine-readable index."""
    body = ""
    for t, b in sections.items():
        if t.lower().startswith("archetypes"):
            body = b
            break
    out = []
    for ln in body.splitlines():
        if not ln.strip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0].lower() in ("job", "---") or set(cells[0]) <= set("-: "):
            continue
        job = clean_md(cells[0])
        out.append({"job": JOB_CODE.get(job.lower(), job),
                    "jobName": job,
                    "move": clean_md(cells[1]),
                    "when": clean_md(cells[2]),
                    "why": clean_md(cells[3])})
    return out


JOBS = {
    "E": "Evidence — the proof is the argument",
    "S": "Structure — the shape of the thinking is the value",
    "N": "Narrative — words carry the weight",
    "C": "Change — the story is a movement between states",
    "T": "Transaction — the deal, scope or ask needs stating plainly",
    "W": "Wayfinding — the reader needs to know where they are",
}


def emit_machine_layer(d, name, sections, core_constraints, compact_constraints):
    colour, type_, system = parse_tokens_css(os.path.join(d, "assets", "tokens.css"))
    archetypes = parse_archetypes(sections)
    slug = os.path.basename(os.path.normpath(d))

    tokens = {"$schema": "https://standards.appliedform.co/token-contract-v1.json",
              "system": name, "version": "1.0.0",
              "note": "Compiled from assets/tokens.css. Do not edit directly.",
              "colour": colour, "type": type_, "system_values": system}
    json.dump(tokens, open(os.path.join(d, "tokens.json"), "w", encoding="utf-8"), indent=2)

    arch = {"system": name, "indexedBy": "rhetorical job, not visual form",
            "jobs": JOBS,
            "selection": "One move is active per artefact. The rest are reference. "
                         "This is a selection mechanism, not a list to satisfy.",
            "moves": archetypes}
    json.dump(arch, open(os.path.join(d, "archetypes.json"), "w", encoding="utf-8"), indent=2)

    manifest = {
        "name": f"{name} — a Standards pack",
        "publisher": "Applied Form", "version": "1.0.0", "schema": "v0.4",
        "type": "design-system",
        "description": (sections.get("Position") or "").split("\n")[0][:200] or
                       f"{name}, a house-style system for AI-assisted work.",
        "entry": "AGENTS.md",
        "instructions": {"frontier": "SKILL.md", "compact": "SKILL-compact.md",
                         "reference": "REFERENCE.md"},
        "contracts": {"tokens": "tokens.json", "archetypes": "archetypes.json"},
        "assets": {"css": "assets/tokens.css",
                   "chartTheme": "assets/chart-theme.json",
                   "matplotlib": f"assets/{slug}.mplstyle"},
        "templates": {"document": f"{name}-report.docx", "deck": f"{name}-deck.pptx"},
        "constraints": {"coreCount": core_constraints,
                        "compactCount": compact_constraints, "budget": BUDGET,
                        "note": "Instruction-following degrades as constraints accumulate. "
                                "Adding rules to the core costs compliance on the rules already there."},
        "typeLicence": "open" if slug != "raw" else "system fonts only, none required",
        "attribution": "Extends a design tradition. Reproduces no organisation's marks. "
                       "Not affiliated with or endorsed by any institution referenced.",
    }
    json.dump(manifest, open(os.path.join(d, "manifest.json"), "w", encoding="utf-8"), indent=2)

    # AGENTS.md — the orchestration entry point the category expects
    ft, fb = floors(sections)
    mats = sections.get("Materials", "")
    pal = "\n".join(f"- `--{k}` `{v['value']}` — {v.get('role','')}".rstrip(" —")
                    for k, v in colour.items())
    jobs_line = " · ".join(sorted({a["job"] for a in archetypes}))
    ag = f"""# {name} — agent instructions

A Standards pack, from Applied Form. This file is the entry point. Read it first.

## Always on — load these for every artefact

These are foundations. Retrieval will not surface them, because a request for one component
returns that component and nothing else, and the gaps get filled with assumptions.

### Floors — never varied, and they override everything below
{fb or "See SKILL.md."}

### Palette — no colour outside this set
{pal}

## On demand — retrieve when the task calls for it

| Need | Read |
|---|---|
| The system's rules, on a frontier model | `SKILL.md` |
| The system's rules, on a small or fast model | `SKILL-compact.md` |
| Full rationales, conflict register, failure modes | `REFERENCE.md` |
| Token contract, machine-readable | `tokens.json` |
| Move index with triggers, machine-readable | `archetypes.json` |

Load `SKILL.md` **or** `SKILL-compact.md`, never both. The core carries
{core_constraints} constraints against a budget of {BUDGET}. Instruction-following degrades as
constraints accumulate, so loading the reference alongside the core costs compliance on
the core.

## Selecting a move

Archetypes are indexed by rhetorical job ({jobs_line}), not by visual form. Pick the one
whose trigger matches the situation. One move is active per artefact; the rest are
reference. Do not attempt to satisfy the whole index.

## Trust levels

| Action | Autonomy |
|---|---|
| Apply tokens, spacing, type scale | Auto |
| Select an archetype by its trigger | Auto |
| Resolve a rule collision using the conflict register | Auto |
| Resolve a collision the register does not cover | Ask |
| Introduce a colour, face or format outside the canon | Never |
| Vary an accessibility floor | Never |

## Before finalising

Restate and check the floors above. They are repeated deliberately: instructions in the
middle of a long context are followed less reliably than those at either end.
"""
    open(os.path.join(d, "AGENTS.md"), "w", encoding="utf-8").write(ag)
    return len(archetypes), len(colour)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--all", action="store_true", help="treat path as a directory of packs")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if any build exceeds the constraint budget")
    ap.add_argument("--audit", action="store_true",
                    help="list every counted constraint, so the count can be checked by eye")
    a = ap.parse_args()
    print("Standards pack compiler — schema v0.4\n")
    packs = []
    if a.all:
        packs = [os.path.join(a.path, d) for d in sorted(os.listdir(a.path))
                 if os.path.isdir(os.path.join(a.path, d))]
    else:
        packs = [a.path]
    over_any = False
    for full in packs:
        r = compile_pack(full)
        if r and r[2]:
            over_any = True
    if a.audit:
        for full in packs:
            skill = os.path.join(full, "SKILL.md")
            if not os.path.exists(skill):
                continue
            uncond, cond = constraint_units(open(skill, encoding="utf-8").read())
            print(f"\n--- {os.path.basename(os.path.normpath(full))}: "
                  f"{len(uncond)} unconditional + {max(cond) if cond else 0} "
                  f"from the largest archetype ---")
            for u in sorted(uncond):
                print(f"    {u[:110]}")
    print("\nBuilds: SKILL.md (frontier) · SKILL-compact.md (small models) · REFERENCE.md (on demand)")
    if over_any:
        print(f"\nAt least one build exceeds the budget of {BUDGET} active constraints.")
        print("Schema v0.4 rule 2: cut rather than reorganise.")
        if a.strict:
            sys.exit(1)
