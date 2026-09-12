# Security policy

## Report privately

Report vulnerabilities through this repository's **Security → Advisories → Report a
vulnerability** route: [start a private vulnerability report](https://github.com/appliedform/standards/security/advisories/new).
Do not put exploit details, credentials or private data in a public issue or pull request.

The presence of this policy does not confirm that GitHub private vulnerability reporting
is enabled. Maintainers must enable and test that route before active recruitment or a
release announcement. If the private reporting button is unavailable, open an issue asking
only for a private security contact route, without affected paths, exploit details or data.
Wait for that route before sending the report. No reporting email is designated here.

Include the commit or release, affected component, expected and actual behaviour, likely
impact and a minimal reproduction using synthetic data. Report only systems you are
authorised to test. Do not include secrets or unnecessary personal information.

## Scope and handling

Relevant reports include MCP resource-boundary escapes, unsafe handling of untrusted
requests or pack files, compiler/distribution defects with a security impact, and exposed
secrets. Ordinary rendering and rule disagreements belong in the issue forms.

This project has no declared long-term-support release line. Maintainers triage against the
current default branch and assess older releases case by case; report the exact version
rather than assuming it is supported. The MCP server reads locally available packs and does
not provide an entitlement service. Serve only the catalogue intended for that client.

Maintainers should acknowledge a private report, agree a safe reproduction, explain its
status and coordinate a fix and disclosure with the reporter. Once the private route is
tested and recruitment opens, the target is acknowledgement within two UK business days
and a status update at least every ten business days; the named backup in `MAINTAINERS.md`
handles escalation or recusal. No target applies while those launch gates remain open.
Release notes should describe the fix without exposing private report content. Publish an
advisory when appropriate and offer attribution only with the reporter's agreement. No
bounty or compensation programme is promised.
