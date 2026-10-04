from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import Optional, List

from app.database import get_session
from app.security import get_current_user
from app.models import User, Commute, UnitSystem
from app import client as app_client
from .schemas import ForecastResponse, ThresholdsSchema, HourlyForecastItem

router = APIRouter(prefix="/weather", tags=["weather"])


def safe_float(val) -> float:
    import math

    try:
        value = float(val)
        if not math.isfinite(value):
            raise ValueError("non-finite forecast")
        return value
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "Weather forecast is incomplete") from exc


def safe_int(val) -> int:
    return int(safe_float(val))


@router.get("/forecast", response_model=ForecastResponse)
async def get_weather_forecast(
    commute_id: Optional[int] = Query(default=None),
    lat: Optional[float] = Query(default=None),
    lon: Optional[float] = Query(default=None),
    dest_lat: Optional[float] = Query(default=None),
    dest_lon: Optional[float] = Query(default=None),
    unit_system: Optional[UnitSystem] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    commute = None
    if commute_id or (lat is None or lon is None):
        query = select(Commute).where(Commute.user_id == current_user.id)
        if commute_id:
            query = query.where(Commute.id == commute_id)
        commute = db.exec(query).first()

    if not commute and (lat is None or lon is None):
        raise HTTPException(status_code=404, detail="Commute configuration not found")

    if commute_id and not commute:
        raise HTTPException(404, "Commute configuration not found")
    unit_system = unit_system or (
        commute.unit_system if commute else UnitSystem.IMPERIAL
    )

    origin_lat = lat if lat is not None else commute.lat
    origin_lon = lon if lon is not None else commute.lon
    d_lat = (
        dest_lat if dest_lat is not None else (commute.dest_lat if commute else None)
    )
    d_lon = (
        dest_lon if dest_lon is not None else (commute.dest_lon if commute else None)
    )

    try:
        origin_raw, dest_raw = await app_client.fetch_route_weather(
            origin_lat, origin_lon, d_lat, d_lon, unit_system=unit_system
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail="Weather service unavailable")

    def parse_hourly(raw_weather: dict) -> List[HourlyForecastItem]:
        hourly_raw = raw_weather.get("hourly", {})
        times = hourly_raw.get("time", [])
        if not times:
            raise HTTPException(503, "Weather forecast is incomplete")
        temps = hourly_raw.get("temperature_2m", [])
        app_temps = hourly_raw.get("apparent_temperature", [])
        winds = hourly_raw.get("wind_speed_10m", [])
        precips = hourly_raw.get("precipitation_probability", [])
        codes = hourly_raw.get("weather_code", [])

        hourly_items = []
        from datetime import datetime
        from zoneinfo import ZoneInfo

        today = (
            datetime.now(ZoneInfo(raw_weather.get("timezone") or "UTC"))
            .date()
            .isoformat()
        )
        indices = [i for i, stamp in enumerate(times) if stamp[:10] == today]
        # Small dated responses from integrations may contain only a requested day.
        if not indices:
            indices = list(range(min(len(times), 24)))
        for i in indices[:24]:
            hourly_items.append(
                HourlyForecastItem(
                    time=str(times[i])
                    if i < len(times) and times[i] is not None
                    else "",
                    temperature=safe_float(temps[i] if i < len(temps) else None),
                    apparent_temp=safe_float(
                        app_temps[i] if i < len(app_temps) else None
                    ),
                    wind_speed=safe_float(winds[i] if i < len(winds) else None),
                    precip_prob=safe_float(precips[i] if i < len(precips) else None),
                    weather_code=safe_int(codes[i] if i < len(codes) else None),
                )
            )
        return hourly_items

    hourly_items = parse_hourly(origin_raw)
    destination_hourly_items = parse_hourly(dest_raw) if dest_raw else None

    if commute:
        thresholds = ThresholdsSchema(
            min_temp_caution=commute.min_temp_caution,
            min_temp_no_go=commute.min_temp_no_go,
            max_wind_caution=commute.max_wind_caution,
            max_wind_no_go=commute.max_wind_no_go,
            rain_threshold=commute.rain_threshold,
        )
        if unit_system != commute.unit_system:
            metric = unit_system == UnitSystem.METRIC
            for field in ("min_temp_caution", "min_temp_no_go"):
                value = getattr(thresholds, field)
                setattr(
                    thresholds,
                    field,
                    (value - 32) * 5 / 9 if metric else value * 9 / 5 + 32,
                )
            for field in ("max_wind_caution", "max_wind_no_go"):
                value = getattr(thresholds, field)
                setattr(
                    thresholds, field, value * 1.609344 if metric else value / 1.609344
                )
    else:
        thresholds = ThresholdsSchema(
            min_temp_caution=45.0,
            min_temp_no_go=38.0,
            max_wind_caution=15.0,
            max_wind_no_go=25.0,
            rain_threshold=30.0,
        )

    return ForecastResponse(
        unit_system=unit_system,
        thresholds=thresholds,
        hourly=hourly_items,
        destination_hourly=destination_hourly_items,
    )
