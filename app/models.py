from enum import Enum
from typing import List, Optional
from sqlmodel import Field, SQLModel, Relationship
from pydantic import BaseModel
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

class RouteAssessmentResult(BaseModel):
    overall_status: Status
    overall_score: int
    outbound_leg: LegAssessment
    return_leg: Optional[LegAssessment] = None
    recommendation: str

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

    def __init__(self, **data):
        if "unit_system" in data and isinstance(data["unit_system"], str):
            try:
                data["unit_system"] = UnitSystem(data["unit_system"])
            except ValueError:
                pass
        super().__init__(**data)

    def __setattr__(self, name, value):
        if name == "unit_system" and isinstance(value, str):
            try:
                value = UnitSystem(value)
            except ValueError:
                pass
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

