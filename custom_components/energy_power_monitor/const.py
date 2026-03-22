import unicodedata

DOMAIN = "energy_power_monitor"

CONF_ROOM = "room"
CONF_SMART_METER_DEVICE = "smart_meter_device"
CONF_ENTITIES = "entities"
CONF_ENTITY_TYPE = "entity_type"
CONF_INTEGRATION_ROOMS = "integration_rooms"

ENTITY_TYPE_POWER = "power"
ENTITY_TYPE_ENERGY = "energy"


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