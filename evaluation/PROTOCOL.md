# Schedule comparison protocol

Protocol version: 0.5.0. This release contains an exploratory harness and a fail-closed
confirmatory implementation for the public Schedule evaluation. No protocol 0.5
confirmatory run or superiority result exists. Externally freeze a strict declaration and
receipt before a held-out run; start a new study rather than changing frozen or completed
evidence.

## Questions and hypotheses

The experimental unit is one model × case × condition × repetition trial. The same fixed
case appears in every generative condition for a model and repetition, allowing paired
condition comparisons.

- **H1 — brief fulfilment:** the agent-native prompt package increases first-pass,
  marker-independent brief fulfilment relative to the original brief, prose brand bible,
  and strong generic scaffold baselines.
- **H2 — context efficiency:** selected context retains brief fulfilment and agent-contract
  conformance while reducing provider-reported prompt tokens relative to the full rule build.
- **H3 — repair:** a bounded, finding-linked repair recovers a measurable share of
  first-pass agent-contract failures while preserving all original-brief facts.

These are unproven hypotheses. The deterministic component is a reference for the plan,
renderer, and checker path; it is not evidence that a model-guidance condition is better.

## Treatment and estimand

`raw_brief` and `brand_bible` receive the same user-facing projection of the original
fixture: format, title, Schedule data, and viewports. They receive the same minimal request
for a static, self-contained HTML response. The latter also receives prose design guidance.
Neither minimal baseline receives engine fields, the compiled plan, component binding, fact ledger,
detailed HTML contract, or model repair assistance. Every fixture explicitly declares all
four column labels, so the compiler does not add source facts seen only by a treatment.

`scaffolded_html`, `full_rules`, `compact_rules`, and `selected_context` receive one
byte-identical normalized source-task payload and the same generic scaffold. The scaffold
specifies static, self-contained HTML; accessible table semantics; responsive viewport
fit; and source-derived fact IDs mapped to semantic slots. It contains no Instrument name,
visual materials, tokens, selected move, rule IDs, package binding, or repair instructions.
The three agent-native treatments add only their declared Instrument rule context to that
generic scaffold. Up to two finding-linked repairs are available only to the agent-native
treatments; `scaffolded_html` always stops after its first call. Every artifact is
rendered and measured after generation by the same deterministic, treatment-blind
brief-fulfilment path.

For H1, comparisons with `raw_brief` and `brand_bible` estimate the complete package
difference. The first-pass `selected_context` versus `scaffolded_html` comparison isolates
the added design-system context over a strong generic prompt; both have the same source
payload, scaffold, generation settings, and first-call budget. H2 compares rule-context
builds inside the agent-native family.

The stricter checker also evaluates Instrument-specific planner, binding, source, and rule
expectations. Its outcome remains `agentContractConformance` and is null for all three
baselines, including `scaffolded_html`, even though the scaffold shares fact IDs and generic
HTML requirements. Retained checker reports for baselines are diagnostics and must not be
used for a comparative claim.

## Fixed inputs

Six development fixtures are in `fixtures/dev/`; eight procedural held-out fixtures are
in `fixtures/held-out/`. They are synthetic and public. “Held-out” means they are excluded
from development decisions for this study, not that they are secret or guaranteed absent
from a model's training data.

Before a confirmatory run:

1. Freeze the selected model routes, conditions, fixture hashes, repetitions, generation
   settings, renderer identity, and protocol file hashes in `precommit.json`.
2. Freeze the live provider catalogue in `model-snapshot.json` before any generation.
3. Do not edit prompts, rules, fixtures, checker behavior, or renderer code during a run.
4. Treat a changed model route, renderer, rule build, or checker as a new experiment.

Exploratory runs may use any explicitly recorded model set. A confirmatory declaration must
contain exactly six pinned routes spanning at least three model families. Its 5–50
repetitions are chosen before held-out execution by the frozen, seeded paired-binary
simulation at 90% power. The planner refuses a design that cannot achieve that power inside
the repetition range and GBP budget.

## Execution

Use temperature 0 when supported and freeze reasoning as `effort=none` unless the protocol
explicitly studies reasoning. A provider-default reasoning run is a separate treatment;
it must not silently consume the artifact output budget. Record requested settings and
all provider-reported effective settings. Repetition is
still required because hosted inference, routing, and model serving can vary. Run every
selected condition for every model, fixture, and repetition. Retain failed calls and
renders. Do not retry a failed observation in place; a separately labelled rerun is a new
observation.

