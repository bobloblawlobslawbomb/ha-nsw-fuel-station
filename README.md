# NSW Fuel Station (enhanced)

A drop-in enhanced fork of the Home Assistant
[NSW Fuel Station](https://www.home-assistant.io/integrations/nsw_fuel_station/)
integration. Same domain (`nsw_fuel_station`), same sensors — plus a **GUI
config flow with a map** to choose which stations to track.

## What's different from the built-in integration

| | Built-in | This fork |
|---|---|---|
| Setup | YAML only (`sensor:` platform) | **GUI config flow** + legacy YAML still works |
| Station selection | Manual `station_id` in YAML | **Pick an area on a map** (radius), then tick the stations |
| Fuel types | Manual list in YAML | Multi-select from what the stations actually sell |
| Change tracking later | Edit YAML + restart | **Options flow** or `nsw_fuel_station.set_tracked_stations` service (no restart) |

The entity schema is unchanged (`station_name`, `station_id` attributes,
`¢/L` units, `NSW Government FuelCheck` attribution), so existing automations,
dashboards and the [Fuel Prices Card](https://github.com/bobloblawlobslawbomb/ha-fuel-prices-card)
keep working.

## Install (HACS)

1. HACS → **⋮ → Custom repositories**
2. Repository: `https://github.com/bobloblawlobslawbomb/ha-nsw-fuel-station`
3. Category: **Integration**
4. **Download**, then restart Home Assistant.
5. Settings → **Devices & Services** → **Add integration** → **NSW Fuel Station Price**.

> ⚠️ This component **replaces the built-in integration** (same domain).
> Any existing YAML `sensor: - platform: nsw_fuel_station` entries keep
> working. To avoid duplicate entities after setting up via the UI, remove
> the old YAML block and restart.

## Manual install

Copy `custom_components/nsw_fuel_station/` into `<config>/custom_components/`
and restart HA.

## Service

`nsw_fuel_station.set_tracked_stations`

| Field | Type | Description |
|---|---|---|
| `station_ids` | `list[int]` (required) | FuelCheck station codes to track (from any sensor's `station_id` attribute) |
| `fuel_types` | `list[str]` (optional) | e.g. `["P95", "P98", "Diesel"]`. Omit to keep current |

Example:

```yaml
service: nsw_fuel_station.set_tracked_stations
data:
  station_ids: [1510, 2262, 691, 18683]
  fuel_types: [P95, P98, Diesel]
```

## License

Apache-2.0 — a fork of `home-assistant/core`'s `nsw_fuel_station` component
(full license text in `LICENSE`). Data © NSW Government via FuelCheck.
