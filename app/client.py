import httpx
import asyncio
from typing import Optional, Tuple, List, Any, Union, Dict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cachetools import TTLCache
from .models import HourlyWeather, UnitSystem

def parse_hourly_at_time(data: dict, target_time: Optional[str] = None) -> HourlyWeather:
    hourly = data.get("hourly", {})
    idx = 0
    if target_time and "time" in hourly and hourly["time"]:
        time_list = hourly["time"]
        try:
            if "T" in target_time:
                prefix = target_time[:13]
                matched = [i for i, t in enumerate(time_list) if str(t).startswith(prefix)]
                if matched:
                    idx = matched[0]
                else:
                    time_part = target_time.split("T")[1]
                    hour = int(time_part.split(":")[0])
                    if 0 <= hour < len(time_list):
                        idx = hour
            else:
                hour = int(target_time.split(":")[0])
                if 0 <= hour < len(time_list):
                    idx = hour
        except Exception:
            idx = 0
    
    def safe_val(arr, i, default=0.0):
        if not arr or i >= len(arr) or arr[i] is None:
            return default
        return arr[i]

    return HourlyWeather(
        temperature=safe_val(hourly.get("temperature_2m"), idx),
        apparent_temp=safe_val(hourly.get("apparent_temperature"), idx),
        wind_speed=safe_val(hourly.get("wind_speed_10m"), idx),
        wind_gusts=safe_val(hourly.get("wind_gusts_10m"), idx),
        precip_prob=safe_val(hourly.get("precipitation_probability"), idx),
        weather_code=int(safe_val(hourly.get("weather_code"), idx, default=0))
    )

class WeatherClient:
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self):
        # Cache for weather results, 15 minute TTL
        self._cache = TTLCache(maxsize=100, ttl=900)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def fetch_weather(self, lat: float, lon: float, unit_system: UnitSystem = UnitSystem.IMPERIAL) -> dict:
        cache_key = f"raw_{lat}_{lon}_{unit_system.value}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m,weather_code",
            "timezone": "auto",
            "temperature_unit": "celsius" if unit_system == UnitSystem.METRIC else "fahrenheit",
            "wind_speed_unit": "kmh" if unit_system == UnitSystem.METRIC else "mph",
            "forecast_days": 1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            self._cache[cache_key] = data
            return data

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def get_hourly_weather(self, lat: float, lon: float, unit_system: UnitSystem = UnitSystem.IMPERIAL) -> HourlyWeather:
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
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    def get_hourly_weather_sync(self, lat: float, lon: float, unit_system: UnitSystem = UnitSystem.IMPERIAL) -> HourlyWeather:
        cache_key = f"{lat}_{lon}_{unit_system.value}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m,weather_code",
            "timezone": "auto",
            "temperature_unit": "celsius" if unit_system == UnitSystem.METRIC else "fahrenheit",
            "wind_speed_unit": "kmh" if unit_system == UnitSystem.METRIC else "mph",
            "forecast_days": 1
        }
        
        with httpx.Client() as client:
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
            *(self.fetch_weather(lat, lon, unit_system=unit_system) for lat, lon in unique_coords)
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

async def fetch_weather(lat: float, lon: float, unit_system: UnitSystem = UnitSystem.IMPERIAL) -> dict:
    return await _default_weather_client.fetch_weather(lat, lon, unit_system)

async def fetch_weather_batch(
    coordinates: List[Tuple[float, float]],
    unit_system: UnitSystem = UnitSystem.IMPERIAL,
) -> List[dict]:
    return await _default_weather_client.fetch_weather_batch(coordinates, unit_system=unit_system)

async def fetch_route_weather(
    origin_lat: float,
    origin_lon: float,
    dest_lat: Optional[float] = None,
    dest_lon: Optional[float] = None,
    unit_system: UnitSystem = UnitSystem.IMPERIAL
) -> Tuple[dict, Optional[dict]]:
    if dest_lat is not None and dest_lon is not None:
        origin_data, dest_data = await asyncio.gather(
            fetch_weather(origin_lat, origin_lon, unit_system=unit_system),
            fetch_weather(dest_lat, dest_lon, unit_system=unit_system)
        )
        return origin_data, dest_data
    else:
        origin_data = await fetch_weather(origin_lat, origin_lon, unit_system=unit_system)
        return origin_data, None
