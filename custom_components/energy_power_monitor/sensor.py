import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo, generate_entity_id
from homeassistant.const import Platform, UnitOfPower, UnitOfEnergy, STATE_UNKNOWN, STATE_UNAVAILABLE
from .const import (
    DOMAIN,
    ENTITY_TYPE_POWER,
    ENTITY_TYPE_ENERGY,
    CONF_SMART_METER_DEVICE,
    CONF_ENTITIES,
    CONF_INTEGRATION_ROOMS,
)
from homeassistant.helpers.translation import async_get_translations
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)
ENTITY_ID_FORMAT = Platform.SENSOR + ".{}"


async def get_translated_none(hass: HomeAssistant):
    """Fetch the translated 'None' value."""
    user_language = hass.config.language
    #_LOGGER.debug(f"SENSOR User Language:: {user_language}")
    
    translations = await async_get_translations(hass, user_language, "config", {DOMAIN})
    none_translation_key = f"component.{DOMAIN}.config.step.select_entities.data.none"
    translated_none = translations.get(none_translation_key, "None")
    #_LOGGER.debug(f"Fetched translation for 'None': {translated_none}")
    
    return translated_none


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up the Energy and Power Monitor sensor based on a config entry."""
    _LOGGER.debug("async_setup_entry function start...")

    async def check_and_setup_entities(event=None):  # Set event=None to make it optional
        """Check for and remove non-existent entities when Home Assistant is fully started."""
        if not hass.is_running:
            _LOGGER.debug("Home Assistant is still not fully running, waiting...")
            return

        _LOGGER.debug("Home Assistant is fully started, proceeding with entity check...")
        TRANSLATION_NONE = await get_translated_none(hass)

        # Fetch configuration data
        room_name = entry.data.get('room')
        entities = entry.data.get(CONF_ENTITIES)
        entity_type = entry.data.get('entity_type')
        integration_rooms = entry.data.get(CONF_INTEGRATION_ROOMS, [])
        smart_meter_device = entry.data.get(CONF_SMART_METER_DEVICE, TRANSLATION_NONE)

        expanded_entities = expand_integration_room_entities(
            hass,
            entities,
            integration_rooms,
            entity_type,
        )
        if set(expanded_entities) != set(entities):
            new_data = entry.data.copy()
            new_data[CONF_ENTITIES] = expanded_entities
            hass.config_entries.async_update_entry(entry, data=new_data)
            entities = expanded_entities

        entities_checked = check_and_remove_nonexistent_entities(hass, entities, entry)
        if set(entities_checked) != set(entities):
            new_data = entry.data.copy()
            new_data[CONF_ENTITIES] = entities_checked
            hass.config_entries.async_update_entry(entry, data=new_data)
            _LOGGER.debug("Config entry updated with valid entities.")

        _LOGGER.debug(
            f"Setting up Energy and Power Monitor sensor: room_name={room_name}, "
            f"entities={entities_checked}, smart_meter_device={smart_meter_device}, "
            f"entry_id={entry.entry_id}, entity_type={entity_type}"
        )

        if not room_name or not isinstance(entities_checked, list):
            _LOGGER.error("Invalid configuration data: room_name or entities are missing or incorrect.")
            return False

        # Create the main sensor for the room
        sensor = EnergyandPowerMonitorSensor(hass, room_name, entities_checked, entry.entry_id, entity_type)
        async_add_entities([sensor])

        # If a smart meter device was selected, create a second sensor for it
        if smart_meter_device and smart_meter_device != TRANSLATION_NONE:  # Only create if there's a valid device selected    
            smart_meter_sensor = SmartMeterSensor(hass, room_name, smart_meter_device, entry.entry_id, entity_type, sensor)
            async_add_entities([smart_meter_sensor])

    # If Home Assistant is already running, call check_and_setup_entities immediately
    if hass.is_running:
        await check_and_setup_entities()
    else:
        # Otherwise, listen for the start event
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, check_and_setup_entities)


def check_and_remove_nonexistent_entities(hass: HomeAssistant, entities, entry):
    """Check if selected entities still exist, and remove those that don't."""
    _LOGGER.debug("Executing function check_and_remove_nonexistent_entities")
    valid_entities = []
    for entity_id in entities:
        if hass.states.get(entity_id):
            #_LOGGER.debug(f"Entity does exist, entity_id:  {entity_id}")
            valid_entities.append(entity_id)  # Keep the entity if it exists
        else:
            _LOGGER.warning(f"Entity {entity_id} no longer exists. It is being removed automatically.")
    _LOGGER.debug(f"Valid entities after check: {valid_entities}")
    return valid_entities


