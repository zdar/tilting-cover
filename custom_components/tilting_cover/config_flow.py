"""Config flow for Tilting Cover integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.entity_registry import (
    async_get as async_get_entity_registry,
    RegistryEntryHider,
)
from homeassistant.helpers.translation import async_get_translations
from homeassistant.components.cover import CoverEntityFeature

from .const import (
    CONF_COVER_ENTITY_ID,
    CONF_TRAVEL_TIME,
    CONF_SLAT_ROTATION_TIME,
    DEFAULT_TRAVEL_TIME,
    DEFAULT_SLAT_ROTATION_TIME,
    DOMAIN,
)

# Additional config keys for inherited metadata
CONF_ORIGINAL_AREA_ID = "original_area_id"
CONF_ORIGINAL_ICON = "original_icon"
CONF_ORIGINAL_ENTITY_CATEGORY = "original_entity_category"

_LOGGER = logging.getLogger(__name__)


class InvalidEntityError(HomeAssistantError):
    """Error to indicate invalid entity."""


class EntityNotFoundError(HomeAssistantError):
    """Error to indicate entity not found."""


class EntityAlreadyConfiguredError(HomeAssistantError):
    """Error to indicate entity already configured."""


class EntityHasTiltError(HomeAssistantError):
    """Error to indicate entity already has tilt functionality."""

async def has_tilt_functionality(hass: HomeAssistant, entity_id: str) -> bool:
    """Check if cover entity already has tilt functionality."""
    state = hass.states.get(entity_id)
    if not state:
        return False
    
    # Check for tilt position attribute
    if "current_tilt_position" in state.attributes:
        return True
        
    # Check for SET_TILT_POSITION feature
    supported_features = state.attributes.get("supported_features", 0)
    if supported_features & CoverEntityFeature.SET_TILT_POSITION:
        return True
        
    return False

async def is_already_configured(hass: HomeAssistant, entity_id: str) -> bool:
    """Check if entity is already configured with this integration."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_COVER_ENTITY_ID) == entity_id:
            return True
    return False

