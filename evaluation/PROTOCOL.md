# Schedule comparison protocol

Protocol version: 0.4.1. This is an exploratory analysis protocol for the first public
Schedule evaluation. The CLI refuses confirmatory execution until the entry gates below
are implemented. Amend and externally freeze this protocol before a confirmatory run;
start a new run rather than changing a completed run.

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

Development fixtures are in `fixtures/dev/`; procedural held-out fixtures are in
`fixtures/held-out/`. They are synthetic and public. “Held-out” means they are excluded
from development decisions for this study, not that they are secret or guaranteed absent
from a model's training data.

Before a confirmatory run:

1. Freeze the selected model routes, conditions, fixture hashes, repetitions, generation
   settings, renderer identity, and protocol file hashes in `precommit.json`.
2. Freeze the live provider catalogue in `model-snapshot.json` before any generation.
3. Do not edit prompts, rules, fixtures, checker behavior, or renderer code during a run.
4. Treat a changed model route, renderer, rule build, or checker as a new experiment.

Exploratory runs may use any explicitly recorded model set. A future confirmatory run must
use at least three models from more than one model family. Decide the model set and
repetition count before inspecting comparative outputs. Three repetitions are useful for
plumbing and variance discovery but are usually too few for a strong general claim;
increase the count based on the minimum effect worth detecting and observed development
variance before opening held-out results.

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

OpenRouter fallback is disabled, but the initial eligible underlying provider endpoint is
not pinned by this adapter. Record the resolved provider when supplied. A confirmatory
declaration must either pin it or define a route-level estimand and a rule for endpoint
changes before any scores are opened.

Run development first. The current release permits exploratory inspection of either split,
but `--mode confirmatory` fails closed. Lock an amended protocol and the number of held-out
repetitions outside the generated run directory before enabling that mode. A smoke run is
operational evidence only and stays outside the repository by default.

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
unknown findings, and earliest attempt as the final tie-break. Count candidates that fail to
improve this order as rejected regressions. A rejected candidate remains evidence and never
replaces a stronger earlier artifact.

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
`first-pass-for-H1`: every card uses attempt 0, whether or not a later repair succeeds.
Reviewers receive shuffled `designer-review.json` cards and PNG-only
`designer-review-assets/` copies. Cards use
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

Use these anchors; 2 and 4 are intermediate judgments:

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| Visual hierarchy | Reading order is unclear or misleading | Main order is clear, with noticeable lapses | Priority and order are immediate and sustained |
| System fidelity | Contradicts or barely expresses Instrument | Recognizable, with generic or inconsistent passages | Coherent and consistent throughout |
| Legibility | Key content is difficult to read at a supplied viewport | Readable, with visible density, spacing, or scale problems | Comfortable and well-spaced at every viewport |
| Rhetorical fit | Obscures scope, duration, or amount | Communicates the transaction with some ambiguity | Makes scope, duration, and amount precise at a glance |
| Overall | Not credible for the stated professional task | Usable but needs visible refinement | Polished, distinctive, and ready for the stated task |

Use at least two designers for a claim about perceived quality. Keep their raw score files,
report agreement as well as means, and disclose reviewer selection and conflicts. Resolve
missing or invalid ratings through the declared review process before unblinding; never
remove a low score after seeing its condition.

## Comparative reporting

The current commands produce descriptive, failure-aware group summaries only. They do not
implement paired estimates, intervals, non-inferiority, model-family strata, or agreement
between reviewers. A future confirmatory analysis must report paired condition differences
within model, case, and repetition when all paired observations exist, alongside the
unpaired all-trial failure-aware rates. Give uncertainty intervals and the exact interval
method. Separate development, held-out, and model-family results. A pooled mean can
supplement those views but cannot replace them.

## Confirmatory entry gates

The public CLI rejects `--mode confirmatory`. Do not remove that gate until all of the
following exist in code and in an externally timestamped declaration created before the
held-out run:

1. the exact model routes and family strata, conditions, held-out fixtures, repetitions,
   provider-endpoint rule, and generation settings;
2. a numerical minimum effect and non-inferiority margin, the paired estimator, interval
   method, missing-data rules, and any multiplicity handling;
3. two or more declared designers, immutable score files, an agreement statistic, and a
   rule for missing artifacts and ratings;
4. tested analysis code that consumes the retained trial records and refuses undeclared
   strata or a changed protocol, renderer, or catalogue identity.

Publish the complete precommit, catalogue snapshot, trial JSONL, retained scrubbed provider
response or normalized error records, artifacts, checker reports, failure records, blinded score sheets, unblinding key after
review, analysis code, and known limitations. Avoid a universal “better” claim. State the
models, routes, cases, date, system version, and outcomes for which the evidence applies.

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

If model identity is unresolved, the frozen zero-price guard fails, the renderer identity
changes, the checker cannot evaluate an artifact, or blinding is broken, disclose that
stratum and exclude it only under a rule declared before unblinding. Otherwise keep it in
the relevant failure denominator.
