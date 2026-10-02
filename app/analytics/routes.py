from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from datetime import date, datetime, timezone
from typing import List, Optional

from app.database import get_session
from app.security import get_current_user
from app.models import User, AssessmentHistory
from .schemas import DailyCommuteStats, DecisionRecordRequest, DecisionRecordResponse
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

@router.post("/record-decision", response_model=DecisionRecordResponse)
def record_commute_decision(
    request: DecisionRecordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Records whether a user decided to ride or drive for their commute.
    Updates an existing assessment history record if matched, or persists a new record.
    """
    raw_decision = request.decision or request.commute_type
    if not raw_decision:
        raise HTTPException(status_code=422, detail="decision or commute_type must be provided")

    norm = raw_decision.strip().lower()
    if norm in ("riding", "ride", "rode", "bike", "bicycle", "motorcycle"):
        commute_type = "riding"
    elif norm in ("driving", "drive", "drove", "car"):
        commute_type = "driving"
    else:
        raise HTTPException(status_code=400, detail=f"Invalid decision '{raw_decision}'. Must be 'riding' or 'driving'.")

    dist = request.commute_distance_km if request.commute_distance_km is not None else (request.distance_km if request.distance_km is not None else 0.0)
    dur = request.duration_minutes if request.duration_minutes is not None else 0.0

    # 1. Direct update by assessment_history_id
    if request.assessment_history_id:
        record = db.get(AssessmentHistory, request.assessment_history_id)
        if not record:
            raise HTTPException(status_code=404, detail="Assessment history record not found")
        if record.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this assessment record")
        record.commute_type = commute_type
        if dist:
            record.commute_distance_km = dist
        if dur:
            record.duration_minutes = dur
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    # 2. Match today's assessment run if present without a decision
    target_dt = request.timestamp or datetime.now(timezone.utc)
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)
    target_date = request.date or target_dt.date()
    start_of_day = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    end_of_day = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)

    query = select(AssessmentHistory).where(
        AssessmentHistory.user_id == current_user.id,
        AssessmentHistory.timestamp >= start_of_day,
        AssessmentHistory.timestamp <= end_of_day
    )
    if request.commute_id is not None:
        query = query.where(AssessmentHistory.commute_id == request.commute_id)

    candidates = db.exec(query.order_by(AssessmentHistory.timestamp.desc())).all()
    unassigned = next((c for c in candidates if not c.commute_type or c.commute_type in ("undecided", "unknown")), None)

    if unassigned:
        unassigned.commute_type = commute_type
        if dist:
            unassigned.commute_distance_km = dist
        if dur:
            unassigned.duration_minutes = dur
        db.add(unassigned)
        db.commit()
        db.refresh(unassigned)
        return unassigned

    # 3. Create a new record
    new_entry = AssessmentHistory(
        user_id=current_user.id,
        commute_id=request.commute_id,
        timestamp=target_dt,
        commute_type=commute_type,
        commute_distance_km=dist,
        duration_minutes=dur,
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return new_entry

