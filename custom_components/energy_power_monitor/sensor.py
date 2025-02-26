import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo, generate_entity_id
from homeassistant.const import Platform, UnitOfPower, UnitOfEnergy
from .const import DOMAIN, ENTITY_TYPE_POWER, ENTITY_TYPE_ENERGY, CONF_SMART_METER_DEVICE, CONF_ENTITIES
from homeassistant.helpers.translation import async_get_translations
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta, datetime

_LOGGER = logging.getLogger(__name__)
ENTITY_ID_FORMAT = Platform.SENSOR + ".{}"

async def get_translated_none(hass: HomeAssistant):
    """Fetch the translated 'None' value."""
    user_language = hass.config.language
    #_LOGGER.debug(f"SENSOR User Language:: {user_language}")
    translations = await async_get_translations(hass, user_language, "config", {DOMAIN})
    none_translation_key = f"component.{DOMAIN}.config.step.select_entities.data.none"
    _LOGGER.debug(f"Full translations fetched: {translations}")
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
        else:
            _LOGGER.debug("Home Assistant is fully started, proceeding with entity check...")

        # Fetch translations
        TRANSLATION_NONE = await get_translated_none(hass)
        # Fetch configuration data
        room_name = entry.data.get('room')
        entities = entry.data.get(CONF_ENTITIES)
        entity_type = entry.data.get('entity_type')
        smart_meter_device = entry.data.get(CONF_SMART_METER_DEVICE, TRANSLATION_NONE)
        entities_checked = check_and_remove_nonexistent_entities(hass, entities, entry)
        if set(entities_checked) != set(entities):
            new_data = entry.data.copy()
            new_data[CONF_ENTITIES] = entities_checked
            hass.config_entries.async_update_entry(entry, data=new_data)
            _LOGGER.debug("Config entry updated with valid entities.")
        _LOGGER.debug(f"Setting up Energy and Power Monitor sensor: room_name={room_name}, entities={entities_checked}, smart_meter_device={smart_meter_device}, entry_id={entry.entry_id}, entity_type={entity_type}")
        if not room_name or not isinstance(entities_checked, list):
            _LOGGER.error("Invalid configuration data: room_name or entities are missing or incorrect.")
            return False

        # Create the main sensor for the room
        sensor = EnergyandPowerMonitorSensor(hass, room_name, entities_checked, entry.entry_id, entity_type)
        async_add_entities([sensor])

        # If a smart meter device was selected, create a second sensor for it
        if smart_meter_device and smart_meter_device != TRANSLATION_NONE:
            smart_meter_sensor = SmartMeterSensor(hass, room_name, smart_meter_device, entry.entry_id, entity_type, sensor)
            async_add_entities([smart_meter_sensor])

    async def reload_integration_periodically(now):
        """Reload the integration every 5 minutes."""
        _LOGGER.debug("Reloading the integration automatically after 5 minutes.")
        await hass.config_entries.async_reload(entry.entry_id)

    async def start_periodic_reload(event):
        async_track_time_interval(hass, reload_integration_periodically, timedelta(minutes=5))

    if hass.is_running:
        await check_and_setup_entities()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, check_and_setup_entities)
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start_periodic_reload)

def check_and_remove_nonexistent_entities(hass: HomeAssistant, entities, entry):
    """Check if selected entities still exist, and remove those that don't."""
    _LOGGER.debug("Executing function check_and_remove_nonexistent_entities")
    valid_entities = []
    for entity_id in entities:
        if hass.states.get(entity_id):
            #_LOGGER.debug(f"Entity does exist, entity_id: {entity_id}")
            valid_entities.append(entity_id)
        else:
            _LOGGER.info(f"Entity {entity_id} not found and removed from sensor attributes.")
    _LOGGER.debug(f"Valid entities after check: {valid_entities}")
    return valid_entities

