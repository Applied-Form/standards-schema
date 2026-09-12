# Instrument agent workflow 0.2

This is an agent-native, local workflow for turning fixed structured content into one
of six deterministic Instrument surfaces:

`capabilities → brief + renderer identity → immutable plan → selected context → HTML → browser evidence → findings → bounded repair`

The planner, checker and repair policy make no model calls and execute no generated
artifact code. An agent supplies a supported brief, consumes a narrow context packet and
may edit the HTML. The allowlisted React renderer turns the plan into a static artifact.
Every hand-off has a closed JSON contract and hash binding so another agent or human can
inspect what happened.

## Canonical support contract

[`support-manifest.json`](support-manifest.json) is the capability source of truth. Its
exact bytes are bound into the plan and renderer identity. Workflow and MCP contracts are
version 0.2.0; the open authored Instrument content remains 1.0.0; the compatible UI
package is 2.0.0. Those versions describe different things and are deliberately separate.

| Job | Exact move | Content kind | Component |
|---|---|---|---|
| E · Evidence | Datum | `datum` | `Datum` |
| S · Structure | Matrix | `matrix` | `Matrix` |
| N · Narrative | Band statement | `bandStatement` | `BandStatement` |
| C · Change | Series | `series` | `Series` |
| T · Transaction | Schedule | `schedule` | `Schedule` |
| W · Wayfinding | Running index | `runningIndex` | `RunningIndex` |

Only static, self-contained HTML is admitted. A brief names its job, move and
discriminated content explicitly; workflow 0.2 does not infer that decision. Each plan
also pins its content sources, planning/checking implementation, component binding,
renderer, fonts, dependencies, Node executable, Playwright launcher and complete browser
payload. Node 22 or 24 LTS is required by the paired renderer.

The capability manifest currently lists no tested MCP clients. Protocol tests are not a
substitute for a clean-profile Codex or Claude Code compatibility trace; the manifest says
so directly rather than implying support.

## Run the Schedule example

Build the sibling `standards-ui` checkout with a supported Node runtime and capture the
identity of the exact renderer that will execute the plan:

```bash
cd /path/to/standards-ui
npm ci
npm run build
npx playwright install chromium
node scripts/workflow-render.mjs --identity > /tmp/standards-renderer-identity.json
```

Then, from this repository:

```bash
python3 -m workflow.cli plan \
  --brief examples/workflow/schedule-brief.json \
  --renderer-identity /tmp/standards-renderer-identity.json \
  --out /tmp/standards-schedule-plan.json

python3 -m workflow.cli context \
  --plan /tmp/standards-schedule-plan.json \
  --out /tmp/standards-schedule-context.json
```

Render the immutable plan from the same UI checkout, then check the exact artifact and
its hash-bound observations:

```bash
node scripts/workflow-render.mjs \
  --plan /tmp/standards-schedule-plan.json \
  --out /tmp/standards-schedule-render

python3 -m workflow.cli check \
  --plan /tmp/standards-schedule-plan.json \
  --html /tmp/standards-schedule-render/artifact.html \
  --evidence /tmp/standards-schedule-render/render-evidence.json
```

The same planner accepts the other five content kinds when their exact job/move pair is
used. Read the [brief schema](schemas/brief.schema.json) or call
`get_workflow_capabilities` before constructing one.

## Facts, relationships and evidence

The plan turns all approved visible strings into an ordered fact ledger, including
component-owned labels such as the Series zero and `Current` labels and Running index
ordinals. The renderer marks every planned fact and records visibility, clipping,
occlusion and contrast at every declared viewport. It also records the move-specific
relationships declared by the support manifest. The checker compares those observations
with the exact plan and artifact hashes.

A supported Series has two to 24 periods. The component's empty-state text is therefore
unreachable through workflow 0.2 rather than appearing outside the fact ledger.

Evidence embeds each PNG and binds its bytes, dimensions, plan, artifact, renderer and
runtime identity. This makes a retained local run reproducible and tamper-evident. The
record is still supplied by the caller; hashes do not attest that an independent process
made a truthful observation. Missing, malformed or stale browser evidence remains
unknown and stops automated repair.

## Best-so-far repair policy

`repair` classifies each non-passing finding as exactly one of
`safe-model-repair`, `renderer-or-configuration`, `human-decision` or
`non-repairable`. Only failed findings in the first class can authorize an automated
repair. Every attempt receives a record, including rejected ties, regressions and repeat
attempts.

Candidates are compared lexicographically in this frozen order:

1. contract pass;
2. brief pass;
3. minimum visible-fact coverage across viewports;
4. static fact coverage;
5. combined contract-fact coverage;
6. fewer critical, error, warning and unknown findings, in that order.

A candidate cannot be accepted if it loses a pass, introduces a new protected fact or
relationship failure, or introduces any new critical/error finding. Equal metrics are a
tie, not an improvement. Repeated artifact bytes, repeated finding fingerprints, stale
evidence, a regression or a non-automated classification stop the loop. A repair always
starts from `bestArtifactSha256`; rejected attempts never become the next base. At most
two repair attempts are authorized, and a history cannot continue after a `complete` or
`stop` record.

Preserve every artifact, evidence record and returned history record. Re-render after any
byte change because evidence for an older artifact is rejected.

## Limits of the result

The checks cover exact content, bounded static markup, declared relationships, viewport
fit, visible facts, the Instrument title band and screenshot integrity. They do not
establish visual quality, rhetorical effectiveness, complete WCAG conformance, factual
truth, model superiority or a beneficial repair effect. Those questions require the
separate [evaluation protocol](../evaluation/README.md).

The five workflow operations are also available through the local MCP server. For one
command that exercises the sibling renderer, a seeded fact failure, a successful repair
with fresh evidence and stop-on-repeat safety, run the
[cross-repository reference loop](../examples/workflow/README.md).
