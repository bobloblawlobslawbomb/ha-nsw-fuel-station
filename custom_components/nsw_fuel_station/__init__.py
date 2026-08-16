"""The nsw_fuel_station component.

Enhanced fork of the built-in integration: adds a GUI config flow with
map-based station selection, per-entry coordinators, and a service to
change the tracked stations at runtime.

License: Apache-2.0 (fork of home-assistant/core's nsw_fuel_station).
"""

from __future__ import annotations

import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .const import CONF_FUEL_TYPES, CONF_STATIONS, DATA_NSW_FUEL_STATION, DOMAIN
from .coordinator import NSWFuelStationCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)

SERVICE_SET_TRACKED_STATIONS = "set_tracked_stations"
ATTR_STATION_IDS = "station_ids"
ATTR_FUEL_TYPES = "fuel_types"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_STATION_IDS): cv.ensure_list(cv.positive_int),
        vol.Optional(ATTR_FUEL_TYPES): cv.ensure_list(cv.string),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NSW Fuel Station component.

    Mirrors the built-in integration: the legacy YAML path (`sensor:
    - platform: nsw_fuel_station`) needs a shared coordinator in
    ``hass.data``, created here unconditionally.
    """
    hass.data.setdefault(DATA_NSW_FUEL_STATION, {})

    coordinator = NSWFuelStationCoordinator(hass)
    hass.data[DATA_NSW_FUEL_STATION]["yaml"] = coordinator

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        _LOGGER.error("Failed to fetch initial NSW fuel station data")

    async def _async_set_tracked_stations(call: ServiceCall) -> None:
        """Replace tracked stations (and optionally fuel types) on all entries."""
        station_ids: list[int] = call.data[ATTR_STATION_IDS]
        new_fuel_types: list[str] | None = call.data.get(ATTR_FUEL_TYPES)

        for entry_id, maybe_coordinator in list(
            hass.data.get(DATA_NSW_FUEL_STATION, {}).items()
        ):
            if entry_id == "yaml" or not isinstance(maybe_coordinator, NSWFuelStationCoordinator):
                continue
            entry = next(
                (e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id == entry_id),
                None,
            )
            if entry is None:
                continue
            options = dict(entry.options)
            options[CONF_STATIONS] = station_ids
            if new_fuel_types is not None:
                options[CONF_FUEL_TYPES] = new_fuel_types
            hass.config_entries.async_update_entry(entry, options=options)
            await hass.config_entries.async_reload_entry(entry)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TRACKED_STATIONS,
        _async_set_tracked_stations,
        schema=SERVICE_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NSW Fuel Station from a config entry."""
    coordinator = NSWFuelStationCoordinator(hass)
    hass.data.setdefault(DATA_NSW_FUEL_STATION, {})[entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady("Failed to fetch NSW fuel station data")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DATA_NSW_FUEL_STATION].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry (after an options change)."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
