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
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)
ENTITY_ID_FORMAT = Platform.SENSOR + ".{}"

async def get_translated_none(hass: HomeAssistant):
    user_language = hass.config.language
    translations = await async_get_translations(hass, user_language, "config", {DOMAIN})
    none_translation_key = f"component.{DOMAIN}.config.step.select_entities.data.none"
    _LOGGER.debug(f"Full translations fetched: {translations}")
    translated_none = translations.get(none_translation_key, "None")
    return translated_none

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    _LOGGER.debug("async_setup_entry function start...")
    async def check_and_setup_entities(event=None):
        if not hass.is_running:
            _LOGGER.debug("Home Assistant is still not fully running, waiting...")
            return
        else:
            _LOGGER.debug("Home Assistant is fully started, proceeding with entity check...")
        TRANSLATION_NONE = await get_translated_none(hass)
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
        sensor = EnergyandPowerMonitorSensor(hass, room_name, entities_checked, entry.entry_id, entity_type)
        async_add_entities([sensor])
        if smart_meter_device and smart_meter_device != TRANSLATION_NONE:
            smart_meter_sensor = SmartMeterSensor(hass, room_name, smart_meter_device, entry.entry_id, entity_type, sensor)
            async_add_entities([smart_meter_sensor])
    if hass.is_running:
        await check_and_setup_entities()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, check_and_setup_entities)

def check_and_remove_nonexistent_entities(hass: HomeAssistant, entities, entry):
    _LOGGER.debug("Executing function check_and_remove_nonexistent_entities")
    valid_entities = []
    for entity_id in entities:
        if hass.states.get(entity_id):
            valid_entities.append(entity_id)
        else:
            _LOGGER.warning(f"Entity {entity_id} no longer exists. Please remove it by clicking Config on the room and then OK.")
    _LOGGER.debug(f"Valid entities after check: {valid_entities}")
    return valid_entities

class EnergyandPowerMonitorSensor(SensorEntity):
    """Representation of an Energy and Power Monitor sensor."""
    
    def __init__(self, hass: HomeAssistant, room_name, entities, entry_id, entity_type):
        self.hass = hass
        self._room_name = room_name
        self._entities = entities
        self._state = 0
        self._entry_id = entry_id
        self._entity_type = entity_type
        self._unique_id = self.generate_unique_id()
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, self._unique_id, hass=self.hass)
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
        """Re-read the configuration on each update and update state."""
        # Re-read the config entry data
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            new_entities = entry.data.get(CONF_ENTITIES, [])
            if new_entities != self._entities:
                _LOGGER.debug(f"{self._room_name} sensor: updating entities from {self._entities} to {new_entities}")
                self._entities = new_entities
        total_value = 0
        valid_entities = check_and_remove_nonexistent_entities(self.hass, self._entities, None)
        self._entities = valid_entities
        for entity_id in self._entities:
            entity = self.hass.states.get(entity_id)
            if entity and entity.state not in (None, 'unknown', 'unavailable'):
                try:
                    entity_value = float(entity.state)
                    total_value += entity_value
                except ValueError:
                    pass
        self._state = max(0, round(total_value, 1))

class SmartMeterSensor(SensorEntity):
    """Representation of a Smart Meter sensor."""
    
    def __init__(self, hass: HomeAssistant, room_name, smart_meter_device, entry_id, entity_type, energy_power_monitor_sensor):
        self.hass = hass
        self._room_name = room_name
        self._smart_meter_device = smart_meter_device
        self._entity_type = entity_type
        self._state = 0
        self._entry_id = entry_id
        self._unique_id = self.generate_unique_id()
        self._energy_power_monitor_sensor = energy_power_monitor_sensor
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, self._unique_id, hass=self.hass)
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
        sanitized_device_name = self._smart_meter_device.split('.')[-1]
        if sanitized_device_name.endswith('_power'):
            sanitized_device_name = sanitized_device_name[:-6]
        elif sanitized_device_name.endswith('_energy'):
            sanitized_device_name = sanitized_device_name[:-7]
        sanitized_room_name = self._room_name.lower().replace(' ', '_')
        return f"smart_meter_{sanitized_room_name}_{sanitized_device_name}"

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

    async def async_update(self):
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.hass.config_entries.async_add_update_listener(self._update_listener)
        )
        await super().async_added_to_hass()

    async def _update_listener(self, hass, entry):
        """Update listener: re-read configuration and force an immediate state update."""
        new_entities = entry.data.get(CONF_ENTITIES, [])
        if new_entities != self._entities:
            _LOGGER.debug(f"{self._room_name} sensor: updating entities from {self._entities} to {new_entities}")
            self._entities = new_entities
        # Force an immediate update instead of waiting for the next poll.
        await self.async_update()
