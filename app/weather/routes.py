from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import Optional

from app.database import get_session
from app.security import get_current_user
from app.models import User, Commute, UnitSystem
from app import client as app_client
from .schemas import ForecastResponse, ThresholdsSchema, HourlyForecastItem

router = APIRouter(prefix="/weather", tags=["weather"])

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

    raw_weather = await app_client.fetch_weather(commute.lat, commute.lon, unit_system=unit_system)
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
            time=str(times[i]),
            temperature=float(temps[i]) if i < len(temps) else 0.0,
            apparent_temp=float(app_temps[i]) if i < len(app_temps) else 0.0,
            wind_speed=float(winds[i]) if i < len(winds) else 0.0,
            precip_prob=float(precips[i]) if i < len(precips) else 0.0,
            weather_code=int(codes[i]) if i < len(codes) else 0
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
