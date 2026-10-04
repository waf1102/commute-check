from app import client as app_client
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from typing import List, Optional, Tuple, Any, AsyncGenerator, Union, Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()


from .models import (
    Commute,
    CommuteCreate,
    AssessmentResult,
    RouteAssessmentResult,
    UnitSystem,
    User,
    AssessmentRequest,
    RouteCheckRequest,
)
from .engine import AssessmentEngine
from .client import WeatherClient
from .notifications import NotificationService
from .database import engine, get_session, create_db_and_tables
from .security import router as auth_router, get_current_user, get_current_user_optional
from .analytics.routes import router as analytics_router
from .analytics.service import record_assessment_run, log_assessment_run
from .weather.routes import router as weather_router
from .push.routes import router as push_router
from .notifications import NotificationService, dispatch_web_push_notification
from .routing import (
    routing_service,
    RoutingService,
    RouteDirectionsRequest,
    RouteDirectionsResponse,
    parse_coordinate,
)

# --- Scheduler Setup ---
JOBS_DB_URL = os.getenv("JOBS_DB_URL", "sqlite:///jobs.db")
jobstores = {
    'default': SQLAlchemyJobStore(url=JOBS_DB_URL)
}
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
    """ Fetch commute, run route assessment, and send notification for corresponding leg. """
    try:
        with Session(engine) as session:
            commute = session.get(Commute, commute_id)
            if not commute:
                print(f"Error: Could not find commute with id {commute_id}")
                return None

            print(f"Running assessment for commute: {commute.name} (leg: {leg_type})")
            try:
                origin_raw, dest_raw = await app_client.fetch_route_weather(
                    commute.lat, commute.lon, commute.dest_lat, commute.dest_lon, commute.unit_system
                )
            except Exception as e:
                print(f"Error fetching route weather for commute {commute_id}: {e}")
                return None

            outbound_time = commute.schedule_time or "08:00"
            return_time = commute.return_schedule_time or "17:00"

            from .client import parse_hourly_at_time
            origin_outbound = parse_hourly_at_time(origin_raw, outbound_time)
            origin_return = parse_hourly_at_time(origin_raw, return_time) if return_time else None

            if dest_raw:
                dest_outbound = parse_hourly_at_time(dest_raw, outbound_time)
                dest_return = parse_hourly_at_time(dest_raw, return_time) if return_time else None
            else:
                dest_outbound = None
                dest_return = None

            route_assessment = engine_instance.assess_route(
                origin_outbound_weather=origin_outbound,
                dest_outbound_weather=dest_outbound,
                dest_return_weather=dest_return,
                origin_return_weather=origin_return,
                commute=commute
            )

            leg_key = leg_type.lower()
            if "return" in leg_key and route_assessment.return_leg:
                leg_assessment = route_assessment.return_leg
            else:
                leg_assessment = route_assessment.outbound_leg

            if commute and commute.name:
                leg_assessment.commute_name = commute.name

            if commute.webhook_url:
                await notification_service_instance.send_notification(
                    commute.webhook_url, leg_assessment, leg_type=leg_type
                )
            if commute.user_id:
                title, body = notification_service_instance._format_message(
                    leg_assessment, leg_type=leg_type, commute_name=commute.name if commute else None
                )
                pinpoints = notification_service_instance.extract_hazard_pinpoints(leg_assessment)
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
                    url="/#route-visualizer",
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
                    overall_status=route_assessment.overall_status.value if hasattr(route_assessment.overall_status, "value") else str(route_assessment.overall_status),
                    overall_score=float(route_assessment.overall_score),
                )
            except Exception as e:
                print(f"Failed to persist assessment history: {e}")

            print(f"Assessment complete for {commute.name} ({leg_type}). Score: {leg_assessment.score}")
            return leg_assessment
    except Exception as e:
        print(f"Error running commute check for commute {commute_id}: {e}")
        return None

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
            id=outbound_job_id,
            args=[commute.id, "outbound"],
            replace_existing=True,
        )
        print(f"Scheduled outbound job '{outbound_job_id}' to run at {commute.schedule_time} on days: {commute.days_of_week}.")

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
            day_of_week=commute.days_of_week or "mon-fri",
            id=return_job_id,
            args=[commute.id, "return"],
            replace_existing=True,
        )
        print(f"Scheduled return job '{return_job_id}' to run at {commute.return_schedule_time} on days: {commute.days_of_week}.")

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
            schedule_commute_check(commute)
            
    yield
    # Shutdown logic
    scheduler.shutdown()

# --- FastAPI App ---
app = FastAPI(
    title="Commute Check API",
    lifespan=lifespan
)

# CORS Middleware
origins = ["http://localhost:5173", "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# --- Commutes CRUD Endpoints & Aliases ---
@app.get("/config", response_model=List[Commute])
@app.get("/api/config", response_model=List[Commute])
@app.get("/commutes", response_model=List[Commute])
@app.get("/api/commutes", response_model=List[Commute])
@app.get("/commute", response_model=List[Commute])
@app.get("/api/commute", response_model=List[Commute])
def read_config(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return session.exec(select(Commute).where(Commute.user_id == user.id)).all()

list_commutes = read_config


@app.get("/config/{commute_id}", response_model=Commute)
@app.get("/api/config/{commute_id}", response_model=Commute)
@app.get("/commutes/{commute_id}", response_model=Commute)
@app.get("/api/commutes/{commute_id}", response_model=Commute)
@app.get("/commute/{commute_id}", response_model=Commute)
@app.get("/api/commute/{commute_id}", response_model=Commute)
def get_commute_endpoint(commute_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    commute = session.get(Commute, commute_id)
    if not commute or commute.user_id != user.id:
        raise HTTPException(status_code=404, detail="Commute not found or not authorized")
    return commute


@app.post("/config", response_model=Commute)
@app.post("/api/config", response_model=Commute)
@app.post("/commutes", response_model=Commute)
@app.post("/api/commutes", response_model=Commute)
@app.post("/commute", response_model=Commute)
@app.post("/api/commute", response_model=Commute)
def create_or_update_config(commute_data: CommuteCreate, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if commute_data.id:
        existing_commute = session.get(Commute, commute_data.id)
        if existing_commute and existing_commute.user_id == user.id:
            update_data = commute_data.model_dump(exclude_unset=True)
            update_data.pop("id", None)
            update_data.pop("user_id", None)
            for key, value in update_data.items():
                setattr(existing_commute, key, value)
            existing_commute.user_id = user.id
            session.add(existing_commute)
            session.commit()
            session.refresh(existing_commute)
            commute_to_return = existing_commute
        elif existing_commute and existing_commute.user_id != user.id:
            raise HTTPException(status_code=404, detail="Commute not found or not authorized")
        else:
            # ID provided but not found, treat as new
            new_data = commute_data.model_dump(exclude_unset=True)
            new_data.pop("id", None)
            new_data.pop("user_id", None)
            new_commute = Commute.model_validate(new_data)
            new_commute.user_id = user.id
            session.add(new_commute)
            session.commit()
            session.refresh(new_commute)
            commute_to_return = new_commute
    else:
        new_data = commute_data.model_dump(exclude_unset=True)
        new_data.pop("id", None)
        new_data.pop("user_id", None)
        new_commute = Commute.model_validate(new_data)
        new_commute.user_id = user.id
        session.add(new_commute)
        session.commit()
        session.refresh(new_commute)
        commute_to_return = new_commute

    # After creating/updating, reschedule the job
    schedule_commute_check(commute_to_return)

    return commute_to_return

create_commute = create_or_update_config


@app.put("/commutes/{commute_id}", response_model=Commute)
@app.put("/api/commutes/{commute_id}", response_model=Commute)
@app.put("/config/{commute_id}", response_model=Commute)
@app.put("/api/config/{commute_id}", response_model=Commute)
@app.put("/commute/{commute_id}", response_model=Commute)
@app.put("/api/commute/{commute_id}", response_model=Commute)
def update_commute_endpoint(commute_id: int, commute_data: CommuteCreate, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    existing_commute = session.get(Commute, commute_id)
    if not existing_commute or existing_commute.user_id != user.id:
        raise HTTPException(status_code=404, detail="Commute not found or not authorized")
    update_data = commute_data.model_dump(exclude_unset=True)
    update_data.pop("id", None)
    update_data.pop("user_id", None)
    for key, value in update_data.items():
        setattr(existing_commute, key, value)
    existing_commute.user_id = user.id
    session.add(existing_commute)
    session.commit()
    session.refresh(existing_commute)
    schedule_commute_check(existing_commute)
    return existing_commute


@app.delete("/config/{commute_id}")
@app.delete("/api/config/{commute_id}")
@app.delete("/commutes/{commute_id}")
@app.delete("/api/commutes/{commute_id}")
@app.delete("/commute/{commute_id}")
@app.delete("/api/commute/{commute_id}")
def delete_config(commute_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    commute = session.get(Commute, commute_id)
    if not commute or commute.user_id != user.id:
        raise HTTPException(status_code=404, detail="Commute not found or not authorized")

    session.delete(commute)
    session.commit()

    # Remove from scheduler
    clear_commute_jobs(commute_id)

    return {"status": "deleted"}

delete_commute_route = delete_config

@app.post("/assess", response_model=AssessmentResult)
@app.post("/api/assess", response_model=AssessmentResult)
async def assess_weather_post(request: AssessmentRequest):
    """
    Manually assess weather via POST for given coordinates, waypoints, and thresholds.
    """
    lat = request.lat
    lon = request.lon
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Latitude and longitude are required")

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

    if waypoints_raw or (thresholds.dest_lat is not None and thresholds.dest_lon is not None):
        coords: List[Tuple[float, float]] = [(lat, lon)]
        waypoint_names: List[str] = [thresholds.name or "Origin"]

        if waypoints_raw:
            for i, w in enumerate(waypoints_raw):
                try:
                    w_lat, w_lon = parse_coordinate(w)
                    coords.append((w_lat, w_lon))
                    w_name = ""
                    if isinstance(w, dict):
                        w_name = w.get("name", "")
                    elif hasattr(w, "name"):
                        w_name = getattr(w, "name", "")
                    waypoint_names.append(w_name or f"Waypoint {i+1}")
                except Exception as e:
                    print(f"Error parsing waypoint {w}: {e}")

        if thresholds.dest_lat is not None and thresholds.dest_lon is not None:
            coords.append((thresholds.dest_lat, thresholds.dest_lon))
            waypoint_names.append(thresholds.dest_name or "Destination")

        try:
            forecasts = await client_instance.fetch_weather_batch(coords, unit_system=unit_system)
        except Exception as e:
            print(f"Weather API error in batch fetch: {e}")
            raise HTTPException(status_code=503, detail="Weather API is currently unavailable")

        route_res = engine_instance.assess_timed_route(
            coordinates=coords,
            departure_time=departure_time,
            weather_data=forecasts,
            commute=thresholds,
            waypoint_names=waypoint_names,
        )

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
            weather = await client_instance.get_hourly_weather(lat, lon, unit_system)
        except Exception as e:
            print(f"Weather API error: {e}")
            raise HTTPException(status_code=503, detail="Weather API is currently unavailable")

        assessment = engine_instance.assess(weather, thresholds)
        return assessment


@app.get("/assess", response_model=AssessmentResult)
@app.get("/api/assess", response_model=AssessmentResult)
async def assess_weather(
    lat: Optional[float] = Query(default=None),
    lon: Optional[float] = Query(default=None),
    dest_lat: Optional[float] = Query(default=None),
    dest_lon: Optional[float] = Query(default=None),
    dest_name: Optional[str] = Query(default=None),
    schedule_time: Optional[str] = Query(default=None),
    departure_time: Optional[str] = Query(default=None),
    min_temp: Optional[float] = Query(default=45.0),
    min_temp_caution: Optional[float] = Query(default=None),
    min_temp_no_go: Optional[float] = Query(default=None),
    max_temp: Optional[float] = Query(default=95.0),
    max_wind: Optional[float] = Query(default=15.0),
    max_wind_caution: Optional[float] = Query(default=None),
    max_wind_no_go: Optional[float] = Query(default=None),
    max_precip: Optional[float] = Query(default=30.0),
    rain_threshold: Optional[float] = Query(default=None),
    unit_system: UnitSystem = Query(default=UnitSystem.IMPERIAL),
    commute_id: Optional[int] = Query(default=None),
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Manually assess weather for given coordinates, destinations, and thresholds via GET.
    """
    if lat is None or lon is None:
        if commute_id:
            commute = session.get(Commute, commute_id)
            if commute and (user is None or commute.user_id == user.id):
                lat = commute.lat
                lon = commute.lon
                if dest_lat is None:
                    dest_lat = commute.dest_lat
                if dest_lon is None:
                    dest_lon = commute.dest_lon
                if dest_name is None:
                    dest_name = commute.dest_name
                if schedule_time is None:
                    schedule_time = commute.schedule_time
        elif user:
            commute = session.exec(select(Commute).where(Commute.user_id == user.id)).first()
            if commute:
                lat = commute.lat
                lon = commute.lon
                if dest_lat is None:
                    dest_lat = commute.dest_lat
                if dest_lon is None:
                    dest_lon = commute.dest_lon
                if dest_name is None:
                    dest_name = commute.dest_name
                if schedule_time is None:
                    schedule_time = commute.schedule_time

    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Latitude and longitude are required")

    effective_min_caution = min_temp_caution if min_temp_caution is not None else min_temp
    effective_min_no_go = min_temp_no_go if min_temp_no_go is not None else (effective_min_caution - 7.0)
    effective_wind_caution = max_wind_caution if max_wind_caution is not None else max_wind
    effective_wind_no_go = max_wind_no_go if max_wind_no_go is not None else (effective_wind_caution + 10.0)
    effective_rain = rain_threshold if rain_threshold is not None else max_precip
    effective_dep_time = departure_time or schedule_time or "08:00"

    req = AssessmentRequest(
        lat=lat,
        lon=lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        dest_name=dest_name,
        departure_time=effective_dep_time,
        schedule_time=effective_dep_time,
        min_temp_caution=effective_min_caution,
        min_temp_no_go=effective_min_no_go,
        max_wind_caution=effective_wind_caution,
        max_wind_no_go=effective_wind_no_go,
        rain_threshold=effective_rain,
        unit_system=unit_system,
    )
    return await assess_weather_post(req)

@app.post("/test-webhook", response_model=AssessmentResult)
@app.post("/api/test-webhook", response_model=AssessmentResult)
async def test_webhook(commute: CommuteCreate):
    """
    Manually trigger a notification test for given coordinates and thresholds.
    """
    try:
        weather = await client_instance.get_hourly_weather(commute.lat, commute.lon, commute.unit_system)
    except Exception as e:
        print(f"Weather API error: {e}")
        raise HTTPException(status_code=503, detail="Weather API is currently unavailable")
    
    assessment = engine_instance.assess(weather, commute)
    
    if commute.webhook_url:
        await notification_service_instance.send_notification(commute.webhook_url, assessment)
    
    return assessment

# --- Route Check Endpoints ---
async def execute_route_check(
    commute_data: Optional[Union[RouteCheckRequest, CommuteCreate, Dict[str, Any]]] = None,
    commute_id: Optional[int] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    dest_lat: Optional[float] = None,
    dest_lon: Optional[float] = None,
    dest_name: Optional[str] = None,
    schedule_time: Optional[str] = None,
    departure_time: Optional[str] = None,
    return_schedule_time: Optional[str] = None,
    unit_system: Optional[UnitSystem] = UnitSystem.IMPERIAL,
    save_history: bool = False,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
) -> RouteAssessmentResult:
    # Extract from commute_data if provided
    if commute_data:
        if commute_id is None and getattr(commute_data, "commute_id", None) is not None:
            commute_id = commute_data.commute_id
        if lat is None and getattr(commute_data, "lat", None) is not None:
            lat = commute_data.lat
        if lon is None and getattr(commute_data, "lon", None) is not None:
            lon = commute_data.lon
        if dest_lat is None and getattr(commute_data, "dest_lat", None) is not None:
            dest_lat = commute_data.dest_lat
        if dest_lon is None and getattr(commute_data, "dest_lon", None) is not None:
            dest_lon = commute_data.dest_lon
        if dest_name is None and getattr(commute_data, "dest_name", None) is not None:
            dest_name = commute_data.dest_name
        if schedule_time is None:
            schedule_time = getattr(commute_data, "schedule_time", None) or getattr(commute_data, "departure_time", None)
        if departure_time is None:
            departure_time = getattr(commute_data, "departure_time", None) or getattr(commute_data, "schedule_time", None)
        if return_schedule_time is None:
            return_schedule_time = getattr(commute_data, "return_schedule_time", None)
        if unit_system is None or unit_system == UnitSystem.IMPERIAL:
            if getattr(commute_data, "unit_system", None):
                unit_system = commute_data.unit_system
        if not save_history and getattr(commute_data, "save_history", False):
            save_history = commute_data.save_history

    commute = None
    if commute_id:
        commute = session.get(Commute, commute_id)
        if not commute or (user and commute.user_id != user.id):
            raise HTTPException(status_code=404, detail="Commute not found or not authorized")
    elif lat is not None and lon is not None:
        min_c = getattr(commute_data, "min_temp_caution", None) if commute_data else None
        if min_c is None:
            min_c = getattr(commute_data, "min_temp", None) if commute_data else None
        if min_c is None:
            min_c = 45.0

        min_ng = getattr(commute_data, "min_temp_no_go", None) if commute_data else None
        if min_ng is None:
            min_ng = min_c - 7.0

        max_wc = getattr(commute_data, "max_wind_caution", None) if commute_data else None
        if max_wc is None:
            max_wc = getattr(commute_data, "max_wind", None) if commute_data else None
        if max_wc is None:
            max_wc = 15.0

        max_wng = getattr(commute_data, "max_wind_no_go", None) if commute_data else None
        if max_wng is None:
            max_wng = max_wc + 10.0

        rain_th = getattr(commute_data, "rain_threshold", None) if commute_data else None
        if rain_th is None:
            rain_th = getattr(commute_data, "max_precip", None) if commute_data else None
        if rain_th is None:
            rain_th = 30.0

        name = getattr(commute_data, "name", "Default Commute") if commute_data else "Default Commute"

        effective_sched = schedule_time or departure_time or "08:00"
        effective_ret = return_schedule_time or "17:00"

        commute = Commute(
            name=name,
            lat=float(lat),
            lon=float(lon),
            dest_name=dest_name,
            dest_lat=float(dest_lat) if dest_lat is not None else None,
            dest_lon=float(dest_lon) if dest_lon is not None else None,
            schedule_time=effective_sched,
            return_schedule_time=effective_ret,
            unit_system=unit_system or UnitSystem.IMPERIAL,
            min_temp_caution=float(min_c),
            min_temp_no_go=float(min_ng),
            max_wind_caution=float(max_wc),
            max_wind_no_go=float(max_wng),
            rain_threshold=float(rain_th),
        )
        if user:
            commute.user_id = user.id
    elif user:
        commute = session.exec(select(Commute).where(Commute.user_id == user.id)).first()

    if not commute:
        raise HTTPException(status_code=404, detail="Commute configuration not found")

    waypoints_raw = getattr(commute_data, "waypoints", None) if commute_data else None
    if not waypoints_raw and commute and getattr(commute, "waypoints", None):
        waypoints_raw = commute.waypoints

    if waypoints_raw:
        coords: List[Tuple[float, float]] = [(commute.lat, commute.lon)]
        wp_names: List[str] = [commute.name or "Origin"]
        for i, w in enumerate(waypoints_raw):
            try:
                w_lat, w_lon = parse_coordinate(w)
                coords.append((w_lat, w_lon))
                w_name = ""
                if isinstance(w, dict):
                    w_name = w.get("name", "")
                elif hasattr(w, "name"):
                    w_name = getattr(w, "name", "")
                wp_names.append(w_name or f"Waypoint {i+1}")
            except Exception as e:
                print(f"Error parsing waypoint {w}: {e}")

        if commute.dest_lat is not None and commute.dest_lon is not None:
            coords.append((commute.dest_lat, commute.dest_lon))
            wp_names.append(commute.dest_name or "Destination")

        try:
            forecasts = await client_instance.fetch_weather_batch(coords, unit_system=commute.unit_system)
        except Exception as e:
            raise HTTPException(status_code=503, detail="Weather service unavailable")

        outbound_time = commute.schedule_time or departure_time or "08:00"
        assessment_result = engine_instance.assess_timed_route(
            coordinates=coords,
            departure_time=outbound_time,
            weather_data=forecasts,
            commute=commute,
            waypoint_names=wp_names,
        )
    else:
        try:
            origin_raw, dest_raw = await app_client.fetch_route_weather(
                commute.lat, commute.lon, commute.dest_lat, commute.dest_lon, commute.unit_system
            )
        except Exception as e:
            raise HTTPException(status_code=503, detail="Weather service unavailable")

        outbound_time = commute.schedule_time or departure_time or "08:00"
        return_time = commute.return_schedule_time or "17:00"

        from .client import parse_hourly_at_time
        origin_outbound = parse_hourly_at_time(origin_raw, outbound_time)
        origin_return = parse_hourly_at_time(origin_raw, return_time) if return_time else None

        if dest_raw:
            dest_outbound = parse_hourly_at_time(dest_raw, outbound_time)
            dest_return = parse_hourly_at_time(dest_raw, return_time) if return_time else None
        else:
            dest_outbound = None
            dest_return = None

        assessment_result = engine_instance.assess_route(
            origin_outbound_weather=origin_outbound,
            dest_outbound_weather=dest_outbound,
            dest_return_weather=dest_return,
            origin_return_weather=origin_return,
            commute=commute
        )

    if save_history and user:
        try:
            record_assessment_run(
                session=session,
                user_id=user.id,
                commute_id=commute.id if commute and getattr(commute, "id", None) else None,
                assessment=assessment_result,
                leg_type="overall"
            )
        except Exception as e:
            print(f"Failed to persist on-demand assessment history: {e}")

    return assessment_result


@app.get("/check", response_model=RouteAssessmentResult)
@app.get("/api/check", response_model=RouteAssessmentResult)
async def check_route_get(
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
    return await execute_route_check(
        commute_data=None,
        commute_id=commute_id,
        lat=lat,
        lon=lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        dest_name=dest_name,
        schedule_time=schedule_time or departure_time,
        departure_time=departure_time or schedule_time,
        return_schedule_time=return_schedule_time,
        unit_system=unit_system,
        save_history=save_history,
        session=session,
        user=user,
    )


@app.post("/check", response_model=RouteAssessmentResult)
@app.post("/api/check", response_model=RouteAssessmentResult)
async def check_route_post(
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
    return await execute_route_check(
        commute_data=commute_data,
        commute_id=commute_id,
        lat=lat,
        lon=lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        dest_name=dest_name,
        schedule_time=schedule_time or departure_time,
        departure_time=departure_time or schedule_time,
        return_schedule_time=return_schedule_time,
        unit_system=unit_system,
        save_history=save_history,
        session=session,
        user=user,
    )


check_route = check_route_post


# --- Route Directions Endpoints ---
@app.post("/api/route/directions", response_model=RouteDirectionsResponse)
@app.post("/route/directions", response_model=RouteDirectionsResponse)
async def get_route_directions_endpoint(request: RouteDirectionsRequest):
    origin = request.origin
    if origin is None and request.origin_lat is not None and request.origin_lon is not None:
        origin = (request.origin_lat, request.origin_lon)

    destination = request.destination
    if destination is None and request.dest_lat is not None and request.dest_lon is not None:
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