async def get_available_covers(hass: HomeAssistant) -> list[str]:
    """Get list of available cover entities that can be enhanced."""
    available_covers = []
    
    for entity_id in hass.states.async_entity_ids("cover"):
        # Skip if already has tilt functionality
        if await has_tilt_functionality(hass, entity_id):
            continue
            
        # Skip if already configured
        if await is_already_configured(hass, entity_id):
            continue
            
        available_covers.append(entity_id)
        
    return available_covers

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input."""
    cover_entity_id = data[CONF_COVER_ENTITY_ID]
    
    # Check if entity exists
    if hass.states.get(cover_entity_id) is None:
        raise EntityNotFoundError("Selected entity does not exist")
    
    # Check if entity is a cover
    if not cover_entity_id.startswith("cover."):
        raise InvalidEntityError("Selected entity is not a cover")
        
    # Check if entity already has tilt functionality
    if await has_tilt_functionality(hass, cover_entity_id):
        raise EntityHasTiltError("Selected cover already has tilt functionality")
        
    # Check if entity is already configured
    if await is_already_configured(hass, cover_entity_id):
        raise EntityAlreadyConfiguredError("Selected cover is already configured")

async def get_entity_name(hass: HomeAssistant, entity_id: str) -> str:
    """Get friendly name of entity with Tilting prefix."""
    state = hass.states.get(entity_id)
    if not state:
        return "Tilting Cover"  # Fallback name
    
    # Get friendly name or use entity_id
    friendly_name = state.attributes.get("friendly_name") or entity_id.split(".")[-1]
    
    # Get translated prefix
    translations = await async_get_translations(hass, hass.config.language, "tilting_cover", {"entity"})
    prefix = translations.get("tilting_cover::entity.name_prefix", "Tilting")
    
    return f"{prefix} {friendly_name}"

async def get_entity_metadata(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    """Get metadata from the underlying entity to inherit."""
    entity_registry = async_get_entity_registry(hass)
    entity_entry = entity_registry.async_get(entity_id)
    
    metadata = {}
    if entity_entry:
        metadata[CONF_ORIGINAL_AREA_ID] = entity_entry.area_id
        # DO NOT copy device_id - it must be unique per entity
        metadata[CONF_ORIGINAL_ICON] = entity_entry.icon
        metadata[CONF_ORIGINAL_ENTITY_CATEGORY] = entity_entry.entity_category
    
    return metadata

async def hide_underlying_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Hide the underlying entity from UI while keeping it functional."""
    try:
        entity_registry = async_get_entity_registry(hass)
        entity_registry.async_update_entity(
            entity_id,
            hidden_by=RegistryEntryHider.INTEGRATION
        )
        _LOGGER.debug("Hidden underlying entity %s after configuring tilting cover", entity_id)
    except Exception as err:
        _LOGGER.warning("Failed to hide underlying entity %s: %s", entity_id, err)
        # Don't raise - this is not critical for functionality


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tilting Cover."""

    VERSION = 1
    
    def __init__(self) -> None:
        """Initialize the config flow."""
        self._selected_entity: str | None = None
        self._errors: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - entity selection."""
        if user_input is not None:
            self._selected_entity = user_input[CONF_COVER_ENTITY_ID]
            
            # Check if already configured
            await self.async_set_unique_id(self._selected_entity)
            self._abort_if_unique_id_configured(updates={CONF_COVER_ENTITY_ID: self._selected_entity})
            
            try:
                await validate_input(self.hass, user_input)
                return await self.async_step_config()
            except EntityNotFoundError:
                self._errors[CONF_COVER_ENTITY_ID] = "entity_not_found"
            except InvalidEntityError:
                self._errors[CONF_COVER_ENTITY_ID] = "not_cover_entity"
            except EntityHasTiltError:
                self._errors[CONF_COVER_ENTITY_ID] = "already_has_tilt"
            except EntityAlreadyConfiguredError:
                self._errors[CONF_COVER_ENTITY_ID] = "already_configured"
            except Exception as err:
                _LOGGER.exception("Unexpected error during validation: %s", err)
                self._errors["base"] = "unknown"

        # Get available covers for selection
        try:
            available_covers = await get_available_covers(self.hass)
            if not available_covers:
                return self.async_abort(reason="no_covers_available")
        except Exception as err:
            _LOGGER.exception("Failed to get available covers: %s", err)
            return self.async_abort(reason="unknown")
        
        schema = vol.Schema({
            vol.Required(CONF_COVER_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="cover",
                    multiple=False,
                    include_entities=available_covers
                )
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=self._errors,
        )

    async def async_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the configuration step.""" 
        if user_input is not None:
            try:
                # Get metadata from underlying entity to inherit
                entity_metadata = await get_entity_metadata(self.hass, self._selected_entity)
                
                # Combine with selected entity and metadata
                full_data = {
                    CONF_COVER_ENTITY_ID: self._selected_entity,
                    **user_input,
                    **entity_metadata
                }
                
                # Hide the underlying entity (non-critical operation)
                await hide_underlying_entity(self.hass, self._selected_entity)
                
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=full_data
                )
            except Exception as err:
                _LOGGER.exception("Failed to create config entry: %s", err)
                self._errors["base"] = "unknown"

        # Generate suggested name with error handling
        try:
            suggested_name = await get_entity_name(self.hass, self._selected_entity)
        except Exception as err:
            _LOGGER.warning("Failed to generate suggested name: %s", err)
            suggested_name = "Tilting Cover"

        schema = vol.Schema({
            vol.Required(CONF_NAME, default=suggested_name): str,
            vol.Required(
                CONF_TRAVEL_TIME, default=DEFAULT_TRAVEL_TIME
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
            vol.Required(
                CONF_SLAT_ROTATION_TIME, default=DEFAULT_SLAT_ROTATION_TIME
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
        })

        return self.async_show_form(
            step_id="config",
            data_schema=schema,
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for Tilting Cover."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                return self.async_create_entry(title="", data=user_input)
            except Exception as err:
                _LOGGER.exception("Failed to save options: %s", err)
                errors["base"] = "unknown"

        schema = vol.Schema({
            vol.Required(
                CONF_TRAVEL_TIME,
                default=self.config_entry.data.get(CONF_TRAVEL_TIME, DEFAULT_TRAVEL_TIME)
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
            vol.Required(
                CONF_SLAT_ROTATION_TIME,
                default=self.config_entry.data.get(CONF_SLAT_ROTATION_TIME, DEFAULT_SLAT_ROTATION_TIME)
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )