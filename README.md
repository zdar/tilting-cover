# Tilting Cover Integration for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub License](https://img.shields.io/github/license/zdar/tilting-cover)](https://github.com/zdar/tilting-cover/blob/main/LICENSE)

## Purpose

This integration extends basic cover entities in Home Assistant that don't support tilt control. Many basic covers only allow "open" and "close" actions, but real blind mechanics follow a sequential pattern: slats rotate first fully, then the cover moves to target position.

## How it works

### Problem with basic covers
- Basic covers only support `open` and `close` actions
- Limited positioning: Only full open or full close, no intermediate positions
- **CRITICAL**: Slats always rotate first, then cover moves (sequential behavior)
- No independent tilt/slat angle control available
- Home Assistant only sees position 0-100% (0%=closed, 100%=open)

### Solution by this integration
1. **Position-Based Algorithm** - Uses underlying entity position changes for calculations (NO timing)
2. **Work Distribution Ratios** - User-configured times determine tilt/travel work ratios
3. **Sequential Movement Model** - Enforces real blind behavior: slats rotate first, then cover moves
4. **Decoupled Architecture** - Independent position tracking + command queue systems
5. **Extended Control** - Adds tilt functions with intermediate positioning
### Technical Documentation

**Authoritative Reference**: [ALGORITHM.md](ALGORITHM.md) contains the complete technical specification, including:
- Decoupled architecture with Independent Position Tracking + Command Queue systems
- Position-based calculation algorithms with work distribution ratios
- Stage 1/Stage 2 operation sequences and external movement handling
- Sequential movement model enforcing slats-first behavior
- Direction change detection with intermediate stop+start sequences
- Persistent storage mechanisms and state recovery procedures

> **Note**: ALGORITHM.md takes precedence for all technical implementation details.
## Configuration

During setup, the integration will ask for:

### Basic Settings
- **Cover Entity** - Select existing cover from HA entities list
- **Name** - Customizable name for the new enhanced entity

### Work Distribution Parameters
- **Travel Time** (5-120s) - Total time for complete 0%↔100% cycle (used for ratio calculation)
- **Slat Rotation Time** (1-10s) - Time portion for slat rotation (used for work distribution ratio)
- **Important**: These times are NOT used for delays - only for calculating work distribution between tilt and travel phases

### Technical Implementation
Integration implements sophisticated position-based algorithms:
- **Stage 1/Stage 2 Operations** - Natural tilt positioning + precise fine-tuning
- **Independent Position Tracking** - Continuous monitoring regardless of movement source
- **Command Queue System** - Ordered execution of user commands with external movement handling
- **Direction Change Detection** - Intermediate stop+start sequence with position storage
- **Persistent State Recovery** - Complete state restoration across HA restarts

## Architecture & Code Quality