class EnergyandPowerMonitorSensor(SensorEntity):
    """Representation of an Energy and Power Monitor sensor."""
    
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
        self._removed = False  # Flag to mark removal
        _LOGGER.debug(f"EnergyandPowerMonitorSensor initialized: {self.entity_id} for room: {self._room_name}, entity_type: {self._entity_type}")

    def generate_unique_id(self):
        sanitized_room_name = self._room_name.lower().replace(' ', '_')
        return f"{DOMAIN}_{sanitized_room_name}_{self._entity_type}"

    @property
    def name(self):
        return f"{self._room_name} selected entities - {self._entity_type.capitalize()}"

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
            name=self._room_name,
            manufacturer="Custom",
            model="Energy and Power Monitor",
        )

    @property
    def extra_state_attributes(self):
        return {"selected_entities": self._entities}

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
        elif self._entity_type == ENTITY_TYPE_ENERGY:
            return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def device_class(self):
        if self._entity_type == ENTITY_TYPE_POWER:
            return SensorDeviceClass.POWER
        elif self._entity_type == ENTITY_TYPE_ENERGY:
            return SensorDeviceClass.ENERGY

    async def async_update(self):
        if self._removed:
            return
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            new_entities = entry.data.get(CONF_ENTITIES, [])
            if new_entities != self._entities:
                _LOGGER.debug(f"{self._room_name} sensor: updating entities from {self._entities} to {new_entities}")
                self._entities = new_entities
        valid_entities = check_and_remove_nonexistent_entities(self.hass, self._entities, None)
        if valid_entities != self._entities:
            _LOGGER.info(f"Sensor {self.entity_id}: updating entities from {self._entities} to {valid_entities}")
        self._entities = valid_entities
        # Only write state if entities have changed
        if hasattr(self, "_prev_entities") and self._prev_entities == self._entities:
            return
        self._prev_entities = self._entities

        total_value = 0
        for entity_id in self._entities:
            entity = self.hass.states.get(entity_id)
            if entity and entity.state not in (None, 'unknown', 'unavailable'):
                try:
                    total_value += float(entity.state)
                except ValueError:
                    pass
        self._state = max(0, round(total_value, 1))
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register update listener when the sensor is added."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            # Store the removal callback; do not call it manually later.
            self._remove_update_listener = entry.add_update_listener(self._update_listener)
            self.async_on_remove(self._remove_update_listener)
        await super().async_added_to_hass()

    async def async_remove(self):
        """Override removal: mark sensor as removed and then call parent removal."""
        self._removed = True
        # Do not call self._remove_update_listener() here as it's already scheduled for removal.
        await super().async_remove()

    async def _update_listener(self, hass, entry):
        if self._removed:
            return
        new_entities = entry.data.get(CONF_ENTITIES, [])
        if new_entities != self._entities:
            _LOGGER.debug(f"{self._room_name} sensor: updating entities from {self._entities} to {new_entities}")
            self._entities = new_entities
        self.async_write_ha_state()
        
    async def async_remove_sensor_entities(self, room_name):
        """Remove this sensor if its room name matches the given room."""
        if room_name == self._room_name:
            _LOGGER.info(f"Removing sensor {self.entity_id} for room: {room_name}")
            self._removed = True
            await self.async_remove()

class SmartMeterSensor(SensorEntity):
    """Representation of a Smart Meter sensor."""
    
    def __init__(self, hass: HomeAssistant, room_name, smart_meter_device, entry_id, entity_type, energy_power_monitor_sensor):
        """Initialize the Smart Meter sensor."""
        self.hass = hass
        self._room_name = room_name
        self._smart_meter_device = smart_meter_device
        self._entity_type = entity_type
        self._state = 0
        self._entry_id = entry_id
        self._unique_id = self.generate_unique_id()
        self._energy_power_monitor_sensor = energy_power_monitor_sensor
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, self._unique_id, hass=self.hass)
        self._removed = False
        _LOGGER.debug(f"SmartMeterSensor initialized: {self.entity_id} for room: {self._room_name}, smart_meter_device: {self._smart_meter_device}")

    def generate_unique_id(self):
        sanitized_room_name = self._room_name.lower().replace(' ', '_')
        return f"{DOMAIN}_{sanitized_room_name}_untracked_{self._entity_type}"

    @property
    def name(self):
        return f"{self._room_name} untracked - {self._entity_type.capitalize()}"

    @property
    def state(self):
        energy_power_monitor_value = self._energy_power_monitor_sensor.state
        smart_meter_value = self.hass.states.get(self._smart_meter_device)
        if (energy_power_monitor_value is not None and smart_meter_value is not None and
                energy_power_monitor_value not in ("unknown", "unavailable") and
                smart_meter_value.state not in ("unknown", "unavailable")):
            try:
                value = float(smart_meter_value.state) - float(energy_power_monitor_value)
                return max(0, round(value, 1))
            except ValueError:
                return None
        return None

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(self._entry_id,)},
            name=self._room_name,
            manufacturer="Custom",
            model="Energy and Power Monitor",
        )

    @property
    def extra_state_attributes(self):
        return {
            "Selected Smart Meter Device": self._smart_meter_device,
            "Energy and Power Monitor": self._energy_power_monitor_sensor.entity_id
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
        elif self._entity_type == ENTITY_TYPE_ENERGY:
            return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def device_class(self):
        if self._entity_type == ENTITY_TYPE_POWER:
            return SensorDeviceClass.POWER
        elif self._entity_type == ENTITY_TYPE_ENERGY:
            return SensorDeviceClass.ENERGY

    @property
    def area_id(self):
        return self._entry_id

    async def async_update(self):
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            self._remove_update_listener = entry.add_update_listener(self._update_listener)
            self.async_on_remove(self._remove_update_listener)
        await super().async_added_to_hass()

    async def async_remove(self):
        self._removed = True
        await super().async_remove()

    async def _update_listener(self, hass, entry):
        if self._removed:
            return
        self.async_write_ha_state()
        
    async def async_remove_sensor_entities(self, room_name):
        if room_name == self._room_name:
            _LOGGER.info(f"Removing sensor {self.entity_id} for room: {room_name}")
            self._removed = True
            await self.async_remove()
