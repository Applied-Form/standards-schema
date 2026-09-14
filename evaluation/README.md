# Comparative evaluation

This directory tests a narrow question: does the agent-native generation package—an
immutable plan, fact ledger, explicit HTML contract, design rules, checker, and bounded
repair—produce a first-pass Schedule that fulfils the same original brief more reliably
than asking the same model to work from that brief, a prose brand bible, or a strong
generic HTML scaffold?

Protocol 0.5 supports exploratory work and a fail-closed confirmatory path. The harness
is not evidence of an advantage by itself: no protocol 0.5 confirmatory study has been
run. The included six development and eight procedural held-out fixtures, plus the offline
regression suite, exercise the apparatus. A comparative claim requires an externally
timestamped declaration and freeze receipt, qualified pinned routes, approved budget, a
complete repeated run, frozen paired analysis, and sealed blinded review as described in
[PROTOCOL.md](PROTOCOL.md).

## Conditions

The two minimal baseline conditions receive the same user-facing projection of the original
fixture—format, title, Schedule data, and viewports—and the same minimal request for a
static, self-contained HTML response. They do not receive engine fields, the compiled plan,
fact ledger, detailed output contract, or repair assistance.

`scaffolded_html` and all three agent-native conditions share a byte-identical normalized
source-task payload, source-derived fact/slot map, and generic HTML scaffold. The scaffold
covers static output, semantic table structure, responsive viewports, accessibility, and
no overflow. It contains no Instrument name, visual rules, tokens, selected move, rule IDs,
package binding, or repair. Agent-native conditions add only their declared Instrument
context to that scaffold; the scaffolded baseline receives one call even when the run
permits agent repair.
Every artifact is rendered and measured after generation by the same treatment-blind
`briefFulfilment` path.

The stricter checker also includes Instrument-specific planner, binding, source, and rule
expectations. Its outcome is therefore named `agentContractConformance`, is null for all
baselines including `scaffolded_html`, and is compared only inside the agent-native family
or with the deterministic reference. Sharing generic fact IDs does not make the full
checker contract a fair scaffold outcome. It is not the H1 outcome.

| Condition | Generation input | Repair | Model call |
|---|---|---:|---:|
| `raw_brief` | Original brief plus a minimal HTML request | no | yes |
| `brand_bible` | The same original brief plus unstructured prose guidance | no | yes |
| `scaffolded_html` | Normalized task, generic semantic scaffold, fact/slot map, and viewport criteria | no | yes |
| `full_rules` | The same scaffold and task payload plus full Instrument rules | up to two exploratory; zero confirmatory | yes |
| `compact_rules` | The same scaffold and task payload plus compact Instrument rules | up to two exploratory; zero confirmatory | yes |
| `selected_context` | The same scaffold and task payload plus move-selected Instrument rules | up to two exploratory; zero confirmatory | yes |
| `deterministic_component` | Pinned React Schedule implementation | no | no; reference control |

First-pass `selected_context` versus `scaffolded_html` isolates the additional Instrument
context over a strong generic prompt because their source data, scaffold, model settings,
and first-call output budget are the same. Comparisons with `raw_brief` and `brand_bible`
remain exploratory whole-package comparisons. Final repaired agent artifacts do not share a
call budget with the baselines and must not be used for that first-pass contrast.

The deterministic condition establishes what the same plan produces through the
versioned component renderer. It is not included as if it were another prompt.

## Quick start

Run commands from the `standards` repository root. The renderer expects a built sibling
checkout at `../standards-ui`, including its Playwright Chromium runtime.

```bash
python3 -m unittest evaluation.tests.test_evaluation evaluation.tests.test_study \
  evaluation.tests.test_qualification -v
python3 -m evaluation.cli credentials
python3 -m evaluation.cli models --ids-only
python3 -m evaluation.cli ledger-init --out /path/to/spend-ledger.json --id evaluation-ledger
python3 -m evaluation.cli smoke --spend-ledger /path/to/spend-ledger.json
```

`credentials` reports only availability and source. The adapter reads
`OPENROUTER_API_KEY` first, then the macOS Keychain generic-password service
`standards-openrouter` for the current account. Override the service or account with
`OPENROUTER_KEYCHAIN_SERVICE` and `OPENROUTER_KEYCHAIN_ACCOUNT`. The secret is never
written to a request record or printed by these commands.

The smoke selects two current exact zero-price text routes and runs one development
case through `raw_brief`, `selected_context`, and the deterministic reference. It uses
one repetition, no repair, and a frozen `reasoning.effort=none` request so output tokens
are available to the artifact rather than hidden reasoning. It cannot support a quality or performance claim.
Its default output is a new operating-system temporary directory outside the repository.

