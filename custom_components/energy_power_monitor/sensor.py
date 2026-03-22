import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo, generate_entity_id
from homeassistant.const import Platform, UnitOfPower, UnitOfEnergy, STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    DOMAIN,
    ENTITY_TYPE_POWER,
    ENTITY_TYPE_ENERGY,
    CONF_SMART_METER_DEVICE,
    CONF_ENTITIES,
    CONF_INTEGRATION_ROOMS,
    sanitize_zone_name,
    is_smart_meter_selected,
)

_LOGGER = logging.getLogger(__name__)
ENTITY_ID_FORMAT = Platform.SENSOR + ".{}"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def check_and_remove_nonexistent_entities(hass: HomeAssistant, entities, entry):
    """Return the subset of entity_ids that still exist in the entity registry."""
    _LOGGER.debug("check_and_remove_nonexistent_entities called")
    entity_registry = er.async_get(hass)
    valid = []
    for entity_id in entities:
        if entity_id in entity_registry.entities:
            valid.append(entity_id)
        else:
            _LOGGER.warning(
                "Entity '%s' no longer exists and will be removed from zone automatically.",
                entity_id,
            )
    _LOGGER.debug("Valid entities after check: %s", valid)
    return valid


def expand_integration_zone_entities(hass: HomeAssistant, entities, integration_zones, entity_type):
    """Expand selected integration zones into their tracked entities."""
    if not integration_zones:
        return list(entities or [])

    entity_registry = er.async_get(hass)
    selected = list(entities or [])
    for zone_id in integration_zones:
        if zone_id in entity_registry.entities:
            selected.append(zone_id)
        untracked = f"{zone_id[:-(len(entity_type) + 1)]}_untracked_{entity_type}"
        if untracked in entity_registry.entities:
            selected.append(untracked)
    return sorted(set(selected))


