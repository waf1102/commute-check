from enum import Enum
from typing import List, Optional
from sqlmodel import Field, SQLModel
from pydantic import BaseModel


class Status(str, Enum):
    GO = "Go"
    CAUTION = "Caution"
    NO_GO = "No-Go"

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

class CommuteBase(SQLModel):
    name: str = "Default Commute"
    lat: float
    lon: float
    webhook_url: Optional[str] = None
    schedule_time: str # HH:MM format
    days_of_week: str = "mon-fri"
    min_temp_caution: float = 45.0
    min_temp_no_go: float = 38.0
    max_wind_caution: float = 15.0
    max_wind_no_go: float = 25.0
    rain_threshold: float = 30.0

class Commute(CommuteBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class CommuteCreate(CommuteBase):
    pass

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str

