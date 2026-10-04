from pydantic import BaseModel
from datetime import date as Date, datetime
from typing import Optional


class DailyCommuteStats(BaseModel):
    date: Date
    days_ridden: int
    days_driven: int
    days_total: int
    avg_score: float
    total_distance_km: float = 0


class DecisionRecordRequest(BaseModel):
    commute_id: Optional[int] = None
    decision: Optional[str] = None
    commute_type: Optional[str] = None
    date: Optional[Date] = None
    timestamp: Optional[datetime] = None
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
    timestamp: datetime
    leg_type: Optional[str] = None
    overall_status: Optional[str] = None
    overall_score: Optional[float] = None
    commute_distance_km: float
    duration_minutes: float
    created_at: datetime
