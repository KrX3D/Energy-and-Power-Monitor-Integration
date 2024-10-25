import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo, generate_entity_id
from homeassistant.const import Platform, UnitOfPower, UnitOfEnergy
from .const import DOMAIN, ENTITY_TYPE_POWER, ENTITY_TYPE_ENERGY, CONF_SMART_METER_DEVICE
from homeassistant.helpers.translation import async_get_translations
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

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
        entities = entry.data.get('entities')
        entity_type = entry.data.get('entity_type')
        smart_meter_device = entry.data.get(CONF_SMART_METER_DEVICE, TRANSLATION_NONE)

        entities_checked = check_and_remove_nonexistent_entities(hass, entities, entry)

        _LOGGER.debug(f"Setting up Energy and Power Monitor sensor: room_name={room_name}, entities={entities_checked}, smart_meter_device={smart_meter_device}, entry_id={entry.entry_id}, entity_type={entity_type}")

        if not room_name or not isinstance(entities, list):
            _LOGGER.error("Invalid configuration data: room_name or entities are missing or incorrect.")
            return False

        # Create the main sensor for the room
        sensor = EnergyandPowerMonitorSensor(hass, room_name, entities_checked, entry.entry_id, entity_type)
        async_add_entities([sensor])

        # If a smart meter device was selected, create a second sensor for it
        if smart_meter_device and smart_meter_device != TRANSLATION_NONE:  # Only create if there's a valid device selected    
            smart_meter_sensor = SmartMeterSensor(hass, room_name, smart_meter_device, entry.entry_id, entity_type, sensor)
            async_add_entities([smart_meter_sensor])

    async def reload_integration_periodically(now):
        """Reload the integration every 5 minutes."""
        _LOGGER.debug("Reloading the integration automatically after 5 minutes.")
        await async_reload_entry(hass, entry)

    # Start the periodic reloader
    async_track_time_interval(hass, reload_integration_periodically, timedelta(minutes=5))
    
    # If Home Assistant is already running, call check_and_setup_entities immediately
    if hass.is_running:
        await check_and_setup_entities()
    else:
        # Otherwise, listen for the start event
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, check_and_setup_entities)

async def async_reload_entry(hass: HomeAssistant, entry):
    """Handle reload of the config entry."""
    _LOGGER.debug("async_reload_entry function start...")
    # Simply call the async_setup_entry to reapply the configuration
    await async_setup_entry(hass, entry)

def check_and_remove_nonexistent_entities(hass: HomeAssistant, entities, entry):
    """Check if selected entities still exist, and remove those that don't."""
    _LOGGER.debug(f"Executing function check_and_remove_nonexistent_entities")
    valid_entities = []

    for entity_id in entities:
        if hass.states.get(entity_id):
            #_LOGGER.debug(f"Entity does exist, entity_id:  {entity_id}")
            valid_entities.append(entity_id)  # Keep the entity if it exists
        else:
            _LOGGER.warning(f"Entity {entity_id} no longer exists. Please removing it, by clicking Config on the room and than OK.")
    
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

        _LOGGER.debug(f"EnergyandPowerMonitorSensor initialized: {self.entity_id} for room: {self._room_name}, entity_type: {self._entity_type}")

    def generate_unique_id(self):
        """Generate a unique ID for the sensor."""
        sanitized_room_name = self._room_name.lower().replace(' ', '_')
        return f"{DOMAIN}_{sanitized_room_name}_{self._entity_type}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._room_name} selected entities - {self._entity_type.capitalize()}"

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
        return {
            "selected_entities": self._entities,
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

    async def async_update(self):
        """Update the sensor state by summing up the values from selected entities."""
        total_value = 0
        for entity_id in self._entities:
            entity = self.hass.states.get(entity_id)
            if entity and entity.state not in (None, 'unknown', 'unavailable'):
                try:
                    entity_value = float(entity.state)
                    total_value += entity_value
                    #_LOGGER.debug(f"Entity {entity_id} has power value {power_value}")
                except ValueError:
                    #_LOGGER.warning(f"Entity {entity_id} has a non-numeric state: {entity.state}")
                    pass #Remove when uncommenting the logger part
            #else:
                #_LOGGER.debug(f"Entity {entity_id} is unavailable or has an unknown state.")

        # Limit the decimals to 1 and ensure the value is not negative
        self._state = max(0, round(total_value, 1))

        #_LOGGER.info(f"Updated EnergyandPowerMonitorSensor {self.entity_id} state to {self._state} {self.unit_of_measurement}")

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

        # Generate the entity ID for this sensor
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, self._unique_id, hass=self.hass)

        _LOGGER.debug(f"SmartMeterSensor initialized: {self.entity_id} for room: {self._room_name}, smart_meter_device: {self._smart_meter_device}")

    def generate_unique_id(self):
        """Generate a unique ID for the Smart Meter sensor."""
        sanitized_room_name = self._room_name.lower().replace(' ', '_')
        return f"{DOMAIN}_{sanitized_room_name}_untracked_{self._entity_type}"

    @property
    def name(self):
        """Return the name of the Smart Meter sensor."""
        return f"{self._room_name} untracked - {self._entity_type.capitalize()}"

    @property
    def state(self):
        """Return the state of the Smart Meter sensor."""
        energy_power_monitor_value = self._energy_power_monitor_sensor.state
        smart_meter_value = self.hass.states.get(self._smart_meter_device)

        if (energy_power_monitor_value is not None and smart_meter_value is not None and
                energy_power_monitor_value != "unknown" and smart_meter_value.state != "unknown" and
                energy_power_monitor_value != "unavailable" and smart_meter_value.state != "unavailable"):
            # Calculate the difference and ensure it's not negative
            value = float(smart_meter_value.state) - float(energy_power_monitor_value)
            return max(0, round(value, 1))
        return None

    @property
    def unique_id(self):
        """Return the unique ID of the Smart Meter sensor."""
        # Generate a unique ID using the room name and the sanitized smart meter device name
        sanitized_device_name = self._smart_meter_device.split('.')[-1]  # Get the name part after the last dot
        if sanitized_device_name.endswith('_power'):
            sanitized_device_name = sanitized_device_name[:-6]  # Remove _power
        elif sanitized_device_name.endswith('_energy'):
            sanitized_device_name = sanitized_device_name[:-7]  # Remove _energy
        
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
        """Return the unit of measurement based on the selected device."""
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
            
    @property
    def area_id(self):
        """Return the area ID for the sensor."""
        return self._entry_id  # or another relevant identifier
