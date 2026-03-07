"""Storage utilities for Tilting Cover integration."""
from __future__ import annotations

import logging
from typing import Any
from datetime import datetime, timezone

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import (
    DEFAULT_STORED_POSITION,
    DEFAULT_STORED_TILT,
    DEFAULT_STORED_TIMESTAMP,
    STORAGE_COVER_POSITION,
    STORAGE_ENTITY_STATE,
    STORAGE_LAST_KNOWN_POSITION,
    STORAGE_TILT_POSITION,
    STORAGE_TIMESTAMP,
)

_LOGGER = logging.getLogger(__name__)


class TiltingCoverStorage:
    """Handle persistent storage for tilting cover state."""

    def __init__(self, hass: HomeAssistant, store: Store, entity_id: str) -> None:
        """Initialize the storage handler."""
        self._hass = hass
        self._store = store
        self._entity_id = entity_id
        self._data: dict[str, Any] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Load data from storage."""
        if self._loaded:
            return
            
        try:
            stored_data = await self._store.async_load()
            if stored_data is not None and isinstance(stored_data, dict):
                self._data = stored_data.get(self._entity_id, {})
                _LOGGER.debug(
                    "Loaded storage data for %s: %s", self._entity_id, self._data
                )
            else:
                self._data = {}
                _LOGGER.debug("No existing storage data found for %s", self._entity_id)
            self._loaded = True
        except Exception as err:
            _LOGGER.error("Error loading storage data for %s: %s", self._entity_id, err)
            self._data = {}
            self._loaded = False
            # Don't raise - allow entity to continue with default values

    async def async_save(self) -> None:
        """Save data to storage."""
        if not self._loaded:
            _LOGGER.warning("Attempting to save before loading for %s", self._entity_id)
            return
            
        try:
            # Load existing data first to preserve other entities
            existing_data = await self._store.async_load() or {}
            if not isinstance(existing_data, dict):
                existing_data = {}
                
            existing_data[self._entity_id] = self._data
            await self._store.async_save(existing_data)
            _LOGGER.debug(
                "Saved storage data for %s: %s", self._entity_id, self._data
            )
        except Exception as err:
            _LOGGER.error("Error saving storage data for %s: %s", self._entity_id, err)
            # Don't raise - this is not critical for entity functionality

    def get_tilt_position(self) -> int:
        """Get the stored tilt position."""
        return self._data.get(STORAGE_TILT_POSITION, DEFAULT_STORED_TILT)

    async def async_set_tilt_position(self, position: int) -> None:
        """Set and save the tilt position."""
        self._data[STORAGE_TILT_POSITION] = position
        await self.async_save()

    def get_cover_position(self) -> int:
        """Get the stored cover position."""
        # Check new key first, fallback to old key for backward compatibility
        return self._data.get(
            STORAGE_COVER_POSITION, 
            self._data.get(STORAGE_LAST_KNOWN_POSITION, DEFAULT_STORED_POSITION)
        )

    async def async_set_cover_position(self, position: int) -> None:
        """Set and save the cover position."""
        self._data[STORAGE_COVER_POSITION] = position
        await self.async_save()

    def get_timestamp(self) -> datetime | None:
        """Get the stored timestamp for position/tilt data."""
        timestamp_str = self._data.get(STORAGE_TIMESTAMP, DEFAULT_STORED_TIMESTAMP)
        if timestamp_str is None:
            return None
        try:
            return datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Invalid timestamp format for %s: %s", self._entity_id, err)
            return None

    async def async_set_timestamp(self, timestamp: datetime | None = None) -> None:
        """Set and save the timestamp for position/tilt data."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        self._data[STORAGE_TIMESTAMP] = timestamp.isoformat()
        await self.async_save()

    async def async_set_position_tilt_pair(
        self, cover_position: int, tilt_position: int, timestamp: datetime | None = None
    ) -> None:
        """Set and save both positions with timestamp as atomic operation."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        updates = {
            STORAGE_COVER_POSITION: cover_position,
            STORAGE_TILT_POSITION: tilt_position,
            STORAGE_TIMESTAMP: timestamp.isoformat(),
        }
        await self.async_update_batch(updates)

    async def async_update_batch(self, updates: dict[str, Any]) -> None:
        """Update multiple data fields in a single operation and save."""
        if not self._loaded:
            _LOGGER.warning("Attempting to update before loading for %s", self._entity_id)
            return
            
        self._data.update(updates)
        await self.async_save()

    def get_position_tilt_pair(self) -> tuple[int, int, datetime | None]:
        """Get the stored position/tilt pair with timestamp."""
        cover_pos = self.get_cover_position()
        tilt_pos = self.get_tilt_position()
        timestamp = self.get_timestamp()
        return cover_pos, tilt_pos, timestamp

    def get_last_known_position(self) -> int:
        """Get the last known cover position (deprecated, use get_cover_position)."""
        return self.get_cover_position()

    async def async_set_last_known_position(self, position: int) -> None:
        """Set and save the last known cover position (deprecated, use async_set_cover_position)."""
        await self.async_set_cover_position(position)

    def get_entity_state(self) -> dict[str, Any]:
        """Get stored entity state data."""
        return self._data.get(STORAGE_ENTITY_STATE, {})

    async def async_set_entity_state(self, state_data: dict[str, Any]) -> None:
        """Set and save entity state data."""
        self._data[STORAGE_ENTITY_STATE] = state_data
        await self.async_save()

    async def async_update_entity_state(self, updates: dict[str, Any]) -> None:
        """Update entity state data with partial updates."""
        current_state = self.get_entity_state()
        current_state.update(updates)
        await self.async_set_entity_state(current_state)

    def has_data(self) -> bool:
        """Check if storage has any data."""
        return bool(self._data and self._loaded)

    def is_loaded(self) -> bool:
        """Check if storage has been loaded."""
        return self._loaded

    async def async_clear(self) -> None:
        """Clear all stored data."""
        if not self._loaded:
            return
            
        self._data.clear()
        await self.async_save()