def is_valid_value(state_obj):
    """Return True when state_obj has a numeric value that can be used in calculations."""
    if state_obj is None:
        return False
    if state_obj.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, None, ""):
        return False
    try:
        float(state_obj.state)
        return True
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up the Energy and Power Monitor sensor based on a config entry."""
    _LOGGER.debug("async_setup_entry start for: %s", entry.title)

    async def check_and_setup_entities(event=None):
        """Set up entities once Home Assistant is fully started."""
        if not hass.is_running:
            _LOGGER.debug("HA not fully running yet, waiting for started event")
            return

        _LOGGER.debug("HA fully started, proceeding with entity setup for: %s", entry.title)

        zone_name = entry.data.get("room")
        entities = entry.data.get(CONF_ENTITIES, [])
        entity_type = entry.data.get("entity_type")
        integration_zones = entry.data.get(CONF_INTEGRATION_ROOMS, [])
        smart_meter_device = entry.data.get(CONF_SMART_METER_DEVICE, "")

        expanded_entities = expand_integration_zone_entities(
            hass, entities, integration_zones, entity_type
        )
        base_entities_checked = check_and_remove_nonexistent_entities(hass, entities, entry)
        if set(base_entities_checked) != set(entities):
            new_data = dict(entry.data)
            new_data[CONF_ENTITIES] = base_entities_checked
            hass.config_entries.async_update_entry(entry, data=new_data)
            _LOGGER.debug("Config entry updated with valid entities only")

        entities_checked = check_and_remove_nonexistent_entities(hass, expanded_entities, entry)

        _LOGGER.debug(
            "Setting up sensor: zone=%s entities=%s smart_meter=%s entity_type=%s",
            zone_name,
            entities_checked,
            smart_meter_device,
            entity_type,
        )

        if not zone_name or not isinstance(entities_checked, list):
            _LOGGER.error("Invalid configuration: zone_name or entities missing for entry %s", entry.title)
            return

        sensor = EnergyandPowerMonitorSensor(hass, zone_name, entities_checked, entry.entry_id, entity_type)
        async_add_entities([sensor])

        if is_smart_meter_selected(smart_meter_device):
            smart_meter_sensor = SmartMeterSensor(
                hass, zone_name, smart_meter_device, entry.entry_id, entity_type, sensor
            )
            async_add_entities([smart_meter_sensor])

    if hass.is_running:
        await check_and_setup_entities()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, check_and_setup_entities)


# ---------------------------------------------------------------------------
# Main zone sensor
# ---------------------------------------------------------------------------

class EnergyandPowerMonitorSensor(SensorEntity):
    """Representation of an Energy and Power Monitor zone sensor with real-time updates."""

    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, zone_name, entities, entry_id, entity_type):
        """Initialize the zone sensor."""
        self.hass = hass
        self._zone_name = zone_name
        self._base_entities = list(entities)
        self._entities = list(entities)
        self._state = 0
        self._entry_id = entry_id
        self._entity_type = entity_type
        self._unique_id = self._make_unique_id()
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, self._unique_id, hass=self.hass)
        self._unsubscribe_state_changes = None
        self._unsubscribe_registry_listener = None
        _LOGGER.debug(
            "EnergyandPowerMonitorSensor init: entity_id=%s zone=%s type=%s",
            self.entity_id,
            self._zone_name,
            self._entity_type,
        )

    def _make_unique_id(self) -> str:
        return f"{DOMAIN}_{sanitize_zone_name(self._zone_name)}_{self._entity_type}"

    # --- HA entity properties ---

    @property
    def name(self):
        return f"{self._zone_name} selected entities - {self._entity_type.capitalize()}"

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(self._entry_id,)},
            name=self._zone_name,
            manufacturer="Custom",
            model="Energy and Power Monitor",
        )

    @property
    def extra_state_attributes(self):
        return {"selected_entities": self._base_entities}

    @property
    def icon(self):
        return "mdi:flash" if self._entity_type == ENTITY_TYPE_POWER else "mdi:counter"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def unit_of_measurement(self):
        if self._entity_type == ENTITY_TYPE_POWER:
            return UnitOfPower.WATT
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def device_class(self):
        if self._entity_type == ENTITY_TYPE_POWER:
            return SensorDeviceClass.POWER
        return SensorDeviceClass.ENERGY

    # --- Internal helpers ---

    def _get_expanded_entities(self, entry):
        """Return the full expanded entity list for the current config entry."""
        if not entry:
            return self._entities
        base_entities = entry.data.get(CONF_ENTITIES, [])
        integration_zones = entry.data.get(CONF_INTEGRATION_ROOMS, [])
        self._base_entities = list(base_entities)
        self.async_write_ha_state()
        return expand_integration_zone_entities(
            self.hass, base_entities, integration_zones, self._entity_type
        )

    def _calculate_state(self):
        """Sum all tracked entities, skipping invalid/negative values."""
        total = 0.0
        valid = []
        for entity_id in self._entities:
            state_obj = self.hass.states.get(entity_id)
            if is_valid_value(state_obj):
                try:
                    value = float(state_obj.state)
                    if value >= 0:
                        total += value
                        valid.append(entity_id)
                except (ValueError, TypeError):
                    _LOGGER.warning("Cannot convert state of '%s' to float: %s", entity_id, state_obj.state)
        if len(valid) != len(self._entities):
            self._entities = valid
        return round(total, 1)

    def _setup_state_listeners(self):
        """Subscribe to state-change events for all tracked entities."""
        if self._unsubscribe_state_changes:
            self._unsubscribe_state_changes()
            self._unsubscribe_state_changes = None

        if not self._entities:
            return

        self._unsubscribe_state_changes = async_track_state_change_event(
            self.hass, self._entities, self._on_state_change
        )
        _LOGGER.debug(
            "State listeners set up for %d entities in zone '%s'",
            len(self._entities),
            self._zone_name,
        )

    def _setup_registry_listener(self):
        """Subscribe to entity registry events so we react to removals / renames."""
        if self._unsubscribe_registry_listener:
            self._unsubscribe_registry_listener()
        self._unsubscribe_registry_listener = self.hass.bus.async_listen(
            "entity_registry_updated",
            self._handle_entity_registry_event,
        )

    def _update_config_entry_entities(self):
        """Persist the current _base_entities back into the config entry."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            new_data = dict(entry.data)
            new_data[CONF_ENTITIES] = list(self._base_entities)
            self.hass.config_entries.async_update_entry(entry, data=new_data)
            _LOGGER.debug("Config entry updated with new entity list: %s", self._base_entities)

    # --- Callbacks ---

    @callback
    def _on_state_change(self, event: Event):
        """Recalculate and push state whenever a tracked entity changes."""
        self._state = self._calculate_state()
        self.async_write_ha_state()

    @callback
    def _handle_entity_registry_event(self, event: Event):
        """React to entity registry updates that affect our tracked entities.

        This replaces the old 5-minute periodic reload:
        - If a tracked entity is removed  → drop it from our list immediately.
        - If a tracked entity is renamed  → update the reference immediately.
        Both cases persist the change to the config entry so it survives restarts.
        """
        action = event.data.get("action")
        entity_id = event.data.get("entity_id")

        if action == "remove":
            if entity_id not in self._entities and entity_id not in self._base_entities:
                return
            _LOGGER.warning(
                "Tracked entity '%s' was removed; removing from zone '%s' automatically.",
                entity_id,
                self._zone_name,
            )
            self._entities = [e for e in self._entities if e != entity_id]
            self._base_entities = [e for e in self._base_entities if e != entity_id]
            self._update_config_entry_entities()
            self._setup_state_listeners()
            self._state = self._calculate_state()
            self.async_write_ha_state()

        elif action == "update":
            changes = event.data.get("changes", {})
            if "entity_id" not in changes:
                return
            old_entity_id = changes["entity_id"]  # value BEFORE the rename
            if old_entity_id not in self._entities and old_entity_id not in self._base_entities:
                return
            _LOGGER.info(
                "Tracked entity renamed '%s' → '%s' in zone '%s'; updating reference.",
                old_entity_id,
                entity_id,
                self._zone_name,
            )
            self._entities = [
                entity_id if e == old_entity_id else e for e in self._entities
            ]
            self._base_entities = [
                entity_id if e == old_entity_id else e for e in self._base_entities
            ]
            self._update_config_entry_entities()
            self._setup_state_listeners()
            self._state = self._calculate_state()
            self.async_write_ha_state()

    # --- HA lifecycle ---

    async def async_added_to_hass(self):
        """Called when entity is added to Home Assistant."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            expanded = self._get_expanded_entities(entry)
            if expanded != self._entities:
                self._entities = expanded
            self.async_on_remove(entry.add_update_listener(self._update_listener))

        self._setup_state_listeners()
        self._setup_registry_listener()

        # Ensure cleanup on removal
        self.async_on_remove(self._teardown_listeners)

        self._state = self._calculate_state()
        await super().async_added_to_hass()

    @callback
    def _teardown_listeners(self):
        """Unsubscribe all listeners."""
        if self._unsubscribe_state_changes:
            self._unsubscribe_state_changes()
            self._unsubscribe_state_changes = None
        if self._unsubscribe_registry_listener:
            self._unsubscribe_registry_listener()
            self._unsubscribe_registry_listener = None

    async def async_update(self):
        """Update state by re-reading config and recalculating."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            new_entities = self._get_expanded_entities(entry)
            if new_entities != self._entities:
                _LOGGER.debug(
                    "Zone '%s': entity list updated %s -> %s",
                    self._zone_name,
                    self._entities,
                    new_entities,
                )
                self._entities = new_entities
                self._setup_state_listeners()
        self._state = self._calculate_state()

    async def _update_listener(self, hass, entry):
        """Called by HA when the config entry is updated via the options flow."""
        new_entities = self._get_expanded_entities(entry)
        if new_entities != self._entities:
            _LOGGER.debug(
                "Zone '%s': config updated, refreshing entities",
                self._zone_name,
            )
            self._entities = new_entities
            self._setup_state_listeners()
        self._state = self._calculate_state()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Clean up when entity is removed."""
        self._teardown_listeners()


# ---------------------------------------------------------------------------
# Smart meter (untracked) sensor
# ---------------------------------------------------------------------------

class SmartMeterSensor(SensorEntity):
    """Untracked consumption sensor: smart_meter - zone_total."""

    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, zone_name, smart_meter_device, entry_id, entity_type, energy_power_monitor_sensor):
        """Initialize the Smart Meter sensor."""
        self.hass = hass
        self._zone_name = zone_name
        self._smart_meter_device = smart_meter_device
        self._entity_type = entity_type
        self._state = None
        self._entry_id = entry_id
        self._energy_power_monitor_sensor = energy_power_monitor_sensor
        # Unique ID: stable, zone-name-based (not device-name-based)
        self._unique_id = f"{DOMAIN}_{sanitize_zone_name(zone_name)}_untracked_{entity_type}"
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, self._unique_id, hass=self.hass)
        self._unsubscribe_state_changes = None
        self._unsubscribe_registry_listener = None
        _LOGGER.debug(
            "SmartMeterSensor init: entity_id=%s zone=%s smart_meter=%s",
            self.entity_id,
            self._zone_name,
            self._smart_meter_device,
        )

    # --- HA entity properties ---

    @property
    def name(self):
        return f"{self._zone_name} untracked - {self._entity_type.capitalize()}"

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def state(self):
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(self._entry_id,)},
            name=self._zone_name,
            manufacturer="Custom",
            model="Energy and Power Monitor",
        )

    @property
    def extra_state_attributes(self):
        return {
            "Selected Smart Meter Device": self._smart_meter_device,
            "Energy and Power Monitor": self._energy_power_monitor_sensor.entity_id,
        }

    @property
    def icon(self):
        return "mdi:flash" if self._entity_type == ENTITY_TYPE_POWER else "mdi:counter"

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def unit_of_measurement(self):
        if self._entity_type == ENTITY_TYPE_POWER:
            return UnitOfPower.WATT
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def device_class(self):
        if self._entity_type == ENTITY_TYPE_POWER:
            return SensorDeviceClass.POWER
        return SensorDeviceClass.ENERGY

    # --- Internal helpers ---

    def _calculate_state(self):
        """Return smart_meter - zone_total, clamped to 0 if negative."""
        monitor_value = self._energy_power_monitor_sensor.state
        smart_meter_state = self.hass.states.get(self._smart_meter_device)

        if not is_valid_value(smart_meter_state):
            _LOGGER.debug("Smart meter '%s' has no valid state", self._smart_meter_device)
            return None
        if monitor_value is None:
            _LOGGER.debug("Zone sensor for '%s' has no valid state yet", self._zone_name)
            return None

        try:
            result = float(smart_meter_state.state) - float(monitor_value)
            return max(0, round(result, 1))
        except (ValueError, TypeError) as exc:
            _LOGGER.warning("Error calculating untracked value for '%s': %s", self._zone_name, exc)
            return None

    def _setup_state_listeners(self):
        """Subscribe to state changes for the smart meter and the main zone sensor."""
        if self._unsubscribe_state_changes:
            self._unsubscribe_state_changes()
            self._unsubscribe_state_changes = None

        entities_to_track = [self._smart_meter_device]
        if self._energy_power_monitor_sensor:
            entities_to_track.append(self._energy_power_monitor_sensor.entity_id)

        self._unsubscribe_state_changes = async_track_state_change_event(
            self.hass, entities_to_track, self._on_state_change
        )
        _LOGGER.debug("SmartMeterSensor '%s' state listeners set up", self.entity_id)

    def _setup_registry_listener(self):
        """Subscribe to entity registry events to handle smart meter renames/removals."""
        if self._unsubscribe_registry_listener:
            self._unsubscribe_registry_listener()
        self._unsubscribe_registry_listener = self.hass.bus.async_listen(
            "entity_registry_updated",
            self._handle_entity_registry_event,
        )

    # --- Callbacks ---

    @callback
    def _on_state_change(self, event: Event):
        """Recalculate on any relevant state change."""
        self._state = self._calculate_state()
        self.async_write_ha_state()

    @callback
    def _handle_entity_registry_event(self, event: Event):
        """Handle smart meter entity removal or rename."""
        action = event.data.get("action")
        entity_id = event.data.get("entity_id")

        if action == "remove" and entity_id == self._smart_meter_device:
            _LOGGER.warning(
                "Smart meter '%s' was removed; zone '%s' untracked sensor will show unavailable.",
                entity_id,
                self._zone_name,
            )
            self._state = None
            self.async_write_ha_state()

        elif action == "update":
            changes = event.data.get("changes", {})
            if "entity_id" not in changes:
                return
            old_entity_id = changes["entity_id"]
            if old_entity_id != self._smart_meter_device:
                return
            _LOGGER.info(
                "Smart meter renamed '%s' → '%s' for zone '%s'; updating reference.",
                old_entity_id,
                entity_id,
                self._zone_name,
            )
            self._smart_meter_device = entity_id
            # Persist the new entity ID to the config entry
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if entry:
                new_data = dict(entry.data)
                new_data[CONF_SMART_METER_DEVICE] = entity_id
                self.hass.config_entries.async_update_entry(entry, data=new_data)
            self._setup_state_listeners()
            self._state = self._calculate_state()
            self.async_write_ha_state()

    # --- HA lifecycle ---

    @callback
    def _teardown_listeners(self):
        """Unsubscribe all listeners."""
        if self._unsubscribe_state_changes:
            self._unsubscribe_state_changes()
            self._unsubscribe_state_changes = None
        if self._unsubscribe_registry_listener:
            self._unsubscribe_registry_listener()
            self._unsubscribe_registry_listener = None

    async def async_added_to_hass(self):
        """Called when entity is added to Home Assistant."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            self.async_on_remove(entry.add_update_listener(self._update_listener))

        self._setup_state_listeners()
        self._setup_registry_listener()
        self.async_on_remove(self._teardown_listeners)

        self._state = self._calculate_state()
        await super().async_added_to_hass()

    async def _update_listener(self, hass, entry):
        """Called when the config entry is updated."""
        self._state = self._calculate_state()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Clean up when entity is removed."""
        self._teardown_listeners()