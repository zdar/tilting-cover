"""Data coordinator for Tilting Cover integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
from .storage import TiltingCoverStorage

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=30)


class TiltingCoverDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Tilting Cover integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        store: Store,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        
        self._entry_id = entry_id
        self._store = store
        self._storage_handlers: dict[str, TiltingCoverStorage] = {}
        
        # Data storage for entities
        self.data: dict[str, Any] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # This coordinator primarily manages data persistence
            # Individual entities manage their own state updates
            return self.data
        except Exception as err:
            _LOGGER.warning("Error during data update: %s", err)
            # Don't raise UpdateFailed for this coordinator as it's not critical
            return self.data

    def get_storage_handler(self, entity_id: str) -> TiltingCoverStorage:
        """Get or create a storage handler for an entity."""
        if entity_id not in self._storage_handlers:
            try:
                self._storage_handlers[entity_id] = TiltingCoverStorage(
                    self.hass, self._store, entity_id
                )
                _LOGGER.info("Created storage handler for entity %s with store key %s", 
                           entity_id, self._store.key)
                
                # CRITICAL FIX: Initialize storage immediately when handler is created
                # Since async methods can't be called from sync context, 
                # the entity must call async_load() in its async_added_to_hass()
                
            except Exception as err:
                _LOGGER.error("Failed to create storage handler for %s: %s", entity_id, err)
                raise HomeAssistantError(f"Storage handler creation failed for {entity_id}") from err
                
        return self._storage_handlers[entity_id]

    async def async_initialize_storage(self) -> None:
        """Initialize storage for all handlers."""
        try:
            for entity_id, handler in self._storage_handlers.items():
                try:
                    await handler.async_load()
                    _LOGGER.debug("Initialized storage for entity %s", entity_id)
                except Exception as err:
                    _LOGGER.warning("Failed to initialize storage for %s: %s", entity_id, err)
                    # Continue with other handlers
        except Exception as err:
            _LOGGER.error("Error during storage initialization: %s", err)
            # Don't raise - let entities handle their own storage failures

    async def async_save_data(self) -> None:
        """Save all data to storage."""
        # Save the coordinator's data store
        if self.data:
            try:
                existing_data = await self._store.async_load() or {}
                existing_data.update(self.data)
                await self._store.async_save(existing_data)
                _LOGGER.debug("Coordinator data saved successfully")
            except Exception as err:
                _LOGGER.error("Error saving coordinator data: %s", err)

        # Save individual storage handlers
        save_tasks = []
        for entity_id, handler in self._storage_handlers.items():
            try:
                save_tasks.append(handler.async_save())
            except Exception as err:
                _LOGGER.warning("Failed to queue save task for %s: %s", entity_id, err)
                
        if save_tasks:
            try:
                await asyncio.gather(*save_tasks, return_exceptions=True)
                _LOGGER.debug("Storage handlers save tasks completed")
            except Exception as err:
                _LOGGER.error("Error saving storage handlers: %s", err)

    async def async_request_refresh(self) -> None:
        """Request a refresh and save data."""
        await self.async_save_data()
        await super().async_request_refresh()