### Design Principles
The integration follows strict **separation of concerns** architecture:

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│   cover.py      │────│  coordinator.py      │────│   storage.py    │
│  Business Logic │    │  Data Coordination   │    │  Data Storage   │
└─────────────────┘    └──────────────────────┘    └─────────────────┘
```

### Component Responsibilities

#### **cover.py** - Business Logic Layer ✅
- Sophisticated tilting algorithm (Independent Position Tracking System)
- Command Queue System (Stage 1/Stage 2 operations)  
- Movement Detection System
- Home Assistant entity interface
- **PROHIBITED**: Direct data store access, persistence implementation

#### **storage.py** - Data Persistence Layer ✅
- TiltingCoverStorage abstraction class
- Atomic storage operations (`async_set_position_tilt_pair`)
- Safe data retrieval (`get_position_tilt_pair`)
- Storage health monitoring, error handling

#### **coordinator.py** - Data Coordination Layer ✅ 
- Storage handler factory (`get_storage_handler`)
- Data coordination between entities
- HA Store management

### Code Quality Standards
Following [Quality Guidelines](.github/copilot-instructions.md):
- ✅ **PEP 8 compliance** with comprehensive type hints
- ✅ **Proper async/await patterns** for HA compatibility
- ✅ **Comprehensive error handling** with specific exceptions
- ✅ **HACS compatibility** requirements maintained
- ✅ **Security best practices** with input validation
- ✅ **Production-ready code** reviewed for reliability

> **Technical Reference**: See [ALGORITHM.md](ALGORITHM.md) for complete implementation details including algorithms, decoupled architecture, and position calculation formulas.

## Current Status

✅ **Implemented:**
- **Decoupled Architecture** - Independent Position Tracking System + Command Queue System
- **Position-Based Algorithm** - Core calculation engine using work distribution ratios
- **Stage 1/Stage 2 Operations** - Natural positioning + precise tilt fine-tuning
- **External Movement Detection** - Fake command injection for external movements
- **Direction Change Handling** - Intermediate stop+start with position storage
- **Persistent Storage** - Atomic position/tilt storage with timestamp tracking
- **HACS Compatibility** - Complete integration structure with manifest
- **Internationalization support** (EN, CS, DE, FR)
- **Error Handling** - Comprehensive error handling and recovery mechanisms

🔄 **Future Enhancements:**
- **Performance Optimization** - Algorithm efficiency improvements
- **Advanced Configuration UI** - Web interface for complex parameter tuning
- **Diagnostic Dashboard** - Real-time algorithm state visualization
- **Enhanced Error Recovery** - Advanced fault-tolerance mechanisms
- **Extended Hardware Support** - Support for additional cover types and protocols

## Internationalization

This integration supports multiple languages following HA standards:

### Supported Languages
- 🇺🇸 **English (en)** - Default language
- 🇨🇿 **Czech (cs)** - Czech Republic  
- 🇩🇪 **German (de)** - Germany
- 🇫🇷 **French (fr)** - France

### Translation Features
- **Auto-detection** - Uses your Home Assistant language settings
- **Config Flow** - All setup dialogs translated
- **Entity Names** - Localized entity and attribute names
- **Error Messages** - Translated error and status messages

### Contributing Translations
Translations are stored in `translations/` directory. To add a new language:

1. Copy `translations/en.json` to `translations/{language_code}.json`
2. Translate all text values (keep JSON keys unchanged)  
3. Test the translation in Home Assistant
4. Submit a pull request

### Translation Files Structure
```
custom_components/tilting_cover/
├── translations/
│   ├── en.json          # English (default)
│   ├── cs.json          # Czech
│   ├── de.json          # German
│   ├── fr.json          # French
│   └── {lang}.json      # Your language
└── strings.json         # Entity/state translations
```

## Persistent Storage

The integration includes robust persistent storage for maintaining state across Home Assistant restarts:

### Stored Data
- **Cover Position** - Current position of the cover (0-100%)
- **Tilt Position** - Current slat tilt position (0-100%)
- **Position Timestamp** - When the position/tilt data was last updated
- **Entity State** - Additional state information for proper restoration

### Storage Features
- **Automatic Backup** - State saved immediately on changes
- **Atomic Updates** - Position/tilt pairs saved together with timestamp
- **Crash Recovery** - Survives Home Assistant crashes/restarts
- **Per-Entity Storage** - Each cover entity has independent storage
- **Storage Health** - Built-in storage system health monitoring
- **Backward Compatibility** - Graceful handling of storage schema changes
- **Proper Abstraction** - Storage operations use dedicated abstraction layer (see Architecture above)

### Benefits
- **Seamless Restarts** - No position loss during HA restarts
- **Reliable State** - Cover and tilt positions maintained consistently  
- **Data Integrity** - Timestamp tracking for position data age with atomic operations
- **Fast Recovery** - Immediate state restoration on startup
- **Performance Optimized** - Efficient storage with minimal I/O operations
- **Maintainable Code** - Clear separation between business logic and data persistence

---

**Note**: Replace `yourusername` with your actual GitHub username before publishing.

## Installation

### HACS Installation (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/zdar/tilting-cover`
6. Select "Integration" as the category
7. Click "Add"
8. Search for "Tilting Cover" and install
9. Restart Home Assistant

### Manual Installation

1. Download the `tilting_cover` folder from the latest release
2. Copy the folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

### Via UI (Recommended)

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Tilting Cover"
4. Select the cover entity you want to add tilt functionality to
5. Configure work distribution parameters:
   - **Travel Time**: Total cycle time for work ratio calculation
   - **Slat Rotation Time**: Slat rotation portion for work distribution
6. Set custom name for the enhanced entity

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| Cover Entity | The existing cover entity to extend | Required |
| Travel Time | Total time for 0%→100% cycle (work ratio calculation) | 20s |
| Slat Rotation Time | Time portion for slat rotation (work ratio calculation) | 3s |
| Name | Custom name for enhanced entity | Auto-generated |

## Multiple Covers Support

