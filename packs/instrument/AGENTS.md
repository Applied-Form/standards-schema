# Instrument — agent instructions

A Standards pack, from Applied Form. This file is the entry point. Read it first.

## Always on — load these for every artefact

These are foundations. Retrieval will not surface them, because a request for one component
returns that component and nothing else, and the gaps get filled with assumptions.

### Floors — never varied, and they override everything below
Body contrast 4.5:1, display 3:1. Colour never the only signal. Focus always visible.
Measure ceiling 66ch. Open-licence type only.

### Palette — no colour outside this set
- `--ground` `#FFFFFF` — The only permitted page ground
- `--ink` `#111111` — Body text, display type, primary fills
- `--rule` `#D8D8D8` — Hairlines and table rules
- `--muted` `#6B6B6B` — Labels, secondary data, captions
- `--signal` `#C8102E` — Identification and single-point emphasis. Never a data series
- `--focus` `#C8102E` — Focus ring. Always visible, never removed

## On demand — retrieve when the task calls for it

| Need | Read |
|---|---|
| The system's flat core rules | `SKILL.md` |
| The same core rules, clustered with precedence | `SKILL-compact.md` |
| Full rationales, conflict register, failure modes | `REFERENCE.md` |
| Token contract, machine-readable | `tokens.json` |
| Move index with triggers, machine-readable | `archetypes.json` |

Load `SKILL.md` **or** `SKILL-compact.md`, never both. The core carries
18 constraints against a budget of 20. Instruction-following degrades as
constraints accumulate, so loading the reference alongside the core costs compliance on
the core.

## Selecting a move

Archetypes are indexed by rhetorical job (C · E · N · S · T · W), not by visual form. Pick the one
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