def expand_integration_room_entities(hass: HomeAssistant, entities, integration_rooms, entity_type):
    """Expand selected integration rooms into their tracked entities."""
    if not integration_rooms:
        return entities

    selected_entities = list(entities)
    all_sensors = hass.states.async_entity_ids("sensor")
    for room_id in integration_rooms:
        room_entities = [entity for entity in all_sensors if entity.startswith(room_id)]
        if room_entities:
            selected_entities.extend(room_entities)
        untracked_entity = f"{room_id[:-(len(entity_type) + 1)]}_untracked_{entity_type}"
        if hass.states.get(untracked_entity):
            selected_entities.append(untracked_entity)

    return sorted(set(selected_entities))


def is_valid_value(state_obj):
    """Check if a state object has a valid numeric value."""
    if state_obj is None:
        return False
    if state_obj.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, None, ''):
        return False
    try:
        float(state_obj.state)
        return True
    except (ValueError, TypeError):
        return False


class EnergyandPowerMonitorSensor(SensorEntity):
    """Representation of an Energy and Power Monitor sensor with real-time updates."""

    def __init__(self, hass: HomeAssistant, room_name, entities, entry_id, entity_type):
        """Initialize the Energy and Power Monitor sensor."""
        self.hass = hass
        self._room_name = room_name
        self._entities = entities
        self._state = 0
        self._entry_id = entry_id
        self._entity_type = entity_type  # Power or Energy type
        self._unique_id = self.generate_unique_id()
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, self._unique_id, hass=self.hass)
        self._unsubscribe_state_changes = None
        _LOGGER.debug(
            f"EnergyandPowerMonitorSensor initialized: {self.entity_id} for room: {self._room_name}, "
            f"entity_type: {self._entity_type}"
        )

    def generate_unique_id(self):
        """Generate a unique ID for the sensor."""
        sanitized_room_name = self._room_name.lower().replace(' ', '_')
        return f"{DOMAIN}_{sanitized_room_name}_{self._entity_type}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._room_name} selected entities - {self._entity_type.capitalize()}"

    @property
    def should_poll(self):
        """Disable polling; rely on state change listeners."""
        return False

    @property
    def state(self):
        """Return the current state of the sensor."""
        return self._state

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the sensor."""
        return DeviceInfo(
            identifiers={(self._entry_id,)},
            name=self._room_name,
            manufacturer="Custom",
            model="Energy and Power Monitor",
        )

    @property
    def extra_state_attributes(self):
        """Return additional attributes of the sensor."""
        return {"selected_entities": self._entities}

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:flash" if self._entity_type == ENTITY_TYPE_POWER else "mdi:counter"

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return SensorStateClass.MEASUREMENT

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement based on entity type."""
        if self._entity_type == ENTITY_TYPE_POWER:
            return UnitOfPower.WATT
        elif self._entity_type == ENTITY_TYPE_ENERGY:
            return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def device_class(self):
        """Return the device class based on entity type."""
        if self._entity_type == ENTITY_TYPE_POWER:
            return SensorDeviceClass.POWER
        elif self._entity_type == ENTITY_TYPE_ENERGY:
            return SensorDeviceClass.ENERGY

    def _calculate_state(self):
        """Calculate the current state from all entities."""
        total_value = 0
        valid_entities = []

        for entity_id in self._entities:
            entity = self.hass.states.get(entity_id)
            if is_valid_value(entity):
                try:
                    entity_value = float(entity.state)
                    # Only add positive values; negative values indicate issues
                    if entity_value >= 0:
                        total_value += entity_value
                        valid_entities.append(entity_id)
                except (ValueError, TypeError):
                    _LOGGER.warning(f"Could not convert state of {entity_id} to float: {entity.state}")

        # Update the entity list if some entities were invalid
        if len(valid_entities) != len(self._entities):
            self._entities = valid_entities

        return round(total_value, 1)

    async def async_update(self):
        """Update state by recalculating from selected entities."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            new_entities = entry.data.get(CONF_ENTITIES, [])
            if new_entities != self._entities:
                _LOGGER.debug(
                    f"{self._room_name} sensor: updating entities from {self._entities} to {new_entities}"
                )
                self._entities = new_entities
                # Resubscribe to new entities
                self._setup_state_listeners()

        self._state = self._calculate_state()

    @callback
    def _on_state_change(self, event):
        """Handle state changes in tracked entities."""
        self._state = self._calculate_state()
        self.async_write_ha_state()

    def _setup_state_listeners(self):
        """Set up state change listeners for all entities."""
        if self._unsubscribe_state_changes:
            self._unsubscribe_state_changes()

        if not self._entities:
            return

        # Listen to state changes on all selected entities
        self._unsubscribe_state_changes = async_track_state_change_event(
            self.hass,
            self._entities,
            self._on_state_change
        )
        _LOGGER.debug(f"State listeners set up for {len(self._entities)} entities in {self._room_name}")

    async def async_added_to_hass(self):
        """Called when entity is added to Home Assistant."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            self.async_on_remove(entry.add_update_listener(self._update_listener))

        # Set up state listeners for real-time updates
        self._setup_state_listeners()

        # Perform initial calculation
        self._state = self._calculate_state()

        await super().async_added_to_hass()

    async def _update_listener(self, hass, entry):
        """Update listener: re-read configuration and update state."""
        new_entities = entry.data.get(CONF_ENTITIES, [])
        if new_entities != self._entities:
            _LOGGER.debug(f"{self._room_name} sensor: updating entities from {self._entities} to {new_entities}")
            self._entities = new_entities
            self._setup_state_listeners()

        self._state = self._calculate_state()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Clean up when entity is removed."""
        if self._unsubscribe_state_changes:
            self._unsubscribe_state_changes()


class SmartMeterSensor(SensorEntity):
    """Representation of a Smart Meter sensor with real-time updates."""

    def __init__(self, hass: HomeAssistant, room_name, smart_meter_device, entry_id, entity_type, energy_power_monitor_sensor):
        """Initialize the Smart Meter sensor."""
        self.hass = hass
        self._room_name = room_name
        self._smart_meter_device = smart_meter_device
        self._entity_type = entity_type
        self._state = None
        self._entry_id = entry_id
        self._unique_id = self.generate_unique_id()
        self._energy_power_monitor_sensor = energy_power_monitor_sensor
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, self._unique_id, hass=self.hass)
        self._unsubscribe_state_changes = None
        _LOGGER.debug(
            f"SmartMeterSensor initialized: {self.entity_id} for room: {self._room_name}, "
            f"smart_meter_device: {self._smart_meter_device}"
        )

    def generate_unique_id(self):
        """Generate a unique ID for the Smart Meter sensor."""
        sanitized_room_name = self._room_name.lower().replace(' ', '_')
        return f"{DOMAIN}_{sanitized_room_name}_untracked_{self._entity_type}"

    @property
    def name(self):
        """Return the name of the Smart Meter sensor."""
        return f"{self._room_name} untracked - {self._entity_type.capitalize()}"

    @property
    def should_poll(self):
        """Disable polling; rely on state change listeners."""
        return False

    @property
    def state(self):
        """Return the state of the Smart Meter sensor."""
        return self._state

    @property
    def unique_id(self):
        """Return the unique ID of the Smart Meter sensor."""
        sanitized_device_name = self._smart_meter_device.split('.')[-1]
        if sanitized_device_name.endswith('_power'):
            sanitized_device_name = sanitized_device_name[:-6]
        elif sanitized_device_name.endswith('_energy'):
            sanitized_device_name = sanitized_device_name[:-7]
        sanitized_room_name = self._room_name.lower().replace(' ', '_')
        return f"smart_meter_{sanitized_room_name}_{sanitized_device_name}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the sensor."""
        return DeviceInfo(
            identifiers={(self._entry_id,)},
            name=self._room_name,
            manufacturer="Custom",
            model="Energy and Power Monitor",
        )

    @property
    def extra_state_attributes(self):
        """Return additional attributes of the sensor."""
        return {
            "Selected Smart Meter Device": self._smart_meter_device,
            "Energy and Power Monitor": self._energy_power_monitor_sensor.entity_id  # Add the entity ID from EnergyandPowerMonitorSensor
        }

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:flash" if self._entity_type == ENTITY_TYPE_POWER else "mdi:counter"

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return SensorStateClass.MEASUREMENT

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement based on entity type."""
        if self._entity_type == ENTITY_TYPE_POWER:
            return UnitOfPower.WATT
        elif self._entity_type == ENTITY_TYPE_ENERGY:
            return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def device_class(self):
        """Return the device class based on entity type."""
        if self._entity_type == ENTITY_TYPE_POWER:
            return SensorDeviceClass.POWER
        elif self._entity_type == ENTITY_TYPE_ENERGY:
            return SensorDeviceClass.ENERGY

    def _calculate_state(self):
        """Calculate untracked value (smart meter - tracked)."""
        energy_power_monitor_value = self._energy_power_monitor_sensor.state
        smart_meter_state = self.hass.states.get(self._smart_meter_device)

        if not is_valid_value(smart_meter_state):
            _LOGGER.debug(f"Smart meter device {self._smart_meter_device} has invalid state")
            return None

        if energy_power_monitor_value is None:
            _LOGGER.debug(f"Energy and Power Monitor sensor has no valid state yet")
            return None

        try:
            smart_meter_value = float(smart_meter_state.state)
            monitor_value = float(energy_power_monitor_value)
            result = smart_meter_value - monitor_value
            # Return 0 if negative (tracked exceeds total, which shouldn't happen)
            return max(0, round(result, 1))
        except (ValueError, TypeError) as e:
            _LOGGER.warning(f"Error calculating smart meter value: {e}")
            return None

    @callback
    def _on_state_change(self, event):
        """Handle state changes in tracked entities."""
        self._state = self._calculate_state()
        self.async_write_ha_state()

    def _setup_state_listeners(self):
        """Set up state change listeners for the smart meter device and main sensor."""
        if self._unsubscribe_state_changes:
            self._unsubscribe_state_changes()

        entities_to_track = [self._smart_meter_device]

        # Subscribe to main sensor state changes too
        if self._energy_power_monitor_sensor:
            entities_to_track.append(self._energy_power_monitor_sensor.entity_id)

        self._unsubscribe_state_changes = async_track_state_change_event(
            self.hass,
            entities_to_track,
            self._on_state_change
        )
        _LOGGER.debug(f"State listeners set up for SmartMeterSensor {self.entity_id}")

    async def async_added_to_hass(self):
        """Called when entity is added to Home Assistant."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            self.async_on_remove(entry.add_update_listener(self._update_listener))

        # Set up state listeners for real-time updates
        self._setup_state_listeners()

        # Perform initial calculation
        self._state = self._calculate_state()

        await super().async_added_to_hass()

    async def _update_listener(self, hass, entry):
        """Update listener when config changes."""
        self._state = self._calculate_state()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Clean up when entity is removed."""
        if self._unsubscribe_state_changes:
            self._unsubscribe_state_changes()