The runner groups cells by case and repetition, shuffles the blocks, then shuffles every
model/condition cell inside each block. The seed and final call order are frozen in the
precommit so provider load or time trends are less likely to align with one condition.

Exact route integrity is part of validity. Reject automatic routers. Store the requested
model, provider-resolved model, selected provider, response identifier, service tier,
system fingerprint, and routing metadata when supplied. Accept the resolved identity only
when it is the exact requested ID or that route's release-dated canonical identity from
the frozen catalogue.

OpenRouter fallback is disabled. Exploratory runs may leave the initial eligible endpoint
unpinned and must retain that caveat. Every confirmatory route pins one named underlying
provider endpoint. The request uses `provider.only: [pinned]`,
`allow_fallbacks: false`, and `require_parameters: true`, with no model fallback list. An
absent or different returned endpoint is a route-integrity failure retained in the
scheduled denominator. Confirmatory routes may be paid inside the frozen budget; the
zero-price catalogue restriction applies to free exploratory discovery.

One atomic GBP ledger covers qualification, development, and confirmatory calls. Before
every provider call the runner reserves the declared worst-case charge and refuses the call
if that would exceed the remaining £500-or-lower cap. Settlement uses retained
provider-reported USD cost and the frozen exchange rate. Missing usage leaves the full
reservation charged. Automatic top-up is false.

Route qualification is itself a frozen two-block run. Block 1 schedules exactly five calls;
block 2 is a separate resume invocation against the same route ID, model, family, snapshot,
provider pin, generation settings, expiry, and budget assumptions. Every call is journaled,
reserved, retained, and checked for the expected text response, accepted exact/canonical
model identity, returned provider pin, and required parameter envelope. An interrupted
in-flight call is retained as indeterminate and never retried in place. Only ten completed
observations across the two five-call blocks can produce a receipt. The receipt requires at
least nine full successes, ten accepted identities, ten pin matches, ten parameter
acceptances, and at least nine expected text outputs. Failed qualification evidence remains
available without `route-qualification.json`. The precommit binds the immutable identity of
the shared cumulative ledger. Resume recomputes every retained result check and verifies its
path, digest, deterministic reservation ID, settlement, snapshot and ledger identity. A
changed record, changed ledger, open reservation, or cost above its worst-case reservation
blocks qualification.

Run development first. Exploratory inspection may use either public split. Confirmatory
mode accepts only the eight held-out fixtures and derives its matrix from a strict protocol
0.5 declaration. It remains blocked until an externally timestamped receipt binds the clean
release commit, protocol and renderer hashes, frozen catalogue, unexpired route
qualifications, reviewer commitments, budget approval and execution authorization. A smoke
run is operational evidence only and stays outside the repository by default.

## Mechanical outcomes

The primary H1 outcome is binary first-pass `briefFulfilment`. It ignores private marker
attributes and passes only when all four transparent components pass:

1. source safety: structurally complete, static, self-contained HTML;
2. Schedule semantics: one visible H1 and named table, four scoped column headers, the
   planned body rows and row headers, and the planned total-row structure;
3. source-fact coverage: every title, label, explicit column label, line field, total, and
   note from the original brief appears in its normalized semantic slot; and
4. browser evidence: hash-bound evidence and screenshots, viewport fit without browser or
   resource errors, marker-independent browser Schedule checks, and every original-brief
   fact present at every viewport in a marker-ID-agnostic corpus of visible, unclipped,
   unobscured, contrast-passing text.

Every scheduled trial is in the H1 denominator; provider and renderer failures score as no
first-pass fulfilment. Report counts, component records, and rates by split, condition, and
requested model before any pooled number. Source-fact coverage is derived from the frozen
original brief, never from `data-std-fact`.

The stricter checker status is `agentContractConformance`. It includes exact
`data-std-fact` placement, approved-text constraints, and Instrument-specific planner,
binding, source, and rule expectations. Report it before and after repair only for
agent-native conditions and the deterministic reference. Baseline trial values, aggregate
counts, denominators, and rates are null; this includes `scaffolded_html`, whose disclosed
generic contract is only a subset of the checker contract. Retained baseline checker
reports are diagnostics only.

