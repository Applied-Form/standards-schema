# Contributing

Standards is an agent-native design foundation: an authoring schema, compiler, MCP server
and the open Instrument system. Read the [licences](LICENSE) and
[project conduct policy](CODE_OF_CONDUCT.md) before participating.

**Contribution status · 12 September 2026:** preparation only. Active contributor
recruitment has not opened. The next proposed status review is 30 September 2026. Before
opening recruitment, Applied Form as project steward must complete legal review of the
[draft CLA](CLA.md), enable and test the private vulnerability route in
[SECURITY.md](SECURITY.md), designate the private conduct route in
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and publicly name maintainers and release
authority. Until then, readers may inspect, fork and prepare changes under the file
licences, but unsolicited issues and pull requests have no response target and will not be
triaged or merged. The paths below describe the proposed process after those gates are
cleared.

## Choose a contribution path

| Your contribution | Start with | Useful evidence |
|---|---|---|
| Designer: challenge a rule, hierarchy or compositional move | [Design or rule challenge](https://github.com/Applied-Form/standards-schema/issues/new?template=design-rule-challenge.yml) | A fixed brief, the rule and an annotated counterexample; no code required |
| Developer: reproduce or fix a compiler, MCP or distribution defect | [Implementation bug](https://github.com/Applied-Form/standards-schema/issues/new?template=implementation-bug.yml) | Version, minimal reproduction, expected result and a focused regression check |
| Designer or developer: improve an example, accessibility or documentation | A [starter issue brief](STARTER-ISSUES.md) or a small pull request | The reader's task and the observable improvement |
| Researcher: test a design or agent-workflow claim | [Evaluation or research proposal](https://github.com/Applied-Form/standards-schema/issues/new?template=evaluation-research.yml) | Fixed inputs, explicit conditions, retained failures, review method and limits |
| Author: build an independent system | [Schema v0.4](schema/schema-v0.4.md) | An original stance, licensed assets and a rendered example |

Browse the [starter issue briefs](STARTER-ISSUES.md) for concrete first slices and the
[roadmap](ROADMAP.md) for their wider context. The briefs are proposal-ready backlog, not
open or assigned issues. Ask about scope in an issue before starting a large change; an
issue is not a promise of acceptance or funded work. Follow [SECURITY.md](SECURITY.md) for
vulnerabilities instead of a public reproduction.

## Developer quickstart

The supported contributor baseline is Git and Python 3.12, matching CI. The compiler,
server and checks use only the Python standard library.

```bash
git clone https://github.com/YOUR-HANDLE/standards.git
cd standards
git remote add upstream https://github.com/Applied-Form/standards-schema.git
git switch -c your-name/focused-change
python3 schema/compile.py --all packs
python3 tests/check.py
```

Create the fork in GitHub before cloning. The final command must exit successfully and
report that every check passed. Inspect
`git diff` after compilation: generated files change only when their authored source has
changed. Make one bounded change, add a regression or fixed example when it proves the
result, and use the pull-request template. The separate React target has its own setup in
[`standards-ui`](https://github.com/appliedform/standards-ui); a foundation contribution
does not require Node or a browser unless it changes that integration.

## No-code design review

You can make a complete design contribution without a development environment. Choose one
public Instrument rule or one supplied PPTX/DOCX template, create a synthetic brief, and
render one representative slide or page in an application you already use. Record the
source commit, application/version, page size or viewport, and fonts; export a PNG or PDF;
annotate the exact hierarchy, legibility or rhetorical failure; and state an observable
acceptance criterion. A well-supported counterexample is complete without a proposed fix.
Use only material you can publish and avoid client or private work.

## Edit sources, then regenerate

For Instrument rules, edit [`SOURCE.md`](packs/instrument/SOURCE.md). For token values,
edit [`assets/tokens.css`](packs/instrument/assets/tokens.css). Chart themes, the
matplotlib style, templates and reference extensions are also authored assets: keep their
semantics consistent with the source. Tooling changes belong in the tooling's source files.

Do not hand-edit generated `SKILL.md`, `SKILL-compact.md`, `REFERENCE.md`, `tokens.json`,
`archetypes.json`, `manifest.json`, `AGENTS.md` or files under a pack's `dist/` directory.
Regenerate them when their sources change:

```bash
python3 schema/compile.py --all packs
python3 tests/check.py
```

The checks use Python's standard library. They cover parsing, licences, distribution
completeness, reproducible builds, constraint budgets, chart semantics, MCP boundaries and
the scoped six-move workflow's plan, content, evidence and repair contracts.
Proof checks are conditional: this repository does not currently ship a `proof/` directory.
A green check is not a visual-quality judgement or a complete accessibility audit.
Inspect the resulting diff and report any skipped checks in the pull request.

## Explain the decision and its limits

For a rule change, name the rhetorical job, the failure, the proposed rule and its tradeoff.
Use the [schema's authoring checklist](schema/schema-v0.4.md#authoring-checklist). A new
active constraint needs a budget explanation and, at the limit, a replacement or removal;
`python3 schema/compile.py --audit packs/instrument` shows what the compiler counts.
Do not present the budget as a demonstrated universal law of design quality.

Use original or clearly licensed synthetic examples. Include long labels, empty or signed
data, small viewports or a revision request when they expose the reported problem. A single
render can establish a counterexample; it cannot establish that one system or model is
generally better. For comparative claims, record model/version, prompts, conditions,
repetitions, failures and review method. Label hypotheses and exploratory results as such.
Do not hide failed outputs or confuse source conformance with human design quality.

Never submit credentials, raw private conversations, client material, proprietary packs or
third-party identities you lack permission to share. Redact before attaching logs or images.
AI-assisted contributions carry the same provenance, review and licensing responsibilities.

Schema changes, new rules or changes to compatibility follow the
[decision process](GOVERNANCE.md). Independent systems can live in their authors' own
repositories; any listing here is subject to review. Respect the licences of reused source
material, use open-licence type and distinguish an original system from a palette variation
or imitation of an organisation's identity.

## Contribution rights

Read the full [draft CLA](CLA.md). Its current signing process is to add your name and date
to [CONTRIBUTORS.md](CONTRIBUTORS.md) with your first pull request. If your employer owns
the work, obtain its sign-off and state that in the pull request. Maintainers must resolve
all recruitment gates above before recruiting contributors under this process.

Under the draft, you keep copyright and grant Applied Form rights that include proprietary
relicensing; no payment, royalty or revenue share is promised. The grants are not limited
to open-source use. Public files retain their stated distribution licences: MIT for tooling,
CC BY 4.0 for the schema and Instrument. Identify any third-party material and its licence.

Accepted code remains attributed in Git. Accepted design counterexamples, research,
documentation, review and security work is credited in the relevant release notes when it
materially informs a release, including a handle or name chosen by the contributor.
Contributors may request anonymous credit or opt out. The signing register in
[CONTRIBUTORS.md](CONTRIBUTORS.md) and contribution credit serve different purposes.

Review, release and appeal expectations are in [GOVERNANCE.md](GOVERNANCE.md). The
[pull-request template](.github/PULL_REQUEST_TEMPLATE.md) is the final submission checklist.
