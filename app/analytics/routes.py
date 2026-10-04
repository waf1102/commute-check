from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from datetime import date, datetime, timezone, timedelta
from typing import List, Optional, Union

from app.database import get_session
from app.security import get_current_user
from app.models import User, AssessmentHistory
from .schemas import DailyCommuteStats, DecisionRecordRequest, DecisionRecordResponse
from .service import get_daily_commute_stats

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/commute-stats/daily", response_model=List[DailyCommuteStats])
def get_daily_stats(
    user_id: Optional[Union[int, str]] = Query(default=None, description="User ID (defaults to current user)"),
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Retrieves daily commute statistics for a given user within a date range.
    Defaults to current authenticated user's ID if user_id is omitted or empty.
    """
    if user_id is None or (isinstance(user_id, str) and user_id.strip() == ""):
        target_user_id = current_user.id
    else:
        try:
            target_user_id = int(user_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Invalid user_id: must be an integer")

    if target_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access analytics for this user.")

    return get_daily_commute_stats(db, target_user_id, start_date, end_date)

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

    # 2. Match unassigned assessment run
    target_dt = request.timestamp or datetime.now(timezone.utc)
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)

    # Determine date range for searching candidates
    # Handle timezone differences across local day boundaries
    if request.date:
        target_date = request.date
        # Search from start to end of target_date in UTC, buffered by 14 hours for timezone offsets
        start_bound = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc) - timedelta(hours=14)
        end_bound = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, 999999, tzinfo=timezone.utc) + timedelta(hours=14)
    else:
        # Default to today / past 24 hours around target_dt
        start_bound = target_dt - timedelta(hours=24)
        end_bound = target_dt + timedelta(hours=6)

    query = select(AssessmentHistory).where(
        AssessmentHistory.user_id == current_user.id,
        AssessmentHistory.timestamp >= start_bound,
        AssessmentHistory.timestamp <= end_bound
    )
    if request.commute_id is not None:
        query = query.where(AssessmentHistory.commute_id == request.commute_id)

    candidates = db.exec(query.order_by(AssessmentHistory.timestamp.desc())).all()

    # Look for an unassigned candidate
    unassigned = None
    if request.date:
        tz = target_dt.tzinfo or timezone.utc
        for c in candidates:
            if not c.commute_type or c.commute_type in ("undecided", "unknown", ""):
                c_date_utc = c.timestamp.date()
                c_date_local = c.timestamp.astimezone(tz).date() if c.timestamp.tzinfo else c_date_utc
                if c_date_utc == target_date or c_date_local == target_date:
                    unassigned = c
                    break
    else:
        unassigned = next(
            (c for c in candidates if not c.commute_type or c.commute_type in ("undecided", "unknown", "")),
            None
        )

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

