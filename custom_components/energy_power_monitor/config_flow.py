import logging
import voluptuous as vol
from homeassistant import config_entries, core
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import async_get as entity_registry_async_get
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
import unicodedata
from homeassistant.helpers.translation import async_get_translations
import re
import asyncio

from .const import (
    DOMAIN, CONF_ROOM, CONF_ENTITIES, CONF_ENTITY_TYPE,
    ENTITY_TYPE_POWER, ENTITY_TYPE_ENERGY,
    CONF_INTEGRATION_ROOMS, CONF_SMART_METER_DEVICE
)
_LOGGER = logging.getLogger(__name__)

# Shared functions
def build_entity_options(hass, entity_ids):
    """Build select options with friendly names for entity IDs."""
    return [
        {"value": entity_id, "label": label}
        for entity_id, label in build_entity_label_map(hass, entity_ids).items()
    ]

def build_select_options_from_map(entity_map):
    """Build select options from a mapping of entity_id -> friendly_name."""
    return [{"value": entity_id, "label": friendly_name} for entity_id, friendly_name in entity_map.items()]

def build_entity_label_map(hass, entity_ids):
    """Build a mapping of entity_id -> friendly label."""
    label_map = {}
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state:
            friendly_name = state.attributes.get("friendly_name", entity_id)
            label_map[entity_id] = f"{friendly_name} - {entity_id}"
        else:
            label_map[entity_id] = entity_id
    return label_map

def get_filtered_entities_for_zone(hass, zone_id):
    """Retrieve the filtered entities for a specific zone."""
    _LOGGER.debug("get_filtered_entities_for_zone function start")
    _LOGGER.debug(f"Zone ID: {zone_id}")
    
    # Get all sensor entities
    all_sensors = hass.states.async_entity_ids('sensor')
    
    # Filter entities that start with the zone ID
    filtered_entities = [entity for entity in all_sensors if entity.startswith(zone_id)]
    _LOGGER.debug(f"get_filtered_entities_for_zone returns: {filtered_entities}")
    return filtered_entities

async def get_integration_entities(hass):
    """Retrieve all sensor entities created by this integration with their friendly names."""
    _LOGGER.debug("get_integration_entities function start")
    entity_registry = er.async_get(hass)
    integration_entities = {}
    for entity_id, entity in entity_registry.entities.items():
        if entity.unique_id.startswith(DOMAIN):
            state = hass.states.get(entity_id)
            if state and 'friendly_name' in state.attributes:
                # Get friendly_name (the UI may remove suffixes as needed)
                friendly_name = state.attributes['friendly_name']
                integration_entities[entity_id] = friendly_name
    _LOGGER.debug(f"get_integration_entities returns: {integration_entities}")
    return integration_entities

def get_selected_entities_for_zones(hass, selected_existing_zones, integration_entities, selected_entities, entity_type):
    """Get entities from selected existing zones and avoid duplicates."""
    _LOGGER.debug("get_selected_entities_for_zones function start")
    _LOGGER.debug(f"Selected zones: {selected_existing_zones}")
    _LOGGER.debug(f"Selected integration entities: {integration_entities}")
    _LOGGER.debug(f"Selected entities: {selected_entities}")
    _LOGGER.debug(f"Selected entity type: {entity_type}")
    for zone_id in selected_existing_zones:
        if zone_id in integration_entities:
            # Add entities from the existing zone to the list of selected entities
            # Ensure not to duplicate entities
            zone_entities = get_filtered_entities_for_zone(hass, zone_id)
            if zone_entities:
                selected_entities.extend(zone_entities)
            # Check for '_untracked_' entity
            untracked_entity = f"{zone_id[:-(len(entity_type) + 1)]}_untracked_{entity_type}"
            _LOGGER.debug(f"Checking for untracked entity: {untracked_entity}")
            entity_state = hass.states.get(untracked_entity)
            if entity_state:
                _LOGGER.debug(f"Found untracked entity: {untracked_entity}")
                selected_entities.append(untracked_entity)
            #else:
                #_LOGGER.debug(f"Untracked entity {untracked_entity} not found.")
    
    # Remove duplicates
    unique_selected_entities = sorted(list(set(selected_entities)))
    _LOGGER.debug(f"get_selected_entities_for_zones returns: {unique_selected_entities}")
    return unique_selected_entities

