from pydantic import BaseModel
from datetime import date

class DailyCommuteStats(BaseModel):
    date: date
    days_ridden: int
    days_driven: int
    days_total: int
    avg_score: float
