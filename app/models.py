from enum import Enum
from typing import List, Optional
from sqlmodel import Field, SQLModel, Relationship
from pydantic import BaseModel
from datetime import datetime
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

class Commute(CommuteBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")

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
    timestamp: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    commute_type: str = Field(nullable=False)
    commute_distance_km: float = Field(nullable=False)
    duration_minutes: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    user: Optional["User"] = Relationship(back_populates="assessment_history")
