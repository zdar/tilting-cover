"""The Tilting Cover integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
from .coordinator import TiltingCoverDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["cover"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tilting Cover from a config entry."""
    try:
        hass.data.setdefault(DOMAIN, {})
        
        # Create storage
        store = Store(
            hass, 
            STORAGE_VERSION, 
            f"{STORAGE_KEY}_{entry.entry_id}",
            atomic_writes=True
        )
        
        # Create coordinator
        coordinator = TiltingCoverDataUpdateCoordinator(
            hass, entry.entry_id, store
        )
        
        # Initialize coordinator
        await coordinator.async_config_entry_first_refresh()
        await coordinator.async_initialize_storage()
        
        # Store coordinator
        hass.data[entry.entry_id] = coordinator
        
        # Set up platforms 
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        # Register cleanup on HA stop
        async def _async_stop_handler(_event: Any) -> None:
            """Handle Home Assistant stop event."""
            await coordinator.async_save_data()
            
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_handler)
        )
        
        _LOGGER.debug("Tilting Cover integration setup completed for entry %s", entry.entry_id)
        return True
        
    except Exception as err:
        _LOGGER.exception("Failed to set up Tilting Cover integration: %s", err)
        raise ConfigEntryNotReady(f"Failed to set up integration: {err}") from err


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        # Unload platforms
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        
        if unload_ok:
            # Save final data before cleanup
            coordinator = hass.data.get(entry.entry_id)
            if coordinator:
                try:
                    await coordinator.async_save_data()
                    _LOGGER.debug("Saved final data before unload")
                except Exception as err:
                    _LOGGER.warning("Failed to save final data during unload: %s", err)
                    # Don't fail unload for this
            
            # Clean up
            hass.data.pop(entry.entry_id, None)
            _LOGGER.debug("Tilting Cover integration unloaded for entry %s", entry.entry_id)
        else:
            _LOGGER.warning("Failed to unload platforms for entry %s", entry.entry_id)
            
        return unload_ok
        
    except Exception as err:
        _LOGGER.exception("Error during unload of entry %s: %s", entry.entry_id, err)
        return False