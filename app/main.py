from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlmodel import Session, select
from typing import List, Optional, Tuple
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()


from .models import (
    Commute,
    CommuteCreate,
    CommuteConfig,
    AssessmentResult,
    RouteAssessmentResult,
    UnitSystem,
    User,
    AssessmentRequest,
    RouteCheckRequest,
)
from .engine import AssessmentEngine
from .assessment import assess_commute, return_days
from .client import WeatherClient
from .notifications import NotificationService
from .database import engine, get_session, create_db_and_tables
from .security import router as auth_router, get_current_user, get_current_user_optional
from .analytics.routes import router as analytics_router
from .analytics.service import record_assessment_run
from .weather.routes import router as weather_router
from .push.routes import router as push_router
from .notifications import dispatch_web_push_notification
from .routing import routing_service, RouteDirectionsRequest, RouteDirectionsResponse

# --- Scheduler Setup ---
JOBS_DB_URL = os.getenv("JOBS_DB_URL", "sqlite:///jobs.db")
jobstores = {"default": SQLAlchemyJobStore(url=JOBS_DB_URL)}
scheduler = AsyncIOScheduler(jobstores=jobstores)

engine_instance = AssessmentEngine()
client_instance = WeatherClient()
notification_service_instance = NotificationService()


def clear_commute_jobs(commute_id: int):
    """Removes all scheduled jobs for a commute."""
    for job_id in [
        f"commute_check_{commute_id}_outbound",
        f"commute_check_{commute_id}_return",
        f"commute_check_{commute_id}",
    ]:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)


async def run_commute_check(commute_id: int, leg_type: str = "outbound"):
    try:
        return await _run_commute_check(commute_id, leg_type)
    except Exception as exc:
        print(
            f"Scheduled assessment failed for commute {commute_id}: {type(exc).__name__}"
        )
        return None


async def _run_commute_check(commute_id: int, leg_type: str):
    """Fetch commute, run route assessment, and send notification for corresponding leg."""
    with Session(engine) as session:
        commute = session.get(Commute, commute_id)
        if not commute:
            print(f"Error: Could not find commute with id {commute_id}")
            return None

        print(f"Running assessment for commute: {commute.name} (leg: {leg_type})")
        try:
            route_assessment = await assess_commute(
                commute, client_instance, engine_instance, scheduled=True
            )
        except Exception as exc:
            print(f"Assessment unavailable for commute {commute_id}: {exc}")
            return None

        leg_key = leg_type.lower()
        if "return" in leg_key and route_assessment.return_leg:
            leg_assessment = route_assessment.return_leg
        else:
            leg_assessment = route_assessment.outbound_leg

        if commute and commute.name:
            leg_assessment.commute_name = commute.name

        if commute.webhook_url:
            try:
                await notification_service_instance.send_notification(
                    commute.webhook_url, leg_assessment, leg_type=leg_type
                )
            except Exception:
                print(f"Notification delivery failed for commute {commute_id}")
        if commute.user_id:
            title, body = notification_service_instance._format_message(
                leg_assessment,
                leg_type=leg_type,
                commute_name=commute.name if commute else None,
            )
            pinpoints = notification_service_instance.extract_hazard_pinpoints(
                leg_assessment
            )
            has_route_hazard = bool(pinpoints)
            hazard_count = len(pinpoints)
            primary_hazard_location = ""
            if pinpoints:
                first_p = pinpoints[0]
                primary_hazard_location = (
                    first_p.get("location")
                    or first_p.get("location_name")
                    or first_p.get("name")
                    or ""
                )
            dispatch_web_push_notification(
                commute.user_id,
                title,
                body,
                session,
                url="/",
                has_route_hazard=has_route_hazard,
                hazard_count=hazard_count,
                primary_hazard_location=primary_hazard_location,
                assessment=leg_assessment,
            )

        # Automatically persist assessment run
        try:
            record_assessment_run(
                session=session,
                user_id=commute.user_id,
                commute_id=commute.id,
                assessment=leg_assessment,
                leg_type=leg_type,
                overall_status=route_assessment.overall_status.value
                if hasattr(route_assessment.overall_status, "value")
                else str(route_assessment.overall_status),
                overall_score=float(route_assessment.overall_score),
            )
        except Exception as e:
            print(f"Failed to persist assessment history: {e}")

        print(
            f"Assessment complete for {commute.name} ({leg_type}). Score: {leg_assessment.score}"
        )
        return leg_assessment


