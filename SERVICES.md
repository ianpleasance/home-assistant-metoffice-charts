# Services Reference

The Met Office Charts integration provides services for manual refresh operations.

## Available Services

### `metoffice_charts.refresh_order`

Manually fetch new weather charts for a specific order.

**Parameters:**

| Parameter | Required | Type | Description | Example |
|-----------|----------|------|-------------|---------|
| `order_id` | Yes | string | The order ID to refresh | `my-weather-maps` |

**Usage:**

```yaml
service: metoffice_charts.refresh_order
data:
  order_id: "my-weather-maps"
```

**Developer Tools:**

```yaml
service: metoffice_charts.refresh_order
data:
  order_id: my-weather-maps
```

---

### `metoffice_charts.refresh_all`

Manually fetch new weather charts for all configured orders.

**Parameters:** None

**Usage:**

```yaml
service: metoffice_charts.refresh_all
```

## Use Cases

### Automation: Refresh Before Leaving Home

Fetch the latest weather charts before you leave home each morning:

```yaml
automation:
  - alias: "Morning Weather Update"
    trigger:
      - platform: time
        at: "07:00:00"
    condition:
      - condition: state
        entity_id: binary_sensor.workday_sensor
        state: "on"
    action:
      - service: metoffice_charts.refresh_all
      - service: notify.mobile_app
        data:
          title: "Weather Charts Updated"
          message: "Latest Met Office charts are ready"
```

### Automation: Refresh on Severe Weather Alert

Fetch updated charts when a severe weather warning is issued:

```yaml
automation:
  - alias: "Severe Weather Chart Update"
    trigger:
      - platform: state
        entity_id: sensor.met_office_weather_warning
        to: "Yellow"
    action:
      - service: metoffice_charts.refresh_order
        data:
          order_id: "my-weather-maps"
      - delay:
          seconds: 5
      - service: notify.mobile_app
        data:
          title: "⚠️ Weather Warning"
          message: "Severe weather detected - charts updated"
          data:
            image: /local/metoffice_charts/pressure.png
```

### Script: Manual Refresh Button

Create a button in your dashboard to manually refresh charts:

```yaml
script:
  refresh_weather_charts:
    alias: "Refresh Weather Charts"
    icon: mdi:refresh
    sequence:
      - service: metoffice_charts.refresh_all
      - service: persistent_notification.create
        data:
          title: "Weather Charts"
          message: "Refreshing all weather charts..."
```

Then add to your dashboard:

```yaml
type: button
name: Refresh Charts
tap_action:
  action: call-service
  service: script.refresh_weather_charts
icon: mdi:weather-cloudy
```

### Automation: Hourly Refresh During Events

Increase refresh frequency during specific weather events:

```yaml
automation:
  - alias: "Frequent Updates During Storm"
    trigger:
      - platform: time_pattern
        minutes: "/15"  # Every 15 minutes
    condition:
      - condition: or
        conditions:
          - condition: numeric_state
            entity_id: sensor.wind_speed
            above: 30
          - condition: state
            entity_id: binary_sensor.rain_today
            state: "on"
    action:
      - service: metoffice_charts.refresh_all
```

### Advanced: Conditional Refresh Based on Chart Age

Only refresh if charts are older than a certain time:

```yaml
automation:
  - alias: "Smart Chart Refresh"
    trigger:
      - platform: state
        entity_id: sensor.pressure_trend
        to: "falling_rapidly"
    condition:
      - condition: template
        value_template: >
          {% set last_update = state_attr('image.met_office_pressure', 'last_updated') %}
          {% if last_update %}
            {{ (now() - last_update).total_seconds() > 1800 }}
          {% else %}
            true
          {% endif %}
    action:
      - service: metoffice_charts.refresh_order
        data:
          order_id: "uk-pressure-maps"
```

## Notes

- Services respect rate limits and API quotas
- Manual refreshes do not affect the configured automatic refresh interval
- All configured orders can be refreshed simultaneously with `refresh_all`
- Check Home Assistant logs for service call results and any errors
- Free tier limit: 1000 images/day across all manual and automatic refreshes

## Troubleshooting

**Service Not Found:**
- Ensure the integration is properly installed and loaded
- Check **Settings → System → Logs** for integration errors

**Service Fails:**
- Verify API credentials are still valid
- Check internet connectivity
- Ensure order still exists in DataHub
- Verify you haven't exceeded daily API limits

**Charts Don't Update:**
- Check entity attributes for `last_updated` timestamp
- Verify files in `/local/metoffice_charts/` directory
- Look for errors in Home Assistant logs