For H2, report first-pass brief fulfilment and agent-contract conformance alongside
provider-reported prompt tokens. Compare selected context with full rules within the same
model and case. Report missing token usage explicitly. Do not describe token reduction as
quality-preserving when brief fulfilment, contract conformance, or blinded design scores
materially deteriorate. The exploratory efficiency metric is all reported prompt tokens
consumed by an agent-native condition/model group divided by its final agent-contract-
conforming artifacts. Its successful-artifact denominator and value are null when there
are no final contract-conforming artifacts; the value is also null for baselines or when
any trial lacks reported prompt-token usage.

For H3, the denominator is agent-native trials that produced a checkable, repairable
first-pass agent-contract failure. Baseline trials are never eligible. Report successful
final contract passes, every repair provider call including a failed call, comparative
source-fact coverage, and agent-contract fact preservation. Provider or renderer failures
before a repair opportunity are reported separately and are not called repair failures.
Group repeated findings by rule before generating a repair prompt so one high-volume rule
cannot truncate later diagnostics. Retain every attempt, then select the deliverable by a
fixed lexicographic policy: contract conformance, brief fulfilment, complete and proportional
source-fact coverage, complete and proportional contract-fact preservation, fewer failed and
unknown findings, and earliest attempt as the final tie-break. Count every candidate that
fails to improve this order, distinguishing a strict regression from a metric tie. A rejected
candidate remains evidence and never replaces a stronger earlier artifact. A tied later
attempt is not evidence that the guard prevented a regression.

H3 is exploratory. Its explicit gate requires at least 30 eligible failures, recovery
estimate at least .30, a seeded one-sided 95% lower bound above .10, and zero selected
content regressions. It never enters a primary confirmatory claim. Confirmatory execution
sets `maxRepairs` to zero; any later repair study needs its own frozen declaration.

Also report:

- final brief fulfilment after zero to two repairs;
- first and final agent-contract conformance for eligible conditions;
- first and final marker-independent source-fact coverage;
- agent-contract marker/fact preservation for eligible conditions;
- client-observed provider latency;
- provider-reported prompt, completion, and total tokens;
- provider-reported cost, including missing values;
- provider, renderer, harness, and model-integrity failure counts with denominators.

Do not replace a missing artifact, usage field, score, or failure with zero unless zero is
the quantity the provider actually reported.

## Blinded design review

Mechanical outcomes do not establish design quality. The precommitted review policy is
`first-pass-for-H1`: every card uses attempt 0 from one predeclared repetition, whether or
not a later exploratory repair succeeds. Exactly three independent reviewers receive
separately shuffled `designer-review-sets/<reviewer>/review.json` files and PNG-only asset
copies. Cards use
cryptographically random IDs and contain no run, case, split, repetition, condition, model,
or trial metadata. Repeated deterministic-reference renders are included at most once per
case so identical control images do not reveal or overweight that condition. Attempt index
and repair state appear only in the hidden key. The key reports scheduled cards, included
cards, missing first-pass renders, and reference duplicates by condition/model. A future
final-product review must use a separately named, precommitted bundle; do not mix repaired
and first-pass artifacts in this H1 review.
They score visual hierarchy, system fidelity, legibility, rhetorical fit, and overall
quality from 1 to 5 using the supplied rubric. Keep `designer-review-key.json` hidden until
all scores and notes are locked.

The review summarizer binds the completed review, hidden key, precommit and run results to
the same run ID, attempt policy and exact protocol version. It fails closed when invoked
from a different protocol version so a newer checkout cannot relabel older evidence.

Use these anchors; 2 and 4 are intermediate judgments:

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| Visual hierarchy | Reading order is unclear or misleading | Main order is clear, with noticeable lapses | Priority and order are immediate and sustained |
| System fidelity | Contradicts or barely expresses Instrument | Recognizable, with generic or inconsistent passages | Coherent and consistent throughout |
| Legibility | Key content is difficult to read at a supplied viewport | Readable, with visible density, spacing, or scale problems | Comfortable and well-spaced at every viewport |
| Rhetorical fit | Obscures scope, duration, or amount | Communicates the transaction with some ambiguity | Makes scope, duration, and amount precise at a glance |
| Overall | Not credible for the stated professional task | Usable but needs visible refinement | Polished, distinctive, and ready for the stated task |

Use exactly three independent declared designers for confirmatory review. Keep their raw score files,
report agreement as well as means, and disclose reviewer selection and conflicts. Resolve
missing or invalid ratings through the declared review process before unblinding; never
remove a low score after seeing its condition.

## Comparative reporting

