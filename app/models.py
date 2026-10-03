from enum import Enum
from typing import List, Optional
from sqlmodel import Field, SQLModel, Relationship
from pydantic import BaseModel, field_validator
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, func


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

class AssessmentResult(BaseModel):
    status: Status
    score: int
    reasons: List[str]
    recommendation: str
    details: Optional[HourlyWeather] = None

class LegAssessment(BaseModel):
    leg_type: str  # "outbound" or "return"
    location_name: str
    schedule_time: str
    status: Status
    score: int
    reasons: List[str]
    weather: HourlyWeather

class HazardPinpoint(BaseModel):
    lat: float
    lon: float
    location_name: Optional[str] = None
    title: Optional[str] = None
    weather_conditions: Optional[str] = None
    weather: Optional[HourlyWeather] = None
    risk_factors: List[str] = []
    severity: Optional[str] = None

class RouteAssessmentResult(BaseModel):
    overall_status: Status
    overall_score: int
    outbound_leg: LegAssessment
    return_leg: Optional[LegAssessment] = None
    recommendation: str
    hazard_pinpoints: Optional[List[HazardPinpoint]] = []


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


class CommuteBase(SQLModel):
    name: str = "Default Commute"
    lat: float
    lon: float
    dest_name: Optional[str] = None
    dest_lat: Optional[float] = None
    dest_lon: Optional[float] = None
    schedule_time: str  # HH:MM format
    return_schedule_time: Optional[str] = "17:00"
    days_of_week: str = "mon-fri"
    webhook_url: Optional[str] = None
    min_temp_caution: float = 45.0
    min_temp_no_go: float = 38.0
    max_wind_caution: float = 15.0
    max_wind_no_go: float = 25.0
    rain_threshold: float = 30.0
    unit_system: UnitSystem = UnitSystem.IMPERIAL
    waypoints: Optional[str] = Field(default=None, nullable=True)

    @field_validator("waypoints", mode="before")
    @classmethod
    def validate_waypoints_field(cls, v):
        if v is None:
            return None
        if isinstance(v, (list, dict)):
            import json
            return json.dumps(v)
        return str(v)

    @field_validator("days_of_week", mode="before")
    @classmethod
    def validate_days_of_week_field(cls, v):
        if v is None:
            return "mon-fri"
        return validate_and_normalize_days_of_week(v)

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
                data["days_of_week"] = validate_and_normalize_days_of_week(data["days_of_week"])
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
        super().__setattr__(name, value)

class Commute(CommuteBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    assessment_history: List["AssessmentHistory"] = Relationship(back_populates="commute")

class CommuteCreate(CommuteBase):
    pass

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    assessment_history: List["AssessmentHistory"] = Relationship(back_populates="user")

class UserCreate(SQLModel):
    email: str
    password: str

class UserOut(SQLModel):
    id: int
    email: str

class AssessmentHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    commute_id: Optional[int] = Field(default=None, foreign_key="commute.id", index=True, nullable=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    leg_type: Optional[str] = Field(default=None, nullable=True)
    overall_status: Optional[str] = Field(default=None, nullable=True)
    overall_score: Optional[float] = Field(default=None, nullable=True)
    weather_reasons: Optional[str] = Field(default=None, nullable=True)
    weather_details: Optional[str] = Field(default=None, nullable=True)
    commute_type: Optional[str] = Field(default=None, nullable=True)
    commute_distance_km: Optional[float] = Field(default=0.0, nullable=True)
    duration_minutes: Optional[float] = Field(default=0.0, nullable=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

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

