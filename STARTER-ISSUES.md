# Starter issue briefs

These are ready-to-file issue briefs, not open or assigned issues. They make the first
contribution small enough to review and give designers, researchers and developers a
shared definition of done. Maintainers should triage and file them when active contributor
recruitment opens.

Recruitment has four unresolved launch gates: legal review of the [draft CLA](CLA.md),
enabling and testing the private vulnerability-reporting route described in
[SECURITY.md](SECURITY.md), designating the private conduct-report contact route described
in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and naming primary and backup maintainers in
[MAINTAINERS.md](MAINTAINERS.md). Publishing this backlog does not clear those gates or
promise that a proposal will be accepted, assigned or funded.

Every brief applies only to the open foundation and Instrument. Use synthetic or clearly
licensed inputs. Do not submit client work, private conversations, credentials, proprietary
packs or an imitation of an organisation's identity. When recruitment opens, use the
[design challenge](https://github.com/appliedform/standards/issues/new?template=design-rule-challenge.yml),
[implementation bug](https://github.com/appliedform/standards/issues/new?template=implementation-bug.yml)
or [evaluation and research](https://github.com/appliedform/standards/issues/new?template=evaluation-research.yml)
form named in each brief.

## Design

### Annotate one long-label counterexample

**Start with:** Design challenge form. **Size:** one focused design review; no code required.

Choose one public Instrument rule or compositional move and one rhetorical job. Create a
fixed synthetic brief whose long labels, empty value or signed value exposes a concrete
layout or hierarchy failure. Render it at one named page size or viewport and annotate the
failure.

Done means the issue contains:

- the source commit, rule or move identifier, fixed brief and target dimensions;
- one shareable render with the failed area marked and described without relying on colour;
- the reader task that fails, plus a proposed acceptance criterion; and
- the licence or authorship of every input and image.

Keep the result as a counterexample. A new universal rule, a full redesign and a claim
about model quality are outside this issue.

### Review one shipped template against its source hierarchy

**Start with:** Design challenge form. **Size:** one template and one artefact type.

Choose either `packs/instrument/Instrument-deck.pptx` or
`packs/instrument/Instrument-report.docx`. Compare one representative spread or page with
the hierarchy, type and spacing guidance in `packs/instrument/SOURCE.md` and
`packs/instrument/assets/tokens.css`.

Done means the issue records the exact template and commit, a rendered image, and no more
than three source-linked findings. For each finding, classify it as a contradiction,
ambiguity or acceptable exception and suggest the smallest correction. A template-wide
refresh or style preference without a reader-task impact is outside this issue. Put any
confirmed correction in a separate, focused pull request after maintainers agree the
source interpretation.

## Evaluation and research

### Audit the shipped blinded-review rubric on a small pilot

**Start with:** Evaluation and research form. **Size:** one review-procedure audit plus a
small pilot; no model purchase required.

Review the five anchored dimensions already defined in
`evaluation/PROTOCOL.md`: visual hierarchy, system fidelity, legibility, rhetorical fit and
overall quality. Exact fact preservation remains a mechanical outcome. Apply the PNG-only,
opaque-ID review bundle to at least three synthetic artifacts and test whether the wording,
asset handling and unblinding procedure work without revealing a condition or model.

Done means two designers can apply the same anchors without treatment labels, all raw scores
and notes are retained, disagreements are visible, and the issue states any procedure change
needed before a held-out run. Three artifacts are a usability pilot, not enough for a
quality, agreement or system-ranking claim.

### Review the frozen comparison before a confirmatory run

**Start with:** Evaluation and research form. **Size:** one protocol and implementation
review; no paid run required.

Audit `evaluation/PROTOCOL.md`, the four fixed fixtures and the prompt builder before the
first claim-bearing run. Confirm that raw-brief and brand-bible conditions receive only their
declared minimal inputs. Confirm that `scaffolded_html` and the agent-native conditions share
the same normalized source task, generic HTML scaffold and first-call budget, while only the
agent-native conditions receive Instrument context. The scaffold must receive neither
Instrument-specific guidance nor repair, and its agent-contract score must remain null because
that checker contains withheld Instrument requirements. Confirm that baseline-neutral factual
and task outcomes are applied consistently without leaking hidden plans into any prompt.

Done means the review records exact prompt hashes, at least three frozen models from more
than one family, a locked repetition count, development-first and held-out stages, all
failure denominators, the non-inferiority margin and interval method, a cost ceiling, and at
least two blinded designers for perceived-quality claims. It must state what null, mixed and
failed results mean and treat first-pass `selected_context` versus `scaffolded_html` as the
bounded design-system-context comparison. Running the comparison or selecting models after
seeing outputs is outside this review issue.

## Client and model adapters

### Reproduce one MCP client setup from a clean checkout

**Start with:** Implementation bug form. **Size:** one named client and one retrieval path.

Use a current released version of one MCP client to connect to `mcp/server.py` from a clean
checkout. Exercise `list_systems`, `get_system` and `select_move` with synthetic input. Keep
the server local and redact the user's absolute path and configuration before sharing it.

Done means the issue or pull request records the operating system, runtime and client
versions, exact setup steps, expected responses and every manual workaround. If the
documented configuration is incomplete, update only the relevant section of
`mcp/README.md` and have a second person follow it. Adding client-specific product claims,
credentials, generation calls or support for several clients is outside this issue.

### Add one provider adapter compatibility test

**Start with:** Evaluation and research form. **Size:** one provider-compatible endpoint;
no live key in the test suite.

Implement one additional provider-compatible endpoint behind the existing
`evaluation.provider.ModelProvider` contract. Demonstrate it with a fake transport or
recorded synthetic response plus success, provider-error, empty-response and model-identity
cases. Keep provider-specific fields in explicit metadata and scrub credential, account and
absolute-path fields before a response is retained.

Done means the adapter preserves the exact requested and resolved model identities and
settings, records missing usage as missing, distinguishes provider failure from an empty
response, states its endpoint-routing limits, and passes entirely offline without a secret.
A provider SDK dependency, automatic retry, unrecorded fallback or performance claim is
outside this issue.

## Accessibility

### Audit keyboard flow and accessible names in the study harness

**Start with:** Design challenge form for findings, or implementation bug form for a
reproducible defect. **Size:** `schema/study.html` and `schema/harness.html` only.

Using synthetic payloads, operate setup, generation controls, review choices, progress and
export without a pointer. Inspect the accessible name, role, state and focus order of each
interactive control at 200% browser zoom and a narrow viewport.

Done means the report names the browser and assistive-technology method, lists the exact
keyboard sequence, and separates confirmed failures from untested behaviour. A clear fix
includes a focused regression check where practical. A complete WCAG conformance claim,
visual redesign or paid generation run is outside this issue.

### Check one chart theme without colour

**Start with:** Design challenge form. **Size:** one synthetic chart rendered through one
shipped theme.

Choose either `packs/instrument/assets/chart-theme.json` or
`packs/instrument/assets/instrument.mplstyle`. Render a chart with at least two series, a
negative value and an annotated state. Review it in greyscale and at 200% zoom, calculate
contrast for text and essential graphical boundaries, and identify any meaning carried by
colour alone.

Done means the fixed data, render command, tool versions, image and contrast calculations
are shareable. Suggest the smallest token, stroke, marker or label change for each failure.
Reworking both chart systems or declaring the whole system accessible is outside this
issue.

## Documentation

### Run the 15-minute clean-checkout first-use test

**Start with:** Implementation bug form. **Size:** one documented path on one platform.

Give a new contributor a clean checkout and choose either compiler first use or MCP
retrieval first use. Without coaching, record the commands they follow, elapsed time,
decision points, missing prerequisites and the first point where expected and actual
behaviour differ.

Done means the report names the commit, platform and runtime, includes redacted terminal
output and proposes at most one focused documentation change. Verify that change from a
second clean directory. Installing every target, rewriting the README or measuring general
developer productivity is outside this issue.

### Verify the authored-versus-generated file map

**Start with:** Implementation bug form. **Size:** five representative changes; documentation
only unless a mismatch is found.

Use `CONTRIBUTING.md`, the compiler and the pack manifest to trace where a contributor
should edit a rule, token, archetype, detailed reference and target adapter. Record the
source file, generated outputs and regeneration command for each case.

Done means all five traces are reproducible, any ambiguous instruction is quoted, and the
smallest documentation correction is proposed. If a generated file differs after a clean
compile, report that separately with the exact diff and command. Changing the compiler,
adding a new build target or restructuring the repository is outside this issue.
