---
name: steward
description: Repo-specific conventions for driving PRs on Energy-and-Power-Monitor-Integration to green.
---

# Steward conventions — Energy and Power Monitor Integration

This is a single-purpose Home Assistant custom integration, distributed via
HACS. Pure Python, no build step, no package manager, no lockfiles.

## Validating a change before pushing

There is no pytest suite yet. Before pushing, run:

- `python -m compileall custom_components/energy_power_monitor` — catches
  syntax errors.
- Translation parity check: every file under
  `custom_components/energy_power_monitor/translations/*.json` must have the
  exact same nested key set as `custom_components/energy_power_monitor/strings.json`.
  A one-off script for this is embedded in
  `.github/workflows/python-checks.yml` — reuse that logic rather than
  re-deriving it.

Both of the above run automatically as the `Python Checks` workflow on every
push and pull request.

## Other CI checks

- `Hassfest` and `Validate` (HACS) validate `manifest.json` / `hacs.json`
  structure against Home Assistant's and HACS's own schemas. They are
  scheduled workflows (daily cron) and GitHub auto-disables scheduled
  workflows after ~60 days of repository inactivity — if one of these checks
  shows as "not reported" rather than passing or failing on a PR, it likely
  means the workflow is disabled, not that it silently passed. That's a
  repo-settings issue (Settings → Actions → re-enable), not something a code
  change in a PR can fix.
- The `Validate` (HACS) check requires the repository to have at least one
  published GitHub Release to pass the "integration" category validation.
  A failure here because no release exists yet is a maintainer decision
  (when to cut a release), not something to work around in a PR.

## Merge conventions

- Merge (don't rebase or force-push) when bringing `main` into an
  in-progress PR branch you did not create.
- `manifest.json`'s `version` field only needs to move in lockstep with an
  actual GitHub Release; don't bump it as part of an unrelated bugfix PR.
