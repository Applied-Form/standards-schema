# Release process

No public release is currently authorised. A person named for Releases in
`MAINTAINERS.md` must own this process, and the legal, security, conduct and contribution
gates in `CONTRIBUTING.md` must be closed before the first announcement.

## Version and compatibility

Use semantic versions for repository releases. Before 1.0, a minor version may change an
experimental interface and a patch must remain compatible. At and after 1.0, breaking
schema, MCP, workflow or generated-distribution changes require a major version. Instrument
and UI package versions remain explicit inside their own manifests; a repository tag must
list every included version in the changelog. Never move or overwrite a published tag.

## Prepare the candidate

1. Start from a clean checkout of the intended commit. Confirm generated outputs were
   produced only from authored sources and the working tree is clean after regeneration.
2. Run `python3 schema/compile.py --all packs` and `python3 tests/check.py` with Python 3.12.
3. Run the documented cross-repository reference loop against the exact UI commit, refresh
   its public manifest and images, and rerun the offline manifest-integrity check.
4. Inspect every generated bundle, template, licence and attribution file. Follow the
   clean-client install instructions for the MCP and each claimed distribution target.
5. Record known compatibility changes, security fixes, evidence limits, skipped manual
   checks and both public repository commits in `CHANGELOG.md`.
6. Create an immutable candidate tag, rebuild from that tag in CI, and compare the produced
   hashes with the candidate receipt before publishing artifacts.

Rendered accessibility, native PPTX/DOCX editing, model comparisons and designer review
are separate checks. Claim only the ones performed for that candidate and link their fixed
inputs, methods and limitations.

## Publish and verify

The named release maintainer may merge the candidate, create the signed release tag and
publish the release artifacts. A second named maintainer verifies the tag, downloadable
files, licence contents, documented install path and private security route from a
non-owner account. Record the release commit, tag, artifact hashes and verification result
in the release notes.

## Roll back or supersede

Do not rewrite a released tag. For an ordinary defect, document the impact, revert or fix
on the default branch, publish a higher patch version and mark the affected version as
superseded. For a security defect, use the private process, coordinate an advisory and
publish the fixed version before disclosing unsafe detail. If safe installation cannot be
restored promptly, remove the affected downloadable artifact, pause the related claim and
leave a public notice that identifies the affected versions and next update.
