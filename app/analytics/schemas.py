from pydantic import BaseModel
from datetime import date as dt_date, datetime as dt_datetime
from typing import Optional, List, Any

class DailyCommuteStats(BaseModel):
    date: dt_date
    days_ridden: int
    days_driven: int
    days_total: int
    avg_score: Optional[float] = 0.0
    total_distance_km: Optional[float] = 0.0
    time_saved_minutes: Optional[float] = 0.0
    fuel_saved_gallons: Optional[float] = 0.0

class DecisionRecordRequest(BaseModel):
    commute_id: Optional[int] = None
    decision: Optional[str] = None
    commute_type: Optional[str] = None
    date: Optional[dt_date] = None
    timestamp: Optional[dt_datetime] = None
    commute_distance_km: Optional[float] = None
    distance_km: Optional[float] = None
    duration_minutes: Optional[float] = None
    assessment_history_id: Optional[int] = None
    notes: Optional[str] = None

class DecisionRecordResponse(BaseModel):
    id: int
    user_id: int
    commute_id: Optional[int] = None
    commute_type: Optional[str] = None
    timestamp: dt_datetime
    leg_type: Optional[str] = None
    overall_status: Optional[str] = None
    overall_score: Optional[float] = None
    commute_distance_km: float
    duration_minutes: float
    created_at: dt_datetime
