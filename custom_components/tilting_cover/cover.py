"""Tilting Cover implementation with decoupled architecture."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_COVER_ENTITY_ID,
    CONF_TRAVEL_TIME, 
    CONF_SLAT_ROTATION_TIME,
    DEFAULT_TRAVEL_TIME,
    DEFAULT_SLAT_ROTATION_TIME,
)
from .config_flow import (
    CONF_ORIGINAL_AREA_ID,
    CONF_ORIGINAL_ICON,
    CONF_ORIGINAL_ENTITY_CATEGORY,
)
from .coordinator import TiltingCoverDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tilting Cover from a config entry."""
    coordinator = hass.data[entry.entry_id]
    
    config = entry.data
    cover_entity_id = config[CONF_COVER_ENTITY_ID]
    travel_time = config.get(CONF_TRAVEL_TIME, DEFAULT_TRAVEL_TIME)
    slat_rotation_time = config.get(CONF_SLAT_ROTATION_TIME, DEFAULT_SLAT_ROTATION_TIME)
    
    entity = TiltingCover(
        coordinator,
        cover_entity_id,
        travel_time,
        slat_rotation_time,
        entry,
    )
    
    async_add_entities([entity])


class TiltingCover(CoverEntity, RestoreEntity):
    """Tilting Cover entity with decoupled architecture."""
    
    def __init__(
        self,
        coordinator: TiltingCoverDataUpdateCoordinator,
        cover_entity_id: str,
        travel_time: int,
        slat_rotation_time: int,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the Tilting Cover."""
        self._coordinator = coordinator
        self._cover_entity_id = cover_entity_id
        self._travel_time = travel_time
        self._slat_rotation_time = slat_rotation_time
        self._config_entry = config_entry
        self._entry_id = config_entry.entry_id
        
        # Cover entity state
        self._current_cover_position: int | None = None
        self._current_tilt_position: int | None = None
        self._underlying_cover_state: str | None = None
        self._underlying_cover_position: int | None = None
        
        # Independent Position Tracking System - Decoupled architecture baseline
        self._last_stored_position: int | None = None
        self._last_stored_tilt: int | None = None
        self._last_stored_underlying_position: int | None = None
        
        # Command Queue System - Decoupled architecture command state
        self._command_queue: list[dict] = []
        self._current_command: dict | None = None
        self._command_in_progress: bool = False
        
        # Persistent data store
        self._data_store = coordinator.data
        
        # Storage handler - proper abstraction layer
        self._storage = coordinator.get_storage_handler(self.unique_id)
        
        # Event listener cleanup
        self._unsub_state_listener = None

    @property 
    def name(self) -> str:
        """Return the name of the entity."""
        # Use the configured name from config entry
        return self._config_entry.data.get("name", f"Tilting {self._cover_entity_id.split('.')[-1]}")

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"tilting_cover_{self._entry_id}"
    
    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend."""
        # Use inherited icon if available, otherwise default
        return self._config_entry.data.get("original_icon") or "mdi:blinds"
    
    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the entity category."""
        # Inherit entity category if available
        category = self._config_entry.data.get("original_entity_category")
        if category and hasattr(EntityCategory, category.upper()):
            return getattr(EntityCategory, category.upper())
        return None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={("tilting_cover", self._entry_id)},
            name=self.name,
            manufacturer="Tilting Cover Integration",
            model="Enhanced Cover",
            sw_version="0.8.0",
            configuration_url=f"https://github.com/zdar/tilting-cover",
        )

    @property
    def device_class(self) -> CoverDeviceClass:
        """Return the device class."""
        return CoverDeviceClass.BLIND

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.SET_TILT_POSITION
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        return self._current_cover_position

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        return self._current_tilt_position

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._current_cover_position is None:
            return None
        return self._current_cover_position == 0

    @property
    def is_open(self) -> bool | None:
        """Return if the cover is open."""
        if self._current_cover_position is None:
            return None
        return self._current_cover_position == 100

    @property
    def state(self) -> str | None:
        """Return the current state of the cover."""
        if self._underlying_cover_state:
            return self._underlying_cover_state
        
        # Fallback state based on position if underlying state unavailable
        if self._current_cover_position is None:
            return None
        elif self._current_cover_position == 0:
            return STATE_CLOSED
        elif self._current_cover_position == 100:
            return STATE_OPEN
        else:
            return STATE_OPEN  # Partially open

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        _LOGGER.info("%s: Starting initialization - entity_id=%s, unique_id=%s", 
                    self.entity_id, self.entity_id, self.unique_id)
        
        try:
            # Initialize storage handler
            await self._storage.async_load()
            _LOGGER.info("%s: Storage initialized - loaded=%s, has_data=%s", 
                        self.entity_id, self._storage.is_loaded(), self._storage.has_data())
            
            # Apply inherited metadata 
            await self._apply_inherited_metadata()
            
            # Restore state from proper storage abstraction
            if self._storage.has_data():
                cover_pos, tilt_pos, _ = self._storage.get_position_tilt_pair()
                self._current_cover_position = cover_pos
                self._current_tilt_position = tilt_pos
                
            # Sync with underlying cover
            await self._sync_with_underlying_cover()
            
            # Subscribe to underlying cover state changes
            self._unsub_state_listener = async_track_state_change_event(
                self.hass, [self._cover_entity_id], self._handle_underlying_state_change
            )
            
            _LOGGER.info("%s: Initialized with position=%s%%, tilt=%s%%",
                          self.entity_id, self._current_cover_position, self._current_tilt_position)
            
            # TEST: Force initial save to verify storage works
            await self._save_state_to_storage()
            _LOGGER.info("%s: Completed initial save test", self.entity_id)
                          
        except Exception as err:
            _LOGGER.error("%s: Error during setup: %s", self.entity_id, err)
            raise HomeAssistantError(f"Failed to set up {self.entity_id}") from err

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        try:
            if self._unsub_state_listener:
                self._unsub_state_listener()
                self._unsub_state_listener = None
                
            # Save final state using proper storage abstraction
            await self._save_state_to_storage()
            _LOGGER.debug("%s: Cleanup completed", self.entity_id)
        except Exception as err:
            _LOGGER.warning("%s: Error during cleanup: %s", self.entity_id, err)

    async def _apply_inherited_metadata(self) -> None:
        """Apply inherited metadata from config entry to entity registry."""
        try:
            from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
            
            entity_registry = async_get_entity_registry(self.hass)
            
            # Get inherited area ID
            area_id = self._config_entry.data.get(CONF_ORIGINAL_AREA_ID)
            if area_id:
                # Update entity registry with inherited area
                entity_registry.async_update_entity(
                    self.entity_id,
                    area_id=area_id
                )
                _LOGGER.debug("%s: Applied inherited area_id: %s", self.entity_id, area_id)
                
        except Exception as err:
            _LOGGER.warning("%s: Failed to apply inherited metadata: %s", self.entity_id, err)
            # Don't raise - this is not critical for functionality

    def _handle_underlying_state_change(self, event) -> None:
        """Handle underlying cover state change."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if not new_state:
            return
        
        # Schedule async processing
        self.hass.async_create_task(self._async_handle_underlying_state_change(new_state, old_state))
    
    async def _async_handle_underlying_state_change(self, new_state, old_state) -> None:
        """Async handler for underlying cover state change."""
        # Update underlying cover state and position
        self._underlying_cover_state = new_state.state
        position_attr = new_state.attributes.get(ATTR_POSITION)
        if position_attr is not None:
            old_underlying_position = self._underlying_cover_position
            self._underlying_cover_position = int(position_attr)
            
            # Detect movement start/stop and process position tracking
            if old_state and old_state.state != new_state.state:
                if new_state.state in [STATE_OPENING, STATE_CLOSING]:
                    await self._handle_movement_start_detected(new_state.state)
                elif new_state.state in [STATE_OPEN, STATE_CLOSED]:
                    await self._handle_movement_stop_detected(new_state.state)
            elif old_underlying_position != self._underlying_cover_position:
                # CRITICAL: Always calculate positions during underlying movement for real-time reporting
                position_result = await self._calculate_position_from_underlying_change(
                    self._underlying_cover_position
                )
                if position_result:
                    self._current_cover_position = position_result["position"]
                    self._current_tilt_position = position_result["tilt"]
                    _LOGGER.debug("%s: Real-time position update - pos=%s%%, tilt=%s%% (underlying=%s%%)",
                                  self.entity_id, self._current_cover_position, 
                                  self._current_tilt_position, self._underlying_cover_position)
                
                # CRITICAL: Sync with definitive positions (0% or 100%) regardless of state
                await self._sync_definitive_positions(self._underlying_cover_position)
        
        self.async_write_ha_state()

    # Independent Position Tracking System - Core algorithm
    async def _calculate_position_from_underlying_change(self, new_underlying_position: int) -> dict | None:
        """Calculate position and tilt from underlying entity change using core algorithm."""
        
        # Get stored baseline positions for calculation
        baseline_position = self._last_stored_position or 0
        baseline_tilt = self._last_stored_tilt or 0
        baseline_underlying = self._last_stored_underlying_position or 0
        
        # Calculate underlying entity movement
        underlying_diff = abs(new_underlying_position - baseline_underlying)
        
        if underlying_diff == 0:
            return {"position": baseline_position, "tilt": baseline_tilt}
        
        # Determine movement direction and targets
        direction = "opening" if new_underlying_position > baseline_underlying else "closing"
        
        # Get command targets if command is active, otherwise use natural targets
        if self._current_command and self._command_in_progress:
            target_position = self._current_command.get("target_position", baseline_position)
            target_tilt = self._current_command.get("target_tilt", baseline_tilt)
        else:
            # NO ACTIVE COMMAND: Calculate natural movement based on direction
            if direction == "opening":
                # Natural opening: move toward 100% position and tilt
                target_position = 100
                target_tilt = 100
            else:
                # Natural closing: move toward 0% position and tilt  
                target_position = 0
                target_tilt = 0
        
        position_diff = abs(target_position - baseline_position)
        tilt_diff = abs(target_tilt - baseline_tilt)
        
        # Calculate work distribution ratios based on time configuration
        total_time = self._travel_time
        tilt_time = self._slat_rotation_time
        travel_time = max(total_time - tilt_time, 0.1)
        
        # Work ratios for underlying movement distribution
        tilt_work_ratio = tilt_time / total_time if total_time > 0 else 0.5
        travel_work_ratio = travel_time / total_time if total_time > 0 else 0.5
        
        # SEQUENTIAL LOGIC: SLATS FIRST, THEN MOVEMENT (Algorithm fundamental principle)
        
        # Phase 1: Slat rotation (happens first)
        if tilt_diff > 0:
            underlying_needed_for_tilt = tilt_diff / tilt_work_ratio if tilt_work_ratio > 0 else 0
            
            if underlying_diff <= underlying_needed_for_tilt:
                # Still in Phase 1 - all movement goes to tilt
                tilt_progress = underlying_diff * tilt_work_ratio
                position_progress = 0
            else:
                # Phase 1 complete - tilt finished, remaining goes to position
                tilt_progress = tilt_diff  # Complete tilt change
                remaining_underlying = underlying_diff - underlying_needed_for_tilt
                position_progress = remaining_underlying * travel_work_ratio
        else:
            # No tilt change - all goes to position movement
            tilt_progress = 0
            position_progress = underlying_diff * travel_work_ratio
        
        # Apply changes based on movement direction
        direction = "opening" if target_position > baseline_position else "closing"
        
        # Calculate final positions
        if direction == "opening":
            final_position = baseline_position + min(position_progress, position_diff)
            final_tilt = baseline_tilt + min(tilt_progress, tilt_diff)
        else:
            final_position = baseline_position - min(position_progress, position_diff)
            final_tilt = baseline_tilt - min(tilt_progress, tilt_diff)
        
        # Clamp to valid ranges
        final_position = max(0, min(100, final_position))
        final_tilt = max(0, min(100, final_tilt))
        
        _LOGGER.debug(
            "%s: Position calculation - underlying %s->%s (diff=%s), ratios(tilt=%.2f,travel=%.2f), tilt_progress=%s, pos_progress=%s, result: pos=%s%%, tilt=%s%%",
            self.entity_id, baseline_underlying, new_underlying_position, underlying_diff,
            tilt_work_ratio, travel_work_ratio, tilt_progress, position_progress,
            int(final_position), int(final_tilt)
        )
        
        return {"position": int(final_position), "tilt": int(final_tilt)}

    # Command Queue System - Stage 1/Stage 2 operations
    async def _process_command_queue(self) -> None:
        """Process commands from queue sequentially."""
        if not self._command_queue or self._command_in_progress:
            return
            
        # Get next command
        self._current_command = self._command_queue.pop(0)
        self._command_in_progress = True
        
        _LOGGER.debug("%s: Processing command %s", self.entity_id, self._current_command)
        
        # Execute command based on stage
        stage = self._current_command.get("stage", "stage_1")
        if stage == "stage_1":
            await self._execute_stage_1_command(self._current_command)
        elif stage == "stage_2":
            await self._execute_stage_2_command(self._current_command)
            
        # Continue processing queue after command completes
        await self._process_command_queue()

    async def _execute_stage_1_command(self, command: dict) -> None:
        """Execute Stage 1 command - position movement with natural tilt."""
        target_position = command["target_position"]
        
        # Update baseline for position tracking before command
        self._last_stored_position = self._current_cover_position
        self._last_stored_tilt = self._current_tilt_position
        self._last_stored_underlying_position = self._underlying_cover_position
        
        # Command underlying entity to target position
        await self.hass.services.async_call(
            "cover", "set_cover_position",
            {"entity_id": self._cover_entity_id, "position": target_position}
        )
        
        # Wait for movement to complete
        await asyncio.sleep(0.5)  # Small delay to let movement start
        
        # Wait until underlying entity reaches target or stops
        timeout_count = 0
        max_timeout = self._travel_time * 2  # Safety timeout
        
        while timeout_count < max_timeout:
            if self._underlying_cover_position == target_position:
                break
            if self._underlying_cover_state in [STATE_OPEN, STATE_CLOSED]:
                break
            await asyncio.sleep(1)
            timeout_count += 1
            
        # Calculate final Stage 1 positions using core algorithm
        if self._underlying_cover_position is not None:
            position_result = await self._calculate_position_from_underlying_change(
                self._underlying_cover_position
            )
            if position_result:
                self._current_cover_position = position_result["position"]
                self._current_tilt_position = position_result["tilt"]
        
        # CRITICAL: Update baseline positions for Stage 2
        self._last_stored_position = self._current_cover_position
        self._last_stored_tilt = self._current_tilt_position
        self._last_stored_underlying_position = self._underlying_cover_position
        
        # Mark Stage 1 complete
        self._current_command = None
        self._command_in_progress = False
        
        _LOGGER.debug("%s: Stage 1 command completed - underlying reached %s%%, position tracking calculated results",
                      self.entity_id, self._underlying_cover_position)

    async def _execute_stage_2_command(self, command: dict) -> None:
        """Execute Stage 2 command - precise tilt positioning."""
        target_tilt = command["target_tilt"]
        current_tilt = self._current_tilt_position or 0
        
        # Calculate tilt difference needed
        tilt_diff = target_tilt - current_tilt
        
        if abs(tilt_diff) < 1:  # Already at target
            self._current_command = None
            self._command_in_progress = False
            return
        
        # Use current baseline (should be updated from Stage 1)
        baseline_position = self._last_stored_position or 0
        baseline_tilt = self._last_stored_tilt or 0
        baseline_underlying = self._last_stored_underlying_position or 0
        
        # Calculate work ratios (same as main algorithm)
        total_time = self._travel_time
        tilt_time = self._slat_rotation_time
        
        # CORRECT ratio: how much tilt per underlying movement
        underlying_to_tilt_ratio = total_time / tilt_time if tilt_time > 0 else 1.0
        
        # CRITICAL FIX: Use minimal pulse-like movement for tilt adjustment
        # Instead of large absolute position changes, use small relative adjustments
        min_underlying_pulse = 2.0  # Minimum 2% underlying movement
        underlying_needed = max(abs(tilt_diff) / underlying_to_tilt_ratio, min_underlying_pulse)
        
        # FIXED DIRECTION LOGIC: Consider cover physics
        # During Stage 2, we want tilt adjustment without major cover movement
        # Use small pulse in direction that matches tilt need BUT avoid large cover displacement
        current_underlying = self._underlying_cover_position or baseline_underlying
        
        if tilt_diff > 0:  # Need more tilt (open slats more)
            # Small pulse toward higher underlying for tilt opening
            target_underlying = current_underlying + underlying_needed
        else:  # Need less tilt (close slats more)  
            # Small pulse toward lower underlying for tilt closing
            target_underlying = current_underlying - underlying_needed
        
        # Limit to reasonable range to avoid excessive cover movement
        target_underlying = max(5, min(95, target_underlying))
        
        # Additional safety: If target would cause major cover position change, reduce it
        position_impact = abs(target_underlying - current_underlying) * (1.0 / underlying_to_tilt_ratio)
        if position_impact > 5:  # More than 5% cover movement
            _LOGGER.warning("%s: Stage 2 would cause %s%% cover movement, reducing pulse",
                           self.entity_id, position_impact)
            underlying_needed = min(underlying_needed, 3.0)  # Limit to 3% max
            if tilt_diff > 0:
                target_underlying = current_underlying + underlying_needed
            else:
                target_underlying = current_underlying - underlying_needed
        
        # Command underlying entity (position tracking will calculate results)
        self._command_in_progress = True
        await self.hass.services.async_call(
            "cover", "set_cover_position",
            {"entity_id": self._cover_entity_id, "position": target_underlying}
        )
        
        # Wait for movement to complete (shorter timeout for tilt adjustment)
        await asyncio.sleep(0.3)  # Small delay to let movement start
        
        # Wait until underlying entity stops (shorter timeout for tilt-only)
        timeout_count = 0
        max_timeout = tilt_time + 5  # Tilt time + safety margin
        
        while timeout_count < max_timeout:
            if self._underlying_cover_state in [STATE_OPEN, STATE_CLOSED]:
                break
            await asyncio.sleep(0.5)
            timeout_count += 0.5
            
        # Mark Stage 2 complete
        self._current_command = None
        self._command_in_progress = False
        
        _LOGGER.info("%s: Stage 2 completed - tilt_diff=%s%%, pulse=%s%%, final_underlying=%s%%, final_tilt=%s%%",
                     self.entity_id, tilt_diff, underlying_needed, 
                     self._underlying_cover_position, self._current_tilt_position)

    # Movement Detection System - External movement handling
    async def _handle_movement_start_detected(self, new_state: str) -> None:
        """Detect external movement start - inject fake command to maintain position tracking."""
        if self._command_in_progress:
            # This is our own command - no action needed
            return
        
        # External movement detected - inject fake command for position tracking
        direction = "opening" if new_state == STATE_OPENING else "closing"
        
        # Determine fake target based on direction
        fake_target_position = 100 if direction == "opening" else 0
        fake_target_tilt = 100 if direction == "opening" else 0
        
        # Inject fake command to enable position tracking
        fake_command = {
            "type": "external_movement",
            "target_position": fake_target_position,
            "target_tilt": fake_target_tilt,
            "stage": "stage_1",
            "is_fake": True
        }
        
        # Set fake command as current command and mark as in progress
        self._current_command = fake_command
        self._command_in_progress = True
        
        # Update baseline for position tracking
        self._last_stored_position = self._current_cover_position
        self._last_stored_tilt = self._current_tilt_position
        self._last_stored_underlying_position = self._underlying_cover_position
        
        _LOGGER.debug("%s: External movement detected (%s) - fake command injected for position tracking",
                      self.entity_id, direction)
        
    async def _handle_movement_stop_detected(self, final_state: str) -> None:
        """Detect external movement stop - update final positions using core algorithm."""
        if not self._current_command or not self._command_in_progress:
            return
        
        # Calculate final position using core position algorithm
        if self._underlying_cover_position is not None:
            position_result = await self._calculate_position_from_underlying_change(
                self._underlying_cover_position
            )
            if position_result:
                self._current_cover_position = position_result["position"]
                self._current_tilt_position = position_result["tilt"]
        
        # Clear fake command
        self._current_command = None
        self._command_in_progress = False
        
        # Handle definitive positions synchronization with disagreement detection
        if final_state == STATE_CLOSED:
            # Check for disagreement before forcing state
            if (self._current_cover_position is not None and 
                self._current_tilt_position is not None):
                pos_diff = abs(self._current_cover_position - 0)
                tilt_diff = abs(self._current_tilt_position - 0)
                
                if pos_diff > 15 or tilt_diff > 15:
                    _LOGGER.warning(
                        "%s: Movement stop disagreement for STATE_CLOSED - expected (0%%, 0%%) but calculated (%s%%, %s%%) - check travel_time=%ss slat_rotation_time=%ss",
                        self.entity_id, self._current_cover_position, 
                        self._current_tilt_position, self._travel_time, self._slat_rotation_time
                    )
            
            self._current_cover_position = 0
            self._current_tilt_position = 0
        elif final_state == STATE_OPEN:
            # Check for disagreement before forcing state
            if (self._current_cover_position is not None and 
                self._current_tilt_position is not None):
                pos_diff = abs(self._current_cover_position - 100)
                tilt_diff = abs(self._current_tilt_position - 100)
                
                if pos_diff > 15 or tilt_diff > 15:
                    _LOGGER.warning(
                        "%s: Movement stop disagreement for STATE_OPEN - expected (100%%, 100%%) but calculated (%s%%, %s%%) - check travel_time=%ss slat_rotation_time=%ss",
                        self.entity_id, self._current_cover_position, 
                        self._current_tilt_position, self._travel_time, self._slat_rotation_time
                    )
            
            self._current_cover_position = 100
            self._current_tilt_position = 100
        
        # Save final state using proper storage abstraction
        await self._save_state_to_storage()
        
        _LOGGER.debug("%s: External movement stopped - final state=%s, position=%s%%, tilt=%s%%",
                      self.entity_id, final_state, 
                      self._current_cover_position, self._current_tilt_position)

    async def _sync_with_underlying_cover(self) -> None:
        """Sync state with underlying cover on startup."""
        state = self.hass.states.get(self._cover_entity_id)
        if not state:
            _LOGGER.warning("%s: Underlying cover entity not found - %s", self.entity_id, self._cover_entity_id)
            return
            
        self._underlying_cover_state = state.state
        
        # Get position if available
        position_attr = state.attributes.get(ATTR_POSITION)
        if position_attr is not None:
            self._underlying_cover_position = int(position_attr)
            
            # Initialize with underlying position if no stored state
            if self._current_cover_position is None:
                self._current_cover_position = self._underlying_cover_position
            
            if self._current_tilt_position is None:
                # Initialize tilt based on position
                if self._underlying_cover_position == 0:
                    self._current_tilt_position = 0
                elif self._underlying_cover_position == 100:
                    self._current_tilt_position = 100
                else:
                    self._current_tilt_position = 50  # Default mid-position
            
            # Update baseline for position tracking
            self._last_stored_position = self._current_cover_position
            self._last_stored_tilt = self._current_tilt_position
            self._last_stored_underlying_position = self._underlying_cover_position
            
            # CRITICAL: Sync with definitive positions on startup
            await self._sync_definitive_positions(self._underlying_cover_position)

    async def _sync_definitive_positions(self, underlying_position: int) -> None:
        """Synchronize with definitive positions (0% or 100%) from underlying cover."""
        if underlying_position == 0:
            # Cover is fully closed - check for timing disagreement
            old_position = self._current_cover_position
            old_tilt = self._current_tilt_position
            
            # Detect significant disagreement with expected closed state
            if old_position is not None and old_tilt is not None:
                position_disagreement = abs(old_position - 0)
                tilt_disagreement = abs(old_tilt - 0)
                
                if position_disagreement > 15 or tilt_disagreement > 15:
                    _LOGGER.warning(
                        "%s: Timing disagreement at closed position - expected (0%%, 0%%) but calculated (%s%%, %s%%) - check travel_time=%ss slat_rotation_time=%ss",
                        self.entity_id, old_position, old_tilt, self._travel_time, self._slat_rotation_time
                    )
            
            self._current_cover_position = 0
            self._current_tilt_position = 0  # Closed slats
            
            if old_position != 0 or old_tilt != 0:
                _LOGGER.debug(
                    "%s: Synchronized to fully closed - %s%% -> 0%%, tilt %s%% -> 0%% (underlying=0%%)",
                    self.entity_id, old_position, old_tilt
                )
                await self._save_state_to_storage()
                
        elif underlying_position == 100:
            # Cover is fully open - check for timing disagreement
            old_position = self._current_cover_position
            old_tilt = self._current_tilt_position
            
            # Detect significant disagreement with expected open state
            if old_position is not None and old_tilt is not None:
                position_disagreement = abs(old_position - 100)
                tilt_disagreement = abs(old_tilt - 100)
                
                if position_disagreement > 15 or tilt_disagreement > 15:
                    _LOGGER.warning(
                        "%s: Timing disagreement at open position - expected (100%%, 100%%) but calculated (%s%%, %s%%) - check travel_time=%ss slat_rotation_time=%ss",
                        self.entity_id, old_position, old_tilt, self._travel_time, self._slat_rotation_time
                    )
            
            self._current_cover_position = 100
            self._current_tilt_position = 100  # Fully tilted slats
            
            if old_position != 100 or old_tilt != 100:
                _LOGGER.debug(
                    "%s: Synchronized to fully open - %s%% -> 100%%, tilt %s%% -> 100%% (underlying=100%%)",
                    self.entity_id, old_position, old_tilt
                )
                await self._save_state_to_storage()

    # Cover control methods - Command Queue System
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        # Clear queue and queue open command
        self._command_queue.clear()
        self._command_queue.append({
            "type": "position_only_stage1",
            "target_position": 100,
            "target_tilt": self._current_tilt_position or 100,
            "stage": "stage_1"
        })
        await self._process_command_queue()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        # Clear queue and queue close command
        self._command_queue.clear()
        self._command_queue.append({
            "type": "position_only_stage1",
            "target_position": 0,
            "target_tilt": self._current_tilt_position or 0,
            "stage": "stage_1"
        })
        await self._process_command_queue()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop command - clear queue and stop underlying entity."""
        # Clear command queue
        self._command_queue.clear()
        self._current_command = None
        self._command_in_progress = False
        
        # Stop underlying entity
        await self.hass.services.async_call(
            "cover", "stop_cover", {"entity_id": self._cover_entity_id}
        )
        
        _LOGGER.debug("%s: Stop command executed - queue cleared, underlying entity stopped", self.entity_id)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Queue position command - does NOT calculate positions."""
        position = kwargs.get(ATTR_POSITION)
        if position is None:
            return
        
        # Clear any pending commands and add new command to queue
        self._command_queue.clear()
        
        # Position only: preserve current tilt with two-stage operation
        target_tilt = self._current_tilt_position or 50
        
        # Add Stage 1 command (position + natural tilt)
        self._command_queue.append({
            "type": "position_only_stage1",
            "target_position": position,
            "target_tilt": target_tilt,
            "stage": "stage_1"
        })
        
        # Add Stage 2 command (restore tilt)
        self._command_queue.append({
            "type": "position_only_stage2",
            "target_position": position,
            "target_tilt": target_tilt,
            "stage": "stage_2"
        })
        
        # Start command execution
        await self._process_command_queue()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt (set to 100%)."""
        await self._queue_tilt_command(100)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt (set to 0%)."""
        await self._queue_tilt_command(0)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        tilt_position = kwargs.get(ATTR_TILT_POSITION)
        if tilt_position is None:
            return
        
        await self._queue_tilt_command(tilt_position)

    async def _queue_tilt_command(self, tilt_position: int) -> None:
        """Queue tilt-only command - Stage 2 operation."""
        if not (0 <= tilt_position <= 100):
            return
        
        # Clear queue and add tilt-only command (Stage 2 directly)
        self._command_queue.clear()
        self._command_queue.append({
            "type": "tilt_only",
            "target_position": self._current_cover_position or 0,
            "target_tilt": tilt_position,
            "stage": "stage_2"
        })
        
        await self._process_command_queue()

    # Utility methods - proper storage abstraction
    async def _save_state_to_storage(self) -> None:
        """Save current state using proper storage abstraction."""
        try:
            if not self._storage.is_loaded():
                _LOGGER.warning("%s: Storage not loaded, skipping save", self.entity_id)
                return
            
            _LOGGER.info("%s: Attempting to save state - position=%s%%, tilt=%s%%",
                        self.entity_id, self._current_cover_position, 
                        self._current_tilt_position)
                
            # Use atomic storage operation
            await self._storage.async_set_position_tilt_pair(
                self._current_cover_position or 0,
                self._current_tilt_position or 0
            )
            
            _LOGGER.info("%s: Successfully saved state via storage abstraction - position=%s%%, tilt=%s%%",
                        self.entity_id, self._current_cover_position, 
                        self._current_tilt_position)
                         
        except Exception as err:
            _LOGGER.error("%s: Error saving state via storage abstraction: %s", self.entity_id, err)