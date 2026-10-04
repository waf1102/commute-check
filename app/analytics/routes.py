from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from datetime import date, datetime, timezone, timedelta
from typing import List, Optional

from app.database import get_session
from app.security import get_current_user
from app.models import User, AssessmentHistory, Commute
from .schemas import DailyCommuteStats, DecisionRecordRequest, DecisionRecordResponse
from .service import get_daily_commute_stats

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/commute-stats/daily", response_model=List[DailyCommuteStats])
def get_daily_stats(
    user_id: Optional[str] = None,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """
    Retrieves daily commute statistics for a given user within a date range.
    The user_id in the path must match the authenticated user's ID.
    """
    try:
        requested_user = int(user_id) if user_id else current_user.id
    except ValueError as exc:
        raise HTTPException(422, "user_id must be an integer") from exc
    if requested_user != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access analytics for this user."
        )

    if end_date < start_date or (end_date - start_date).days > 366:
        raise HTTPException(422, "Choose a date range of up to one year")
    return get_daily_commute_stats(db, current_user.id, start_date, end_date)


@router.post("/record-decision", response_model=DecisionRecordResponse)
def record_commute_decision(
    request: DecisionRecordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """
    Records whether a user decided to ride or drive for their commute.
    Updates an existing assessment history record if matched, or persists a new record.
    """
    if request.commute_id is not None:
        commute = db.get(Commute, request.commute_id)
        if not commute or commute.user_id != current_user.id:
            raise HTTPException(404, "Commute not found")
    raw_decision = request.decision or request.commute_type
    if not raw_decision:
        raise HTTPException(
            status_code=422, detail="decision or commute_type must be provided"
        )

    norm = raw_decision.strip().lower()
    if norm in ("riding", "ride", "rode", "bike", "bicycle", "motorcycle"):
        commute_type = "riding"
    elif norm in ("driving", "drive", "drove", "car"):
        commute_type = "driving"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision '{raw_decision}'. Must be 'riding' or 'driving'.",
        )

    dist = (
        request.commute_distance_km
        if request.commute_distance_km is not None
        else (request.distance_km if request.distance_km is not None else 0.0)
    )
    dur = request.duration_minutes if request.duration_minutes is not None else 0.0

    # 1. Direct update by assessment_history_id
    if request.assessment_history_id:
        record = db.get(AssessmentHistory, request.assessment_history_id)
        if not record:
            raise HTTPException(
                status_code=404, detail="Assessment history record not found"
            )
        if record.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to modify this assessment record",
            )
        record.commute_type = commute_type
        if dist:
            record.commute_distance_km = dist
        if dur:
            record.duration_minutes = dur
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    # Match the requested calendar day in the caller's timestamp offset.
    target_dt = request.timestamp or datetime.now(timezone.utc)
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)
    target_date = request.date or target_dt.date()
    start_of_day = datetime(
        target_date.year, target_date.month, target_date.day, tzinfo=target_dt.tzinfo
    )
    end_of_day = (start_of_day + timedelta(days=1)).astimezone(timezone.utc)
    start_of_day = start_of_day.astimezone(timezone.utc)

    query = select(AssessmentHistory).where(
        AssessmentHistory.user_id == current_user.id,
        AssessmentHistory.timestamp >= start_of_day,
        AssessmentHistory.timestamp < end_of_day,
    )
    if request.commute_id is not None:
        query = query.where(AssessmentHistory.commute_id == request.commute_id)

    candidates = db.exec(query.order_by(AssessmentHistory.timestamp.desc())).all()
    unassigned = next(
        (c for c in candidates if c.commute_type in ("riding", "driving")), None
    ) or next(iter(candidates), None)

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
        timestamp=datetime.combine(target_date, target_dt.timetz()),
        commute_type=commute_type,
        commute_distance_km=dist,
        duration_minutes=dur,
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return new_entry