def schedule_commute_check(commute: Commute):
    """Adds or updates independent outbound and return jobs in the scheduler for a given commute."""
    if commute.id is None:
        return

    # Clean up legacy job if present
    legacy_job_id = f"commute_check_{commute.id}"
    if scheduler.get_job(legacy_job_id):
        scheduler.remove_job(legacy_job_id)

    # 1. Outbound job
    outbound_job_id = f"commute_check_{commute.id}_outbound"
    if scheduler.get_job(outbound_job_id):
        scheduler.remove_job(outbound_job_id)

    if commute.schedule_time:
        parts = commute.schedule_time.strip().split(":")
        outbound_hour, outbound_minute = parts[0].strip(), parts[1].strip()
        scheduler.add_job(
            run_commute_check,
            "cron",
            hour=outbound_hour,
            minute=outbound_minute,
            day_of_week=commute.days_of_week or "mon-fri",
            timezone=commute.timezone,
            id=outbound_job_id,
            args=[commute.id, "outbound"],
            replace_existing=True,
        )
        print(
            f"Scheduled outbound job '{outbound_job_id}' to run at {commute.schedule_time} on days: {commute.days_of_week}."
        )

    # 2. Return job
    return_job_id = f"commute_check_{commute.id}_return"
    if scheduler.get_job(return_job_id):
        scheduler.remove_job(return_job_id)

    if commute.return_schedule_time and commute.return_schedule_time.strip():
        parts = commute.return_schedule_time.strip().split(":")
        return_hour, return_minute = parts[0].strip(), parts[1].strip()
        scheduler.add_job(
            run_commute_check,
            "cron",
            hour=return_hour,
            minute=return_minute,
            day_of_week=return_days(commute),
            timezone=commute.timezone,
            id=return_job_id,
            args=[commute.id, "return"],
            replace_existing=True,
        )
        print(
            f"Scheduled return job '{return_job_id}' to run at {commute.return_schedule_time} on days: {commute.days_of_week}."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    create_db_and_tables()
    scheduler.start()

    # Schedule existing commutes
    with Session(engine) as session:
        commutes = session.exec(select(Commute)).all()
        for commute in commutes:
            print(f"Scheduling job for existing commute: {commute.name}")
            try:
                schedule_commute_check(commute)
            except (ValueError, LookupError) as exc:
                print(f"Commute {commute.id} needs its schedule updated: {exc}")

    yield
    # Shutdown logic
    scheduler.shutdown()


# --- FastAPI App ---
app = FastAPI(title="Commute Check API", lifespan=lifespan)

# CORS Middleware
origins = ["http://localhost:5173", "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .places import router as places_router

app.include_router(places_router)
app.include_router(auth_router)
app.include_router(analytics_router)
app.include_router(analytics_router, prefix="/api")
app.include_router(weather_router)
app.include_router(weather_router, prefix="/api")
app.include_router(push_router)
app.include_router(push_router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/config", response_model=List[Commute])
@app.get("/api/config", response_model=List[Commute])
@app.get("/commute", response_model=List[Commute])
@app.get("/api/commute", response_model=List[Commute])
def read_config(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
    commutes = session.exec(select(Commute).where(Commute.user_id == user.id)).all()
    return commutes


@app.post("/config", response_model=Commute)
@app.post("/api/config", response_model=Commute)
@app.post("/commute", response_model=Commute)
@app.post("/api/commute", response_model=Commute)
def create_or_update_config(
    commute_data: CommuteConfig,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if commute_data.id is not None:
        existing = session.get(Commute, commute_data.id)
        if not existing or existing.user_id != user.id:
            raise HTTPException(
                status_code=404, detail="Commute not found or not authorized"
            )
        for key, value in commute_data.model_dump(exclude={"id"}).items():
            setattr(existing, key, value)
        commute = existing
    else:
        commute = Commute.model_validate(commute_data, update={"user_id": user.id})
    session.add(commute)
    session.commit()
    session.refresh(commute)
    schedule_commute_check(commute)
    return commute


@app.get("/commutes/{commute_id}", response_model=Commute)
@app.get("/api/commutes/{commute_id}", response_model=Commute)
@app.get("/commute/{commute_id}", response_model=Commute)
@app.get("/api/commute/{commute_id}", response_model=Commute)
@app.get("/config/{commute_id}", response_model=Commute)
@app.get("/api/config/{commute_id}", response_model=Commute)
def get_commute(
    commute_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    commute = session.get(Commute, commute_id)
    if not commute or commute.user_id != user.id:
        raise HTTPException(404, "Commute not found")
    return commute


@app.delete("/config/{commute_id}")
@app.delete("/api/config/{commute_id}")
@app.delete("/commute/{commute_id}")
@app.delete("/api/commute/{commute_id}")
def delete_config(
    commute_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    commute = session.get(Commute, commute_id)
    if not commute or commute.user_id != user.id:
        raise HTTPException(
            status_code=404, detail="Commute not found or not authorized"
        )

    session.delete(commute)
    session.commit()

    # Remove from scheduler
    clear_commute_jobs(commute_id)

    return {"status": "deleted"}


@app.post("/assess", response_model=AssessmentResult)
@app.post("/api/assess", response_model=AssessmentResult)
async def assess_weather_post(request: AssessmentRequest):
    """
    Manually assess weather via POST for given coordinates, waypoints, and thresholds.
    """
    lat = request.lat
    lon = request.lon
    if lat is None or lon is None:
        raise HTTPException(
            status_code=400, detail="Latitude and longitude are required"
        )

    waypoints_raw = request.waypoints
    unit_system = request.unit_system
    departure_time = request.departure_time or request.schedule_time or "08:00"

    thresholds = Commute(
        lat=lat,
        lon=lon,
        dest_name=request.dest_name,
        dest_lat=request.dest_lat,
        dest_lon=request.dest_lon,
        schedule_time=departure_time,
        min_temp_caution=request.min_temp_caution,
        min_temp_no_go=request.min_temp_no_go,
        max_wind_caution=request.max_wind_caution,
        max_wind_no_go=request.max_wind_no_go,
        rain_threshold=request.rain_threshold,
        unit_system=unit_system,
    )

    if waypoints_raw or (
        thresholds.dest_lat is not None and thresholds.dest_lon is not None
    ):
        coords: List[Tuple[float, float]] = [(lat, lon)]
        waypoint_names: List[str] = [thresholds.name or "Origin"]

        if waypoints_raw:
            from .routing import parse_coordinate

            for i, w in enumerate(waypoints_raw):
                coords.append(parse_coordinate(w))
                name = (
                    w.get("name") if isinstance(w, dict) else getattr(w, "name", None)
                )
                waypoint_names.append(name or f"Waypoint {i + 1}")

        if thresholds.dest_lat is not None and thresholds.dest_lon is not None:
            coords.append((thresholds.dest_lat, thresholds.dest_lon))
            waypoint_names.append(thresholds.dest_name or "Destination")

        try:
            forecasts = await client_instance.fetch_weather_batch(
                coords, unit_system=unit_system
            )
        except Exception as e:
            print(f"Weather API error in batch fetch: {e}")
            raise HTTPException(
                status_code=503, detail="Weather API is currently unavailable"
            )

        try:
            route_res = engine_instance.assess_timed_route(
                coordinates=coords,
                departure_time=departure_time,
                weather_data=forecasts,
                commute=thresholds,
                waypoint_names=waypoint_names,
            )
        except ValueError as exc:
            raise HTTPException(
                503, "Weather forecast is incomplete or unavailable for this departure"
            ) from exc

        return AssessmentResult(
            status=route_res.overall_status,
            score=route_res.overall_score,
            reasons=route_res.outbound_leg.reasons,
            recommendation=route_res.recommendation,
            details=route_res.outbound_leg.weather,
            segments=route_res.segments,
            waypoint_evaluations=route_res.waypoint_evaluations,
            hazard_pinpoints=route_res.hazard_pinpoints,
        )
    else:
        try:
            raw = await client_instance.fetch_weather(lat, lon, unit_system)
            from .client import parse_hourly_at_time

            weather = parse_hourly_at_time(raw, departure_time)
        except Exception as e:
            print(f"Weather API error: {e}")
            raise HTTPException(
                status_code=503, detail="Weather API is currently unavailable"
            )

        assessment = engine_instance.assess(weather, thresholds)
        return assessment


@app.get("/api/assess", response_model=AssessmentResult)
@app.get("/assess", response_model=AssessmentResult)
async def assess_weather(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    min_temp: float = 45.0,
    max_temp: float = 95.0,
    max_wind: float = 15.0,
    max_precip: float = 30.0,
    unit_system: UnitSystem = UnitSystem.IMPERIAL,
    dest_lat: Optional[float] = Query(default=None, ge=-90, le=90),
    dest_lon: Optional[float] = Query(default=None, ge=-180, le=180),
    dest_name: Optional[str] = None,
    departure_time: Optional[str] = None,
    schedule_time: Optional[str] = None,
):
    """
    Manually assess weather for given coordinates and thresholds.
    """
    if dest_lat is not None or dest_lon is not None:
        if dest_lat is None or dest_lon is None:
            raise HTTPException(422, "Choose a complete destination")
        return await assess_weather_post(
            AssessmentRequest(
                lat=lat,
                lon=lon,
                dest_lat=dest_lat,
                dest_lon=dest_lon,
                dest_name=dest_name,
                departure_time=departure_time or schedule_time,
                min_temp_caution=min_temp,
                min_temp_no_go=min_temp - 7,
                max_wind_caution=max_wind,
                max_wind_no_go=max_wind + 10,
                rain_threshold=max_precip,
                unit_system=unit_system,
            )
        )
    try:
        weather = await client_instance.get_hourly_weather(lat, lon, unit_system)
    except Exception as e:
        print(f"Weather API error: {e}")
        raise HTTPException(
            status_code=503, detail="Weather API is currently unavailable"
        )

    # Create a temporary Commute object to hold thresholds for the assessment engine.
    # We use some heuristic mapping for the 'no_go' thresholds based on caution inputs.
    thresholds = Commute(
        lat=lat,
        lon=lon,
        schedule_time="08:00",  # Dummy schedule
        min_temp_caution=min_temp,
        min_temp_no_go=min_temp - 7.0,
        max_wind_caution=max_wind,
        max_wind_no_go=max_wind + 10.0,
        rain_threshold=max_precip,
        unit_system=unit_system,
    )

    assessment = engine_instance.assess(weather, thresholds)
    return assessment


@app.post("/test-webhook", response_model=AssessmentResult)
@app.post("/api/test-webhook", response_model=AssessmentResult)
async def test_webhook(commute: CommuteCreate, user: User = Depends(get_current_user)):
    """
    Manually trigger a notification test for given coordinates and thresholds.
    """
    try:
        weather = await client_instance.get_hourly_weather(
            commute.lat, commute.lon, commute.unit_system
        )
    except Exception as e:
        print(f"Weather API error: {e}")
        raise HTTPException(
            status_code=503, detail="Weather API is currently unavailable"
        )

    assessment = engine_instance.assess(weather, commute)

    if not commute.webhook_url:
        raise HTTPException(422, "Enter a notification URL first")
    try:
        delivered = await notification_service_instance.send_notification(
            commute.webhook_url, assessment
        )
    except Exception as exc:
        raise HTTPException(
            502, "The notification could not be delivered. Check the URL and try again."
        ) from exc
    if not delivered:
        raise HTTPException(502, "The notification service did not accept this URL")
    return assessment


# --- Commutes CRUD Endpoints ---
@app.get("/commutes", response_model=List[Commute])
@app.get("/api/commutes", response_model=List[Commute])
def list_commutes(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
    return session.exec(select(Commute).where(Commute.user_id == user.id)).all()


@app.post("/commutes", response_model=Commute)
@app.post("/api/commutes", response_model=Commute)
def create_commute(
    commute_data: CommuteCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    new_commute = Commute.model_validate(commute_data)
    new_commute.user_id = user.id
    session.add(new_commute)
    session.commit()
    session.refresh(new_commute)
    schedule_commute_check(new_commute)
    return new_commute


@app.put("/commutes/{commute_id}", response_model=Commute)
@app.put("/api/commutes/{commute_id}", response_model=Commute)
@app.put("/commute/{commute_id}", response_model=Commute)
@app.put("/api/commute/{commute_id}", response_model=Commute)
@app.put("/config/{commute_id}", response_model=Commute)
@app.put("/api/config/{commute_id}", response_model=Commute)
def update_commute_endpoint(
    commute_id: int,
    commute_data: CommuteCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    existing_commute = session.get(Commute, commute_id)
    if not existing_commute or existing_commute.user_id != user.id:
        raise HTTPException(
            status_code=404, detail="Commute not found or not authorized"
        )
    update_data = commute_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(existing_commute, key, value)
    session.add(existing_commute)
    session.commit()
    session.refresh(existing_commute)
    schedule_commute_check(existing_commute)
    return existing_commute


@app.delete("/commutes/{commute_id}")
@app.delete("/api/commutes/{commute_id}")
def delete_commute_route(
    commute_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return delete_config(commute_id, session, user)


# --- Route Check Endpoints ---
@app.post("/check", response_model=RouteAssessmentResult)
@app.post("/api/check", response_model=RouteAssessmentResult)
@app.get("/check", response_model=RouteAssessmentResult)
@app.get("/api/check", response_model=RouteAssessmentResult)
async def check_route(
    commute_data: Optional[RouteCheckRequest] = None,
    commute_id: Optional[int] = Query(default=None),
    lat: Optional[float] = Query(default=None),
    lon: Optional[float] = Query(default=None),
    dest_lat: Optional[float] = Query(default=None),
    dest_lon: Optional[float] = Query(default=None),
    dest_name: Optional[str] = Query(default=None),
    schedule_time: Optional[str] = Query(default=None),
    departure_time: Optional[str] = Query(default=None),
    return_schedule_time: Optional[str] = Query(default=None),
    unit_system: UnitSystem = Query(default=UnitSystem.IMPERIAL),
    save_history: bool = Query(default=False),
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    data = commute_data.model_dump(exclude_unset=True) if commute_data else {}
    commute_id = commute_id or data.get("commute_id")
    save_history = save_history or data.get("save_history", False)
    commute = None
    if commute_id:
        if user is None:
            raise HTTPException(401, "Sign in to check a saved commute")
        commute = session.get(Commute, commute_id)
        if not commute or commute.user_id != user.id:
            raise HTTPException(
                status_code=404, detail="Commute not found or not authorized"
            )
    elif data or (lat is not None and lon is not None):
        if not data:
            data = dict(
                lat=lat,
                lon=lon,
                dest_name=dest_name,
                dest_lat=dest_lat,
                dest_lon=dest_lon,
                schedule_time=schedule_time or departure_time or "08:00",
                return_schedule_time=return_schedule_time or "17:00",
                unit_system=unit_system,
            )
        else:
            data = dict(data)
            if not data.get("schedule_time"):
                data["schedule_time"] = data.get("departure_time") or "08:00"
        try:
            settings = CommuteCreate.model_validate(data)
        except ValidationError as exc:
            raise HTTPException(422, str(exc)) from exc
        commute = Commute.model_validate(settings)
        commute.user_id = user.id if user else None
    elif user:
        commute = session.exec(
            select(Commute).where(Commute.user_id == user.id)
        ).first()

    if not commute:
        raise HTTPException(status_code=404, detail="Commute configuration not found")

    try:
        assessment_result = await assess_commute(
            commute, client_instance, engine_instance
        )
    except Exception as exc:
        print(f"Route assessment unavailable: {exc}")
        raise HTTPException(
            status_code=503,
            detail="A complete forecast is unavailable for this trip. Please try again.",
        ) from exc

    if save_history and user:
        try:
            record_assessment_run(
                session=session,
                user_id=user.id,
                commute_id=commute.id
                if commute and getattr(commute, "id", None)
                else None,
                assessment=assessment_result,
                leg_type="overall",
            )
        except Exception as e:
            print(f"Failed to persist on-demand assessment history: {e}")

    return assessment_result


# --- Route Directions Endpoints ---
@app.post("/api/route/directions", response_model=RouteDirectionsResponse)
@app.post("/route/directions", response_model=RouteDirectionsResponse)
async def get_route_directions_endpoint(request: RouteDirectionsRequest):
    origin = request.origin
    if (
        origin is None
        and request.origin_lat is not None
        and request.origin_lon is not None
    ):
        origin = (request.origin_lat, request.origin_lon)

    destination = request.destination
    if (
        destination is None
        and request.dest_lat is not None
        and request.dest_lon is not None
    ):
        destination = (request.dest_lat, request.dest_lon)

    if origin is None or destination is None:
        raise HTTPException(
            status_code=400,
            detail="Both origin and destination coordinates are required.",
        )

    try:
        directions = await routing_service.get_route_directions(
            origin=origin,
            destination=destination,
            waypoints=request.waypoints or [],
        )
        return directions
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing service error: {str(e)}")
