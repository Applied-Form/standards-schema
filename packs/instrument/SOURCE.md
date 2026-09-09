---
name: instrument
description: "Apply the Instrument design system — technical modernism — to any document, deck, page, interface or chart. Use whenever the user asks for output in Instrument, says 'use my house style' and Instrument is their installed system, or asks for a report, deck, data page, dashboard or technical document that should look designed rather than default. Public Sans and DM Mono on white, an ink band, high density, signal red used once. Descended from the institutional graphic programmes of the 1960s and 70s."
---

# Instrument

A Standards pack, from Applied Form. Technical modernism. The page is an instrument: every mark earns its place by carrying
information.

## Before producing anything, answer these four

1. **Which artefact?** Report page · essay opening · deck spread · product screen · poster · chart-and-table.
2. **Which archetype?** Pick from the table below by the job it does, not by how it looks.
3. **Is this a load-bearing surface?** If yes, nothing changes. Instrument has no signature
   device to suspend, which is why it needs no second register.
4. **What is the one loud element?** One per eight. If you cannot name it, there isn't one.

## Materials

**Type.** Public Sans for everything textual, 400/600/800, sentence case. DM Mono for every
numeral, unit, identifier, column header and label — no exceptions, and never for running
prose. Measure never exceeds 66 characters. Never serif, never italic.

**Colour.** Only these five.

| Token | Value | Role |
|---|---|---|
| `--ground` | `#FFFFFF` | The only ground |
| `--ink` | `#111111` | All text, the band, primary fills |
| `--rule` | `#D8D8D8` | Hairlines, table rules |
| `--muted` | `#6B6B6B` | Labels, secondary data, captions |
| `--signal` | `#C8102E` | Identification, one point of emphasis, interaction |

Signal red is never a data series. On any one surface it carries exactly one meaning and
nothing else: clickable where the surface is interactive, emphasis where it is static.

**Grid.** 12 columns, 24px gutter, 8px base unit. Spacing 8/16/24/32/48/64/96. Nothing off
the scale.

**Imagery.** None permitted. Type, rule and data carry the visual load.

**Ornament.** None. Rules are structural, never decorative. No border radius, no shadow, no gradient.

## The invariant element

A solid ink band, four base units deep, full measure, title reversed at 100% white. It
appears on every artefact. On a 1:1 format it drops to three units. This is the mark.

## State encoding

Glyph, word and position together, so everything reads identically in one colour.

`▲ Approved` · `■ In review` · `● Blocked` · `□ Queued`

Tint is optional and never load-bearing.

## Archetypes

Indexed by the job they do. `When` is the trigger; `Why` is what it buys.

| Job | Move | When | Why |
|---|---|---|---|
| Evidence | **Datum** | One figure reframes the section | Scale in mono reads as a measurement, not a boast |
| Evidence | **Plate** | A figure needs a number and caption to be cited later | Makes the evidence quotable |
| Evidence | **Register** | Three or four figures state the position together | Read in one sweep on a shared baseline |
| Structure | **Key** | A legend must be understood before the data | Says the data is worth decoding |
| Structure | **Matrix** | Two variables must be crossed | The grid is the argument |
| Narrative | **Band statement** | A section must be declared, not introduced | The invariant doing rhetorical work |
| Change | **Series** | The same measure across periods | Change reads as shape before number |
| Transaction | **Schedule** | Scope, cost or duration must be stated exactly | Precision is the persuasion |
| Wayfinding | **Running index** | Past page two of a long document | Position is information |

The set is open. A valid addition makes a specific class of data more legible.

## Data treatment

DM Mono, tabular figures, right-aligned. Units always stated. Table headers tracked
uppercase in muted, with a 1.5px ink rule beneath. Series colours: ink and muted only.
Use direct labels and line or marker patterns to distinguish additional series.
Data marks, including a singled-out bar or point, stay ink or muted. A selected datum
has a neutral label and an explicit word or weight cue; one red rule beside that label
may accent it on a static surface. The cue remains legible in one colour, and red never
carries small text on white.

## Density and attention

Density is high — the highest information rate the floors permit. One loud element in
eight; the hero moves are Datum and Plate only. Spend maps to the argument, never to
page count.

## Prohibitions

No serif. No colour beyond the five. No decorative imagery. No centred text except in the
band. No border radius. No shadow. No gradient. No italic. Nothing off the 8px scale.

## Conflict register

When two rules collide, this decides. Where it is silent, the higher-level rule wins.

| Collision | Resolution |
|---|---|
| Density vs measure ceiling | Measure wins. Add columns, never lengthen the line |
| Signal vs contrast floor | Floor wins. Red never carries small text on white |
| Band vs format | On 1:1 the band is three units |
| Datum scale vs display contrast | Contrast wins. Reduce size before reducing contrast |

## Floors — never varied

Body contrast 4.5:1, display 3:1. Colour never the only signal. Focus always visible.
Measure ceiling 66ch. Open-licence type only.

## Failure mode

Pastiche reads as a Swiss poster tribute: oversized ranged-left sans and an arbitrary red
square. The correction is that every element must be doing informational work, and the red
must be identifying something specific.

## Files

- `assets/tokens.css` — paste into any web project
- `assets/instrument.mplstyle` — matplotlib chart theme
- `assets/chart-theme.json` — chart config for JS libraries
- `Instrument-report.docx` — document template
- `Instrument-deck.pptx` — deck template
