*** This is development version. Do not use in production. ***

# Tilting Cover Integration for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub License](https://img.shields.io/github/license/zdar/tilting-cover)](https://github.com/zdar/tilting-cover/blob/main/LICENSE)

## Purpose

Tilting Cover adds tilt/slat control to basic Home Assistant cover entities that normally support only open/close and simple position handling.

## Main Advantages

- Adds tilt support to existing non-tilting covers
- Supports position + tilt control from one entity
- Handles real blind behavior (slats then movement)
- Works with multiple independent covers
- Keeps state between Home Assistant restarts
- Supports multiple languages (EN, CS, DE, FR)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant.
2. Go to Integrations.
3. Open the menu (three dots) in the top-right corner.
4. Select Custom repositories.
5. Add repository URL: `https://github.com/zdar/tilting-cover`
6. Category: Integration
7. Install Tilting Cover.
8. Restart Home Assistant.

### Manual Installation

1. Download folder `tilting_cover` from the latest release.
2. Copy it to your `custom_components` directory.
3. Restart Home Assistant.

## Basic Setup

1. Home Assistant → Settings → Devices & Services.
2. Click Add Integration.
3. Search for Tilting Cover.
4. Select the source cover entity.
5. Configure:
   - Travel Time
   - Slat Rotation Time
   - Name

## Technical Information

All technical details (architecture, algorithm, queue processing, storage model, debugging, and implementation behavior) are documented in [Technical information.md](Technical%20information.md).

## Support

- 🐛 [Report bugs](https://github.com/zdar/tilting-cover/issues)
- 💡 [Request features](https://github.com/zdar/tilting-cover/issues)

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE).