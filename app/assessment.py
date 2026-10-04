"""One assessment path for saved checks and scheduled notifications."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from apscheduler.triggers.cron import CronTrigger
from .models import Commute, RouteAssessmentResult
from .engine import AssessmentEngine, _worst_status
from .client import WeatherClient


def departure_dates(commute: Commute, now: datetime | None = None, scheduled=False):
    zone = ZoneInfo(commute.timezone)
    now = (now or datetime.now(zone)).astimezone(zone)
    trigger = CronTrigger(
        day_of_week=commute.days_of_week, hour=0, minute=0, timezone=zone
    )
    # Include the previous day for an overnight return still ahead of us.
    for offset in range(-1, 9):
        day = (now + timedelta(days=offset)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if trigger.get_next_fire_time(None, day) != day:
            continue
        outbound = datetime.fromisoformat(
            f"{day.date()}T{commute.schedule_time}"
        ).replace(tzinfo=zone)
        returning = None
        if commute.return_schedule_time:
            returning = datetime.fromisoformat(
                f"{day.date()}T{commute.return_schedule_time}"
            ).replace(tzinfo=zone)
            if returning <= outbound:
                returning += timedelta(days=1)
        end = returning or outbound
        if end >= now - (timedelta(minutes=5) if scheduled else timedelta()) and (
            offset >= 0 or returning
        ):
            return outbound, returning
    raise ValueError("No departure found in the forecast window")


async def assess_commute(
    commute: Commute,
    client: WeatherClient,
    engine: AssessmentEngine,
    *,
    now=None,
    scheduled=False,
) -> RouteAssessmentResult:
    outbound, returning = departure_dates(commute, now, scheduled)
    coords = [(commute.lat, commute.lon)]
    names = [commute.origin_name or "Home"]
    for waypoint in sorted(commute.waypoints or [], key=lambda w: w.order):
        coords.append((waypoint.lat, waypoint.lon))
        names.append(waypoint.name or "Stop")
    if commute.dest_lat is not None and commute.dest_lon is not None:
        coords.append((commute.dest_lat, commute.dest_lon))
        names.append(commute.dest_name or "Work")
    forecasts = await client.fetch_weather_batch(coords, commute.unit_system)
    estimated = True
    durations = []
    if len(coords) > 1:
        directions = await engine.routing_service.get_route_directions(
            coords[0], coords[-1], coords[1:-1]
        )
        durations = [leg.duration / 60 for leg in directions.legs]
        estimated = directions.fallback
    result = engine.assess_timed_route(
        coords,
        outbound.isoformat(),
        forecasts,
        commute,
        segment_durations=durations,
        waypoint_names=names,
    )
    if returning:
        reverse_durations = []
        if len(coords) > 1:
            directions = await engine.routing_service.get_route_directions(
                coords[-1], coords[0], list(reversed(coords[1:-1]))
            )
            reverse_durations = [leg.duration / 60 for leg in directions.legs]
            estimated = estimated or directions.fallback
        back = engine.assess_timed_route(
            list(reversed(coords)),
            returning.isoformat(),
            list(reversed(forecasts)),
            commute,
            segment_durations=reverse_durations,
            waypoint_names=list(reversed(names)),
        )
        result.return_leg = back.outbound_leg.model_copy(update={"leg_type": "return"})
        result.overall_status = _worst_status(
            result.overall_status, back.overall_status
        )
        result.overall_score = min(result.overall_score, back.overall_score)
        result.segments += back.segments
        result.waypoint_evaluations += back.waypoint_evaluations
        result.hazard_pinpoints += back.hazard_pinpoints
    result.recommendation = {
        "Go": "Conditions are within your weather limits.",
        "Caution": "Some conditions need extra care. Review both trips before riding.",
        "No-Go": "Conditions exceed your limits. Consider another way to travel.",
    }[result.overall_status]
    result.assessment_date = outbound.date().isoformat()
    result.checked_at = datetime.now(ZoneInfo("UTC")).isoformat()
    result.timezone = commute.timezone
    result.routing_estimated = estimated
    result.commute_name = commute.name
    return result


def return_days(commute: Commute) -> str:
    """An overnight return belongs to the day after each outbound commute day."""
    if (
        not commute.return_schedule_time
        or commute.return_schedule_time > commute.schedule_time
    ):
        return commute.days_of_week
    trigger = CronTrigger(
        day_of_week=commute.days_of_week, hour=0, minute=0, timezone="UTC"
    )
    monday = datetime(2026, 1, 5, tzinfo=ZoneInfo("UTC"))
    days = []
    for index in range(7):
        day = monday + timedelta(days=index)
        if trigger.get_next_fire_time(None, day) == day:
            days.append((index + 1) % 7)
    return ",".join(str(day) for day in sorted(days))
