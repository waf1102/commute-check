import json
import pandas as pd
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
        if hasattr(assessment, "overall_status") and hasattr(assessment, "overall_score"):
            # RouteAssessmentResult
            if overall_status is None:
                overall_status = assessment.overall_status.value if hasattr(assessment.overall_status, "value") else str(assessment.overall_status)
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
                    details_dict["outbound"] = out_weather.model_dump() if hasattr(out_weather, "model_dump") else out_weather
                if hasattr(assessment, "return_leg") and assessment.return_leg:
                    ret_weather = getattr(assessment.return_leg, "weather", None)
                    details_dict["return"] = ret_weather.model_dump() if hasattr(ret_weather, "model_dump") else ret_weather
                weather_details = details_dict if details_dict else None
        elif hasattr(assessment, "weather") and hasattr(assessment, "leg_type"):
            # LegAssessment
            if overall_status is None:
                overall_status = assessment.status.value if hasattr(assessment.status, "value") else str(assessment.status)
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
                overall_status = assessment.status.value if hasattr(assessment.status, "value") else str(assessment.status)
            if overall_score is None:
                overall_score = float(assessment.score)
            if leg_type is None:
                leg_type = "outbound"
            if weather_reasons is None:
                weather_reasons = getattr(assessment, "reasons", None)
            if weather_details is None and getattr(assessment, "details", None):
                det = assessment.details
                weather_details = det.model_dump() if hasattr(det, "model_dump") else det

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
    db: Session,
    user_id: int,
    start_date: date,
    end_date: date
) -> List[Dict[str, Any]]:
    """
    Retrieves daily commute statistics for a given user within a date range.
    Aggregates data into days ridden, days driven, total days, average score,
    total distance commuted, time saved, and fuel saved.
    """
    if start_date > end_date:
        return []

    # Fetch raw data for the user within the date range
    # Convert date objects to datetime for comparison with AssessmentHistory.timestamp
    start_datetime = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=timezone.utc)
    end_datetime = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, 999999, tzinfo=timezone.utc)

    raw_data = db.exec(
        select(AssessmentHistory).where(
            AssessmentHistory.user_id == user_id,
            AssessmentHistory.timestamp >= start_datetime,
            AssessmentHistory.timestamp <= end_datetime
        ).order_by(AssessmentHistory.timestamp)
    ).all()

    if not raw_data:
        return []

    # Convert to list of dicts for pandas aggregation
    data_dicts = []
    for record in raw_data:
        score_val = record.overall_score
        if score_val is None:
            score_val = getattr(record, "score", None)
        if score_val is None and getattr(record, "assessment_result", None):
            score_val = getattr(record.assessment_result, "score", None)

        dist = float(record.commute_distance_km or 0.0)
        dur = float(record.duration_minutes or 0.0)

        data_dicts.append({
            "timestamp": record.timestamp,
            "commute_type": record.commute_type,
            "assessment_result_score": score_val,
            "distance_km": dist,
            "duration_minutes": dur,
        })

    df = pd.DataFrame(data_dicts)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date

    grouped = df.groupby('date')
    result = []
    for d, group in grouped:
        ridden = group[group['commute_type'] == 'riding']
        driven = group[group['commute_type'] == 'driving']
        days_ridden = int(len(ridden))
        days_driven = int(len(driven))
        days_total = days_ridden + days_driven

        scores = group['assessment_result_score'].dropna()
        avg_score = round(float(scores.mean()), 2) if len(scores) > 0 else 0.0
        total_dist = round(float(group['distance_km'].sum()), 2)

        ridden_dist = float(ridden['distance_km'].sum())
        ridden_dur = float(ridden['duration_minutes'].sum())

        # Fuel saved: based on standard 25 MPG car baseline: (miles / 25 mpg)
        # 1 km = 0.621371 miles
        fuel_saved = round((ridden_dist * 0.621371) / 25.0, 2) if ridden_dist > 0 else 0.0

        # Time saved: estimating ~20% commute time saved when riding vs driving traffic;
        # fallback to distance or count if duration not specified
        if ridden_dur > 0:
            time_saved = round(ridden_dur * 0.20, 2)
        elif ridden_dist > 0:
            time_saved = round(ridden_dist * 0.5, 2)
        elif days_ridden > 0:
            time_saved = round(days_ridden * 10.0, 2)
        else:
            time_saved = 0.0

        if days_total > 0 or avg_score > 0 or total_dist > 0:
            result.append({
                "date": d,
                "days_ridden": days_ridden,
                "days_driven": days_driven,
                "days_total": days_total,
                "avg_score": avg_score,
                "total_distance_km": total_dist,
                "time_saved_minutes": time_saved,
                "fuel_saved_gallons": fuel_saved,
            })

    return result

