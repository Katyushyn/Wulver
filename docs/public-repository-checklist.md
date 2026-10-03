# Public repository checklist

This checklist records work that must be completed before changing the GitHub
repository visibility to public.

## Required before public visibility

- [ ] Select and add the final software license after deciding whether Wulver
      permits proprietary derivatives or requires published modifications.
- [ ] Define the first version number and compatibility policy.
- [ ] Verify a clean installation on a new machine from the documented steps.
- [ ] Add a redistribution-safe neutral corporate demo theme and demo content.
- [ ] Complete installation, production deployment, backup/restore, upgrade,
      theme development, and module development documentation.
- [ ] Review every dependency and bundled asset license.
- [ ] Run the full test suite and security checks in CI.
- [ ] Run a final secret and personal-data scan over the complete new Git history.
- [ ] Configure GitHub branch protection, required checks, security advisories,
      Dependabot, and repository topics/description.
- [ ] Add public support and release channels without exposing a private address.

## Release follow-up

- [ ] Publish signed version tags and release notes.
- [ ] Add a supported-version table to `SECURITY.md`.
- [ ] Add screenshots only after the neutral demo theme is ready.
- [ ] Publish package and deployment instructions only after clean-build testing.
- [ ] Decide whether optional modules live in separate repositories or a managed
      multi-package workspace.
