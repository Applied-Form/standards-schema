# System schema v0.4

A specification for authoring house style systems intended to be executed by language
models.

**Status:** current. Supersedes v0.3.

v0.1 → v0.3 were derived by reverse-engineering historical manuals and revised against
build evidence. v0.4 is the first version revised against published
instruction-following literature. Two internal development comparisons also shaped the
questions, but a later-identified blinding defect invalidates their consistency outcome;
no comparative result from those rounds is evidence for this revision.

---

## What changed, and why

### The evidence issue that forced the rewrite

**Correction, 1 September 2026.** Two internal development rounds attempted to compare a
flat schema with a layered, precedence-ordered one. Their consistency measure was collected
through a blinding defect in `study.html`: identities were revealed after question 1 and
question 2 re-rendered the same artefacts. The interface is fixed, but both rounds must be
re-run. Their apparent outcomes, including any brief counts, must not be cited.

The published work explains this precisely, and had already tested the same intervention on
the same model class. A benchmark stacking verifier-checked instructions found that
follow rate falls from around 96% at one instruction to between 20% and 60% at twenty, and
that the decline is non-linear. It then evaluated a rewrite that clusters instructions by
category, merges overlapping ones, and inserts a precedence note where two rules conflict —
which is what the v0.3 layered structure does.

Its benefit is **capability-graded**: roughly +11 points of follow rate for the weakest
model tested, +3.3 for the middle one, and essentially unchanged for the strongest, where
the measured effect was −1.2 points and not statistically robust. The proposed mechanism is
that a strong model reconstructs the structure while reading the raw prompt, so writing it
out helps a weaker model and adds little for a stronger one.

**So the v0.3 conclusion was too broad.** Precedence is not useless, but the published
capability-graded result is a hypothesis for this domain rather than proof about these
design tasks. The v0.4 rewrite depends on the literature below and on a smaller active
constraint set; the invalidated internal comparisons provide no supporting result.

### The finding I had underweighted

Constraint count. An audit of the six shipped packs:

| Pack | Constraint-bearing statements |
|---|---|
| Agitprop | 30 |
| Broadsheet | 31 |
| Contra | 31 |
| Instrument | 32 |
| Raw | 31 |
| Cornice | 37 |

Every pack sits past the point where measured follow rate falls to between a fifth and
three fifths. No structural arrangement fixes that; only fewer active constraints does.

The same work found the failure is not uniform forgetting but structured interference:
around 12% of satisfiable instruction pairs fail significantly more often than their
individual rates predict, and the interaction topology is reproducible across models and
tasks. Rule collisions are real, which vindicates the conflict register as a concept while
relocating where its benefit lands.

### The third finding

Position. Separate work on primacy and recency effects reports that instructions in the
middle of a long prompt lose compliance relative to those at the edges, a structural
consequence of how attention distributes across a sequence. Every v0.3 pack states its
accessibility floors once, at the top, and never again.

---

## The three rules of v0.4

### 1. One source, two compilations

A system is authored once as `SOURCE.md` and compiled to two delivery formats.

| Build | Evaluation condition | Structure |
|---|---|---|
| `SKILL.md` | Flat core | Core only. Minimum viable constraint set |
| `SKILL-compact.md` | Clustered core | Same rules, with precedence, a numbered checklist and verification line |
| `REFERENCE.md` | On demand | Full detail. Loaded when a specific answer is needed |

The compact build follows the structure evaluated in the literature. Its benefit for a
specific design task and model remains an empirical question. Treat both builds as named
conditions, record the choice and do not infer it from a model label.

### 2. A constraint budget, enforced

**Target: no more than twenty active constraints in any single call. Aim for twelve.**

"Any single call" includes the compact build, which is loaded on its own. It carries the
same rule set as the core, restructured — never a larger one. A compact build that adds
sections is backwards: the collapse curve is steepest on exactly the models it is for.

Three mechanisms get there.

**Prune.** Remove any constraint that restates a floor, that no artefact has ever violated,
or that a competent reader would infer. Length is not thoroughness. Check before pruning:
Instrument's "red never carries small text on white" looks like a restatement of the
contrast floor and is not — the red passes at 5.88:1, so that rule is stricter than the
floor, and cutting it would lose a real constraint.

**Attach.** Every prohibition sits on the element it governs. A gathered list at the end is
a checklist for the reference build, never the only home for a rule: a prohibition that
exists only in that list does not reach the flat core build at all. Thirteen rules across
five packs were lost this way before it was caught.

**Tier.** Split into an always-loaded core and an on-demand reference. The core carries
identity, materials, prohibitions and the archetype triggers. The reference carries the
full archetype rationales, data treatment, the conflict register and the failure modes. A
model producing a poster does not need the table rules in context.

**Select.** The archetype index is a selection mechanism, not a list to satisfy. One move is
active per artefact; the other eight are reference. Indexing by rhetorical job is what makes
selection possible, so that structure survives from v0.3 intact.

**What counts as one constraint.** The budget is only meaningful if the unit is defined,
and the unit is a *statement in force*, not a word.

- A statement counts once however many trigger words it carries. "Colour never the only
  signal" is one floor, not two.
- Identical statements count once however often they repeat. The floors are deliberately
  stated at both ends of a build; that is one set of rules, not two.
