import unicodedata

DOMAIN = "energy_power_monitor"

CONF_ROOM = "room"
CONF_SMART_METER_DEVICE = "smart_meter_device"
CONF_ENTITIES = "entities"
CONF_ENTITY_TYPE = "entity_type"
CONF_INTEGRATION_ROOMS = "integration_rooms"
CONF_HIDE_FROM_INCLUDED_ZONES = "hide_from_included_zones"
CONF_EXCLUDED_ENTITIES = "excluded_entities"
CONF_ENTRY_KIND = "entry_kind"

# Form-only field keys for the Excluded Entities picker: the underlying stored
# data (CONF_EXCLUDED_ENTITIES) stays one combined list, but the form splits
# the picker into a Power dropdown and an Energy dropdown for readability.
CONF_EXCLUDED_POWER_ENTITIES = "excluded_power_entities"
CONF_EXCLUDED_ENERGY_ENTITIES = "excluded_energy_entities"

ENTITY_TYPE_POWER = "power"
ENTITY_TYPE_ENERGY = "energy"

# Marks the single, global "Excluded Entities" config entry (see config_flow.py)
# as distinct from a normal per-zone config entry. Zone entries have no
# CONF_ENTRY_KIND key at all, so `entry.data.get(CONF_ENTRY_KIND) ==
# ENTRY_KIND_EXCLUSIONS` is the only check needed to tell them apart.
ENTRY_KIND_EXCLUSIONS = "exclusions"
EXCLUDED_ENTITIES_TITLE = "Excluded Entities"


def sanitize_zone_name(zone_name: str) -> str:
    """Normalize and sanitize a zone name for consistent use in entity IDs.

    Applies NFKD unicode normalization, strips non-ASCII characters, then
    lower-cases and replaces spaces and hyphens with underscores — matching
    exactly what Home Assistant does when it auto-generates entity IDs.
    """
    normalized = unicodedata.normalize("NFKD", zone_name).encode("ascii", "ignore").decode("utf-8")
    return normalized.lower().replace(" ", "_").replace("-", "_")


def is_smart_meter_selected(value: str | None) -> bool:
    """Return True only when value looks like a real sensor entity ID.

    Used everywhere we need to distinguish 'no smart meter chosen' from
    an actual selection.  Handles empty strings, None, and old translated
    sentinel values ('None', 'Keine', 'Aucune', …) all as "not selected".
    """
    return bool(value and value.startswith("sensor."))