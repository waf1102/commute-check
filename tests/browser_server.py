"""Real API and database for browser tests; only external providers are replaced."""

import os
import tempfile
from pathlib import Path

_data = Path(tempfile.mkdtemp(prefix="commute-browser-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_data / 'commutes.db'}"
os.environ["JOBS_DB_URL"] = f"sqlite:///{_data / 'jobs.db'}"
os.environ["SECRET_KEY"] = "browser-test-key-not-for-deployment"

from app.main import app as app, client_instance, engine_instance
from app.places import _cache
from app.routing import calculate_haversine_fallback
from tests.helpers import forecast

_cache["Boston"] = [
    {
        "name": "Boston, Massachusetts, United States",
        "lat": 42.36,
        "lon": -71.06,
        "timezone": "America/New_York",
    }
]
_cache["Cambridge"] = [
    {
        "name": "Cambridge, Massachusetts, United States",
        "lat": 42.37,
        "lon": -71.12,
        "timezone": "America/New_York",
    }
]


async def weather(coordinates, unit_system):
    data = forecast(temperature=70 if unit_system == "imperial" else 21, gusts=8)
    # A bad return journey must influence the overall recommendation.
    data["hourly"]["precipitation_probability"] = [
        80 if int(t[11:13]) >= 20 else 0 for t in data["hourly"]["time"]
    ]
    return [data for _ in coordinates]


async def directions(origin, destination, waypoints=None):
    return calculate_haversine_fallback([origin, *(waypoints or []), destination])


client_instance.fetch_weather_batch = weather
engine_instance.routing_service.get_route_directions = directions
