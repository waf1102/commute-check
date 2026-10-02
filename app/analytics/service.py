import pandas as pd
from datetime import date, datetime, timezone
from typing import List, Dict, Any

from sqlmodel import Session, select
from app.models import AssessmentHistory

def get_daily_commute_stats(
    db: Session,
    user_id: int,
    start_date: date,
    end_date: date
) -> List[Dict[str, Any]]:
    """
    Retrieves daily commute statistics for a given user within a date range.
    Aggregates data into days ridden, days driven, total days, and average score.
    """
    # Fetch raw data for the user within the date range
    # Convert date objects to datetime for comparison with AssessmentHistory.timestamp
    start_datetime = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
    end_datetime = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc) # End of the day

    raw_data = db.exec(
        select(AssessmentHistory).where(
            AssessmentHistory.user_id == user_id,
            AssessmentHistory.timestamp >= start_datetime,
            AssessmentHistory.timestamp <= end_datetime
        ).order_by(AssessmentHistory.timestamp)
    ).all()

    if not raw_data:
        return []

    # Convert to list of dicts for pandas
    # Ensure all relevant fields are present, including assessment_result for score
    data_dicts = []
    for record in raw_data:
        data_dicts.append({
            "timestamp": record.timestamp,
            "commute_type": record.commute_type,
            "assessment_result_score": getattr(record.assessment_result, "score", None) if getattr(record, "assessment_result", None) else getattr(record, "score", None)
        })

    df = pd.DataFrame(data_dicts)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    # Fill any missing assessment scores with a default (e.g., 0) before aggregation if needed
    # Or handle them during aggregation. For avg_score, NaN will be ignored.

    # Resample to daily frequency and aggregate
    daily_stats = df.resample('D').agg(
        days_ridden=('commute_type', lambda x: (x == 'riding').sum()),
        days_driven=('commute_type', lambda x: (x == 'driving').sum()),
        avg_score=('assessment_result_score', 'mean')
    ).fillna(0) # Fill NaN for days with no data

    # Calculate days_total
    daily_stats['days_total'] = daily_stats['days_ridden'] + daily_stats['days_driven']

    # Convert DataFrame to a list of dicts for API response
    result = []
    for index, row in daily_stats.iterrows():
        # Only include days where there was some activity or score
        if row['days_total'] > 0 or row['avg_score'] > 0:
            result.append({
                "date": index.date(), # Convert timestamp index back to date object
                "days_ridden": int(row['days_ridden']),
                "days_driven": int(row['days_driven']),
                "days_total": int(row['days_total']),
                "avg_score": round(row['avg_score'], 2) if row['avg_score'] is not None else None
            })
    return result
