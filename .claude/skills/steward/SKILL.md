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

## Config-flow architecture notes

This integration has exactly one config-flow domain (`DOMAIN =
"energy_power_monitor"`) but two different *kinds* of config entry living
side by side in `hass.config_entries.async_entries(DOMAIN)`:

- **Zone entries** (the original kind): one per user-created zone, forward
  to the `sensor` platform, carry `CONF_ROOM`/`CONF_ENTITIES`/etc.
- **The "Excluded Entities" entry** (added for the global entity-exclusion
  feature): a singleton settings-only entry, tagged via
  `entry.data.get(CONF_ENTRY_KIND) == ENTRY_KIND_EXCLUSIONS`. It forwards to
  no platforms (see the early-return in `__init__.py`'s
  `async_setup_entry`/`async_unload_entry`) and creates no sensors.

This is the pattern to reach for again if a future feature needs one
integration-wide setting rather than a per-zone one: a dedicated config
entry, reached from a menu on `async_step_user` (via `async_show_menu`),
enforced as a singleton by checking for an existing entry of that kind
before creating another, with its own `OptionsFlow` subclass returned from
`async_get_options_flow` based on `config_entry.data.get(CONF_ENTRY_KIND)`.
It was chosen over a HA subentries in this codebase because it needed no
new HA config-flow API and it gives the setting a visible, independently
"Configure"-able entry in the integration's own entry list — which is what
"easily accessible and recognizable" from a user request cashes out to in
this integration's UI.

Every helper in `config_flow.py` that loops over
`hass.config_entries.async_entries(DOMAIN)` (e.g.
`get_selected_smart_meter_devices`, `get_selected_integration_zones`) must
tolerate entries that aren't zones — they already do, because they only
ever read zone-specific keys via `entry.data.get(key, default)`, which is
silently absent (not an error) on the exclusions entry. Keep that
`.get(..., default)` discipline if you add a third entry kind.

## Never call `generate_entity_id(..., hass=hass)` for this integration's own entities

`EnergyandPowerMonitorSensor`/`SmartMeterSensor` build their `entity_id`
directly (`ENTITY_ID_FORMAT.format(self._unique_id)`), not via
`homeassistant.helpers.entity.generate_entity_id()`. That function used to be
used here and was removed because it avoids collisions by checking which
entity_ids are *currently live* in `hass.states` — a check that has nothing
to do with whether the id is actually free for this `unique_id`, and is
unreliable right at startup/reload (a not-yet-torn-down old entity can
occupy the slug this entity is about to reclaim). In practice this showed up
as debug logs like `entity_id=sensor.energy_power_monitor_kuche_power_2`
on every restart; it was mostly harmless for already-registered zones
(Home Assistant's entity platform always overwrites `entity.entity_id` with
whatever the entity registry has on file for that `unique_id` once
`async_add_entities()` runs — confirmed by later log lines using the clean,
unsuffixed id), but for a *brand-new* zone whose unique_id isn't in the
registry yet, this bogus suggested id becomes the permanently stored one.

Since `self._unique_id` for both sensor classes is already a fully
deterministic slug (derived from `sanitize_zone_name()` + entity type, not
from anything HA needs to disambiguate), there is nothing for
`generate_entity_id`'s live-state check to usefully add — building the
`entity_id` string directly is both simpler and correct. If a genuine
`unique_id` collision ever occurs, the entity registry's own
`async_get_or_create()` disambiguates it when the entity is actually added,
which is the right layer for that job.
