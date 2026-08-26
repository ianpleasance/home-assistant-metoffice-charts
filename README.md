# Met Office Charts for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-c62828.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/github/v/release/ianpleasance/home-assistant-metoffice-charts?display_name=tag&sort=semver&color=blue&label=version)](https://github.com/ianpleasance/home-assistant-metoffice-charts/releases/latest)
[![license](https://img.shields.io/github/license/ianpleasance/home-assistant-metoffice-charts)](LICENSE)

A Home Assistant integration for downloading weather chart images from the Met Office DataHub. Display surface pressure maps, rainfall radar, satellite imagery, and more in your dashboards.

## Features

- **DataHub Integration** — uses the official Met Office DataHub API (DataPoint was retired December 2025)
- **Image Entities** — one image entity per chart parameter in your DataHub order
- **Local Storage** — charts saved to `/config/www/metoffice_charts/` accessible at `/local/metoffice_charts/`
- **Configurable Refresh** — 5-1440 minutes (default: 60 minutes)
- **Rich Attributes** — run time, forecast period, file paths for each chart
- **Free Tier Compatible** — works with Met Office DataHub free tier (1000 images/day)

## Chart Types

The integration downloads whatever chart parameters you select in your Met Office DataHub Map Images order. Common parameters include:

| Category | Parameters |
|----------|-----------|
| **Precipitation** | Rainfall rate, accumulation, radar composites |
| **Temperature** | Surface temperature, apparent temperature, dew point |
| **Wind** | Wind speed, gusts, direction |
| **Pressure** | Surface pressure, pressure tendency |
| **Cloud** | Cloud cover, cloud base height |
| **Visibility** | Visibility, fog probability |

## Prerequisites

Before installing, you need:

1. **Met Office DataHub Account** — Register at [datahub.metoffice.gov.uk](https://datahub.metoffice.gov.uk/)
2. **Map Images Subscription** (free tier available):
   - Go to **My Subscriptions** → **Map Images** → **Continue to data**
   - Click **Start a new order**
   - Select your **region** (e.g., "Europe", "UK")
   - Choose **parameters** you want (Temperature, Precipitation, Pressure, etc.)
   - Name your order (e.g., "My Weather Maps")
   - Complete the order
3. **API Key** — found in your DataHub account settings
4. **Order ID** — your order name transformed to lowercase-with-hyphens (e.g., "My Weather Maps" → `my-weather-maps`)

## Installation

### Via HACS (Recommended)

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/ianpleasance/hass-metoffice-charts` — Category: Integration
3. Search **Met Office Charts** → **Download**
4. Restart Home Assistant

### Manual Installation

1. Download the [latest release](https://github.com/ianpleasance/hass-metoffice-charts/releases)
2. Extract and copy `custom_components/metoffice_charts` to your `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Met Office Charts"
4. Enter your credentials:
   - **API Key**: Your DataHub API key
   - **Order ID**: Your order ID (e.g., `my-weather-maps`)
   - **Refresh Interval**: How often to check for new charts (default: 60 minutes)
5. Click **Submit**

## Usage

### Lovelace Dashboard

Display as an image entity:

```yaml
type: picture-entity
entity: image.met_office_temperature
show_state: false
show_name: true
```

Or use the file path directly:

```yaml
type: picture
image: /local/metoffice_charts/temperature.png
```

### Multiple Charts in Grid

```yaml
type: grid
columns: 2
cards:
  - type: picture-entity
    entity: image.met_office_temperature
    show_name: true
  - type: picture-entity
    entity: image.met_office_precipitation
    show_name: true
  - type: picture-entity
    entity: image.met_office_pressure
    show_name: true
  - type: picture-entity
    entity: image.met_office_wind_speed
    show_name: true
```

### Automation Example

Notify when new charts are available:

```yaml
automation:
  - alias: "New Weather Charts Available"
    trigger:
      - platform: state
        entity_id: image.met_office_temperature
    action:
      - service: notify.mobile_app
        data:
          title: "Weather Charts Updated"
          message: "New Met Office charts are available"
```

## Entities Created

The integration creates one image entity per parameter in your DataHub order:

- `image.met_office_<parameter_name>` — The chart image entity

### Entity Attributes

Each image entity includes:

| Attribute | Description |
|-----------|-------------|
| `parameter` | Parameter name (e.g., "temperature", "precipitation") |
| `order_id` | Your DataHub order ID |
| `file_url` | Local URL path (`/local/metoffice_charts/...`) |
| `file_path` | Absolute filesystem path |
| `last_updated` | When the image was last fetched |
| `run_time` | Model run time from Met Office |
| `forecast_period` | Forecast period/timestep |
| `attribution` | Data source attribution |

## Configuration Options

After setup, you can modify settings via **Configure**:

- **Refresh Interval** — change how often charts are fetched (5-1440 minutes)

## Services

The integration provides services for manual refresh operations:

### `metoffice_charts.refresh_order`

Manually fetch new weather charts for a specific order.

```yaml
service: metoffice_charts.refresh_order
data:
  order_id: "my-weather-maps"
```

### `metoffice_charts.refresh_all`

Manually fetch new weather charts for all configured orders.

```yaml
service: metoffice_charts.refresh_all
```

### Usage in Automations

```yaml
automation:
  - alias: "Refresh Weather Charts Every Morning"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: metoffice_charts.refresh_all
```

## Troubleshooting

### "Invalid API Key"

- Verify your API key in your DataHub account settings
- Ensure you're copying the complete key including any special characters

### "Order Not Found"

- Check your Order ID format: lowercase with spaces replaced by hyphens
- Verify the order exists in your DataHub "My Orders" page
- Ensure your Map Images subscription is active

### No Images Appearing

- Check Home Assistant logs: **Settings** → **System** → **Logs**
- Search for "metoffice_charts" to see error messages
- Verify your order has completed at least one run in DataHub
- Check you haven't exceeded the 1000 images/day limit (free tier)
- Ensure `/config/www/metoffice_charts/` directory is writable

### Images Not Updating

- Verify your refresh interval setting
- Check the DataHub order is generating new data at the expected frequency
- Ensure network connectivity to `data.hub.api.metoffice.gov.uk`
- Check Home Assistant logs for API errors

### "Cannot Connect"

- Check your internet connection
- Verify DataHub API is accessible: [datahub.metoffice.gov.uk](https://datahub.metoffice.gov.uk/)
- Check Home Assistant firewall settings allow outbound HTTPS

## Advanced Usage

### Using Charts in Scripts

```yaml
script:
  save_weather_chart:
    sequence:
      - service: camera.snapshot
        data:
          entity_id: image.met_office_temperature
          filename: "/config/www/archive/weather_{{ now().strftime('%Y%m%d_%H%M%S') }}.png"
```

### Creating Animated Loops

Save multiple timesteps and create animations using external tools or the [animate](https://github.com/custom-cards/animate) custom card.

## Support

- **Issues**: [GitHub Issues](https://github.com/ianpleasance/hass-metoffice-charts/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ianpleasance/hass-metoffice-charts/discussions)
- **Documentation**: [Met Office DataHub Docs](https://datahub.metoffice.gov.uk/docs)

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

This project is licensed under the Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Met Office for providing the DataHub API
- Home Assistant community

## Disclaimer

This integration is not affiliated with, endorsed by, or connected to the Met Office. Use of the Met Office DataHub is subject to their [terms and conditions](https://www.metoffice.gov.uk/about-us/legal).

**DataHub Charges**: The Met Office DataHub Map Images service is currently free with a 1000 images/day limit. Future pricing may change — check [datahub.metoffice.gov.uk](https://datahub.metoffice.gov.uk/) for current terms.
