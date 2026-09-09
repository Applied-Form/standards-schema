# Governance

## Stewardship and authority

Applied Form is the project steward, as recorded in [CONTRIBUTORS.md](CONTRIBUTORS.md).
Repository owners and maintainers with the appropriate permissions review, merge and
release work. This document appoints no individual, partner or contributor to those roles.
Contributing, signing the CLA or proposing a roadmap item does not confer merge authority,
ownership or compensation.

Maintainer appointments and changes to this process should be recorded in a public project
decision. Maintainers are expected to explain decisions, preserve attribution, disclose
relevant conflicts and avoid promising review capacity they do not have. Responses and
acceptance are not guaranteed.

## Decisions and requests for comment

Small, compatible fixes may go straight to a pull request. Start an issue for a schema or
rule change, a new public interface, a compatibility break, an evaluation claim or a change
to governance or licensing. Prefix broader proposals with `RFC:`; the design-challenge
form can supply the evidence for a rule proposal.

A request for comment should state the problem and rhetorical job, proposal, alternatives,
compatibility and licence implications, evidence and its limits, and acceptance criteria.
Maintainers should allow time for affected contributors to respond, normally at least seven
days for a substantial proposal. Urgent security fixes may use the private reporting path.

A maintainer records the outcome and reason: accepted, needs revision, deferred or declined.
Popularity is useful input, not a binding vote. Changes still need an implementation review
and relevant checks. Decisions must distinguish a project preference from a tested finding.

## Review and release

Reviewers check authored sources, generated output, tests, evidence limits, licences and
privacy using the [contribution guide](CONTRIBUTING.md). Seek a second reviewer for
substantial changes where one is available; disclose when the steward is the sole reviewer.

A release maintainer should verify a clean, reproducible build; run the public checks;
inspect installable bundles and documented examples; record changes and compatibility
notes in [CHANGELOG.md](CHANGELOG.md); and identify the release commit. A passing compiler
check does not establish rendered accessibility, design quality or benchmark superiority.
Any such claim needs its own evidence. Release announcements also require a working
[private vulnerability reporting route](SECURITY.md).

The [CLA](CLA.md) is an unreviewed draft. Obtain legal review before active contributor
recruitment, and record the reviewed process and any changed terms clearly. These policies
do not amend its current grants or the [file licences](LICENSE).

## Disagreement and appeal

Ask for reconsideration in the original issue or pull request, with the specific decision,
new evidence or process concern, and requested remedy. Maintainers should give a reasoned
response and seek a different reviewer where one is available. If none is available, say
so; do not imply an independent appeal body exists. The project steward makes the final
project decision. Conduct reports follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and
sensitive security details remain private under [SECURITY.md](SECURITY.md).
