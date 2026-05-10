# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-05-10

### Added
- **Services**: Manual refresh services
  - `metoffice_charts.refresh_order` - Refresh a specific order
  - `metoffice_charts.refresh_all` - Refresh all configured orders
  - Service descriptions in 13 languages
- **Multi-language Support**: Full translations for 13 languages
  - Danish (da), German (de), Spanish (es), Finnish (fi)
  - French (fr), Italian (it), Japanese (ja), Dutch (nl)
  - Norwegian (no), Polish (pl), Portuguese (pt), Swedish (sv)
  - English (en) - complete with data descriptions
- **Entity Cleanup**: Automatic removal of old entities when order changes
  - Tracks order_id changes
  - Removes orphaned entities
  - Logs cleanup operations
- **services.yaml**: Service documentation for Home Assistant UI

### Changed
- Data structure now stores coordinator and order_id separately
- Services registered once per integration (not per entry)
- Improved logging for service calls

## [0.2.0] - 2026-02-19

### Changed
- **Code Standards**: Aligned with integration code standards
  - Added `from __future__ import annotations` to all modules
  - Improved type hints throughout
  - Enhanced error messages with specific error codes
  - Better logging with info-level messages for successful operations
  - Proper typing for all function signatures
- **Configuration**: Enhanced config flow validation
  - Specific error messages for different failure scenarios
  - Better user feedback during setup
  - Description placeholders for dynamic help text
- **Documentation**: Comprehensive documentation updates
  - Tables for features and chart types
  - Detailed troubleshooting section
  - Usage examples for dashboards and automations
  - Advanced usage patterns
- **Manifest**: Added minimum Home Assistant version requirement (2024.1.0)
- **Constants**: Added attribution constant for proper data source credit

### Fixed
- Removed `aiofiles` version pin that conflicted with Home Assistant core dependencies
- Home Assistant core already includes `aiofiles>=24.1.0`

## [0.1.1] - 2026-02-19

### Fixed
- Removed `aiofiles` dependency conflict with Home Assistant core

## [0.1.0] - 2026-02-19

### Added
- Initial release
- Met Office DataHub API integration
- Image entities for weather charts
- UI configuration flow
- Automatic chart download to `/local/metoffice_charts/`
- Configurable refresh interval (5-1440 minutes)
- Support for Met Office DataHub Map Images (free tier)
- HACS compatibility

### Features
- Download weather map PNG images from DataHub
- Create image entity per parameter in order
- Save files to local storage with public access
- Entity attributes include run time, forecast period, file paths
- Options flow for updating refresh interval
