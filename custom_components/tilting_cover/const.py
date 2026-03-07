"""Constants for the Tilting Cover integration."""
from __future__ import annotations

DOMAIN = "tilting_cover"

# Configuration keys
CONF_COVER_ENTITY = "cover_entity_id"  # Alias for backward compatibility
CONF_COVER_ENTITY_ID = "cover_entity_id"
CONF_TRAVEL_TIME = "travel_time"
CONF_SLAT_ROTATION_TIME = "slat_rotation_time"

# Default values  
DEFAULT_TRAVEL_TIME = 20  # seconds for full 0%->100% or 100%->0% travel (matches ALGORITHM.md example)
DEFAULT_SLAT_ROTATION_TIME = 3  # seconds for slat rotation during movement

# Tilt constants (HA tilt positions are 0-100%)
TILT_CLOSED = 0      # 0% - No tilt/closed
TILT_OPEN = 100      # 100% - Maximum tilt/open

# Attributes
ATTR_ESTIMATED_POSITION = "estimated_position"    # 0-100% cover position
ATTR_ESTIMATED_TILT = "estimated_tilt"            # 0-100% tilt position
ATTR_SLAT_TILT_POSITION = "slat_tilt_position"    # Target tilt (0-100%)
ATTR_ORIGINAL_COVER_ENTITY_ID = "original_cover_entity_id"  # Reference to wrapped entity
ATTR_STORED_COVER_POSITION = "stored_cover_position"        # Position from persistent storage
ATTR_STORED_TILT_POSITION = "stored_tilt_position"          # Tilt from persistent storage
ATTR_POSITION_TIMESTAMP = "position_timestamp"              # When position was last stored
ATTR_POSITION_DATA_AGE = "position_data_age"                # Human readable data age
ATTR_STORAGE_HEALTHY = "storage_healthy"                    # Storage system health status

# State tracking
ATTR_LAST_POSITION = "last_position"
ATTR_LAST_UPDATE = "last_update"
ATTR_MOVEMENT_START = "movement_start"
ATTR_TARGET_POSITION = "target_position"

# Persistent storage keys
STORAGE_KEY = "tilting_cover_storage"
STORAGE_VERSION = 1
STORAGE_TILT_POSITION = "tilt_position"
STORAGE_COVER_POSITION = "cover_position"
STORAGE_TIMESTAMP = "timestamp"
STORAGE_LAST_KNOWN_POSITION = "last_known_position"  # Deprecated, use STORAGE_COVER_POSITION
STORAGE_ENTITY_STATE = "entity_state"

# Default storage values
DEFAULT_STORED_TILT = 0  # Default tilt position when no storage available
DEFAULT_STORED_POSITION = 0  # Default cover position
DEFAULT_STORED_TIMESTAMP = None  # Default timestamp when no storage available