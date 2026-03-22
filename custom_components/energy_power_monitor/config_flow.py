import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.helpers.translation import async_get_translations

from .const import (
    DOMAIN,
    CONF_ROOM,
    CONF_ENTITIES,
    CONF_ENTITY_TYPE,
    ENTITY_TYPE_POWER,
    ENTITY_TYPE_ENERGY,
    CONF_INTEGRATION_ROOMS,
    CONF_SMART_METER_DEVICE,
    sanitize_zone_name,
    is_smart_meter_selected,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def build_entity_options(hass, entity_ids):
    """Build select options with friendly names for entity IDs."""
    return [
        {"value": entity_id, "label": label}
        for entity_id, label in build_entity_label_map(hass, entity_ids).items()
    ]


def build_select_options_from_map(entity_map):
    """Build select options from a mapping of entity_id -> friendly_name."""
    return [
        {"value": entity_id, "label": friendly_name}
        for entity_id, friendly_name in entity_map.items()
    ]


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
    """Retrieve all sensor entities whose ID starts with zone_id."""
    _LOGGER.debug("get_filtered_entities_for_zone: zone_id=%s", zone_id)
    all_sensors = hass.states.async_entity_ids("sensor")
    filtered = [e for e in all_sensors if e.startswith(zone_id)]
    _LOGGER.debug("get_filtered_entities_for_zone returns: %s", filtered)
    return filtered


async def get_integration_entities(hass):
    """Retrieve main zone sensor entities created by this integration (excludes untracked sensors)."""
    entity_registry = er.async_get(hass)
    integration_entities = {}
    for entity_id, entity in entity_registry.entities.items():
        if not (entity.unique_id and entity.unique_id.startswith(DOMAIN)):
            continue
        # Exclude untracked sensors — only main zone sensors are valid zone targets
        if "_untracked_" in entity_id:
            continue
        state = hass.states.get(entity_id)
        if state and "friendly_name" in state.attributes:
            integration_entities[entity_id] = state.attributes["friendly_name"]
    _LOGGER.debug("get_integration_entities: %s", integration_entities)
    return integration_entities


def get_selected_entities_for_zones(hass, selected_existing_zones, integration_entities, selected_entities, entity_type):
    """Get entities from selected existing zones, avoiding duplicates."""
    _LOGGER.debug(
        "get_selected_entities_for_zones: zones=%s entity_type=%s",
        selected_existing_zones,
        entity_type,
    )
    for zone_id in selected_existing_zones:
        if zone_id in integration_entities:
            zone_entities = get_filtered_entities_for_zone(hass, zone_id)
            if zone_entities:
                selected_entities.extend(zone_entities)
            untracked_entity = f"{zone_id[:-(len(entity_type) + 1)]}_untracked_{entity_type}"
            if hass.states.get(untracked_entity):
                selected_entities.append(untracked_entity)

    unique_selected = sorted(set(selected_entities))
    _LOGGER.debug("get_selected_entities_for_zones returns: %s", unique_selected)
    return unique_selected


async def get_translated_entity_type(hass, entity_type):
    """Return the translated display name for the given entity type (Power / Energy)."""
    user_language = hass.config.language
    translations = await async_get_translations(hass, user_language, "selector", {DOMAIN})
    key = f"component.{DOMAIN}.selector.entity_type.options.{entity_type}"
    result = translations.get(key, entity_type.capitalize())
    _LOGGER.debug("Translated entity type '%s' -> '%s'", entity_type, result)
    return result


def get_selected_smart_meter_devices(hass, filtered_entities):
    """Return the set of smart meter entity IDs already assigned to a zone."""
    _LOGGER.debug("get_selected_smart_meter_devices start")
    old_entities_smd_untracked = [
        e for e in filtered_entities
        if e.startswith(f"sensor.{DOMAIN}") and "_untracked_" in e
    ]
    selected = set()
    for entity in old_entities_smd_untracked:
        state = hass.states.get(entity)
        if state:
            device = state.attributes.get("Selected Smart Meter Device")
            if is_smart_meter_selected(device):
                selected.add(device)
    for entry in hass.config_entries.async_entries(DOMAIN):
        device = entry.data.get(CONF_SMART_METER_DEVICE)
        if is_smart_meter_selected(device):
            selected.add(device)
    _LOGGER.debug("Already assigned smart meter devices: %s", selected)
    return selected


def normalize_smart_meter_selection(user_input):
    """Return the selected smart meter entity ID, or '' if none selected."""
    value = user_input.get(CONF_SMART_METER_DEVICE, "")
    return value if is_smart_meter_selected(value) else ""


def remove_smart_meter_from_entities(selected_smd, selected_entities):
    """Remove the smart meter entity from the selected entities list if present."""
    if selected_smd and selected_smd in selected_entities:
        selected_entities.remove(selected_smd)
    return selected_entities


def get_selected_integration_zones(hass, existing_zones=None, exclude_entry_id=None):
    """Return the set of integration zone entity_ids already assigned to any config entry.

    Integration zones are stored in CONF_INTEGRATION_ROOMS on the config entry, NOT in
    the sensor's selected_entities state attribute (which only holds CONF_ENTITIES).
    We therefore read directly from config entry data here.

    exclude_entry_id: when called from the options flow, pass the current entry's ID so
    a zone is not considered taken by itself and remains visible in its own picker.
    """
    assigned = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == exclude_entry_id:
            continue
        for zone_id in entry.data.get(CONF_INTEGRATION_ROOMS, []):
            assigned.add(zone_id)
    _LOGGER.debug("Already assigned integration zones: %s", assigned)
    return assigned


def build_existing_zones_for_gui(integration_entities):
    """Build a {entity_id: friendly_name} dict suitable for zone dropdowns."""
    existing = {
        entity_id: friendly_name
        .replace(" selected entities - Power", "")
        .replace(" selected entities - Energy", "")
        for entity_id, friendly_name in integration_entities.items()
    }
    return dict(sorted(existing.items(), key=lambda item: item[1]))


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------

class EnergyandPowerMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for energy_power_monitor."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            self.selected_type = user_input[CONF_ENTITY_TYPE]
            self.zone_name = user_input[CONF_ROOM]
            return await self.async_step_select_entities()

        data_schema = vol.Schema({
            vol.Required(CONF_ROOM): cv.string,
            vol.Required(CONF_ENTITY_TYPE, default=ENTITY_TYPE_POWER): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": ENTITY_TYPE_ENERGY, "label": ENTITY_TYPE_ENERGY},
                        {"value": ENTITY_TYPE_POWER, "label": ENTITY_TYPE_POWER},
                    ],
                    translation_key="entity_type",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_select_entities(self, user_input=None):
        errors = {}

        # Gather all sensor entities of the right type
        all_entities = self.hass.states.async_entity_ids("sensor")
        if self.selected_type == ENTITY_TYPE_POWER:
            filtered_entities = [e for e in all_entities if e.endswith("_power")]
        else:
            filtered_entities = [e for e in all_entities if e.endswith("_energy")]

        selected_smart_meter_devices = get_selected_smart_meter_devices(self.hass, filtered_entities)
        # Strip integration-owned entities and already-used entities
        filtered_entities = [e for e in filtered_entities if not e.startswith(f"sensor.{DOMAIN}")]
        existing_entities_in_zones = set()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            existing_entities_in_zones.update(entry.data.get(CONF_ENTITIES, []))
        filtered_entities = sorted([
            e for e in filtered_entities
            if e not in existing_entities_in_zones and e not in selected_smart_meter_devices
        ])
        _LOGGER.debug("Filtered entities for new zone: %s", filtered_entities)

        integration_entities = await get_integration_entities(self.hass)

        if user_input is not None:
            selected_entities = list(user_input.get(CONF_ENTITIES, []))
            selected_existing_zones = list(user_input.get(CONF_INTEGRATION_ROOMS, []))
            selected_entities = get_selected_entities_for_zones(
                self.hass,
                selected_existing_zones,
                integration_entities,
                selected_entities,
                self.selected_type,
            )
            selected_smd = normalize_smart_meter_selection(user_input)
            selected_entities = remove_smart_meter_from_entities(selected_smd, selected_entities)
            translated_entity_type = await get_translated_entity_type(self.hass, self.selected_type)
            _LOGGER.info("Creating entry: entities=%s entity_type=%s", selected_entities, translated_entity_type)
            return self.async_create_entry(
                title=f"{translated_entity_type} - {self.zone_name}",
                data={
                    CONF_ROOM: self.zone_name,
                    CONF_SMART_METER_DEVICE: selected_smd,
                    CONF_ENTITY_TYPE: self.selected_type,
                    CONF_ENTITIES: selected_entities,
                    CONF_INTEGRATION_ROOMS: selected_existing_zones,
                },
            )

        existing_zones = build_existing_zones_for_gui(integration_entities)
        assigned_integration_zones = get_selected_integration_zones(self.hass)
        filtered_existing_zones = {
            eid: name
            for eid, name in existing_zones.items()
            if eid not in assigned_integration_zones
        }

        entity_options = build_entity_options(self.hass, filtered_entities)
        smart_meter_options = list({o["value"]: o for o in entity_options}.values())

        data_schema = vol.Schema({
            vol.Optional(CONF_SMART_METER_DEVICE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=smart_meter_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_ENTITIES, default=[]): vol.All(
                cv.multi_select(build_entity_label_map(self.hass, filtered_entities))
            ),
            vol.Optional(CONF_INTEGRATION_ROOMS, default=[]): vol.All(
                cv.multi_select(filtered_existing_zones)
            ),
        })
        return self.async_show_form(
            step_id="select_entities", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow."""
        return EnergyandPowerMonitorOptionsFlowHandler()


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------

class EnergyandPowerMonitorOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options reconfiguration."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Manage the options."""
        errors = {}
        old_data = self.config_entry.data
        old_zone = old_data.get(CONF_ROOM, "")
        old_entities_smd = old_data.get(CONF_SMART_METER_DEVICE, "")
        old_entities = set(old_data.get(CONF_ENTITIES, []))
        old_integration_zones = old_data.get(CONF_INTEGRATION_ROOMS, [])
        current_zone = old_data.get(CONF_ROOM, "")

        integration_entities = await get_integration_entities(self.hass)

        if user_input is not None:
            try:
                current_entity_type = old_data.get(CONF_ENTITY_TYPE, ENTITY_TYPE_POWER)
                if user_input[CONF_ROOM] != old_zone:
                    _LOGGER.debug("Zone name changed, updating references")
                    await self.update_all_references(old_zone, user_input[CONF_ROOM], current_entity_type)
                    await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                await self.async_remove_old_config(old_zone)
                await self.async_remove_sensor_entities(old_zone)

                selected_entities = list(user_input.get(CONF_ENTITIES, []))
                selected_existing_zones = list(user_input.get(CONF_INTEGRATION_ROOMS, []))
                selected_smd = normalize_smart_meter_selection(user_input)

                selected_entities = get_selected_entities_for_zones(
                    self.hass,
                    selected_existing_zones,
                    integration_entities,
                    selected_entities,
                    current_entity_type,
                )
                selected_entities = remove_smart_meter_from_entities(selected_smd, selected_entities)

                translated_entity_type = await get_translated_entity_type(self.hass, current_entity_type)
                new_options = {
                    CONF_ROOM: user_input[CONF_ROOM],
                    CONF_SMART_METER_DEVICE: selected_smd,
                    CONF_ENTITY_TYPE: current_entity_type,
                    CONF_ENTITIES: selected_entities,
                    CONF_INTEGRATION_ROOMS: selected_existing_zones,
                }
                await self.async_create_new_config(new_options, translated_entity_type)
                return self.async_create_entry(
                    title=f"{translated_entity_type} - {new_options[CONF_ROOM]}",
                    data=new_options,
                )
            except Exception as ex:
                _LOGGER.exception("Unexpected exception during options update: %s", ex)
                errors["base"] = "unknown"

        # Build the form
        existing_zones = build_existing_zones_for_gui(integration_entities)
        # Remove the current zone from zone picker so it can't be a sub-zone of itself
        if current_zone:
            existing_zones = {k: v for k, v in existing_zones.items() if v != current_zone}

        filtered_old_entities = {e for e in old_entities if not e.startswith(f"sensor.{DOMAIN}")}
        old_integration_entities = {e for e in old_entities if e.startswith(f"sensor.{DOMAIN}")}

        # Rebuild which old integration zones are still active
        filtered_old_integration_zones = []
        for entity_id in old_integration_zones:
            friendly_name = existing_zones.get(entity_id, "").strip()
            if friendly_name:
                filtered_old_integration_zones.append(friendly_name)

        all_entities = self.hass.states.async_entity_ids("sensor")
        base_entity_id = f"sensor.{DOMAIN}_{sanitize_zone_name(current_zone)}"
        entity_id = None
        if self.hass.states.get(f"{base_entity_id}_power"):
            entity_id = f"{base_entity_id}_power"
        if self.hass.states.get(f"{base_entity_id}_energy"):
            entity_id = f"{base_entity_id}_energy"

        device_class = None
        if entity_id and self.hass.states.get(entity_id):
            device_class = self.hass.states.get(entity_id).attributes.get("device_class", ENTITY_TYPE_POWER)

        if device_class == ENTITY_TYPE_POWER:
            filtered_entities = [e for e in all_entities if e.endswith("_power")]
        elif device_class == ENTITY_TYPE_ENERGY:
            filtered_entities = [e for e in all_entities if e.endswith("_energy")]
        else:
            filtered_entities = [e for e in all_entities if e.endswith("_power") or e.endswith("_energy")]

        selected_smart_meter_devices = get_selected_smart_meter_devices(self.hass, filtered_entities)
        filtered_entities = [e for e in filtered_entities if not e.startswith(f"sensor.{DOMAIN}")]

        existing_zones_for_gui = {name: eid for eid, name in existing_zones.items()}
        selected_integration_zones = [
            existing_zones_for_gui[name]
            for name in filtered_old_integration_zones
            if name in existing_zones_for_gui
        ]

        assigned_integration_zones = get_selected_integration_zones(self.hass, exclude_entry_id=self.config_entry.entry_id)
        filtered_existing_zones = {
            eid: name
            for eid, name in existing_zones.items()
            if eid not in assigned_integration_zones
        }

        existing_entities_in_zones = set()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            existing_entities_in_zones.update(entry.data.get(CONF_ENTITIES, []))

        filtered_entities = sorted(
            e for e in filtered_entities
            if e not in existing_entities_in_zones and e not in selected_smart_meter_devices
        )
        filtered_entities = sorted(set(filtered_entities))
        combined_entities = sorted(
            set(filtered_entities) | filtered_old_entities | old_integration_entities
        )
        _LOGGER.debug("Combined entities for options form: %s", combined_entities)

        # Pre-select existing smart meter if valid
        if is_smart_meter_selected(old_entities_smd):
            smd_schema_field = vol.Optional(CONF_SMART_METER_DEVICE, default=old_entities_smd)
        else:
            smd_schema_field = vol.Optional(CONF_SMART_METER_DEVICE)

        # Smart meter options: available filtered entities + current smd re-inserted if set
        smart_meter_pool = sorted(set(filtered_entities))
        if is_smart_meter_selected(old_entities_smd) and old_entities_smd not in smart_meter_pool:
            smart_meter_pool.insert(0, old_entities_smd)
        smart_meter_option_list = build_entity_options(self.hass, smart_meter_pool)
        smart_meter_option_list = list({o["value"]: o for o in smart_meter_option_list}.values())

        # Combined entity list: filtered available + previously selected (so existing picks stay visible)
        combined_entities = sorted(
            set(filtered_entities) | filtered_old_entities | old_integration_entities
        )
        # Remove smart meter from entity picker to avoid dual-selection
        if is_smart_meter_selected(old_entities_smd):
            combined_entities = [e for e in combined_entities if e != old_entities_smd]

        options_schema = vol.Schema({
            vol.Required(CONF_ROOM, default=old_zone): cv.string,
            smd_schema_field: selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=smart_meter_option_list,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_ENTITIES, default=list(old_entities)): vol.All(
                cv.multi_select(build_entity_label_map(self.hass, combined_entities))
            ),
            vol.Optional(CONF_INTEGRATION_ROOMS, default=selected_integration_zones): vol.All(
                cv.multi_select(filtered_existing_zones)
            ),
        })
        return self.async_show_form(step_id="user", data_schema=options_schema, errors=errors)

    async def update_all_references(self, old_zone: str, new_zone: str, current_entity_type: str):
        """Update references to old_zone in all other config entries after a rename."""
        sanitized_old = sanitize_zone_name(old_zone)
        sanitized_new = sanitize_zone_name(new_zone)
        old_main_id = f"sensor.{DOMAIN}_{sanitized_old}_{current_entity_type}"
        new_main_id = f"sensor.{DOMAIN}_{sanitized_new}_{current_entity_type}"
        old_smart_prefix = f"sensor.{DOMAIN}_{sanitized_old}_untracked_"
        new_smart_prefix = f"sensor.{DOMAIN}_{sanitized_new}_untracked_"

        _LOGGER.debug("update_all_references: %s -> %s", old_main_id, new_main_id)
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id == self.config_entry.entry_id:
                continue
            data = dict(entry.data)
            updated = False

            if CONF_INTEGRATION_ROOMS in data:
                new_zones = [
                    new_main_id if z == old_main_id else z
                    for z in data[CONF_INTEGRATION_ROOMS]
                ]
                if new_zones != data[CONF_INTEGRATION_ROOMS]:
                    data[CONF_INTEGRATION_ROOMS] = new_zones
                    updated = True

            if CONF_ENTITIES in data:
                new_ents = []
                for ent in data[CONF_ENTITIES]:
                    if ent == old_main_id:
                        new_ents.append(new_main_id)
                        updated = True
                    elif ent.startswith(old_smart_prefix):
                        new_ents.append(new_smart_prefix + ent[len(old_smart_prefix):])
                        updated = True
                    else:
                        new_ents.append(ent)
                data[CONF_ENTITIES] = new_ents

            if updated:
                zone_name = entry.data.get(CONF_ROOM, "unknown")
                _LOGGER.debug("Updating references in zone '%s'", zone_name)
                self.hass.config_entries.async_update_entry(entry, data=data)
        _LOGGER.debug("Completed update_all_references")

    async def async_remove_old_config(self, old_zone: str):
        """Remove the old sensor configuration."""
        _LOGGER.info("Removing old configuration for zone: %s", old_zone)
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get(CONF_ROOM) == old_zone:
                sensor_data = self.hass.data.get(f"{DOMAIN}_config", {}).get(entry.entry_id, {})
                for sensor in sensor_data.get("sensors", []):
                    if hasattr(sensor, "async_remove_sensor_entities"):
                        await sensor.async_remove_sensor_entities(old_zone)

    async def async_create_new_config(self, options: dict, translated_entity_type: str):
        """Persist updated options and reload the entry."""
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            title=f"{translated_entity_type} - {options[CONF_ROOM]}",
            data=options,
        )
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)

    async def async_remove_sensor_entities(self, zone_name: str):
        """Remove all sensor entities associated with the old zone name."""
        entity_registry = er.async_get(self.hass)
        current_entity_type = self.config_entry.data.get(CONF_ENTITY_TYPE)
        sanitized = sanitize_zone_name(zone_name)
        entity_id_se = f"sensor.{DOMAIN}_{sanitized}_{current_entity_type}"
        entity_id_cr = f"sensor.{DOMAIN}_{sanitized}_untracked_{current_entity_type}"
        _LOGGER.info("Attempting to remove entities: %s and %s", entity_id_se, entity_id_cr)
        for eid in (entity_id_se, entity_id_cr):
            if eid in entity_registry.entities:
                _LOGGER.info("Removing from entity registry: %s", eid)
                entity_registry.async_remove(eid)
            if self.hass.states.get(eid):
                _LOGGER.info("Removing entity state: %s", eid)
                self.hass.states.async_remove(eid)
                