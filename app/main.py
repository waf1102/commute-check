from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from typing import Optional
from .models import UserThresholds, AssessmentResult
from .engine import AssessmentEngine
from .client import WeatherClient
from .notifications import NotificationService

app = FastAPI(title="Commute Check API")
engine = AssessmentEngine()
client = WeatherClient()
notification_service = NotificationService()

@app.get("/assess", response_model=AssessmentResult)
async def assess_commute(
    lat: float = Query(..., description="Latitude of the location"),
    lon: float = Query(..., description="Longitude of the location"),
    webhook_url: Optional[str] = Query(None, description="Optional webhook URL for notifications"),
    background_tasks: BackgroundTasks = None
):
    """
    Triggers the riding assessment for the given location using current weather data.
    """
    try:
        # 1. Fetch hourly weather data from Open-Meteo
        weather = await client.get_hourly_weather(lat, lon)
        
        # 2. Apply the assessment engine logic with default thresholds
        thresholds = UserThresholds() # Default thresholds for MVP
        
        # 3. Compute the assessment result
        assessment = engine.assess(weather, thresholds)
        
        # 4. Trigger notification if webhook_url is provided
        if webhook_url and background_tasks:
            background_tasks.add_task(notification_service.send_notification, webhook_url, assessment)
            
        return assessment
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy"}