async def get_translated_entity_type(hass, entity_type):
    """Fetch the translated entity type (Power/Energy)."""
    user_language = hass.config.language
    #_LOGGER.debug(f"User Language:: {user_language}")  # Log the result
    # Fetch translations for your specific integration and the correct context (config_flow)
    translations = await async_get_translations(hass, user_language, "config", {DOMAIN})
    #_LOGGER.debug(f"Fetched translations for entity_type: {translations}")  # Log the fetched translations
     
    if entity_type == 'energy':
        entity_type = translations.get(f"component.{DOMAIN}.entity_type.energy", "Energy")
    elif entity_type == 'power':
        entity_type = translations.get(f"component.{DOMAIN}.entity_type.power", "Power")
    _LOGGER.debug(f"Translated entity type: {entity_type}")
    return entity_type

async def get_translated_none(hass):
    """Fetch the translated 'None' value."""
    user_language = hass.config.language
    #_LOGGER.debug(f"User Language:: {user_language}")  # Log the result
    translations = await async_get_translations(hass, user_language, "config", {DOMAIN})
    # Construct the translation key
    none_translation_key = f"component.{DOMAIN}.config.step.select_entities.data.none"
    #_LOGGER.debug(f"Full translations fetched: {translations}")
    translated_none = translations.get(none_translation_key, "None")
    _LOGGER.debug(f"Translated 'None': {translated_none}")
    return translated_none

def get_selected_smart_meter_devices(hass, filtered_entities, translated_none=None):
    """Retrieve the selected smart meter devices from filtered entities."""
    _LOGGER.debug("get_selected_smart_meter_devices function start")
    # Filter entities that start with 'sensor.energy_power_monitor'
    old_entities_smd = [entity for entity in filtered_entities if entity.startswith(f'sensor.{DOMAIN}')]
    old_entities_smd_untracked = [entity for entity in old_entities_smd if '_untracked_' in entity]
    selected_smart_meter_devices = set()  # Use a set to avoid duplicates
    for entity in old_entities_smd_untracked:
        state = hass.states.get(entity)  # Get the state of the entity
        if state and 'Selected Smart Meter Device' in state.attributes:
            selected_device = state.attributes['Selected Smart Meter Device']
            selected_smart_meter_devices.add(selected_device)
    for entry in hass.config_entries.async_entries(DOMAIN):
        selected_device = entry.data.get(CONF_SMART_METER_DEVICE)
        if selected_device and selected_device not in ("", translated_none):
            selected_smart_meter_devices.add(selected_device)
    _LOGGER.debug(f"Already created Smart Meter Devices: {old_entities_smd_untracked}")
    _LOGGER.debug(f"Selected smart meter devices: {selected_smart_meter_devices}")
    return selected_smart_meter_devices

def normalize_smart_meter_selection(user_input, translated_none):
    """Normalize smart meter selection from user input."""
    if CONF_SMART_METER_DEVICE in user_input:
        selected_smd = user_input.get(CONF_SMART_METER_DEVICE)
    else:
        selected_smd = translated_none
    if selected_smd in ("", translated_none, None):
        return translated_none
    return selected_smd

def remove_smart_meter_from_entities(selected_smd, selected_entities):
    """Remove smart meter entity from selected entities if present."""
    if selected_smd and selected_smd in selected_entities:
        selected_entities.remove(selected_smd)
    return selected_entities

# Get all Integration zones that were already selected and assigned to a zone
def get_selected_integration_zones(hass, existing_zones):
    """Retrieve the selected smart meter devices from filtered entities."""
    _LOGGER.debug("get_selected_integration_zones function start")
    filtered_entities_with_friendly_name = {}  # Initialize a dictionary to store filtered entities and their friendly names
    for entity_id in existing_zones:  # Iterate over the existing zone entity IDs
        # Get the entity's state object from Home Assistant
        entity_state = hass.states.get(entity_id)
        if entity_state:
            selected_entities = entity_state.attributes.get('selected_entities', [])
            # Filter entities that start with 'sensor.energy_power_monitor' and do not end with '_untracked_'
            for entity in selected_entities:
                if entity.startswith(f'sensor.{DOMAIN}') and not entity.endswith(('_untracked_power', '_untracked_energy')):
                    friendly_name = hass.states.get(entity).attributes.get('friendly_name', entity)
                    friendly_name = friendly_name.replace(" selected entities - Power", "").replace(" selected entities - Energy", "")
                    filtered_entities_with_friendly_name[entity] = friendly_name
            #_LOGGER.info(f"Zone: {entity_id} - Filtered entities: {filtered_entities_with_friendly_name}")
        #else:
            #_LOGGER.warning(f"Entity {entity_id} not found in Home Assistant states.")
    sorted_filtered_entities = dict(sorted(filtered_entities_with_friendly_name.items(), key=lambda item: item[1]))
    #_LOGGER.debug(f"Sorted filtered entities with friendly names: {sorted_filtered_entities}")
    return sorted_filtered_entities