For a repeated development comparison:

```bash
python3 -m evaluation.cli run \
  --mode exploratory \
  --models google/gemma-4-31b-it:free,liquid/lfm-2.5-2.6b:free \
  --conditions raw_brief,brand_bible,scaffolded_html,selected_context,full_rules \
  --split dev \
  --repetitions 3 \
  --reasoning off \
  --spend-ledger /path/to/spend-ledger.json
```

Model IDs in examples are illustrative: discovery is live, and a route may no longer be
available or free. Confirmatory execution accepts an already frozen catalogue only. It fails before provider
discovery or generation unless the strict declaration, external freeze receipt, eight
held-out fixture hashes, exactly six pinned routes across at least three model families,
three independent committed reviewers, seeded 90%-power repetition choice, cumulative
spend ledger, approved GBP budget, release commit, renderer identity, and protocol bytes all match.

## What is frozen before generation

Before the first provider call, a run writes:

- `model-snapshot.json`, the complete filtered catalogue response used by the adapter;
- `spend-ledger-start.json`, the externally frozen cumulative ledger snapshot;
- `precommit.json`, containing hypotheses, conditions, fixture hashes, matrix, settings,
  blocked-randomization seed, renderer identity, Python/platform and adapter environment,
  protocol hashes, selected catalogue entries, and the canonical snapshot hash.

OpenRouter calls are allowed only for exact IDs in that frozen snapshot. Exploratory discovery
requires every published price field to be zero. A confirmatory route may be paid within the
fixed £500 ledger cap, but must publish finite non-negative prompt and completion prices.
Automatic routers are rejected. Provider fallback is disabled. Exploratory free calls carry
a zero-price ceiling and may still leave the initial provider endpoint unpinned and
disclose that limitation. Protocol 0.5 confirmatory declarations name one underlying
provider endpoint per model. The adapter sends `provider.only: [pinned]`,
`allow_fallbacks: false`, and `require_parameters: true`; it sends no model fallback list.
The cell fails if the returned endpoint is absent or different.
The response records both requested and resolved model identities. A resolved ID is
accepted only when it equals the request or the release-dated `canonical_slug` captured
for that route in the frozen catalogue; every other substitution fails the call.
No tools or `tool_choice` field are sent; the artifact task has no tool surface.

The adapter makes no automatic retry. A transport error, rate limit, empty response,
identity mismatch, nonzero reported cost on a declared free route, or render failure remains in the H1 trial
denominator. Agent-contract checker failures remain in the eligible agent/reference
denominator and are retained for every condition as diagnostics.

Every provider call first makes an atomic worst-case GBP reservation in one shared ledger
whose scope covers qualification, development, and confirmatory work. The ledger refuses a
call that would exceed the remaining fixed cap. It settles from retained provider usage;
when usage is missing, the full reservation stays charged. Automatic top-up is always false.

## Run records

Each run contains:

```text
precommit.json
model-snapshot.json
cell-journal.json
study-declaration.json          # confirmatory only
freeze-receipt.json             # confirmatory only
spend-ledger-start.json
spend-ledger-final.json
trials.jsonl
trials/<trial-id>/
  brief.json
  plan.json
  attempt-<n>/
    request.json
    provider-response.json
    extraction.json
    submitted.html
    render/
    report.json
  trial.json
designer-review.json
designer-review-key.json
designer-review-assets/<blind-id>/
  schedule-<viewport>.png
designer-review-sets/<reviewer-id>/
  review.json
  assets/<blind-id>/*.png
results.json
```

Stored artifact, evidence, report, and raw-response paths are relative to the run
directory, declared by `pathBase`. This makes a retained run relocatable and prevents a
publication from exposing a contributor's home-directory path. Default comparison runs
go into ignored `evaluation/runs/`; copy a completed, reviewed run deliberately if it is
to become published evidence.

Parsed provider response objects are retained after recursive credential and
account-identifier scrubbing, including parsed HTTP error responses. Transport failures
and malformed or oversized bodies retain a bounded normalized error rather than unsafe raw
bytes. Request messages, transformations applied to outer transport wrappers, renderer
evidence, checker findings, repair packets, exact routing metadata, token usage,
provider-reported cost, and observed latency remain inspectable.

## Metrics

- **First-pass brief fulfilment (H1):** a marker-independent pass before repair, divided by
  every scheduled trial in the condition/model group. A pass requires safe, static HTML;
  one semantic Schedule with the planned rows and total; every fact explicitly frozen in
  the original brief in its semantic slot; and valid browser evidence, viewport fit,
  browser-observed table structure, every original-brief fact visibly present at every
  viewport, and screenshots. Provider and render failures are failures in this denominator.
