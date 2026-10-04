import httpx
import asyncio
from typing import Optional, Tuple, List
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from cachetools import TTLCache
from .models import HourlyWeather, UnitSystem


def parse_hourly_at_time(
    data: dict, target_time: Optional[str] = None
) -> HourlyWeather:
    """Interpolate a complete forecast; never substitute zeros or another date."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import math

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        raise ValueError("Forecast has no timestamps")
    zone = ZoneInfo(data.get("timezone") or "UTC")
    stamps = [datetime.fromisoformat(t).replace(tzinfo=zone) for t in times]
    if target_time is None:
        target = datetime.now(zone)
    elif "T" in target_time:
        target = datetime.fromisoformat(target_time)
        target = (
            target.replace(tzinfo=zone)
            if target.tzinfo is None
            else target.astimezone(zone)
        )
    else:
        target = datetime.fromisoformat(
            f"{datetime.now(zone).date().isoformat()}T{target_time}"
        ).replace(tzinfo=zone)
    if target < stamps[0] or target > stamps[-1]:
        raise ValueError("Requested departure is outside the available forecast")
    right = next(i for i, stamp in enumerate(stamps) if stamp >= target)
    left = max(0, right - 1) if stamps[right] != target else right
    fraction = (
        0
        if left == right
        else (target - stamps[left]).total_seconds()
        / (stamps[right] - stamps[left]).total_seconds()
    )

    def value(key, interpolate=True):
        array = hourly.get(key, [])
        try:
            lo, hi = float(array[left]), float(array[right])
        except (IndexError, TypeError, ValueError):
            raise ValueError(f"Forecast is missing {key}") from None
        if not math.isfinite(lo) or not math.isfinite(hi):
            raise ValueError(f"Invalid forecast value for {key}")
        if not interpolate:
            # Preserve hazardous codes on either side of an interpolated hour.
            hazards = {56, 57, 66, 67, 71, 73, 75, 77, 85, 86, 95, 96, 99}
            return int(lo if int(lo) in hazards else hi if int(hi) in hazards else lo)
        return lo + (hi - lo) * fraction

    return HourlyWeather(
        temperature=value("temperature_2m"),
        apparent_temp=value("apparent_temperature"),
        wind_speed=value("wind_speed_10m"),
        wind_gusts=value("wind_gusts_10m"),
        precip_prob=value("precipitation_probability"),
        weather_code=value("weather_code", False),
    )


class WeatherClient:
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self):
        # Cache for weather results, 15 minute TTL
        self._cache = TTLCache(maxsize=100, ttl=900)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    async def fetch_weather(
        self, lat: float, lon: float, unit_system: UnitSystem = UnitSystem.IMPERIAL
    ) -> dict:
        cache_key = f"raw_{lat}_{lon}_{unit_system.value}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m,weather_code",
            "timezone": "auto",
            "temperature_unit": "celsius"
            if unit_system == UnitSystem.METRIC
            else "fahrenheit",
            "wind_speed_unit": "kmh" if unit_system == UnitSystem.METRIC else "mph",
            "forecast_days": 9,
            "past_days": 1,
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            self._cache[cache_key] = data
            return data

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    async def get_hourly_weather(
        self, lat: float, lon: float, unit_system: UnitSystem = UnitSystem.IMPERIAL
    ) -> HourlyWeather:
        cache_key = f"{lat}_{lon}_{unit_system.value}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        data = await self.fetch_weather(lat, lon, unit_system)
        result = parse_hourly_at_time(data)
        self._cache[cache_key] = result
        return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def get_hourly_weather_sync(
        self, lat: float, lon: float, unit_system: UnitSystem = UnitSystem.IMPERIAL
    ) -> HourlyWeather:
        cache_key = f"{lat}_{lon}_{unit_system.value}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m,weather_code",
            "timezone": "auto",
            "temperature_unit": "celsius"
            if unit_system == UnitSystem.METRIC
            else "fahrenheit",
            "wind_speed_unit": "kmh" if unit_system == UnitSystem.METRIC else "mph",
            "forecast_days": 9,
            "past_days": 1,
        }

        with httpx.Client(timeout=10) as client:
            response = client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            result = parse_hourly_at_time(data)
            self._cache[cache_key] = result
            return result

    async def fetch_weather_batch(
        self,
        coordinates: List[Tuple[float, float]],
        unit_system: UnitSystem = UnitSystem.IMPERIAL,
    ) -> List[dict]:
        """
        Concurrent batch forecast retrieval across multiple route coordinates.
        Leverages the TTL cache to avoid redundant calls and deduplicates identical coordinates.
        """
        if not coordinates:
            return []

        norm_coords: List[Tuple[float, float]] = []
        for c in coordinates:
            if isinstance(c, (list, tuple)):
                norm_coords.append((float(c[0]), float(c[1])))
            elif isinstance(c, dict):
                norm_coords.append((float(c["lat"]), float(c["lon"])))
            elif hasattr(c, "lat") and hasattr(c, "lon"):
                norm_coords.append((float(c.lat), float(c.lon)))
            else:
                raise ValueError(f"Invalid coordinate format: {c}")

        unique_coords = list(dict.fromkeys(norm_coords))
        results = await asyncio.gather(
            *(
                self.fetch_weather(lat, lon, unit_system=unit_system)
                for lat, lon in unique_coords
            )
        )
        coord_map = dict(zip(unique_coords, results))
        return [coord_map[coord] for coord in norm_coords]

    async def get_hourly_weather_batch(
        self,
        coordinates: List[Tuple[float, float]],
        target_times: Optional[List[Optional[str]]] = None,
        unit_system: UnitSystem = UnitSystem.IMPERIAL,
    ) -> List[HourlyWeather]:
        forecasts = await self.fetch_weather_batch(coordinates, unit_system=unit_system)
        weathers: List[HourlyWeather] = []
        for i, data in enumerate(forecasts):
            t_time = target_times[i] if target_times and i < len(target_times) else None
            weathers.append(parse_hourly_at_time(data, target_time=t_time))
        return weathers


_default_weather_client = WeatherClient()


async def fetch_weather(
    lat: float, lon: float, unit_system: UnitSystem = UnitSystem.IMPERIAL
) -> dict:
    return await _default_weather_client.fetch_weather(lat, lon, unit_system)


async def fetch_weather_batch(
    coordinates: List[Tuple[float, float]],
    unit_system: UnitSystem = UnitSystem.IMPERIAL,
) -> List[dict]:
    return await _default_weather_client.fetch_weather_batch(
        coordinates, unit_system=unit_system
    )


async def fetch_route_weather(
    origin_lat: float,
    origin_lon: float,
    dest_lat: Optional[float] = None,
    dest_lon: Optional[float] = None,
    unit_system: UnitSystem = UnitSystem.IMPERIAL,
) -> Tuple[dict, Optional[dict]]:
    if dest_lat is not None and dest_lon is not None:
        origin_data, dest_data = await asyncio.gather(
            fetch_weather(origin_lat, origin_lon, unit_system=unit_system),
            fetch_weather(dest_lat, dest_lon, unit_system=unit_system),
        )
        return origin_data, dest_data
    else:
        origin_data = await fetch_weather(
            origin_lat, origin_lon, unit_system=unit_system
        )
        return origin_data, None