def build_existing_zones_for_gui(integration_entities):
    """Build existing zones mapping for GUI selections."""
    existing_zones = {
        entity_id: friendly_name.replace(" selected entities - Power", "").replace(" selected entities - Energy", "")
        for entity_id, friendly_name in integration_entities.items()
    }
    existing_zones = dict(sorted(existing_zones.items(), key=lambda item: item[1]))
    return existing_zones

@config_entries.HANDLERS.register(DOMAIN)
class EnergyandPowerMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for energy_power_monitor."""
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Store the energy/power selection and zone name for use in step 2
            self.selected_type = user_input[CONF_ENTITY_TYPE]
            self.zone_name = user_input[CONF_ROOM]
            # Proceed to the next step after this input
            return await self.async_step_select_entities()
        data_schema = vol.Schema({
            vol.Required(CONF_ROOM): cv.string,
            vol.Required(CONF_ENTITY_TYPE, default=ENTITY_TYPE_POWER): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": ENTITY_TYPE_ENERGY, "label": ENTITY_TYPE_ENERGY},
                        {"value": ENTITY_TYPE_POWER, "label": ENTITY_TYPE_POWER}
                    ],
                    translation_key="entity_type",
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_select_entities(self, user_input=None):
        errors = {}
        TRANSLATION_NONE = await get_translated_none(self.hass)
        # Get all sensor entity IDs
        all_entities = self.hass.states.async_entity_ids('sensor')
        # Filter entities based on the selected type from the first GUI
        if self.selected_type == ENTITY_TYPE_POWER:
            filtered_entities = [entity for entity in all_entities if entity.endswith('_power')]
        else:
            filtered_entities = [entity for entity in all_entities if entity.endswith('_energy')]
        selected_smart_meter_devices = get_selected_smart_meter_devices(self.hass, filtered_entities, TRANSLATION_NONE)
        # Remove entities that start with 'sensor.energy_power_monitor'
        filtered_entities = [entity for entity in filtered_entities if not entity.startswith(f'sensor.{DOMAIN}')]
        existing_entities_in_zones = set()
        # Get current integration entries
        current_entries = self.hass.config_entries.async_entries(DOMAIN)
        for entry in current_entries:
            entities = entry.data.get(CONF_ENTITIES, [])
            existing_entities_in_zones.update(entities)
        _LOGGER.debug(f"Already picked entities: {existing_entities_in_zones}")
        # Exclude entities already used by other zones
        filtered_entities = sorted([
            entity for entity in filtered_entities 
            if entity not in existing_entities_in_zones and entity not in selected_smart_meter_devices
        ])
        _LOGGER.debug(f"Filtered entities after: {filtered_entities}")
        integration_entities = await get_integration_entities(self.hass)
        if user_input is not None:
            selected_entities = user_input.get(CONF_ENTITIES, [])
            selected_existing_zones = user_input.get(CONF_INTEGRATION_ROOMS, [])
            # Get selected entities from the existing zones
            selected_entities = get_selected_entities_for_zones(
                self.hass,
                selected_existing_zones,
                integration_entities,
                selected_entities,
                self.selected_type,
            )
            selected_smd = normalize_smart_meter_selection(user_input, TRANSLATION_NONE)
            _LOGGER.info(f"selected_smd before: {selected_smd}")
            _LOGGER.info(f"selected_smd after: {selected_smd}")
            selected_entities = remove_smart_meter_from_entities(selected_smd, selected_entities)
            translated_entity_type = await get_translated_entity_type(self.hass, self.selected_type)
            _LOGGER.info(f"Selected entities: {selected_entities}")
            _LOGGER.info(f"Entity type: {translated_entity_type}")
            return self.async_create_entry(
                title=f"{translated_entity_type} - {self.zone_name}",
                data={
                    CONF_ROOM: self.zone_name,
                    CONF_SMART_METER_DEVICE: selected_smd,
                    CONF_ENTITY_TYPE: self.selected_type,
                    CONF_ENTITIES: selected_entities,
                    CONF_INTEGRATION_ROOMS: selected_existing_zones
                }
            )
        existing_zones = build_existing_zones_for_gui(integration_entities)
        _LOGGER.info(f"Existing zones with friendly names: {existing_zones}")
        assigned_integration_zones = get_selected_integration_zones(self.hass, existing_zones)
        # Remove zones already assigned
        filtered_existing_zones = {entity_id: friendly_name for entity_id, friendly_name in existing_zones.items() if entity_id not in assigned_integration_zones}
        _LOGGER.info(f"Filtered existing zones (excluding assigned integration zones): {filtered_existing_zones}")
        entity_options = build_entity_options(self.hass, sorted(filtered_entities))
        smart_meter_options = list({option["value"]: option for option in entity_options}.values())
        smart_meter_options.insert(0, {"value": TRANSLATION_NONE, "label": TRANSLATION_NONE})
        integration_zone_options = build_select_options_from_map(filtered_existing_zones)
        # Note: Real-time dynamic updating of one dropdown based on another's selection is not supported.
        data_schema = vol.Schema({
            vol.Optional(CONF_SMART_METER_DEVICE, default=TRANSLATION_NONE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=smart_meter_options,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional(CONF_ENTITIES, default=[]): vol.All(
                cv.multi_select(build_entity_label_map(self.hass, filtered_entities))
            ),
            vol.Optional(CONF_INTEGRATION_ROOMS, default=[]): vol.All(cv.multi_select(filtered_existing_zones))
        })
        return self.async_show_form(step_id="select_entities", data_schema=data_schema, errors=errors)

    async def async_step_options(self, user_input=None):
        """Handle options flow to reconfigure the zone."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow."""
        return EnergyandPowerMonitorOptionsFlowHandler(config_entry)

class EnergyandPowerMonitorOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""
    VERSION = 1

    def __init__(self, config_entry):
        """Initialize options flow."""
        self._config_entry = config_entry
        self.options = dict(config_entry.data)

    async def update_all_references(self, old_zone: str, new_zone: str, current_entity_type: str):
        """
        Update references to the old zone in all other config entries.
        This updates both CONF_INTEGRATION_ROOMS and CONF_ENTITIES if they reference the old sensor ID.
        """
        sanitized_old = old_zone.lower().replace(" ", "_")
        sanitized_new = new_zone.lower().replace(" ", "_")
        old_main_id = f"sensor.{DOMAIN}_{sanitized_old}_{current_entity_type}"
        new_main_id = f"sensor.{DOMAIN}_{sanitized_new}_{current_entity_type}"
        old_smart_prefix = f"sensor.{DOMAIN}_{sanitized_old}_untracked_"
        new_smart_prefix = f"sensor.{DOMAIN}_{sanitized_new}_untracked_"

        _LOGGER.debug(f"update_all_references: Updating references from {old_main_id} to {new_main_id}")
        entries = self.hass.config_entries.async_entries(DOMAIN)
        for entry in entries:
            if entry.entry_id == self.config_entry.entry_id:
                continue
            zone_name = entry.data.get(CONF_ROOM, "Unknown")
            data = dict(entry.data)
            updated = False

            # Update integration_zones list
            if CONF_INTEGRATION_ROOMS in data:
                new_zones_list = []
                for zone in data[CONF_INTEGRATION_ROOMS]:
                    if zone == old_main_id:
                        new_zones_list.append(new_main_id)
                        updated = True
                        _LOGGER.debug(f"Updated integration zone: {zone} -> {new_main_id} in zone {zone_name}")
                    else:
                        new_zones_list.append(zone)
                data[CONF_INTEGRATION_ROOMS] = new_zones_list
                _LOGGER.debug(f"data[{CONF_INTEGRATION_ROOMS}] = {new_zones_list}")
            
            # Update entities list
            if CONF_ENTITIES in data:
                new_entities_list = []
                for ent in data[CONF_ENTITIES]:
                    if ent == old_main_id:
                        new_entities_list.append(new_main_id)
                        updated = True
                        _LOGGER.debug(f"Updated entity: {ent} -> {new_main_id} in zone {zone_name}")
                    elif ent.startswith(old_smart_prefix):
                        new_ent = new_smart_prefix + ent[len(old_smart_prefix):]
                        new_entities_list.append(new_ent)
                        updated = True
                        _LOGGER.debug(f"Updated smart entity from prefix {old_smart_prefix} to {new_smart_prefix}: {ent} -> {new_ent} in zone {zone_name}")
                    else:
                        new_entities_list.append(ent)
                        _LOGGER.debug(f"Appending entity without change: {ent} in zone {zone_name}")
                data[CONF_ENTITIES] = new_entities_list
                _LOGGER.debug(f"data[{CONF_ENTITIES}] = {new_entities_list}")
            
            if updated:
                _LOGGER.debug(f"Updating references in config entry for zone: {zone_name} from {old_main_id} to {new_main_id}")
                self.hass.config_entries.async_update_entry(entry, data=data)
        _LOGGER.debug("Completed update_all_references")


    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Manage the options."""
        errors = {}
        TRANSLATION_NONE = await get_translated_none(self.hass)
        old_zone = self.config_entry.data.get(CONF_ROOM, "")
        old_entities_smd = self.config_entry.data.get(CONF_SMART_METER_DEVICE, "")
        old_entities = set(self.config_entry.data.get(CONF_ENTITIES, []))
        old_integration_zones = self.config_entry.data.get(CONF_INTEGRATION_ROOMS, [])
        current_zone = self.config_entry.data.get(CONF_ROOM, "")

        # Use get_integration_entities for existing zones
        integration_entities = await get_integration_entities(self.hass)
        if user_input is not None:
            try:
                # If the zone name has changed, update references in all other config entries
                if user_input[CONF_ROOM] != old_zone:
                    current_entity_type = self.config_entry.data.get(CONF_ENTITY_TYPE)
                    _LOGGER.debug("Zone name has changed, updating references...")
                    await self.update_all_references(old_zone, user_input[CONF_ROOM], current_entity_type)
                    _LOGGER.debug("Reloading current config entry after updating references")
                    await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                
                await self.async_remove_old_config(old_zone)
                await self.async_remove_sensor_entities(old_zone)

                # Retrieve new configuration
                selected_entities = user_input.get(CONF_ENTITIES, [])
                selected_existing_zones = user_input.get(CONF_INTEGRATION_ROOMS, [])
                selected_smd = normalize_smart_meter_selection(user_input, TRANSLATION_NONE)

                current_entity_type = self.config_entry.data.get(CONF_ENTITY_TYPE)  # Default to power if not found

                # Get selected entities from the existing zones
                selected_entities = get_selected_entities_for_zones(
                    self.hass,
                    selected_existing_zones,
                    integration_entities,
                    selected_entities,
                    current_entity_type,
                )
                selected_entities = remove_smart_meter_from_entities(selected_smd, selected_entities)
                _LOGGER.info(f"Selected entities: {selected_entities}")

                translated_entity_type = await get_translated_entity_type(self.hass, current_entity_type)
                self.options.update({
                    CONF_ROOM: user_input[CONF_ROOM],
                    CONF_SMART_METER_DEVICE: selected_smd,
                    CONF_ENTITIES: selected_entities,
                    CONF_INTEGRATION_ROOMS: selected_existing_zones
                })
                await self.async_create_new_config(self.options, translated_entity_type)
                # Do not force a reload here to prevent looping; assume the sensor platform updates naturally.
                return self.async_create_entry(
                    title=f"{translated_entity_type} - {self.options[CONF_ROOM]}",
                    data=self.options
                )
            except Exception as ex:
                _LOGGER.exception("Unexpected exception during options update: %s", ex)
                errors["base"] = "unknown"
        existing_zones = build_existing_zones_for_gui(integration_entities)  # Sort by friendly name
        _LOGGER.info(f"Existing zones with friendly names: {existing_zones}")

        # Remove the currently configured zone from the options
        current_zone = self.config_entry.data.get(CONF_ROOM)
        if current_zone:
            existing_zones = {k: v for k, v in existing_zones.items() if v != current_zone}

        # Detailed logging for debugging the filtering process
        _LOGGER.debug(f"Old integration zones: {old_integration_zones}")
        _LOGGER.debug(f"Existing zones: {existing_zones}")

        # Filter the old entities (already selected)
        filtered_old_entities = set(entity for entity in old_entities if not entity.startswith(f'sensor.{DOMAIN}'))
        _LOGGER.debug(f"Old entities: {old_entities}")
        _LOGGER.debug(f"Old filtered entities: {filtered_old_entities}")

        # Detailed logging for the filtering operation
        filtered_old_integration_zones = []
        for entity_id in old_integration_zones:
            friendly_name = existing_zones.get(entity_id, '').strip()
            if friendly_name:
                filtered_old_integration_zones.append(friendly_name)
        _LOGGER.debug(f"Filtered previously selected Integration Zones: {filtered_old_integration_zones}")

        all_entities = self.hass.states.async_entity_ids('sensor')

        # Sanitize the zone name by replacing spaces with underscores        
        normalized_name = unicodedata.normalize('NFKD', current_zone).encode('ascii', 'ignore').decode('utf-8')
        sanitized_zone_name = normalized_name.replace(" ", "_").replace("-", "_")
        base_entity_id = f"sensor.{DOMAIN}_{sanitized_zone_name.lower()}"
        _LOGGER.debug(f"Current zone base_entity_id: {base_entity_id}")
        entity_id = None

        # Check for the existence of either _power or _energy
        if self.hass.states.get(f"{base_entity_id}_power"):
            entity_id = f"{base_entity_id}_power"
        if self.hass.states.get(f"{base_entity_id}_energy"):
            entity_id = f"{base_entity_id}_energy"
        _LOGGER.debug(f"Current zone entity_id: {entity_id}")
        device_class = None
        if self.hass.states.get(entity_id):
            state = self.hass.states.get(entity_id)
            device_class = state.attributes.get('device_class', ENTITY_TYPE_POWER)
            _LOGGER.debug(f"Current zone state: {state}")
            _LOGGER.debug(f"Current zone device_class: {device_class}")

        if device_class == ENTITY_TYPE_POWER:
            filtered_entities = [entity for entity in all_entities if entity.endswith('_power')]
        elif device_class == ENTITY_TYPE_ENERGY:
            filtered_entities = [entity for entity in all_entities if entity.endswith('_energy')]
        else:
            filtered_entities = [entity for entity in all_entities if entity.endswith('_power') or entity.endswith('_energy')]
        selected_smart_meter_devices = get_selected_smart_meter_devices(self.hass, filtered_entities, TRANSLATION_NONE)

        filtered_entities = [entity for entity in filtered_entities if not entity.startswith(f'sensor.{DOMAIN}')]
        existing_zones_for_gui = {friendly_name: entity_id for entity_id, friendly_name in existing_zones.items()}
        selected_integration_zones = [existing_zones_for_gui[name] for name in filtered_old_integration_zones if name in existing_zones_for_gui]
        _LOGGER.debug(f"Filtered selected_integration_zones: {selected_integration_zones}")
        assigned_integration_zones = get_selected_integration_zones(self.hass, existing_zones)
        filtered_existing_zones = {entity_id: friendly_name for entity_id, friendly_name in existing_zones.items() if entity_id not in assigned_integration_zones}
        _LOGGER.info(f"Filtered existing zones (excluding assigned integration zones): {filtered_existing_zones}")
        existing_entities_in_zones = set()

        current_entries = self.hass.config_entries.async_entries(DOMAIN)
        for entry in current_entries:
            entities = entry.data.get(CONF_ENTITIES, [])
            existing_entities_in_zones.update(entities)
        _LOGGER.debug(f"Already picked entities: {existing_entities_in_zones}")
        
        filtered_entities = sorted([entity for entity in filtered_entities if entity not in existing_entities_in_zones and entity not in selected_smart_meter_devices])
        filtered_entities = sorted(set(filtered_entities))
        combined_entities = sorted(filtered_old_entities.union(filtered_entities))
        _LOGGER.debug(f"Combined entities: {combined_entities}")

        smart_meter_options = sorted(filtered_entities)
        if old_entities_smd and old_entities_smd != TRANSLATION_NONE:
            _LOGGER.debug(f"old_entities_smd entities: {old_entities_smd}")
            smart_meter_options.insert(0, old_entities_smd)
            _LOGGER.debug(f"smart_meter_options entities: {smart_meter_options}")

        sorted_options = sorted(set(smart_meter_options))
        sorted_options.insert(0, TRANSLATION_NONE)
        _LOGGER.debug(f"sorted_options entities: {sorted_options}")
        
        if old_entities_smd in ("", TRANSLATION_NONE, None):
            default_smart_meter_device = TRANSLATION_NONE
        else:
            default_smart_meter_device = old_entities_smd
        smart_meter_option_list = build_entity_options(
            self.hass,
            [option for option in sorted_options if option != TRANSLATION_NONE]
        )
        smart_meter_option_list.insert(0, {"value": TRANSLATION_NONE, "label": TRANSLATION_NONE})
        smart_meter_option_list = list({option["value"]: option for option in smart_meter_option_list}.values())
        if old_entities_smd and old_entities_smd != TRANSLATION_NONE and old_entities_smd in combined_entities:
            combined_entities = [entity for entity in combined_entities if entity != old_entities_smd]
        integration_zone_options = build_select_options_from_map(filtered_existing_zones)
        options_schema = vol.Schema({
            vol.Required(CONF_ROOM, default=old_zone): cv.string,
            vol.Optional(CONF_SMART_METER_DEVICE, default=default_smart_meter_device): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=smart_meter_option_list,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional(CONF_ENTITIES, default=list(old_entities)): vol.All(
                cv.multi_select(build_entity_label_map(self.hass, combined_entities))
            ),
            vol.Optional(CONF_INTEGRATION_ROOMS, default=selected_integration_zones): vol.All(cv.multi_select(filtered_existing_zones))
        })
        return self.async_show_form(step_id="user", data_schema=options_schema, errors=errors)

    async def async_remove_old_config(self, old_zone):
        """Remove the old sensor configuration."""
        _LOGGER.info("Removing old configuration for zone: %s", old_zone)
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get(CONF_ROOM) == old_zone:
                if entry.entry_id in self.hass.data.get(f'{DOMAIN}_config', {}):
                    sensor_data = self.hass.data[f'{DOMAIN}_config'][entry.entry_id]
                    sensors = sensor_data.get('sensors', [])
                    for sensor in sensors:
                        if hasattr(sensor, "async_remove_sensor_entities"):
                            await sensor.async_remove_sensor_entities(old_zone)

    async def async_create_new_config(self, user_input, translated_entity_type):
        """Create the new configuration."""
        zone_name = user_input[CONF_ROOM]
        smart_meter_device = user_input.get(CONF_SMART_METER_DEVICE)  # Get the smart meter device from the user input
        entities = user_input[CONF_ENTITIES]
        #_LOGGER.info(f"Creating new configuration for zone: {zone_name} with entities: {entities} and smart meter: {smart_meter_device}")
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            title=f"{translated_entity_type} - {zone_name}",
            data={
                CONF_ROOM: zone_name,
                CONF_SMART_METER_DEVICE: smart_meter_device,
                CONF_ENTITIES: entities,
                CONF_ENTITY_TYPE: user_input[CONF_ENTITY_TYPE],
                CONF_INTEGRATION_ROOMS: user_input.get(CONF_INTEGRATION_ROOMS, [])
            }
        )
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)

    async def async_remove_sensor_entities(self, zone_name):
        """Remove all sensor entities associated with the old zone name and log them."""
        entity_registry = entity_registry_async_get(self.hass)
        current_entity_type = self.config_entry.data.get(CONF_ENTITY_TYPE)
        _LOGGER.info(f"Entity Type: {current_entity_type}")
        #_LOGGER.debug(f"zone name: {zone_name}")
        normalized_name = unicodedata.normalize('NFKD', zone_name).encode('ascii', 'ignore').decode('utf-8')
        sanitized_zone_name = normalized_name.replace(" ", "_").replace("-", "_")
        entity_id_se = f"sensor.{DOMAIN}_{sanitized_zone_name.lower()}_{current_entity_type}"
        entity_id_cr = f"sensor.{DOMAIN}_{sanitized_zone_name.lower()}_untracked_{current_entity_type}"
        _LOGGER.info(f"Attempting to remove entity: {entity_id_se} and {entity_id_cr}")
        if entity_id_se in entity_registry.entities:
            _LOGGER.info(f"Removing entity from registry: {entity_id_se}")
            entity_registry.async_remove(entity_id_se)
        if self.hass.states.get(entity_id_se):
            _LOGGER.info(f"Removing entity state: {entity_id_se}")
            self.hass.states.async_remove(entity_id_se)
        if entity_id_cr in entity_registry.entities:
            _LOGGER.info(f"Removing entity from registry: {entity_id_cr}")
            entity_registry.async_remove(entity_id_cr)
        if self.hass.states.get(entity_id_cr):
            _LOGGER.info(f"Removing entity state: {entity_id_cr}")
            self.hass.states.async_remove(entity_id_cr)