- **Final brief fulfilment:** the same neutral outcome for the deterministically selected
  best attempt. Selection prefers contract conformance, then brief fulfilment, source facts,
  contract facts, and fewer failed or unknown findings; an earlier attempt wins a tie.
  Non-improving repair outputs remain in the record and are counted, but they cannot replace
  a stronger deliverable. Strict regressions and metric ties are reported separately.
  Baselines receive no repair, so their final result equals first pass.
- **Agent-contract conformance:** the full Instrument planner/checker contract before and
  after repair. Baseline values and denominators are null, including for `scaffolded_html`,
  because its generic prompt does not disclose the Instrument-specific parts of that
  contract. Compare this metric only among agent-native conditions and the deterministic
  reference.
- **Repair success:** final agent-contract pass among agent-native trials that produced a
  checkable, repairable first-pass contract failure. Repeated findings are grouped by rule
  before prompting so high-volume fact diagnostics cannot hide later structural or visual
  rules. The summary reports every rejected non-improving candidate and separates strict
  regressions from metric ties.
  The exploratory H3 gate requires at least 30 eligible failures, recovery at least .30,
  a one-sided 95% lower bound above .10, and zero selected-content regressions. H3 never
  enters primary confirmatory claims, and confirmatory generation fixes `maxRepairs` at zero.
- **Source-fact coverage:** normalized original-brief text in its marker-independent static
  semantic slot. Browser evidence separately requires every fact in a marker-ID-agnostic
  corpus of visible, unclipped, unobscured, contrast-passing text at every viewport. Both
  results list missing fact IDs. Marker exactness remains an agent-contract diagnostic.
- **Latency:** client-observed provider round-trip milliseconds.
- **Tokens and cost:** values reported by the provider, retained as missing when the
  provider omits them.
- **Prompt tokens per final agent-contract-conforming artifact:** all provider-reported
  prompt tokens consumed in an agent-native group divided by its final contract-conforming
  artifacts. The value is null for baselines, when no such artifact exists, or when any
  trial omits prompt-token usage.
- **Failures:** separate provider, renderer, harness, and model-integrity counts, each with
  the full trial denominator.
- **Designer scores:** blinded 1–5 ratings for hierarchy, system fidelity, legibility,
  rhetorical fit, and overall quality.

The precommitted review policy is `first-pass-for-H1`. Confirmatory generation selects one
predeclared repetition and creates exactly three separately shuffled packages under
`designer-review-sets/`. Give each reviewer only their `review.json` and PNG assets, without
the rest of the run or `designer-review-key.json`.
Do not give reviewers the model-generated HTML; it is retained for audit but is not a safe
standalone review surface.
The review copies use cryptographically random blind IDs and omit run, case, condition,
model, and repetition metadata. They always copy attempt 0; attempt index and repair state
exist only in the hidden key. The key also reports scheduled, included, missing, excluded
repetitions, and deduplicated cards by condition/model. A deterministic reference appears at most once per
case, even when model treatments have multiple repetitions. After every card has integer
scores from 1 to 5 and the file's status is `complete`, run:

```bash
python3 -m evaluation.cli review-summary --run /path/to/run
```

Review summarization fails closed unless the completed review, hidden key, precommit and
run results all carry the current evaluator's exact protocol version, run ID and first-pass
policy. Use the checkout that produced an older retained run; a newer evaluator will not
relabel it.

Keep one immutable completed file per declared reviewer. Seal them only after all cards
are scored; the seal checks the blind card set, computes ordinal Krippendorff alpha for
every dimension, includes missing artifacts at the declared score of 1, and records hashes
of every reviewer file.

Exploratory `results.json` summaries remain descriptive. The separate `analyze` command
implements the protocol 0.5 paired failure-aware risk difference, deterministic stratified
bootstrap interval, model and family strata, Holm adjustment for secondary H1 contrasts,
and the declared H2 token and non-inferiority checks. It refuses incomplete or undeclared
cells. Mechanical analysis remains claim-ineligible until a matching multi-reviewer set is
sealed and its agreement gate passes.

## Adding a provider

Implement the `ModelProvider` protocol in [provider.py](provider.py). Return normalized
fields through `CompletionResult` and retain the scrubbed original response in `raw`.
Freeze a provider catalogue or equivalent identity record and pass it to
`run_experiment`; an adapter can expose `model_snapshot_sha256` and
`experiment_metadata` so the runner verifies that the precommit and adapter use the same
snapshot. Provider-specific failures must return `ok=False` instead of being discarded.

## Protocol 0.5 controls

