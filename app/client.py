import httpx
from .models import HourlyWeather

class WeatherClient:
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    async def get_hourly_weather(self, lat: float, lon: float) -> HourlyWeather:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m,weather_code",
            "timezone": "auto",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "forecast_days": 1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            hourly = data.get("hourly", {})
            
            return HourlyWeather(
                temperature=hourly.get("temperature_2m", [0])[0],
                apparent_temp=hourly.get("apparent_temperature", [0])[0],
                wind_speed=hourly.get("wind_speed_10m", [0])[0],
                wind_gusts=hourly.get("wind_gusts_10m", [0])[0],
                precip_prob=hourly.get("precipitation_probability", [0])[0],
                weather_code=hourly.get("weather_code", [0])[0]
            )

    def get_hourly_weather_sync(self, lat: float, lon: float) -> HourlyWeather:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m,weather_code",
            "timezone": "auto",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "forecast_days": 1
        }
        
        with httpx.Client() as client:
            response = client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            hourly = data.get("hourly", {})
            
            return HourlyWeather(
                temperature=hourly.get("temperature_2m", [0])[0],
                apparent_temp=hourly.get("apparent_temperature", [0])[0],
                wind_speed=hourly.get("wind_speed_10m", [0])[0],
                wind_gusts=hourly.get("wind_gusts_10m", [0])[0],
                precip_prob=hourly.get("precipitation_probability", [0])[0],
                weather_code=hourly.get("weather_code", [0])[0]
            )
