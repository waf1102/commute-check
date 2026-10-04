from enum import Enum
from typing import List, Optional, Tuple, Any, Union
from sqlmodel import Field, SQLModel, Relationship
from pydantic import BaseModel, field_validator, model_validator
from datetime import datetime, timezone
from sqlalchemy import Column, String
from sqlalchemy.types import TypeDecorator, JSON


class Status(str, Enum):
    GO = "Go"
    CAUTION = "Caution"
    NO_GO = "No-Go"


class UnitSystem(str, Enum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class CommuteType(str, Enum):
    RIDING = "riding"
    DRIVING = "driving"


class HourlyWeather(BaseModel):
    temperature: float
    apparent_temp: float
    wind_speed: float
    wind_gusts: float
    precip_prob: float
    weather_code: int


class HazardPinpoint(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None
    coordinates: Optional[Tuple[float, float]] = None
    estimated_time: Optional[str] = None
    time: Optional[str] = None
    encounter_time: Optional[str] = None
    parameter: Optional[str] = None
    parameter_breached: Optional[str] = None
    hazard: Optional[str] = None
    hazard_type: Optional[str] = None
    value: Optional[Union[float, str]] = None
    threshold: Optional[Union[float, str]] = None
    warning_message: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[Union[Status, str]] = Status.CAUTION
    location: Optional[str] = None
    location_name: Optional[str] = None
    title: Optional[str] = None
    weather_conditions: Optional[str] = None
    weather: Optional[HourlyWeather] = None
    risk_factors: List[str] = []

    def __init__(self, **data):
        if "coordinates" in data and data["coordinates"]:
            c = data["coordinates"]
            if "lat" not in data or data["lat"] is None:
                data["lat"] = float(c[0])
            if "lon" not in data or data["lon"] is None:
                data["lon"] = float(c[1])
        elif (
            "lat" in data
            and "lon" in data
            and data["lat"] is not None
            and data["lon"] is not None
        ):
            data["coordinates"] = (float(data["lat"]), float(data["lon"]))

        if "parameter" in data and "parameter_breached" not in data:
            data["parameter_breached"] = data["parameter"]
        elif "parameter_breached" in data and "parameter" not in data:
            data["parameter"] = data["parameter_breached"]

        if "hazard" in data and "parameter" not in data:
            data["parameter"] = data["hazard"]
        elif "parameter" in data and "hazard" not in data:
            data["hazard"] = data["parameter"]

        if "time" in data and "estimated_time" not in data:
            data["estimated_time"] = data["time"]
        elif "estimated_time" in data and "time" not in data:
            data["time"] = data["estimated_time"]

        if "encounter_time" in data and "estimated_time" not in data:
            data["estimated_time"] = data["encounter_time"]
        elif "estimated_time" in data and "encounter_time" not in data:
            data["encounter_time"] = data["estimated_time"]

        if "location" in data and "location_name" not in data:
            data["location_name"] = data["location"]
        elif "location_name" in data and "location" not in data:
            data["location"] = data["location_name"]

        if "estimated_time" not in data or data["estimated_time"] is None:
            data["estimated_time"] = ""
        if "parameter" not in data or data["parameter"] is None:
            data["parameter"] = data.get("hazard") or "weather"
        if "warning_message" not in data or data["warning_message"] is None:
            data["warning_message"] = (
                data.get("title")
                or data.get("description")
                or "Adverse weather conditions"
            )
        if "description" not in data or data["description"] is None:
            data["description"] = data["warning_message"]

        super().__init__(**data)

    def __eq__(self, other):
        if isinstance(other, dict):
            return all(getattr(self, k, None) == v for k, v in other.items())
        return super().__eq__(other)


class WaypointEvaluation(BaseModel):
    index: int = 0
    name: Optional[str] = None
    lat: float
    lon: float
    coordinates: Optional[Tuple[float, float]] = None
    estimated_arrival_time: str
    eta: Optional[str] = None
    weather: HourlyWeather
    status: Status
    score: int
    reasons: List[str] = []
    hazard_pinpoints: List[HazardPinpoint] = []

    def __init__(self, **data):
        if "coordinates" in data and data["coordinates"]:
            c = data["coordinates"]
            if "lat" not in data:
                data["lat"] = float(c[0])
            if "lon" not in data:
                data["lon"] = float(c[1])
        elif "lat" in data and "lon" in data:
            data["coordinates"] = (float(data["lat"]), float(data["lon"]))

        if "estimated_arrival_time" in data and "eta" not in data:
            data["eta"] = data["estimated_arrival_time"]
        elif "eta" in data and "estimated_arrival_time" not in data:
            data["estimated_arrival_time"] = data["eta"]

        super().__init__(**data)


class RouteSegment(BaseModel):
    segment_index: int = 0
    start_lat: float
    start_lon: float
    start_coord: Optional[Tuple[float, float]] = None
    end_lat: float
    end_lon: float
    end_coord: Optional[Tuple[float, float]] = None
    start_name: Optional[str] = None
    end_name: Optional[str] = None
    distance_km: float = 0.0
    duration_minutes: float = 0.0
    start_time: str = ""
    end_time: str = ""
    status: Status = Status.GO
    score: int = 100
    reasons: List[str] = []
    hazard_pinpoints: List[HazardPinpoint] = []
    weather: Optional[HourlyWeather] = None

    def __init__(self, **data):
        if "start_coord" in data and data["start_coord"]:
            c = data["start_coord"]
            if "start_lat" not in data:
                data["start_lat"] = float(c[0])
            if "start_lon" not in data:
                data["start_lon"] = float(c[1])
        elif "start_lat" in data and "start_lon" in data:
            data["start_coord"] = (float(data["start_lat"]), float(data["start_lon"]))

        if "end_coord" in data and data["end_coord"]:
            c = data["end_coord"]
            if "end_lat" not in data:
                data["end_lat"] = float(c[0])
            if "end_lon" not in data:
                data["end_lon"] = float(c[1])
        elif "end_lat" in data and "end_lon" in data:
            data["end_coord"] = (float(data["end_lat"]), float(data["end_lon"]))

        super().__init__(**data)


class AssessmentResult(BaseModel):
    status: Status
    score: int
    reasons: List[str]
    recommendation: str
    details: Optional[HourlyWeather] = None
    segments: List[RouteSegment] = []
    waypoint_evaluations: List[WaypointEvaluation] = []
    hazard_pinpoints: List[HazardPinpoint] = []
    waypoint_risks: Optional[List[Any]] = None
    commute_name: Optional[str] = None


class LegAssessment(BaseModel):
    leg_type: str  # "outbound" or "return"
    location_name: str
    schedule_time: str
    status: Status
    score: int
    reasons: List[str]
    weather: HourlyWeather
    segments: List[RouteSegment] = []
    waypoint_evaluations: List[WaypointEvaluation] = []
    hazard_pinpoints: List[HazardPinpoint] = []
    waypoint_risks: Optional[List[Any]] = None
    commute_name: Optional[str] = None


class RouteAssessmentResult(BaseModel):
    assessment_date: Optional[str] = None
    checked_at: Optional[str] = None
    timezone: str = "UTC"
    routing_estimated: bool = True
    overall_status: Status
    overall_score: int
    outbound_leg: LegAssessment
    return_leg: Optional[LegAssessment] = None
    recommendation: str
    segments: List[RouteSegment] = []
    waypoint_evaluations: List[WaypointEvaluation] = []
    hazard_pinpoints: List[HazardPinpoint] = []
    commute_name: Optional[str] = None


class AssessmentRequest(BaseModel):
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    dest_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    dest_lon: Optional[float] = Field(default=None, ge=-180, le=180)
    dest_name: Optional[str] = None
    departure_time: Optional[str] = None
    schedule_time: Optional[str] = None
    waypoints: Optional[List[Any]] = None
    min_temp_caution: float = 45.0
    min_temp_no_go: float = 38.0
    max_wind_caution: float = 15.0
    max_wind_no_go: float = 25.0
    rain_threshold: float = 30.0
    unit_system: UnitSystem = UnitSystem.IMPERIAL

    @model_validator(mode="before")
    @classmethod
    def legacy_limits(cls, value):
        if not isinstance(value, dict):
            return value
        value = dict(value)
        if value.get("min_temp") is not None:
            value.setdefault("min_temp_caution", value["min_temp"])
            value.setdefault("min_temp_no_go", float(value["min_temp"]) - 7)
        if value.get("max_wind") is not None:
            value.setdefault("max_wind_caution", value["max_wind"])
            value.setdefault("max_wind_no_go", float(value["max_wind"]) + 10)
        if value.get("max_precip") is not None:
            value.setdefault("rain_threshold", value["max_precip"])
        return value

    @field_validator("waypoints", mode="before")
    @classmethod
    def checked_waypoints(cls, value):
        from .routing import parse_coordinate

        if value is None:
            return []
        if not isinstance(value, list) or len(value) > 8:
            raise ValueError("Use at most 8 stops")
        for waypoint in value:
            parse_coordinate(waypoint)
        return value


class RouteCheckRequest(AssessmentRequest):
    commute_id: Optional[int] = None
    name: str = "Default Commute"
    origin_name: Optional[str] = None
    return_schedule_time: Optional[str] = "17:00"
    days_of_week: str = "mon-fri"
    timezone: str = "UTC"
    save_history: bool = False


DAY_NAME_MAP = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}
VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
VALID_NUMS = {"0", "1", "2", "3", "4", "5", "6"}


def validate_and_normalize_days_of_week(val: str) -> str:
    if not isinstance(val, str):
        raise ValueError("days_of_week must be a string")
    val = val.strip()
    if not val:
        raise ValueError("days_of_week cannot be empty")

    if val == "*":
        return "*"

    raw_parts = val.split(",")
    norm_parts = []
    for raw_p in raw_parts:
        p = raw_p.strip()
        if not p:
            raise ValueError("days_of_week contains empty day expression")
        if "-" in p:
            sub = p.split("-")
            if len(sub) != 2 or not sub[0].strip() or not sub[1].strip():
                raise ValueError(f"Invalid day range expression: {p}")
            s = DAY_NAME_MAP.get(sub[0].strip().lower(), sub[0].strip().lower())
            e = DAY_NAME_MAP.get(sub[1].strip().lower(), sub[1].strip().lower())
            if s not in VALID_DAYS and s not in VALID_NUMS:
                raise ValueError(f"Invalid weekday name or number: {sub[0]}")
            if e not in VALID_DAYS and e not in VALID_NUMS:
                raise ValueError(f"Invalid weekday name or number: {sub[1]}")
            norm_parts.append(f"{s}-{e}")
        else:
            token = DAY_NAME_MAP.get(p.lower(), p.lower())
            if token not in VALID_DAYS and token not in VALID_NUMS:
                raise ValueError(f"Invalid weekday name or number: {p}")
            norm_parts.append(token)

    normalized = ",".join(norm_parts)
    try:
        from apscheduler.triggers.cron import CronTrigger

        CronTrigger(day_of_week=normalized)
    except Exception as exc:
        raise ValueError(f"Invalid days_of_week expression: {val}") from exc

    return normalized


class Waypoint(BaseModel):
    id: Optional[Union[str, int]] = None
    name: str = ""
    lat: float
    lon: float
    order: int = 0
    status: Optional[str] = None

    @field_validator("lat")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError(f"Latitude must be between -90 and 90, got {v}")
        return v

    @field_validator("lon")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180.0 <= v <= 180.0):
            raise ValueError(f"Longitude must be between -180 and 180, got {v}")
        return v

    def __getitem__(self, item):
        return getattr(self, item)


