from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from datetime import date
from typing import List

from app.database import get_session
from app.security import get_current_user
from app.models import User
from .schemas import DailyCommuteStats
from .service import get_daily_commute_stats

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/commute-stats/daily", response_model=List[DailyCommuteStats])
def get_daily_stats(
    user_id: int,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Retrieves daily commute statistics for a given user within a date range.
    The user_id in the path must match the authenticated user's ID.
    """
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access analytics for this user.")

    return get_daily_commute_stats(db, user_id, start_date, end_date)
