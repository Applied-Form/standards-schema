# Comparative evaluation

This directory tests a narrow question: does the agent-native generation package—an
immutable plan, fact ledger, explicit HTML contract, design rules, checker, and bounded
repair—produce a first-pass Schedule that fulfils the same original brief more reliably
than asking the same model to work from that brief, a prose brand bible, or a strong
generic HTML scaffold?

It is an exploratory evaluation harness, not evidence of an advantage by itself. The
included fixtures and offline regression suite exercise the apparatus; the smoke command
adds a live operational check. A future comparative claim
requires the confirmatory entry gates, a precommitted repeated run, its failures and
denominators, and the blinded designer review described in [PROTOCOL.md](PROTOCOL.md).

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
| `full_rules` | The same scaffold and task payload plus full Instrument rules | up to two | yes |
| `compact_rules` | The same scaffold and task payload plus compact Instrument rules | up to two | yes |
| `selected_context` | The same scaffold and task payload plus move-selected Instrument rules | up to two | yes |
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
python3 -m unittest evaluation.tests.test_evaluation -v
python3 -m evaluation.cli credentials
python3 -m evaluation.cli models --ids-only
python3 -m evaluation.cli smoke
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
  --reasoning off
```

Model IDs in examples are illustrative: discovery is live, and a route may no longer be
available or free. `--mode confirmatory` deliberately fails closed. Enable it only after
the paired estimator, interval method, numerical non-inferiority margin, multi-reviewer
agreement method, and externally frozen held-out declaration are implemented and tested.

## What is frozen before generation

Before the first provider call, a run writes:

- `model-snapshot.json`, the complete filtered catalogue response used by the adapter;
- `precommit.json`, containing hypotheses, conditions, fixture hashes, matrix, settings,
  blocked-randomization seed, renderer identity, Python/platform and adapter environment,
  protocol hashes, selected catalogue entries, and the canonical snapshot hash.

OpenRouter calls are allowed only for exact IDs in that frozen snapshot. The snapshot
must explicitly publish zero for every price field and advertise text output. Automatic
routers are rejected. Provider fallback is disabled and the request carries a zero-price
ceiling. OpenRouter still chooses the initial eligible underlying provider endpoint for
each request; that endpoint is not pinned, so the response records the selected provider
when supplied and confirmatory work must predeclare how endpoint variation is handled.
The response records both requested and resolved model identities. A resolved ID is
accepted only when it equals the request or the release-dated `canonical_slug` captured
for that route in the frozen catalogue; every other substitution fails the call.
No tools or `tool_choice` field are sent; the artifact task has no tool surface.

The adapter makes no automatic retry. A transport error, rate limit, empty response,
identity mismatch, nonzero reported cost, or render failure remains in the H1 trial
denominator. Agent-contract checker failures remain in the eligible agent/reference
denominator and are retained for every condition as diagnostics.

## Run records

Each run contains:

```text
precommit.json
model-snapshot.json
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
- **Final brief fulfilment:** the same neutral outcome for the final available artifact.
  Baselines receive no repair, so their final result equals first pass.
- **Agent-contract conformance:** the full Instrument planner/checker contract before and
  after repair. Baseline values and denominators are null, including for `scaffolded_html`,
  because its generic prompt does not disclose the Instrument-specific parts of that
  contract. Compare this metric only among agent-native conditions and the deterministic
  reference.
- **Repair success:** final agent-contract pass among agent-native trials that produced a
  checkable, repairable first-pass contract failure.
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

The precommitted review policy is `first-pass-for-H1`. To complete human review, give
reviewers `designer-review.json` and the PNG-only
`designer-review-assets/` without the rest of the run or `designer-review-key.json`.
Do not give reviewers the model-generated HTML; it is retained for audit but is not a safe
standalone review surface.
The review copies use cryptographically random blind IDs and omit run, case, condition,
model, and repetition metadata. They always copy attempt 0; attempt index and repair state
exist only in the hidden key. The key also reports scheduled, included, missing, and
deduplicated cards by condition/model. A deterministic reference appears at most once per
case, even when model treatments have multiple repetitions. After every card has integer
scores from 1 to 5 and the file's status is `complete`, run:

```bash
python3 -m evaluation.cli review-summary --run /path/to/run
```

Keep individual reviewer files when more than one designer scores the artifacts. Agree
in advance how multiple files will be combined; the current command validates and
summarizes one completed review file.

The built-in summaries are descriptive. They do not implement the protocol's paired
condition estimator, uncertainty intervals, non-inferiority test, model-family strata, or
multi-reviewer agreement. Those are explicit entry gates for a future confirmatory mode;
do not infer them from `results.json` or `designer-results.json`.

## Adding a provider

Implement the `ModelProvider` protocol in [provider.py](provider.py). Return normalized
fields through `CompletionResult` and retain the scrubbed original response in `raw`.
Freeze a provider catalogue or equivalent identity record and pass it to
`run_experiment`; an adapter can expose `model_snapshot_sha256` and
`experiment_metadata` so the runner verifies that the precommit and adapter use the same
snapshot. Provider-specific failures must return `ok=False` instead of being discarded.