def validate_and_sort_waypoints(v) -> List[Waypoint]:
    if v is None:
        return []
    if isinstance(v, str):
        import json

        try:
            v = json.loads(v)
        except Exception as exc:
            raise ValueError(f"Invalid JSON string for waypoints: {exc}") from exc
    if not isinstance(v, list):
        raise ValueError("waypoints must be a list")

    parsed = []
    for index, item in enumerate(v):
        if isinstance(item, Waypoint):
            parsed.append(item)
        elif isinstance(item, dict):
            from .routing import parse_coordinate

            lat, lon = parse_coordinate(item)
            parsed.append(
                Waypoint(
                    **{
                        **item,
                        "lat": lat,
                        "lon": lon,
                        "order": item.get("order", index),
                    }
                )
            )
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            parsed.append(Waypoint(lat=item[0], lon=item[1], order=index))
        elif hasattr(item, "model_dump"):
            parsed.append(Waypoint(**item.model_dump()))
        else:
            raise ValueError(f"Invalid waypoint item: {item}")
    return sorted(parsed, key=lambda wp: wp.order)


class WaypointsJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, list):
                result = []
                for item in value:
                    if isinstance(item, BaseModel):
                        result.append(item.model_dump())
                    elif isinstance(item, dict):
                        result.append(item)
                    else:
                        result.append(item)
                return result
            if isinstance(value, str):
                import json

                try:
                    return json.loads(value)
                except Exception:
                    return value
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            import json

            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except Exception:
                    pass
            if isinstance(value, list):
                return [
                    Waypoint(**item) if isinstance(item, dict) else item
                    for item in value
                ]
        return value or []


