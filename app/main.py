from app import client as app_client
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from typing import List, Optional, AsyncGenerator
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()


from .models import Commute, CommuteCreate, AssessmentResult, RouteAssessmentResult, UnitSystem, User
from .engine import AssessmentEngine
from .client import WeatherClient
from .notifications import NotificationService
from .database import engine, get_session, create_db_and_tables
from .security import router as auth_router, get_current_user
from .analytics.routes import router as analytics_router
from .weather.routes import router as weather_router
from .push.routes import router as push_router
from .notifications import NotificationService, dispatch_web_push_notification

# --- Scheduler Setup ---
JOBS_DB_URL = os.getenv("JOBS_DB_URL", "sqlite:///jobs.db")
jobstores = {
    'default': SQLAlchemyJobStore(url=JOBS_DB_URL)
}
scheduler = AsyncIOScheduler(jobstores=jobstores)

engine_instance = AssessmentEngine()
client_instance = WeatherClient()
notification_service_instance = NotificationService()

async def run_commute_check(commute_id: int):
    """ Fetch commute, run assessment, and send notification. """
    with Session(engine) as session:
        commute = session.get(Commute, commute_id)
        if not commute:
            print(f"Error: Could not find commute with id {commute_id}")
            return

        print(f"Running assessment for commute: {commute.name}")
        weather = await client_instance.get_hourly_weather(commute.lat, commute.lon, commute.unit_system)
        assessment = engine_instance.assess(weather, commute)
        
        if commute.webhook_url:
            await notification_service_instance.send_notification(commute.webhook_url, assessment)
        if commute.user_id:
            title, body = notification_service_instance._format_message(assessment)
            dispatch_web_push_notification(commute.user_id, title, body, session)
        print(f"Assessment complete for {commute.name}. Score: {assessment.score}")

