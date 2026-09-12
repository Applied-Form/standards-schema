# Instrument Schedule workflow preview

This preview implements one complete, local agent workflow for a fixed-content
transaction schedule:

`brief + renderer identity → validated plan → selected context → React artifact → browser evidence → findings → bounded repair`

It makes no model calls and executes no generated artifact code. In this alpha slice,
the agent supplies and preserves structured facts while an allowlisted React component
renders them deterministically. The selected context is a replayable input for model
experiments and future generation paths; the trusted render path does not ask a model to
recreate component code. The checker links each finding to a stable rule.

The plan pins the exact renderer source, component and runtime modules, fonts, dependency
lock, Node executable, Playwright browser revision, launcher and complete installed browser
payload reported by the rendering host.
Evidence embeds each PNG and binds its bytes, dimensions, plan and artifact. These checks
make a local run reproducible and tamper-evident. They are still caller-supplied records,
not remote attestation that a particular process ran.
For the supported Schedule, browser observations also verify one visible title, the
full-width 32px ink band and reversed title, table/footer structure, visual duration-before-
amount order, exact visible facts, contrast, clipping, occlusion and horizontal fit.

## Supported scope

- Instrument
- Transaction job (`T`)
- Schedule move
- One static, self-contained HTML surface
- An explicit `full` or `compact` instruction-build choice, without assuming one performs better
- One to three viewports from 320–1920 by 320–2160 pixels
- At most two repair attempts
- A total render-evidence transport limit of 3.5 MB

Other moves and native document formats return an explicit unsupported result.
Mechanical conformance does not establish visual quality, complete WCAG
conformance or comparative performance against another approach.

## Run the example

First build the sibling `standards-ui` checkout and record the identity of the exact
renderer that will execute the plan:

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

Render the plan from the same `standards-ui` checkout:

```bash
node scripts/workflow-render.mjs \
  --plan /tmp/standards-schedule-plan.json \
  --out /tmp/standards-schedule-render
```

Then check the exact artifact and its hash-bound browser observations:

```bash
python3 -m workflow.cli check \
  --plan /tmp/standards-schedule-plan.json \
  --html /tmp/standards-schedule-render/artifact.html \
  --evidence /tmp/standards-schedule-render/render-evidence.json
```

Use `repair` with the same inputs to obtain the next action and a history record.
Append that record to a JSON array only when attempting a repair. The workflow
validates the chain and stops after two attempts; keep every prior artifact and
freshly render each change because evidence for old HTML is rejected.

The same four operations are available through the local MCP server. `plan_artifact`
accepts the brief and the renderer identity as separate objects. The workflow tools
advertise exact input and output schemas and return native `structuredContent` alongside
the text representation. Malformed data is rejected before dispatch.

For a single command that exercises the real sibling renderer, a seeded fact failure,
successful repair with fresh evidence, and the honest two-attempt stop path, run the
[cross-repository reference loop](../examples/workflow/README.md).