class CommuteBase(SQLModel):
    name: str = "Default Commute"
    origin_name: str = "Home"
    timezone: str = "UTC"
    lat: float
    lon: float
    dest_name: Optional[str] = None
    dest_lat: Optional[float] = None
    dest_lon: Optional[float] = None
    schedule_time: str  # HH:MM format
    return_schedule_time: Optional[str] = Field(
        default="17:00", sa_column=Column(String().evaluates_none(), nullable=True)
    )
    days_of_week: str = "mon-fri"
    webhook_url: Optional[str] = None
    min_temp_caution: float = 45.0
    min_temp_no_go: float = 38.0
    max_wind_caution: float = 15.0
    max_wind_no_go: float = 25.0
    rain_threshold: float = 30.0
    unit_system: UnitSystem = UnitSystem.IMPERIAL
    waypoints: Optional[List[Waypoint]] = Field(
        default_factory=list, sa_column=Column(WaypointsJSON)
    )

    @field_validator("days_of_week", mode="before")
    @classmethod
    def validate_days_of_week_field(cls, v):
        if v is None:
            return "mon-fri"
        return validate_and_normalize_days_of_week(v)

    @field_validator("waypoints", mode="before")
    @classmethod
    def validate_waypoints_field(cls, v):
        return validate_and_sort_waypoints(v)

    def __init__(self, **data):
        if "unit_system" in data and isinstance(data["unit_system"], str):
            try:
                data["unit_system"] = UnitSystem(data["unit_system"])
            except ValueError:
                pass
        if "days_of_week" in data:
            if data["days_of_week"] is None:
                data["days_of_week"] = "mon-fri"
            else:
                data["days_of_week"] = validate_and_normalize_days_of_week(
                    data["days_of_week"]
                )
        if "waypoints" in data:
            data["waypoints"] = validate_and_sort_waypoints(data["waypoints"])
        super().__init__(**data)

    def __setattr__(self, name, value):
        if name == "unit_system" and isinstance(value, str):
            try:
                value = UnitSystem(value)
            except ValueError:
                pass
        elif name == "days_of_week":
            if value is not None:
                value = validate_and_normalize_days_of_week(value)
            else:
                value = "mon-fri"
        elif name == "waypoints":
            if value is not None:
                value = validate_and_sort_waypoints(value)
            else:
                value = []
        super().__setattr__(name, value)


