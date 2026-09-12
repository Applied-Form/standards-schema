# Standards by Applied Form

Design systems written as rulesets a language model can execute, not as mood boards.

This repository holds the open half: the **schema** systems are authored against, the
**compiler** that turns one source into three builds, an **MCP server** that serves them to
agents, and **Instrument** — an open reference system, available under CC BY 4.0.

## Start here

| If you want to… | Open |
|---|---|
| Use a system today | [Instrument](packs/instrument/README.md) — CC BY 4.0 |
| Understand how systems are written | [Schema v0.4](schema/schema-v0.4.md) |
| Serve the system to an agent | [MCP setup and tools](mcp/README.md) |
| Run the agent-native plan/check/repair workflow | [Six-move Instrument workflow](workflow/README.md) |
| Prepare a design contribution | [Design and rule challenges](CONTRIBUTING.md#choose-a-contribution-path) — no code required |
| Prepare a developer contribution | [Developer quickstart](CONTRIBUTING.md#developer-quickstart) |
| Write your own system | [Schema v0.4](schema/schema-v0.4.md), then [Contributing](CONTRIBUTING.md) |
| Check the evidence | [Evaluation protocol and harness](evaluation/README.md), [reproducible workflow proof](examples/workflow/README.md), and [study run sheet](schema/RUNNING-THE-STUDY.md) |
| See proposed work | [Open foundation roadmap](ROADMAP.md) |

Project process: [governance](GOVERNANCE.md), [maintainer status](MAINTAINERS.md),
[conduct](CODE_OF_CONDUCT.md), [private security reporting](SECURITY.md),
[release process](RELEASING.md) and [changelog](CHANGELOG.md).
The [CLA](CLA.md) is an unreviewed draft; legal review remains required before active
contributor recruitment.

## The argument

Adjectives do not constrain a model. Ask for "warm and editorial" and you get the average of
everything ever described that way. What constrains is a prohibition, a count, a named
compositional move, and a rule for what wins when two rules collide.

An entire category has grown up around making design systems readable by agents — enforcement,
retrieval, conformance checking. All of it assumes you already have a system worth enforcing.
This is the other half.

## What is here

```
schema/
  schema-v0.4.md        current. One source, two builds, a constraint budget
  schema-v0.3.md        superseded, kept because the argument is instructive
  compile.py            SOURCE.md -> three builds. Standard library only
  study.html            the study harness: seven briefs, blind, two questions
  harness.html          single A/B comparison
  RUNNING-THE-STUDY.md  the run sheet. One sitting, under a dollar

packs/instrument/       technical modernism. Free, complete, CC BY 4.0
  dist/claude/          the pack as an Agent Skill, with its assets
  dist/cursor/          the pack as a Cursor rule (.mdc)
mcp/server.py           MCP server. Standard library only, stdio
workflow/               versioned plan, selected context, artifact checks and bounded repair
evaluation/             fixed-condition, multi-model evaluation and blinded-review harness
examples/workflow/      reproducible browser reference loop and synthetic review artifacts
tests/check.py          the checks CI runs. No dependencies
```

## Installing a system

Every pack compiles to the places a system is actually installed. Nothing in `dist/` is
written by hand; it is regenerated on every run, so a system cannot be current in one target
and stale in another.

| Target | Path | Notes |
|---|---|---|
| **Claude Agent Skill** | `packs/<pack>/dist/claude/<pack>/` | Instructions, reference, licence, assets and referenced templates. Drop the complete directory into your skills folder |
| **Cursor rule** | `packs/<pack>/dist/cursor/<pack>.mdc` | Put it in `.cursor/rules/`. Uses the compact build, because a rule sits in context permanently |
| **MCP** | `mcp/server.py` | Serves every pack to any MCP client |
| **Tokens / charts** | `packs/<pack>/assets/` | CSS custom properties, chart theme, matplotlib style |

## Edit sources, regenerate builds

Author rules in `SOURCE.md` and tokens in `assets/tokens.css`; keep hand-authored chart
assets and templates consistent with them. Do not hand-edit generated instructions,
contracts or distribution files. See [Contributing](CONTRIBUTING.md#edit-sources-then-regenerate).

```bash
python3 schema/compile.py --all packs    # regenerate every build
python3 tests/check.py                   # the checks CI runs
```

CI checks reproducible builds, distribution completeness, constraint budgets, declared
colour pairs, chart semantics and MCP boundaries. These checks do not establish rendered
accessibility or design quality; report what was actually tested.

## On the evidence

Earlier internal comparisons did not show a clear consistency advantage for a layered,
precedence-ordered schema over a flatter one. Their consistency measure was collected before
a blinding defect in `study.html` was fixed, so those rounds cannot support a comparative
claim and must be re-run before their result is quoted.

The repository therefore makes no current claim that Standards is superior to a strong
brand guide, improves a particular model, or reduces human correction. The public
[evaluation harness](evaluation/README.md) is built to test those questions across fixed
conditions, development and held-out cases, frozen model routes, complete failure records,
mechanical conformance and blinded human review. The deterministic
[reference loop](examples/workflow/README.md) proves plan/check/repair/stop mechanics only; it
makes no model call. The earlier study design remains documented in
[`schema/RUNNING-THE-STUDY.md`](schema/RUNNING-THE-STUDY.md).

Precision about evidence is part of the product. Publish the fixtures, model identifiers,
settings, failures, denominators, scoring records and limits with any result.

## Where things live

| Repository | | Contents |
|---|---|---|
| [`appliedform/standards`](https://github.com/appliedform/standards) | public | **this one** — schema, compiler, MCP server, Instrument |
| [`appliedform/standards-ui`](https://github.com/appliedform/standards-ui) | public | React target — the shared job contract and Instrument |
| `appliedform/standards-packs` | private | the five systems for sale |
| `appliedform/standards-internal` | private | proof, handoff, commercial, handover |

## The rest of the catalogue

Five more systems — Broadsheet (editorial), Raw (neo-brutalist), Agitprop (constructivist),
Contra (expressive postmodern) and Cornice (ornamental, generative) — are proprietary and are
not in this repository.

Instrument is free because a system installed as somebody's default is worth more than a
system sold once. Import it, fork it, put it in your own repo and let your tooling enforce it.

## Licence

Split deliberately: schema CC BY 4.0, tooling MIT, Instrument CC BY 4.0. See [LICENSE](LICENSE).
The current contribution terms are in the [draft CLA](CLA.md).

Every system extends a design tradition. No organisation's marks, logotypes or identities are
reproduced, and nothing here is affiliated with or endorsed by any institution referenced.
Type is open licence throughout.
