# Maintainer register

No public maintainer is currently appointed. Naming a primary and a backup for every row is
a launch gate for active contributor recruitment and the first public release. Repository
permission alone does not fill a role; appointments are recorded here through the project
decision process in `GOVERNANCE.md`.

| Area | Primary | Backup | Authority |
|---|---|---|---|
| Rules and design review | Unassigned | Unassigned | Accept design decisions and rule changes |
| Compiler, MCP and workflow | Unassigned | Unassigned | Review and merge tooling changes |
| Evaluation and evidence | Unassigned | Unassigned | Approve protocols and evidence claims |
| Security reports | Unassigned | Unassigned | Receive reports and coordinate fixes |
| Conduct reports | Unassigned | Unassigned | Receive and resolve sensitive reports |
| Releases | Unassigned | Unassigned | Tag, publish, pause and supersede releases |

An appointment records the person's GitHub handle, the effective date, the rows they own,
and any limit on authority. A maintainer discloses a material conflict and transfers that
decision to the listed backup. If both are conflicted or unavailable, the Applied Form
project steward records a temporary independent reviewer or pauses the decision. Removing
or replacing a maintainer uses the same public record, except where privacy or safety
requires a minimal notice.

When the first appointments are recorded, add matching, valid handles to
`.github/CODEOWNERS` for the owned paths. Do not publish placeholder or nonexistent handles;
branch protection and the repository's review rules must be tested with the real accounts.

The response targets in `GOVERNANCE.md` take effect only after this register is populated
and `CONTRIBUTING.md` says recruitment is open.
