import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Set up the component
async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the energy_power_monitor component."""
    hass.data.setdefault(DOMAIN, {"rooms": []})
    return True

# Handle the setup of the config entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a config entry for Energy and Power Monitor."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    _LOGGER.debug(f"Setting up Energy and Power Monitor for entry_id: {entry.title}")

    # Set up the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True
    
# Handle unloading of the config entry
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle unloading of an entry."""
    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    _LOGGER.debug(f"Unloading Energy and Power Monitor for entry_id: {entry.title}")

    # Unload the sensor platform (fix: pass string, not list)
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    return True


# Handle removal of the config entry
async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Remove a config entry."""
    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    _LOGGER.debug(f"Removing Energy and Power Monitor for entry_id: {entry.title}")

    return True