def schedule_commute_check(commute: Commute):
    """Adds or updates a job in the scheduler for a given commute."""
    job_id = f"commute_check_{commute.id}"
    
    scheduler.add_job(
        run_commute_check,
        'cron',
        hour=commute.schedule_time.split(':')[0],
        minute=commute.schedule_time.split(':')[1],
        day_of_week=commute.days_of_week,
        id=job_id,
        args=[commute.id],
        replace_existing=True,
    )
    print(f"Scheduled job '{job_id}' to run at {commute.schedule_time} on days: {commute.days_of_week}.")

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
app.include_router(weather_router)
app.include_router(push_router)

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/config", response_model=List[Commute])
@app.get("/api/config", response_model=List[Commute])
def read_config(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    commutes = session.exec(select(Commute).where(Commute.user_id == user.id)).all()
    return commutes

@app.post("/config", response_model=Commute)
@app.post("/api/config", response_model=Commute)
def create_or_update_config(commute_data: Commute, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if commute_data.id:
        existing_commute = session.get(Commute, commute_data.id)
        if existing_commute and existing_commute.user_id == user.id:
            update_data = commute_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(existing_commute, key, value)
            session.add(existing_commute)
            session.commit()
            session.refresh(existing_commute)
            commute_to_return = existing_commute
        elif existing_commute and existing_commute.user_id != user.id:
            raise HTTPException(status_code=404, detail="Commute not found or not authorized")
        else:
            # ID provided but not found, treat as new
            commute_data.id = None
            new_commute = Commute.model_validate(commute_data)
            new_commute.user_id = user.id
            session.add(new_commute)
            session.commit()
            session.refresh(new_commute)
            commute_to_return = new_commute
    else:
        new_commute = Commute.model_validate(commute_data)
        new_commute.user_id = user.id
        session.add(new_commute)
        session.commit()
        session.refresh(new_commute)
        commute_to_return = new_commute

    # After creating/updating, reschedule the job
    schedule_commute_check(commute_to_return)

    return commute_to_return

@app.delete("/config/{commute_id}")
@app.delete("/api/config/{commute_id}")
def delete_config(commute_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    commute = session.get(Commute, commute_id)
    if not commute or commute.user_id != user.id:
        raise HTTPException(status_code=404, detail="Commute not found or not authorized")

    session.delete(commute)
    session.commit()

    # Remove from scheduler
    job_id = f"commute_check_{commute_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    return {"status": "deleted"}

@app.get("/assess", response_model=AssessmentResult)
async def assess_weather(
    lat: float, 
    lon: float, 
    min_temp: float = 45.0, 
    max_temp: float = 95.0, 
    max_wind: float = 15.0, 
    max_precip: float = 30.0,
    unit_system: UnitSystem = UnitSystem.IMPERIAL
):
    """
    Manually assess weather for given coordinates and thresholds.
    """
    try:
        weather = await client_instance.get_hourly_weather(lat, lon, unit_system)
    except Exception as e:
        print(f"Weather API error: {e}")
        raise HTTPException(status_code=503, detail="Weather API is currently unavailable")
    
    # Create a temporary Commute object to hold thresholds for the assessment engine.
    # We use some heuristic mapping for the 'no_go' thresholds based on caution inputs.
    thresholds = Commute(
        lat=lat,
        lon=lon,
        schedule_time="08:00", # Dummy schedule
        min_temp_caution=min_temp,
        min_temp_no_go=min_temp - 7.0,
        max_wind_caution=max_wind,
        max_wind_no_go=max_wind + 10.0,
        rain_threshold=max_precip,
        unit_system=unit_system
    )
    
    assessment = engine_instance.assess(weather, thresholds)
    return assessment

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

# --- Commutes CRUD Endpoints ---
@app.get("/commutes", response_model=List[Commute])
@app.get("/api/commutes", response_model=List[Commute])
def list_commutes(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return session.exec(select(Commute).where(Commute.user_id == user.id)).all()

@app.post("/commutes", response_model=Commute)
@app.post("/api/commutes", response_model=Commute)
def create_commute(commute_data: CommuteCreate, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    new_commute = Commute.model_validate(commute_data)
    new_commute.user_id = user.id
    session.add(new_commute)
    session.commit()
    session.refresh(new_commute)
    schedule_commute_check(new_commute)
    return new_commute

@app.put("/commutes/{commute_id}", response_model=Commute)
@app.put("/api/commutes/{commute_id}", response_model=Commute)
def update_commute_endpoint(commute_id: int, commute_data: CommuteCreate, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    existing_commute = session.get(Commute, commute_id)
    if not existing_commute or existing_commute.user_id != user.id:
        raise HTTPException(status_code=404, detail="Commute not found or not authorized")
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
def delete_commute_route(commute_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return delete_config(commute_id, session, user)

# --- Route Check Endpoints ---
@app.post("/check", response_model=RouteAssessmentResult)
@app.post("/api/check", response_model=RouteAssessmentResult)
@app.get("/check", response_model=RouteAssessmentResult)
@app.get("/api/check", response_model=RouteAssessmentResult)
async def check_route(
    commute_data: Optional[CommuteCreate] = None,
    commute_id: Optional[int] = Query(default=None),
    lat: Optional[float] = Query(default=None),
    lon: Optional[float] = Query(default=None),
    dest_lat: Optional[float] = Query(default=None),
    dest_lon: Optional[float] = Query(default=None),
    dest_name: Optional[str] = Query(default=None),
    schedule_time: Optional[str] = Query(default=None),
    return_schedule_time: Optional[str] = Query(default=None),
    unit_system: UnitSystem = Query(default=UnitSystem.IMPERIAL),
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
):
    commute = None
    if commute_data:
        commute = Commute.model_validate(commute_data)
        if user:
            commute.user_id = user.id
    elif commute_id:
        commute = session.get(Commute, commute_id)
        if not commute or (user and commute.user_id != user.id):
            raise HTTPException(status_code=404, detail="Commute not found or not authorized")
    elif lat is not None and lon is not None:
        commute = Commute(
            lat=lat,
            lon=lon,
            dest_name=dest_name,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            schedule_time=schedule_time or "08:00",
            return_schedule_time=return_schedule_time or "17:00",
            unit_system=unit_system
        )
    elif user:
        commute = session.exec(select(Commute).where(Commute.user_id == user.id)).first()

    if not commute:
        raise HTTPException(status_code=404, detail="Commute configuration not found")

    try:
        origin_raw, dest_raw = await app_client.fetch_route_weather(
            commute.lat, commute.lon, commute.dest_lat, commute.dest_lon, commute.unit_system
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail="Weather service unavailable")

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

    return engine_instance.assess_route(
        origin_outbound_weather=origin_outbound,
        dest_outbound_weather=dest_outbound,
        dest_return_weather=dest_return,
        origin_return_weather=origin_return,
        commute=commute
    )