class Commute(CommuteBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    assessment_history: List["AssessmentHistory"] = Relationship(
        back_populates="commute"
    )


class CommuteCreate(CommuteBase):
    @model_validator(mode="after")
    def validate_settings(self):
        import math
        import re
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        if not self.name.strip():
            raise ValueError("Give your commute a name")
        for name, limit in [
            ("lat", 90),
            ("lon", 180),
            ("dest_lat", 90),
            ("dest_lon", 180),
        ]:
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or abs(value) > limit):
                raise ValueError(f"{name} must be between {-limit} and {limit}")
        if (self.dest_lat is None) != (self.dest_lon is None):
            raise ValueError("Choose a complete destination")
        for name in ("schedule_time", "return_schedule_time"):
            value = getattr(self, name)
            if value is not None and not re.fullmatch(
                r"(?:[01]\d|2[0-3]):[0-5]\d", value
            ):
                raise ValueError("Departure times must use HH:MM")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Choose a valid time zone")
        values = [
            self.min_temp_no_go,
            self.min_temp_caution,
            self.max_wind_caution,
            self.max_wind_no_go,
            self.rain_threshold,
        ]
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Weather limits must be finite numbers")
        if not all(
            -100 <= v <= 150 for v in (self.min_temp_no_go, self.min_temp_caution)
        ):
            raise ValueError("Temperature limits must be between -100 and 150")
        if self.min_temp_no_go > self.min_temp_caution:
            raise ValueError(
                "The avoid-riding temperature must be below the caution temperature"
            )
        if not 0 <= self.max_wind_caution <= self.max_wind_no_go:
            raise ValueError("Wind limits must increase from caution to avoid riding")
        if not 0 <= self.rain_threshold <= 100:
            raise ValueError("Rain chance must be between 0 and 100")
        if len(self.waypoints or []) > 8:
            raise ValueError("Use at most 8 stops")
        return self


