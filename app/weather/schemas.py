from pydantic import BaseModel
from typing import List
from app.models import UnitSystem

class ThresholdsSchema(BaseModel):
    min_temp_caution: float
    min_temp_no_go: float
    max_wind_caution: float
    max_wind_no_go: float
    rain_threshold: float

class HourlyForecastItem(BaseModel):
    time: str
    temperature: float
    apparent_temp: float
    wind_speed: float
    precip_prob: float
    weather_code: int

class ForecastResponse(BaseModel):
    unit_system: UnitSystem
    thresholds: ThresholdsSchema
    hourly: List[HourlyForecastItem]
