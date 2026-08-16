"""Pure data helpers for the NSW Fuel Station integration.

No Home Assistant imports here — keeps the station-selection logic
unit-testable outside HA.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from nsw_fuel import Station

EARTH_RADIUS_KM = 6371.0

FUEL_TYPE_LABELS = {
    "E10": "E10 (95 RON, 10% ethanol)",
    "U91": "Unleaded 91",
    "E85": "E85",
    "P95": "Premium 95",
    "P98": "Premium 98",
    "DL": "Diesel",
    "PDL": "Premium Diesel",
    "B20": "B20 Biodiesel",
    "LPG": "LPG",
    "CNG": "CNG",
    "EV": "EV charging",
}

DEFAULT_FUEL_TYPES = ["P95", "P98", "U91", "E10", "DL"]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def station_label(station: Station, distance_km: float | None) -> str:
    """Human-readable label for a station option."""
    name = station.name or ""
    if station.brand and name.lower().startswith(station.brand.lower()):
        label = name  # brand already part of the name (e.g. "Ampol Foodary Armidale")
    else:
        label = f"{station.brand} {name}".strip() if station.brand else name
    address = f" — {station.address}" if station.address else ""
    distance = f" ({distance_km:.1f} km)" if distance_km is not None else ""
    return f"{label}{address}{distance}"


def stations_within_radius(
    stations: dict[int, Station], lat: float, lon: float, radius_km: float
) -> list[tuple[Station, float]]:
    """Return (station, distance_km) pairs within radius, sorted by distance."""
    nearby = []
    for station in stations.values():
        distance = haversine_km(lat, lon, station.latitude, station.longitude)
        if distance <= radius_km:
            nearby.append((station, distance))
    nearby.sort(key=lambda item: item[1])
    return nearby


def fuel_types_for_stations(
    stations: dict[int, Station],
    prices: dict[tuple[int, str], float],
    station_codes: list[int],
) -> set[str]:
    """Union of fuel types sold by the given stations."""
    available: set[str] = set()
    for code in station_codes:
        if code not in stations:
            continue
        for station_code, fuel_type in prices:
            if station_code == code:
                available.add(fuel_type)
    return {f for f in available if f in FUEL_TYPE_LABELS}