The Tilting Cover integration **fully supports multiple independent covers**. Users can configure as many tilting covers as they have underlying cover entities in Home Assistant.

### Key Features
- **🔄 Independent Configuration**: Each cover has its own settings (travel time, slat rotation time, name)
- **💾 Isolated Storage**: Each cover maintains separate persistent state storage 
- **🎯 Unique Identity**: Each cover gets its own entity ID, device, and unique identifiers
- **🚫 Duplicate Prevention**: Config flow prevents configuring the same underlying cover twice
- **🔍 Smart Filtering**: Only shows covers that can be enhanced (excludes those with built-in tilt)

### Setup Process
1. **First Cover**: Add integration → select any compatible cover entity → configure
2. **Additional Covers**: Go to existing integration → click "Configure" → select next cover from available covers
3. **Independent Operation**: Each tilting cover operates completely independently
4. **Easy Management**: All covers appear under single integration with multiple config entries

### Example Configuration
```
Original Covers:
├── cover.bedroom_blind (basic cover) 
├── cover.living_room_blind (basic cover)
├── cover.bathroom_blind (has built-in tilt) ❌ Cannot enhance
└── cover.office_blind (basic cover)

After Enhancement:
├── cover.tilting_bedroom_blind ✅ Enhanced
├── cover.tilting_living_room_blind ✅ Enhanced  
├── cover.tilting_office_blind ✅ Enhanced
└── Original covers are hidden but functional
```

### Limitations
- Cannot enhance covers that already have built-in tilt functionality
- Cannot configure the same underlying cover multiple times
- Each tilting cover requires a separate underlying cover entity

## Usage Example

```yaml
# Automation example - Morning routine
automation:
  - alias: "Morning Blinds Routine"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      # Single call - sets both position and tilt simultaneously
      - service: cover.set_cover_position
        target:
          entity_id: cover.living_room_tilting_cover
        data:
          position: 100
          tilt_position: 45
```

```yaml
# Another example - Afternoon sun protection
automation:
  - alias: "Afternoon Sun Protection"
    trigger:
      platform: time
      at: "14:00:00"
    action:
      # Move to 60% open with 30% tilt - integration handles staging automatically
      - service: cover.set_cover_position
        target:
          entity_id: cover.living_room_tilting_cover
        data:
          position: 60
          tilt_position: 30
```

```yaml
# Lovelace card example
type: entities
entities:
  - entity: cover.living_room_tilting_cover
    name: Living Room Blinds
    secondary_info: last-changed
```

## Services

This integration provides all standard Home Assistant cover services:

### Standard Cover Services
- `cover.open_cover`
- `cover.close_cover`
- `cover.stop_cover`
- `cover.set_cover_position`

### Tilt-Specific Services
- `cover.open_cover_tilt`
- `cover.close_cover_tilt`
- `cover.stop_cover_tilt`
- `cover.set_cover_tilt_position`

## State Attributes

The tilting cover entity provides these key attributes:

- `current_position`: Current cover position (from original cover)
- `current_tilt_position`: Current tilt position (0-100)
- `supported_features`: Combined features from original cover + tilt features
- `original_cover_entity_id`: Reference to the wrapped cover entity
- `estimated_position`: Real-time position estimation during movement
- `estimated_tilt`: Real-time tilt estimation during movement
- `stored_cover_position`: Last stored position in persistent storage
- `stored_tilt_position`: Last stored tilt position in persistent storage
- `position_timestamp`: When position data was last stored
- `storage_healthy`: Persistent storage system health status

## Troubleshooting

### Common Issues

**Cover entity not available**
- Ensure the selected cover entity exists and is functioning
- Check that the original cover entity is not disabled

**Tilt commands not working**
- Verify the integration is properly installed and configured
- Check Home Assistant logs for any error messages

**State synchronization issues**
- The integration automatically syncs with the original cover
- If sync is lost, try restarting the integration

### Debug Logging

Enable debug logging for troubleshooting:

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.tilting_cover: debug
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

- 🐛 [Report bugs](https://github.com/zdar/tilting-cover/issues)
- 💡 [Request features](https://github.com/zdar/tilting-cover/issues)
- 📖 [Documentation](https://github.com/zdar/tilting-cover/wiki)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Home Assistant community for the excellent platform
- HACS for making custom integrations easily accessible

---

**Note**: Replace `yourusername` with your actual GitHub username before publishing.