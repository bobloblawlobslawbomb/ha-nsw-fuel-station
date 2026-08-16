"""Config flow for the NSW Fuel Station integration.

Enhanced fork of the built-in integration: a GUI config flow where the user
picks an area on a map (location selector + radius), then selects which
fuel stations to track and which fuel types to report.

License: Apache-2.0 (fork of home-assistant/core's nsw_fuel_station).
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from nsw_fuel import FuelCheckClient, FuelCheckError, Station

from .const import CONF_FUEL_TYPES, CONF_STATIONS, DOMAIN
from .station_data import (
    DEFAULT_FUEL_TYPES,
    FUEL_TYPE_LABELS,
    fuel_types_for_stations,
    station_label,
    stations_within_radius,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_RADIUS_KM = 10


async def _fetch_data(hass: HomeAssistant, client: FuelCheckClient) -> Any:
    """Fetch all fuel prices in an executor (the client is synchronous)."""
    return await hass.async_add_executor_job(client.get_fuel_prices)


class NSWFuelStationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the enhanced NSW Fuel Station integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._lat: float | None = None
        self._lon: float | None = None
        self._radius: float | None = None
        self._nearby: list[tuple[Station, float]] = []
        self._station_fuel_types: dict[int, set[str]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: pick an area on the map."""
        errors: dict[str, str] = {}

        if user_input is not None:
            location = user_input["location"]
            self._lat = float(location[CONF_LATITUDE])
            self._lon = float(location[CONF_LONGITUDE])
            self._radius = float(location.get(CONF_RADIUS, DEFAULT_RADIUS_KM))
            return await self.async_step_stations()

        data_schema = vol.Schema(
            {
                vol.Required("location"): selector.LocationSelector(
                    selector.LocationSelectorConfig(radius=True)
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: select which stations to track."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._selected_stations: list[str] = user_input[CONF_STATIONS]
            return await self.async_step_fuel_types()

        # Fetch station + price data and filter by the picked radius.
        client = FuelCheckClient()
        try:
            data = await _fetch_data(self.hass, client)
        except FuelCheckError as exc:
            _LOGGER.warning("Failed to fetch NSW fuel station data: %s", exc)
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("location"): selector.LocationSelector(
                            selector.LocationSelectorConfig(radius=True)
                        ),
                    }
                ),
                errors={"base": "api_error"},
            )

        self._nearby = stations_within_radius(
            data.stations, self._lat or 0, self._lon or 0, self._radius or DEFAULT_RADIUS_KM
        )
        if not self._nearby:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("location"): selector.LocationSelector(
                            selector.LocationSelectorConfig(radius=True)
                        ),
                    }
                ),
                errors={"base": "no_stations"},
            )

        # Track which fuel types each station actually sells.
        self._station_fuel_types = {}
        for station in data.stations.values():
            fuels: set[str] = set()
            for station_code, fuel_type in data.prices:
                if station_code == station.code:
                    fuels.add(fuel_type)
            self._station_fuel_types[station.code] = fuels

        options = [
            {
                "value": str(station.code),
                "label": station_label(station, distance),
            }
            for station, distance in self._nearby
        ]

        data_schema = vol.Schema(
            {
                vol.Required(CONF_STATIONS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="stations",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_fuel_types(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 3: select which fuel types to track."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"NSW Fuel Stations ({len(self._selected_stations)})",
                data={},
                options={
                    CONF_LATITUDE: self._lat,
                    CONF_LONGITUDE: self._lon,
                    CONF_RADIUS: self._radius,
                    CONF_STATIONS: [int(code) for code in self._selected_stations],
                    CONF_FUEL_TYPES: user_input[CONF_FUEL_TYPES],
                },
            )

        # Union of fuel types across the selected stations.
        available: set[str] = set()
        for code in (int(c) for c in self._selected_stations):
            available |= self._station_fuel_types.get(code, set())
        available = {f for f in available if f in FUEL_TYPE_LABELS}
        default = [f for f in DEFAULT_FUEL_TYPES if f in available]

        options = [
            {"value": fuel, "label": FUEL_TYPE_LABELS.get(fuel, fuel)}
            for fuel in sorted(available)
        ]

        data_schema = vol.Schema(
            {
                vol.Required(CONF_FUEL_TYPES, default=default): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="fuel_types",
            data_schema=data_schema,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return NSWFuelStationOptionsFlow(config_entry)


class NSWFuelStationOptionsFlow(OptionsFlow):
    """Options flow: change the tracked area, stations, or fuel types."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry
        options = config_entry.options
        self._lat = float(options.get(CONF_LATITUDE, 0))
        self._lon = float(options.get(CONF_LONGITUDE, 0))
        self._radius = float(options.get(CONF_RADIUS, DEFAULT_RADIUS_KM))
        self._nearby: list[tuple[Station, float]] = []
        self._station_fuel_types: dict[int, set[str]] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Options step 1: adjust the area on the map."""
        errors: dict[str, str] = {}

        if user_input is not None:
            location = user_input["location"]
            self._lat = float(location[CONF_LATITUDE])
            self._lon = float(location[CONF_LONGITUDE])
            self._radius = float(location.get(CONF_RADIUS, DEFAULT_RADIUS_KM))
            return await self.async_step_stations()

        data_schema = vol.Schema(
            {
                vol.Required(
                    "location",
                    default={
                        CONF_LATITUDE: self._lat,
                        CONF_LONGITUDE: self._lon,
                        CONF_RADIUS: self._radius,
                    },
                ): selector.LocationSelector(
                    selector.LocationSelectorConfig(radius=True)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)

    async def async_step_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Options step 2: select stations."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._selected_stations: list[str] = user_input[CONF_STATIONS]
            return await self.async_step_fuel_types()

        client = FuelCheckClient()
        try:
            data = await _fetch_data(self.hass, client)
        except FuelCheckError as exc:
            _LOGGER.warning("Failed to fetch NSW fuel station data: %s", exc)
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required("location"): selector.LocationSelector(
                            selector.LocationSelectorConfig(radius=True)
                        ),
                    }
                ),
                errors={"base": "api_error"},
            )

        self._nearby = stations_within_radius(
            data.stations, self._lat, self._lon, self._radius
        )
        if not self._nearby:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required("location"): selector.LocationSelector(
                            selector.LocationSelectorConfig(radius=True)
                        ),
                    }
                ),
                errors={"base": "no_stations"},
            )

        self._station_fuel_types = {}
        for station in data.stations.values():
            fuels = {
                fuel_type
                for station_code, fuel_type in data.prices
                if station_code == station.code
            }
            self._station_fuel_types[station.code] = fuels

        current = {str(code) for code in self._config_entry.options.get(CONF_STATIONS, [])}
        options = [
            {
                "value": str(station.code),
                "label": station_label(station, distance),
            }
            for station, distance in self._nearby
        ]

        data_schema = vol.Schema(
            {
                vol.Required(CONF_STATIONS, default=list(current)): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="stations", data_schema=data_schema, errors=errors)

    async def async_step_fuel_types(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Options step 3: select fuel types."""
        if user_input is not None:
            options = {
                CONF_LATITUDE: self._lat,
                CONF_LONGITUDE: self._lon,
                CONF_RADIUS: self._radius,
                CONF_STATIONS: [int(code) for code in self._selected_stations],
                CONF_FUEL_TYPES: user_input[CONF_FUEL_TYPES],
            }
            return self.async_create_entry(title="", data=options)

        available: set[str] = set()
        for code in (int(c) for c in self._selected_stations):
            available |= self._station_fuel_types.get(code, set())
        available = {f for f in available if f in FUEL_TYPE_LABELS}
        default = [
            f
            for f in self._config_entry.options.get(CONF_FUEL_TYPES, DEFAULT_FUEL_TYPES)
            if f in available
        ]

        options = [
            {"value": fuel, "label": FUEL_TYPE_LABELS.get(fuel, fuel)}
            for fuel in sorted(available)
        ]

        data_schema = vol.Schema(
            {
                vol.Required(CONF_FUEL_TYPES, default=default): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="fuel_types", data_schema=data_schema)
