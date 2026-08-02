from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import Optional
import httpx

from app.database import get_session
from app.security import get_current_user
from app.models import User, Commute, UnitSystem
from app import client as app_client
from .schemas import ForecastResponse, ThresholdsSchema, HourlyForecastItem

router = APIRouter(prefix="/weather", tags=["weather"])

def safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def safe_int(val, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

@router.get("/forecast", response_model=ForecastResponse)
async def get_weather_forecast(
    commute_id: Optional[int] = Query(default=None),
    unit_system: UnitSystem = Query(default=UnitSystem.IMPERIAL),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    query = select(Commute).where(Commute.user_id == current_user.id)
    if commute_id:
        query = query.where(Commute.id == commute_id)
    commute = db.exec(query).first()
    
    if not commute:
        raise HTTPException(status_code=404, detail="Commute configuration not found")

    try:
        raw_weather = await app_client.fetch_weather(commute.lat, commute.lon, unit_system=unit_system)
    except Exception as e:
        raise HTTPException(status_code=502, detail="Weather service unavailable")

    hourly_raw = raw_weather.get("hourly", {})
    
    times = hourly_raw.get("time", [])
    temps = hourly_raw.get("temperature_2m", [])
    app_temps = hourly_raw.get("apparent_temperature", [])
    winds = hourly_raw.get("wind_speed_10m", [])
    precips = hourly_raw.get("precipitation_probability", [])
    codes = hourly_raw.get("weather_code", [])

    hourly_items = []
    for i in range(min(len(times), 24)):
        hourly_items.append(HourlyForecastItem(
            time=str(times[i]) if i < len(times) and times[i] is not None else "",
            temperature=safe_float(temps[i] if i < len(temps) else None),
            apparent_temp=safe_float(app_temps[i] if i < len(app_temps) else None),
            wind_speed=safe_float(winds[i] if i < len(winds) else None),
            precip_prob=safe_float(precips[i] if i < len(precips) else None),
            weather_code=safe_int(codes[i] if i < len(codes) else None)
        ))

    thresholds = ThresholdsSchema(
        min_temp_caution=commute.min_temp_caution,
        min_temp_no_go=commute.min_temp_no_go,
        max_wind_caution=commute.max_wind_caution,
        max_wind_no_go=commute.max_wind_no_go,
        rain_threshold=commute.rain_threshold
    )

    return ForecastResponse(
        unit_system=unit_system,
        thresholds=thresholds,
        hourly=hourly_items
    )