class CommuteConfig(CommuteCreate):
    id: Optional[int] = None


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    assessment_history: List["AssessmentHistory"] = Relationship(back_populates="user")


class UserCreate(SQLModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        import re

        value = value.strip().lower()
        if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def valid_password(cls, value):
        if len(value) < 8 or len(value.encode("utf-8")) > 72:
            raise ValueError(
                "Use at least 8 characters and no more than 72 bytes for your password"
            )
        return value


class UserOut(SQLModel):
    id: int
    email: str


class AssessmentHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    commute_id: Optional[int] = Field(
        default=None, foreign_key="commute.id", index=True, nullable=True
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    leg_type: Optional[str] = Field(default=None, nullable=True)
    overall_status: Optional[str] = Field(default=None, nullable=True)
    overall_score: Optional[float] = Field(default=None, nullable=True)
    weather_reasons: Optional[str] = Field(default=None, nullable=True)
    weather_details: Optional[str] = Field(default=None, nullable=True)
    commute_type: Optional[str] = Field(default=None, nullable=True)
    commute_distance_km: Optional[float] = Field(default=0.0, nullable=True)
    duration_minutes: Optional[float] = Field(default=0.0, nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    user: Optional["User"] = Relationship(back_populates="assessment_history")
    commute: Optional["Commute"] = Relationship(back_populates="assessment_history")

    def __init__(self, **data):
        if "reasons" in data and "weather_reasons" not in data:
            val = data.pop("reasons")
            if isinstance(val, (list, dict)):
                import json

                data["weather_reasons"] = json.dumps(val)
            else:
                data["weather_reasons"] = str(val) if val is not None else None
        if "details" in data and "weather_details" not in data:
            val = data.pop("details")
            if isinstance(val, (list, dict)):
                import json

                data["weather_details"] = json.dumps(val)
            elif hasattr(val, "model_dump"):
                import json

                data["weather_details"] = json.dumps(val.model_dump())
            else:
                data["weather_details"] = str(val) if val is not None else None
        super().__init__(**data)

    @property
    def score(self) -> Optional[float]:
        return self.overall_score

    @property
    def reasons(self) -> List[str]:
        if not self.weather_reasons:
            return []
        try:
            import json

            parsed = json.loads(self.weather_reasons)
            if isinstance(parsed, list):
                return parsed
            return [str(parsed)]
        except Exception:
            return [self.weather_reasons]

    @property
    def details(self) -> Optional[dict]:
        if not self.weather_details:
            return None
        try:
            import json

            return json.loads(self.weather_details)
        except Exception:
            return None