- The archetype `When` column is a selection trigger, not a rule to obey, and is not
  counted. "A legend must be understood before the data" tells the model when to reach for
  a move; it is not a constraint on the output.
- A move's own prohibitions are **conditional**. One move is active per artefact, so the
  active count carries the largest single move's prohibitions, not all nine sets. This is
  the selection argument above, applied to the measurement rather than only to the prose.
- A conflict-register row is a **tiebreaker**, not a rule. "Measure wins" adds no obligation
  the measure ceiling did not already impose; it says which of two counted rules yields.
  Counting resolutions would count the same constraint twice, once as a rule and again as
  its own tiebreak.
- Headings, callouts and explanatory prose are not rules.

`compile.py --audit` prints every statement it counted so the number can be checked by eye,
and `--strict` exits non-zero when a build is over. Counting occurrences of a few English
words instead would double-count single rules, count triggers and prose as constraints, and
could be reduced by rewording rather than by cutting — which is the opposite of the
intended behaviour.

Count the constraints. If a build exceeds twenty, cut rather than reorganise.

### 3. Floors at both ends

State the accessibility floors at the top of the core **and restate them as the last thing
before the model generates.** This is not redundancy for a human reader; it is placing the
non-negotiable rules where compliance is measurably highest.

Anything else that must never be violated goes in both positions too. Everything else goes
once, in the middle, and accepts a lower compliance rate.

---

## The layers, retained as an authoring discipline

The six-layer structure from v0.3 stays, demoted from delivery format to drafting method.
Writing a conflict register is still what forces the author to decide what wins when density
fights the measure ceiling. Those decisions belong in the system. The scaffolding that
produced them does not have to ship in the core instruction context.

**Layer 0 — Invariants.** Accessibility floors, licence terms, no asset dependency. Identical
in every system. Appear at both ends of the core.

**Layer 1 — Position.** Name, lineage, stance, refusals, nearest neighbour and the tell,
extensibility posture.

**Layer 2 — Canon.** Permitted formats, artefact set, invariant element, production
constraints.

**Layer 3 — Materials.** Type, colour, imagery stance, ornament, mark construction, state
encoding, interaction colour.

**Layer 4 — Composition.** Spatial strategy, base unit, archetypes indexed by rhetorical job
with When and Why, density, sequence, attention budget.

**Layer 5 — Variation.** Variation budget, product register (required in every system, even
when the answer is "none needed"), deviation grammar where applicable.

**Layer 6 — Compilation and control.** Data treatment, targets, conflict register, failure
modes.

---

## The shared rhetorical-job taxonomy

Unchanged, and now doing more work than before, since it is the selection mechanism that
keeps the active constraint count down.

| Code | Job | When it applies |
|---|---|---|
| **E** | Evidence | The proof is the argument |
| **S** | Structure | The shape of the thinking is the value |
| **N** | Narrative | Words carry the weight |
| **C** | Change | The story is a movement between states |
| **T** | Transaction | The deal, the scope, the ask needs stating plainly |
| **W** | Wayfinding | The reader needs to know where they are |

---

## Authoring checklist

- [ ] **Both** builds are under twenty constraints. Counted by `compile.py`, not estimated.
- [ ] Floors appear at the top of the core and again at the end.
- [ ] Archetypes indexed by job, each with a When trigger.
- [ ] Product register stated, even if the answer is "none needed".
- [ ] Conflict register written — it belongs in the reference and the compact build.
- [ ] Prohibitions attached to the element they govern, not gathered in one list.
- [ ] Nearest neighbour named, with the single distinguishing tell.
- [ ] Both builds compiled from one source. Never edited separately.

---

## Open questions

1. Does the constraint budget hold at twenty, or is the real number lower for design work
   than for the verifier-checkable instructions the benchmark used? Testable, and the
   harness can be adapted to it.
2. **Is the compact build actually better on a small model?** This is inference from the
   literature, not evidence from these systems, and it is the single highest-value
   experiment remaining. Run the shipped-builds payload against `claude-haiku-4-5`, then
   Sonnet as the control. It is a decision gate, not a curiosity: if compact wins, the
   strongest claim in the product becomes owned rather than borrowed; if it does not, drop
   the split and ship one build, which is a cheaper product to maintain and worth knowing.
   Everything needed to run it is in place — the harness is fixed, blinded, and persists
   progress. What it needs is an API key and a judge, both of which are human.
3. Does tiering into core and reference cost anything when the reference is never loaded?
4. My two studies measured judged quality, the literature measures verifier-checkable
   compliance. Those are different questions and the agreement between them is only
   suggestive.

---

## Sources

- Anand & Chattaraj, *Instruction Stacking Collapse: A Benchmark and the Capability-Dependent
  Value of Prompt Compilation*, arXiv:2608.02639 — collapse curve, conflict topology, the
  capability-graded value of precedence-style compilation.
- Zhou et al., *Instruction-Following Evaluation for Large Language Models*, arXiv:2311.07911.
- Jiang et al., *FollowBench*, ACL 2024 — multi-level constraint following.
- Guo et al., *RECAST*, arXiv:2505.19030 — degradation as constraint count rises.
- Work on primacy and recency effects in prompts — position-dependent compliance.

**Method note.** v0.1–v0.3 were built without reference to this literature. That was a
mistake, and it cost two studies to discover something already published with better
statistics. The lesson is recorded here so the next version starts from the field rather
than from first principles.