Run summaries remain descriptive and failure-aware. Confirmatory analysis is a separate,
frozen step. H1 uses the paired risk difference within model, case and repetition, with
every scheduled provider or render failure scored as zero. Its deterministic bootstrap
resamples model strata and cases using the declared seed and replicate count, and reports
model and family strata. The primary comparison is `selected_context` versus
`scaffolded_html`; secondary raw-brief and brand-bible comparisons use Holm-adjusted
one-sided p-values. H1 passes only when the point estimate is at least .10 and its
one-sided 95% lower bound is greater than zero. A missing scheduled cell blocks analysis.

H2 uses first-call provider-reported prompt tokens in complete selected/full pairs and
requires mean token ratio at most .80. Its one-sided 95% lower bounds must exceed the
negative non-inferiority margins for brief fulfilment, agent-contract conformance, and
source-fact coverage. The failure-aware paired designer-overall result uses the same
one-sided interval and a -.25 margin after review sealing; it cannot pass while review is
missing. Report the descriptive all-trial rates alongside these paired outputs.

## Confirmatory entry gates

`validate-declaration` enforces a strict, additional-properties-closed declaration: exact
release and protocol identities; eight held-out fixture hashes; exactly six pinned model
routes spanning at least three declared families; a complete matrix; 5–50 repetitions
selected by the frozen seeded simulation at 90% power; no confirmatory repairs; exactly
20,000 bootstrap resamples; H1 minimum effect .10, alpha .05 and power .90; H2 margins
.05/.05/.02/.25 and mean token ratio no greater than .80; exactly three independent
reviewers with ordinal-alpha threshold .67; renderer digest; protocol hashes; and a GBP
budget ceiling of £500.

`validate-freeze` additionally requires an independent custodian, retained declaration
digest, HTTPS timestamp evidence, signature method/value/key identity with a locally
verified result, release commit, catalogue digest, unexpired route-qualification receipt
hashes, reviewer commitments, frozen cumulative-ledger digest, approved budget and explicit
execution authorization. Every route receipt records exactly ten calls across two time
blocks, at least 90% success and 100% accepted identity. Actual `run --mode confirmatory`
repeats these checks against the clean checkout and
renderer before constructing a provider adapter. It uses the already frozen snapshot and
never performs catalogue discovery. Any mismatch blocks generation.

The deterministic cell journal is written before calls. It records pending, in-flight,
complete and indeterminate cells with matrix and trial hashes. Resume validates all frozen
inputs, preserves a completed response if it reached disk, and converts an unresolved
in-flight cell to a scheduled indeterminate failure without retry.

Each declared reviewer completes a separately shuffled copy of the same opaque first-pass cards.
`review-seal` requires every score, exact card membership and unique declared reviewer IDs;
it hashes raw files and reports ordinal Krippendorff alpha by dimension. The declared
minimum is exactly three reviewers. Missing first-pass artifacts enter condition means at
score 1; missing ratings block sealing. Agreement below the declared threshold blocks the
claim gate.

`analyze` consumes only a complete declaration-bound matrix. It emits an
additional-properties-closed analysis result and cannot make the primary claim gate true
without a matching sealed review set. The implementation makes confirmatory execution
possible after external inputs exist; it does not claim those inputs or evidence currently
exist.

`bundle` creates a separate retention copy, excludes the hidden unblinding key by default,
redacts account and provider response identifiers, rebuilds affected journal hashes and
writes a sorted SHA-256 manifest. Verification rejects symlinks, credential patterns,
private absolute paths, unsafe identifier fields and hash drift. Include the unblinding key
only after every review is sealed and disclosure is intended.

## Interpretation gates

A claim that selected context is more efficient requires lower reported input tokens,
non-inferior brief fulfilment and agent-contract conformance under predeclared margins, no
material source-fact-coverage loss, and no material blinded-design-score loss. A claim that
the agent-native package improves results requires a held-out brief-fulfilment advantage
over the specifically named comparators. A claim that executable design-system context adds
value beyond strong generic prompting requires an advantage over `scaffolded_html` on the
same first-pass budget, with failures retained and uncertainty reported. A claim about
repair requires successful agent-contract recovery plus complete source-fact
coverage and contract fact preservation; repaired appearance alone is insufficient.

If model identity is unresolved, an applicable frozen pricing guard fails, the renderer identity
changes, the checker cannot evaluate an artifact, or blinding is broken, disclose that
stratum and exclude it only under a rule declared before unblinding. Otherwise keep it in
the relevant failure denominator.