The machine-readable contracts live in `evaluation/schemas/`. `study-declaration.schema.json`
freezes the estimands, model families, routes, fixtures, settings, margins, randomization,
reviewers and budget. `freeze-receipt.schema.json` binds those bytes to an independent
custodian, retained declaration digest, timestamp evidence, locally verified signature,
spend-ledger digest, and explicit execution authorization. Each route qualification binds
exactly ten reserved calls across two time blocks, at least 90% success, 100% accepted
identity, text output, accepted parameters, and the provider pin.

Qualify one route in two explicit invocations. Each invocation makes exactly five calls;
block 2 must resume the byte-identical block-1 precommit. Replace these illustrative values
with the route's frozen provider, reservation, expiry, and paths. Add
`--require-zero-price` for a route declared free; omit it for an eligible paid route inside
the fixed GBP cap. `--provider-endpoint` is the exact endpoint slug used by `provider.only`;
`--provider-display-name` is the corresponding name returned in router metadata. Freeze
both from the same endpoint-catalogue response:

These two qualification invocations make provider calls and charge their reservations to
the shared ledger.

```bash
python3 -m evaluation.cli route-qualify \
  --route-id route-a --model maker/model-a --model-family family-a \
  --provider-endpoint "pinned-provider" --provider-display-name "Pinned Provider" \
  --snapshot snapshot.json \
  --spend-ledger spend-ledger.json --out /path/to/route-a-qualification \
  --block 1 --expires-at 2026-10-01T00:00:00Z \
  --worst-case-call-cost-gbp .05 --usd-to-gbp-rate .80

python3 -m evaluation.cli route-qualify \
  --route-id route-a --model maker/model-a --model-family family-a \
  --provider-endpoint "pinned-provider" --provider-display-name "Pinned Provider" \
  --snapshot snapshot.json \
  --spend-ledger spend-ledger.json --out /path/to/route-a-qualification \
  --block 2 --resume --expires-at 2026-10-01T00:00:00Z \
  --worst-case-call-cost-gbp .05 --usd-to-gbp-rate .80
```

The qualifier journals each call before reserving spend, then reserves before provider
access. A stopped in-flight call becomes an indeterminate retained failure and is not
retried. `route-qualification.json` appears only after both five-call blocks finish and all
receipt gates pass. Resume verifies the frozen model snapshot, cumulative-ledger identity,
deterministic call IDs, every finalized reservation, provider-result bytes, result digests,
and recomputed checks before making another call. Otherwise the evidence and failure
records remain without a receipt. A qualification directory contains
`qualification-precommit.json`, `model-snapshot.json`, `qualification-journal.json`, ten
provider results, `qualification-evidence.json`, and either a conforming receipt or
`qualification-failure.json`.

These commands are offline and spend no provider budget:

```bash
python3 -m evaluation.cli ledger-init --out spend-ledger.json --id evaluation-ledger
python3 -m evaluation.cli ledger-status --ledger spend-ledger.json
python3 -m evaluation.cli validate-declaration --declaration declaration.json \
  --freeze-receipt receipt.json --snapshot snapshot.json --spend-ledger spend-ledger.json
python3 -m evaluation.cli validate-freeze \
  --declaration declaration.json --freeze-receipt receipt.json --snapshot snapshot.json \
  --spend-ledger spend-ledger.json
python3 -m evaluation.cli power \
  --baseline-rate .55 --treatment-rate .70 --pair-correlation .40 --routes 6
python3 -m evaluation.cli review-seal \
  --run /path/to/run --declaration declaration.json \
  --reviews reviewer-a.json reviewer-b.json reviewer-c.json --out review-set.json
python3 -m evaluation.cli analyze \
  --run /path/to/run --declaration declaration.json --review-set review-set.json \
  --out analysis-result.json
python3 -m evaluation.cli bundle \
  --run /path/to/run --out /path/to/publication-copy
python3 -m evaluation.cli bundle-verify --bundle /path/to/publication-copy
```

Every run writes an atomic `cell-journal.json` before its first model call. `run --resume
--out <same-directory>` checks every frozen input and retained trial hash. A cell left in
flight is retained as an indeterminate scheduled failure and is never retried in place.
The publication command copies the evidence, removes the hidden key unless explicitly
requested, redacts account and provider response identifiers, rebuilds journal hashes,
and writes a verifiable sorted manifest. It rejects symlinks, credentials, private absolute
paths, unsafe identifier fields, and manifest drift.

The confirmatory declaration fixes exactly six routes across at least three families,
eight held-out fixtures, 5–50 repetitions selected by the declared seeded simulation,
20,000 paired bootstrap resamples, H1 effect/alpha/power of .10/.05/.90, H2 margins of
.05/.05/.02/.25 and token ratio at most .80, exactly three independent reviewers with
ordinal-alpha threshold .67, no repair, and total budget at or below £500. The planner
raises instead of selecting an underpowered or over-budget design.
