import json
from datetime import date, datetime, timezone
from typing import List, Dict, Any, Optional, Union

from sqlmodel import Session, select
from app.models import AssessmentHistory, Commute


def record_assessment_run(
    session: Session,
    *,
    user_id: Optional[int] = None,
    commute_id: Optional[int] = None,
    assessment: Optional[Any] = None,
    leg_type: Optional[str] = None,
    overall_status: Optional[str] = None,
    overall_score: Optional[float] = None,
    weather_reasons: Optional[Union[List[str], str]] = None,
    weather_details: Optional[Union[dict, str]] = None,
    commute_type: Optional[str] = None,
    commute_distance_km: float = 0.0,
    duration_minutes: float = 0.0,
    timestamp: Optional[datetime] = None,
) -> AssessmentHistory:
    """
    Persist an assessment run to AssessmentHistory.
    Usable by scheduled checks and on-demand assessments.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    elif timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    # Infer user_id from commute if omitted
    if user_id is None and commute_id is not None:
        commute = session.get(Commute, commute_id)
        if commute and commute.user_id:
            user_id = commute.user_id

    # Extract information from assessment object
    if assessment is not None:
        if hasattr(assessment, "overall_status") and hasattr(
            assessment, "overall_score"
        ):
            # RouteAssessmentResult
            if overall_status is None:
                overall_status = (
                    assessment.overall_status.value
                    if hasattr(assessment.overall_status, "value")
                    else str(assessment.overall_status)
                )
            if overall_score is None:
                overall_score = float(assessment.overall_score)
            if leg_type is None:
                leg_type = "overall"
            if weather_reasons is None:
                reasons = []
                if hasattr(assessment, "outbound_leg") and assessment.outbound_leg:
                    reasons.extend(getattr(assessment.outbound_leg, "reasons", []))
                if hasattr(assessment, "return_leg") and assessment.return_leg:
                    reasons.extend(getattr(assessment.return_leg, "reasons", []))
                weather_reasons = reasons if reasons else None
            if weather_details is None:
                details_dict = {}
                if hasattr(assessment, "outbound_leg") and assessment.outbound_leg:
                    out_weather = getattr(assessment.outbound_leg, "weather", None)
                    details_dict["outbound"] = (
                        out_weather.model_dump()
                        if hasattr(out_weather, "model_dump")
                        else out_weather
                    )
                if hasattr(assessment, "return_leg") and assessment.return_leg:
                    ret_weather = getattr(assessment.return_leg, "weather", None)
                    details_dict["return"] = (
                        ret_weather.model_dump()
                        if hasattr(ret_weather, "model_dump")
                        else ret_weather
                    )
                weather_details = details_dict if details_dict else None
        elif hasattr(assessment, "weather") and hasattr(assessment, "leg_type"):
            # LegAssessment
            if overall_status is None:
                overall_status = (
                    assessment.status.value
                    if hasattr(assessment.status, "value")
                    else str(assessment.status)
                )
            if overall_score is None:
                overall_score = float(assessment.score)
            if leg_type is None:
                leg_type = assessment.leg_type
            if weather_reasons is None:
                weather_reasons = getattr(assessment, "reasons", None)
            if weather_details is None and getattr(assessment, "weather", None):
                w = assessment.weather
                weather_details = w.model_dump() if hasattr(w, "model_dump") else w
        elif hasattr(assessment, "status") and hasattr(assessment, "score"):
            # AssessmentResult
            if overall_status is None:
                overall_status = (
                    assessment.status.value
                    if hasattr(assessment.status, "value")
                    else str(assessment.status)
                )
            if overall_score is None:
                overall_score = float(assessment.score)
            if leg_type is None:
                leg_type = "outbound"
            if weather_reasons is None:
                weather_reasons = getattr(assessment, "reasons", None)
            if weather_details is None and getattr(assessment, "details", None):
                det = assessment.details
                weather_details = (
                    det.model_dump() if hasattr(det, "model_dump") else det
                )

    # Serialize reasons/details strings if needed
    reasons_str = None
    if weather_reasons is not None:
        if isinstance(weather_reasons, (list, dict)):
            reasons_str = json.dumps(weather_reasons)
        else:
            reasons_str = str(weather_reasons)

    details_str = None
    if weather_details is not None:
        if isinstance(weather_details, (list, dict)):
            details_str = json.dumps(weather_details)
        elif hasattr(weather_details, "model_dump"):
            details_str = json.dumps(weather_details.model_dump())
        else:
            details_str = str(weather_details)

    history_entry = AssessmentHistory(
        user_id=user_id,
        commute_id=commute_id,
        timestamp=timestamp,
        leg_type=leg_type or "overall",
        overall_status=overall_status,
        overall_score=overall_score,
        weather_reasons=reasons_str,
        weather_details=details_str,
        commute_type=commute_type,
        commute_distance_km=commute_distance_km,
        duration_minutes=duration_minutes,
        created_at=datetime.now(timezone.utc),
    )
    session.add(history_entry)
    session.commit()
    session.refresh(history_entry)
    return history_entry


# Alias for versatility
log_assessment_run = record_assessment_run


def get_daily_commute_stats(
    db: Session, user_id: int, start_date: date, end_date: date
) -> List[Dict[str, Any]]:
    """
    Retrieves daily commute statistics for a given user within a date range.
    Aggregates data into days ridden, days driven, total days, and average score.
    """
    # Fetch raw data for the user within the date range
    # Convert date objects to datetime for comparison with AssessmentHistory.timestamp
    start_datetime = datetime(
        start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc
    )
    end_datetime = datetime(
        end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc
    )  # End of the day

    raw_data = db.exec(
        select(AssessmentHistory)
        .where(
            AssessmentHistory.user_id == user_id,
            AssessmentHistory.timestamp >= start_datetime,
            AssessmentHistory.timestamp <= end_datetime,
        )
        .order_by(AssessmentHistory.timestamp)
    ).all()

    if not raw_data:
        return []

    days = {}
    for record in raw_data:
        key = record.timestamp.date()
        day = days.setdefault(
            key,
            {
                "date": key,
                "days_ridden": 0,
                "days_driven": 0,
                "scores": [],
                "total_distance_km": 0,
            },
        )
        day["total_distance_km"] += record.commute_distance_km or 0
        if record.commute_type == "riding":
            day["days_ridden"] = 1
        if record.commute_type == "driving":
            day["days_driven"] = 1
        if record.overall_score is not None:
            day["scores"].append(record.overall_score)
    result = []
    for day in days.values():
        scores = day.pop("scores")
        day["days_total"] = day["days_ridden"] + day["days_driven"]
        day["avg_score"] = round(sum(scores) / len(scores), 2) if scores else 0
        result.append(day)
    return result
