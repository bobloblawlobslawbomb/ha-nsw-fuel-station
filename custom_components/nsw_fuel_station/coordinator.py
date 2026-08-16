"""Coordinator for the NSW Fuel Station integration."""

from dataclasses import dataclass
import datetime
import logging
from typing import Any, override

import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .station_data import Station

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(hours=1)

API_URL = "https://api.onegov.nsw.gov.au/FuelCheckApp/v1/fuel/prices"


@dataclass
class StationPriceData:
    """Data structure for O(1) price and name lookups."""

    stations: dict[int, Station]
    prices: dict[tuple[int, str], float]


class NSWFuelStationCoordinator(DataUpdateCoordinator[StationPriceData]):
    """Class to manage fetching NSW fuel station data."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry | None = None
    ) -> None:
        """Initialize the coordinator.

        ``config_entry`` is required for the config-entry path (so
        ``async_config_entry_first_refresh`` works); the legacy YAML path
        passes None, matching the built-in integration.
        """
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="sensor",
            update_interval=SCAN_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> StationPriceData:
        """Fetch data from API."""
        return await self.hass.async_add_executor_job(_fetch_station_price_data)


def _fetch_station_price_data(client: Any | None = None) -> StationPriceData:
    """Fetch the FuelCheck price dump and restructure it.

    The dump is fetched directly (plain requests + a ``requesttimestamp``
    header — the same call the nsw-fuel-api-client makes) because that
    client's released ``Station`` DTO has no coordinates; the raw API
    provides ``location`` per station.
    """
    timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    try:
        response = requests.get(
            API_URL, headers={"requesttimestamp": timestamp}, timeout=30
        )
        response.raise_for_status()
        raw = response.json()
    except Exception as exc:  # noqa: BLE001 - surface any fetch failure
        raise UpdateFailed(
            f"Failed to fetch NSW Fuel station price data: {exc}"
        ) from exc

    stations: dict[int, Station] = {}
    for entry in raw.get("stations", []):
        try:
            code = int(entry["code"])
        except (KeyError, TypeError, ValueError):
            continue
        location = entry.get("location") or {}
        stations[code] = Station(
            code=code,
            name=entry.get("name", ""),
            brand=entry.get("brand"),
            address=entry.get("address"),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
        )

    prices: dict[tuple[int, str], float] = {}
    for entry in raw.get("prices", []):
        try:
            code = int(entry["stationcode"])
            fuel_type = entry["fueltype"]
            price = float(entry["price"])
        except (KeyError, TypeError, ValueError):
            continue
        prices[(code, fuel_type)] = price

    return StationPriceData(stations=stations, prices=prices)
