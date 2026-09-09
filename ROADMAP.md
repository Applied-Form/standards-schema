# Open foundation roadmap

Standards aims to help agents select a design approach, make a composition plan, produce
an artefact and check and repair it against explicit rules. The foundation here already
includes authored rules, compiled instruction builds, token and archetype contracts,
an MCP retrieval and move-selection interface, and Instrument assets and templates.
An integrated plan/check/repair loop is proposed work, not a shipped capability or a
demonstrated quality advantage.

This roadmap is ordered by dependency, without promised dates. Discuss substantial work
through the [decision process](GOVERNANCE.md) before implementing it. Active contributor
recruitment awaits review of the [draft CLA](CLA.md) and the reporting arrangements.

## First: dependable foundations

- Make documented installations reproducible from a clean checkout, with every referenced
  file and licence present in the exported bundle. Add regression cases for missing or
  stale files and unsafe resource paths.
- Keep authored rules, token values, chart assets and implementations consistent. Treat
  contradictions as design defects, and preserve non-colour cues for state and emphasis.
- Provide a short first-use path and explicit boundaries: what the compiler verifies,
  what a rendered check covers and what still requires human judgement.

Done means a contributor can follow the installation example, reproduce the checks and
report a failure with enough information for another person to investigate it.

## Next: an inspectable agent workflow

- **Select and plan:** build on MCP `select_move` with an inspectable plan that records the
  rhetorical job, selected move, content needs, source version and applicable rules.
- **Check:** define a versioned conformance result with stable rule identifiers, evidence
  locations, severity and explicit `unknown` results for checks that cannot be performed.
- **Repair:** return bounded, actionable findings to the agent; preserve required content,
  retain the prior artefact and recheck the revision. Record unresolved findings and stop
  conditions rather than silently declaring success.
- **Provenance:** carry pack and schema versions, source hashes and tool versions through
  the plan and checks. Keep private prompts and credentials out of public fixtures.

Done means one documented end-to-end example can be reproduced, a seeded defect produces
a useful finding, and a repair either fixes it or reports the remaining failure honestly.

## Then: reference quality and credible evaluation

- Create reviewed Instrument examples for Evidence, Structure, Narrative, Change,
  Transaction and Wayfinding across appropriate interfaces, report pages and deck spreads.
  Include long labels, empty and signed data, accessible status cues, narrow layouts and
  a follow-up revision that must preserve content.
- Pair developer checks with designer annotation. Publish the brief, licensed assets,
  expected behaviour and known limits so others can reproduce the example.
- Establish a public evaluation protocol with development cases separated from held-out
  cases. Keep fixed content, comparable conditions, failed attempts, model settings and
  costs visible. Report conformance separately from blinded human quality judgements.

Done means an independent contributor can reproduce a result and see what it does and
does not support. Examples and development results alone will not justify broad claims
about superiority, model capability or the benefit of a particular schema structure.

## Useful contributions

| Opportunity | Designer contribution | Developer contribution |
|---|---|---|
| Rule contradiction | Annotated counterexample and a proposed precedence decision | A source/asset regression case |
| Reference example | A fixed brief, composition rationale and review | Reproducible rendering and content-preservation checks |
| Accessibility | Reading order, status semantics and non-colour review | Keyboard, semantic and responsive checks in the relevant target |
| Agent workflow | Define useful plan and repair feedback | Versioned contracts, MCP integration and failure fixtures |
| Evaluation | A review rubric and documented uncertainty | Repeatable runs, complete records and honest summaries |
| First use | Identify a confusing decision or missing explanation | Reproduce and repair installation or documentation steps |

Start with [CONTRIBUTING.md](CONTRIBUTING.md). The
[React implementation](https://github.com/appliedform/standards-ui) has its own source and
checks; report an implementation defect in the repository that owns it. This roadmap
covers the open foundation only. Do not submit private packs, client work or restricted
third-party assets as examples.
