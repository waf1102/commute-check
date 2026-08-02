import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cachetools import TTLCache
from .models import HourlyWeather, UnitSystem

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
            
            hourly = data.get("hourly", {})
            
            result = HourlyWeather(
                temperature=hourly.get("temperature_2m", [0])[0],
                apparent_temp=hourly.get("apparent_temperature", [0])[0],
                wind_speed=hourly.get("wind_speed_10m", [0])[0],
                wind_gusts=hourly.get("wind_gusts_10m", [0])[0],
                precip_prob=hourly.get("precipitation_probability", [0])[0],
                weather_code=hourly.get("weather_code", [0])[0]
            )
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
            
            hourly = data.get("hourly", {})
            
            result = HourlyWeather(
                temperature=hourly.get("temperature_2m", [0])[0],
                apparent_temp=hourly.get("apparent_temperature", [0])[0],
                wind_speed=hourly.get("wind_speed_10m", [0])[0],
                wind_gusts=hourly.get("wind_gusts_10m", [0])[0],
                precip_prob=hourly.get("precipitation_probability", [0])[0],
                weather_code=hourly.get("weather_code", [0])[0]
            )
            self._cache[cache_key] = result
            return result

_default_weather_client = WeatherClient()

async def fetch_weather(lat: float, lon: float, unit_system: UnitSystem = UnitSystem.IMPERIAL) -> dict:
    return await _default_weather_client.fetch_weather(lat, lon, unit_system)
