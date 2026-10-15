# Instrument

**A Standards pack. Standards by Applied Form.**

Free, complete and reusable under CC BY 4.0 — the whole system, not a sample.

Technical modernism, for AI-assisted work. Public Sans and DM Mono on white, an ink band,
high density, signal red used once. Descended from the institutional graphic programmes of
the 1960s and 70s.

## What's in it

| File | What it is |
|---|---|
| `SKILL.md` · `SKILL-compact.md` · `REFERENCE.md` | Two core instruction structures and on-demand detail |
| `SOURCE.md` | The single source the three builds are compiled from |
| `assets/tokens.css` | Design tokens for any web project |
| `assets/chart-theme.json` | Chart configuration for JS charting libraries |
| `assets/instrument.mplstyle` | matplotlib style for Python plots |
| `Instrument-report.docx` | Word template |
| `Instrument-deck.pptx` | Deck template with speaker-note triggers |

## Which build to use

| File | Structure | Why it exists |
|---|---|---|
| `SKILL.md` | Flat core | Core only, under the constraint budget |
| `SKILL-compact.md` | Clustered core | The same core rules grouped by category, with explicit precedence, a numbered checklist and a verification line |
| `REFERENCE.md` | Either, on demand | Full archetype rationales, data treatment, conflict register, failure modes. Load when a specific answer is needed |
| `SOURCE.md` | Authoring only | The single source. Edit this, then recompile — never edit the builds directly |

Recompile with `python3 schema/compile.py --all packs`.

The two instruction structures are evaluation conditions. Published work motivates the
comparison, but this repository has not yet established which performs better for a given
design task or model. Choose explicitly and record the choice rather than inferring it from
a model label.

**On constraint count.** The core build is held under twenty active constraints as an
explicit design hypothesis: shorter, prioritised instructions may be easier for an agent to
apply consistently. This repository has not established the threshold or shown that adding
one rule necessarily reduces compliance with another. The public evaluation protocol tests
context length alongside conformance and design review before any such claim is made.

## Installing the skill

**Claude.** Drop `SKILL.md` and the `assets/` folder into a skill directory, or add the
contents of `SKILL.md` to a Project's instructions. Then ask for work "in Instrument".

**Cursor and similar.** Paste `SKILL.md` into a rules file. It is written to be read as
instructions, not documentation.

**Anything else.** `SKILL.md` is plain markdown and works as a system prompt as-is.

## Using the templates

Both templates are working documents, not empty shells. Replace the content and the system
holds, because the structure carries the rules rather than the sample text. The deck's
speaker notes state each archetype's trigger, so the deck also teaches the system.

## Type

Public Sans and DM Mono, both open licence, both on Google Fonts:

```
https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600;800&family=DM+Mono:wght@400;500&display=swap
```

Nothing in this pack requires a commercial font licence. The pack contains no font
binaries. The retained React workflow examples embed redistributable WOFF2 files for
offline reproduction and carry the complete SIL Open Font License 1.1 notices separately
and inside the HTML metadata.

## The rules, in one screen

Five colours and no sixth. Every numeral, unit and identifier in DM Mono. Measure never
past 66 characters. Nothing off the 8px scale. No image assets, no ornament, no italic, no
rounded corners, no shadow. Signal red identifies one thing or means interactive, never
both on one surface. One loud element in eight.

When two rules collide, the conflict register in `SKILL.md` decides.

## Lineage and attribution

Instrument extends a tradition of institutional graphic systems, among them the NASA
Graphics Standards Manual (1975), the National Park Service Unigrid (1977) and Otl Aicher's
Munich 1972 programme. It reproduces no organisation's marks, logotypes or identity, and is
not affiliated with or endorsed by any institution referenced. All sample data is
illustrative and describes no real product or programme.
