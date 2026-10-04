import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.models import (
    Status,
    HourlyWeather,
    Commute,
    CommuteCreate,
    AssessmentRequest,
    HazardPinpoint,
    WaypointEvaluation,
    RouteSegment,
    UnitSystem,
    User,
)
from app.routing import RoutingService, haversine_distance
from app.engine import AssessmentEngine
from app.client import WeatherClient, parse_hourly_at_time
from app.main import app, get_session
from app.security import ALGORITHM, SECRET_KEY
from jose import jwt
from datetime import timedelta, timezone


@pytest.fixture
def routing_service():
    return RoutingService(default_speed_kmh=60.0)


@pytest.fixture
def engine(routing_service):
    return AssessmentEngine(routing_service=routing_service)


@pytest.fixture
def thresholds():
    return Commute(
        name="Test Commute",
        lat=37.7749,
        lon=-122.4194,
        dest_name="Office",
        dest_lat=37.3861,
        dest_lon=-122.0839,
        schedule_time="08:00",
        min_temp_caution=45.0,
        min_temp_no_go=38.0,
        max_wind_caution=15.0,
        max_wind_no_go=25.0,
        rain_threshold=30.0,
    )


# ---------------------------------------------------------------------------
# 1. RoutingService tests
# ---------------------------------------------------------------------------
def test_routing_service_distance_and_durations(routing_service):
    # San Francisco to San Jose (~65-75 km)
    sf = (37.7749, -122.4194)
    sj = (37.3382, -121.8863)

    distance = routing_service.calculate_distance(sf, sj)
    assert 60.0 < distance < 80.0

    # At 60 km/h, ~70 km should take ~70 minutes
    duration = routing_service.calculate_segment_duration(sf, sj, speed_kmh=60.0)
    assert 60.0 < duration < 80.0

    # Multi-point segment durations
    coords = [sf, (37.5, -122.2), sj]
    durations = routing_service.compute_segment_durations(coords, speed_kmh=60.0)
    assert len(durations) == 2
    assert all(d > 0 for d in durations)


def test_routing_service_compute_etas(routing_service):
    departure_time = "08:00"
    durations = [30.0, 45.0, 20.0]
    etas = routing_service.compute_etas(departure_time, durations)

    assert len(etas) == 4
    assert etas[0] == "08:00"
    assert etas[1] == "08:30"
    assert etas[2] == "09:15"
    assert etas[3] == "09:35"


def test_routing_service_compute_etas_iso_format(routing_service):
    departure_time = "2026-10-03T08:00:00"
    durations = [30.0, 45.0]
    etas = routing_service.compute_etas(departure_time, durations)

    assert len(etas) == 3
    assert etas[0] == "2026-10-03T08:00:00"
    assert "08:30:00" in etas[1]
    assert "09:15:00" in etas[2]


# ---------------------------------------------------------------------------
# 2. Time-Shifted Weather Sampling along Route Waypoints
# ---------------------------------------------------------------------------
def test_time_interpolated_weather_sampling_detects_delayed_hazard(engine, thresholds):
    """
    Test a 3-point route: Origin (08:00), Midpoint (09:00), Destination (10:00).
    At 08:00, weather at all points is clear.
    At 09:00, heavy rain develops at Midpoint.
    Time-interpolated assessment should detect the rain at 09:00 for the midpoint.
    """
    coordinates = [
        (37.7749, -122.4194),  # Origin
        (37.5630, -122.3255),  # Midpoint
        (37.3861, -122.0839),  # Destination
    ]
    # Explicit 60-minute segments
    segment_durations = [60.0, 60.0]

    # Mock hourly forecasts for each location (24 hours)
    origin_forecast = {
        "hourly": {
            "time": [f"2026-10-03T{h:02d}:00" for h in range(24)],
            "temperature_2m": [65.0] * 24,
            "apparent_temperature": [65.0] * 24,
            "wind_speed_10m": [8.0] * 24,
            "wind_gusts_10m": [10.0] * 24,
            "precipitation_probability": [0.0] * 24,
            "weather_code": [0] * 24,
        }
    }

    # Midpoint: clear at 08:00 (index 8), but severe storm & rain at 09:00 (index 9)
    mid_precip = [0.0] * 24
    mid_precip[9] = 80.0  # 80% rain probability at 09:00
    mid_weather_codes = [0] * 24
    mid_weather_codes[9] = 65  # Heavy rain
    midpoint_forecast = {
        "hourly": {
            "time": [f"2026-10-03T{h:02d}:00" for h in range(24)],
            "temperature_2m": [62.0] * 24,
            "apparent_temperature": [62.0] * 24,
            "wind_speed_10m": [10.0] * 24,
            "wind_gusts_10m": [12.0] * 24,
            "precipitation_probability": mid_precip,
            "weather_code": mid_weather_codes,
        }
    }

    dest_forecast = {
        "hourly": {
            "time": [f"2026-10-03T{h:02d}:00" for h in range(24)],
            "temperature_2m": [68.0] * 24,
            "apparent_temperature": [68.0] * 24,
            "wind_speed_10m": [6.0] * 24,
            "wind_gusts_10m": [8.0] * 24,
            "precipitation_probability": [5.0] * 24,
            "weather_code": [0] * 24,
        }
    }

    forecasts = [origin_forecast, midpoint_forecast, dest_forecast]

    result = engine.assess_timed_route(
        coordinates=coordinates,
        departure_time="08:00",
        weather_data=forecasts,
        commute=thresholds,
        segment_durations=segment_durations,
        waypoint_names=["San Francisco", "San Mateo", "Mountain View"],
    )

    # Waypoints:
    # SF (08:00) -> Go
    # San Mateo (09:00) -> No-Go (80% rain > 30% threshold)
    # Mountain View (10:00) -> Go
    assert len(result.waypoint_evaluations) == 3
    assert result.waypoint_evaluations[0].estimated_arrival_time == "08:00"
    assert result.waypoint_evaluations[0].status == Status.GO

    assert result.waypoint_evaluations[1].estimated_arrival_time == "09:00"
    assert result.waypoint_evaluations[1].status == Status.NO_GO
    assert result.waypoint_evaluations[1].weather.precip_prob == 80.0

    assert result.waypoint_evaluations[2].estimated_arrival_time == "10:00"
    assert result.waypoint_evaluations[2].status == Status.GO

    # Segments:
    # Segment 0 (SF -> San Mateo): worst status between SF (Go) and San Mateo (No-Go) is No-Go
    # Segment 1 (San Mateo -> Mountain View): worst status is No-Go
    assert len(result.segments) == 2
    assert result.segments[0].status == Status.NO_GO
    assert result.segments[1].status == Status.NO_GO

    # Composite route safety status reflects the worst segment:
    assert result.overall_status == Status.NO_GO
    assert result.overall_score <= 30
    assert result.recommendation == "Riding not recommended."

    # Hazard Pinpoints should identify the rain breach at San Mateo
    assert len(result.hazard_pinpoints) >= 1
    rain_pinpoints = [p for p in result.hazard_pinpoints if p.parameter in ("precipitation_probability", "precip_prob")]
    assert len(rain_pinpoints) == 1
    pinpoint = rain_pinpoints[0]
    assert pinpoint.coordinates == (37.5630, -122.3255)
    assert pinpoint.estimated_time == "09:00"
    assert pinpoint.value == 80.0
    assert pinpoint.threshold == 30.0
    assert pinpoint.severity == Status.NO_GO


# ---------------------------------------------------------------------------
# 3. Hazard Pinpoint Detection for Multiple Parameters
# ---------------------------------------------------------------------------
def test_hazard_pinpoint_detection_parameters(engine, thresholds):
    # 1. Ice risk
    ice_weather = HourlyWeather(
        temperature=35.0, apparent_temp=30.0, wind_speed=5.0, wind_gusts=5.0, precip_prob=0.0, weather_code=0
    )
    hazards = engine.detect_hazard_pinpoints(ice_weather, thresholds, (37.7, -122.4), "08:00")
    temp_hazards = [h for h in hazards if h.parameter == "temperature"]
    assert len(temp_hazards) == 1
    assert temp_hazards[0].severity == Status.NO_GO
    assert temp_hazards[0].value == 30.0
    assert temp_hazards[0].threshold == thresholds.min_temp_no_go

    # 2. Wind caution and No-Go
    wind_caution = HourlyWeather(
        temperature=70.0, apparent_temp=70.0, wind_speed=18.0, wind_gusts=20.0, precip_prob=0.0, weather_code=0
    )
    hazards_wind_caution = engine.detect_hazard_pinpoints(wind_caution, thresholds, (37.7, -122.4), "08:15")
    wind_hazards = [h for h in hazards_wind_caution if h.parameter == "wind_speed"]
    assert len(wind_hazards) == 1
    assert wind_hazards[0].severity == Status.CAUTION
    assert wind_hazards[0].value == 18.0
    assert wind_hazards[0].threshold == thresholds.max_wind_caution

    wind_nogo = HourlyWeather(
        temperature=70.0, apparent_temp=70.0, wind_speed=30.0, wind_gusts=40.0, precip_prob=0.0, weather_code=0
    )
    hazards_wind_nogo = engine.detect_hazard_pinpoints(wind_nogo, thresholds, (37.7, -122.4), "08:30")
    speed_nogo = [h for h in hazards_wind_nogo if h.parameter == "wind_speed"]
    gust_nogo = [h for h in hazards_wind_nogo if h.parameter == "wind_gusts"]
    assert len(speed_nogo) == 1 and speed_nogo[0].severity == Status.NO_GO
    assert len(gust_nogo) == 1 and gust_nogo[0].severity == Status.NO_GO

    # 3. Weather code >= 71 (e.g., 95 Thunderstorm)
    storm_weather = HourlyWeather(
        temperature=70.0, apparent_temp=70.0, wind_speed=10.0, wind_gusts=12.0, precip_prob=10.0, weather_code=95
    )
    hazards_storm = engine.detect_hazard_pinpoints(storm_weather, thresholds, (37.7, -122.4), "08:45")
    code_hazards = [h for h in hazards_storm if h.parameter == "weather_code"]
    assert len(code_hazards) == 1
    assert code_hazards[0].severity == Status.NO_GO
    assert code_hazards[0].value == 95.0


# ---------------------------------------------------------------------------
# 4. Composite Route Safety Status & Segment Risk Scoring
# ---------------------------------------------------------------------------
def test_composite_route_safety_caution_and_no_go(engine, thresholds):
    coords = [
        (37.7, -122.4),
        (37.6, -122.3),
        (37.5, -122.2),
        (37.4, -122.1),
    ]
    # Segment 1: Go (both points clear)
    # Segment 2: Caution (chilly temperature)
    # Segment 3: Go (clear)
    w_clear = HourlyWeather(
        temperature=70.0, apparent_temp=70.0, wind_speed=5.0, wind_gusts=5.0, precip_prob=0.0, weather_code=0
    )
    w_caution = HourlyWeather(
        temperature=42.0, apparent_temp=40.0, wind_speed=5.0, wind_gusts=5.0, precip_prob=0.0, weather_code=0
    )

    weather_list_caution = [w_clear, w_caution, w_clear, w_clear]
    result_caution = engine.assess_timed_route(
        coordinates=coords,
        departure_time="08:00",
        weather_data=weather_list_caution,
        commute=thresholds,
        segment_durations=[15.0, 15.0, 15.0],
    )

    assert len(result_caution.segments) == 3
    # Segment 0 has w_caution as end_wp -> Status.CAUTION
    assert result_caution.segments[0].status == Status.CAUTION
    # Segment 1 has w_caution as start_wp -> Status.CAUTION
    assert result_caution.segments[1].status == Status.CAUTION
    # Segment 2 has w_clear at both ends -> Status.GO
    assert result_caution.segments[2].status == Status.GO

    # Overall route status must reflect worst segment: CAUTION
    assert result_caution.overall_status == Status.CAUTION
    assert result_caution.overall_score == 70
    assert result_caution.recommendation == "Ride with caution. Wear appropriate gear."

    # Now make Segment 3 No-Go with high winds
    w_nogo = HourlyWeather(
        temperature=70.0, apparent_temp=70.0, wind_speed=35.0, wind_gusts=45.0, precip_prob=0.0, weather_code=0
    )
    weather_list_nogo = [w_clear, w_caution, w_clear, w_nogo]
    result_nogo = engine.assess_timed_route(
        coordinates=coords,
        departure_time="08:00",
        weather_data=weather_list_nogo,
        commute=thresholds,
        segment_durations=[15.0, 15.0, 15.0],
    )

    assert result_nogo.segments[2].status == Status.NO_GO
    assert result_nogo.overall_status == Status.NO_GO
    assert result_nogo.overall_score == 0
    assert result_nogo.recommendation == "Riding not recommended."


# ---------------------------------------------------------------------------
# 5. WeatherClient Batch Retrieval and TTL Cache
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_weather_client_batch_sampling_and_ttl_cache():
    client = WeatherClient()
    coords = [
        (37.7749, -122.4194),
        (37.5630, -122.3255),
        (37.7749, -122.4194),  # Duplicate coordinate in same batch
    ]

    mock_resp = {
        "hourly": {
            "time": ["2026-10-03T08:00"],
            "temperature_2m": [65.0],
            "apparent_temperature": [65.0],
            "wind_speed_10m": [8.0],
            "wind_gusts_10m": [10.0],
            "precipitation_probability": [0.0],
            "weather_code": [0],
        }
    }

    call_count = 0

    async def mock_fetch(lat, lon, unit_system=UnitSystem.IMPERIAL):
        nonlocal call_count
        call_count += 1
        return mock_resp

    with patch.object(client, "fetch_weather", side_effect=mock_fetch):
        results = await client.fetch_weather_batch(coords, unit_system=UnitSystem.IMPERIAL)
        assert len(results) == 3
        # Since first and third coordinates are identical, fetch_weather should only be called twice!
        assert call_count == 2

    # Second batch call should hit client TTL cache if using client._cache
    client._cache[f"raw_37.7749_-122.4194_imperial"] = mock_resp
    client._cache[f"raw_37.563_-122.3255_imperial"] = mock_resp

    with patch("httpx.AsyncClient.get") as mock_http_get:
        cached_results = await client.fetch_weather_batch(coords, unit_system=UnitSystem.IMPERIAL)
        assert len(cached_results) == 3
        # Network shouldn't be touched due to cache hits
        mock_http_get.assert_not_called()


# ---------------------------------------------------------------------------
# 6. API Endpoints: POST /check and POST /assess with Waypoints
# ---------------------------------------------------------------------------
DATABASE_URL = "sqlite:///./test_route.db"
test_engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


@pytest.fixture(autouse=True, scope="module")
def cleanup_route_db():
    yield
    test_engine.dispose()
    import os

    if os.path.exists("./test_route.db"):
        try:
            os.remove("./test_route.db")
        except OSError:
            pass


def get_test_session():
    with Session(test_engine) as session:
        yield session


@pytest.fixture(name="api_client")
def api_client_fixture():
    SQLModel.metadata.create_all(test_engine)
    app.dependency_overrides[get_session] = get_test_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(test_engine)


def test_post_check_with_waypoints(api_client):
    from app.security import get_password_hash

    with Session(test_engine) as session:
        user = User(email="route_test@example.com", hashed_password=get_password_hash("pass123"))
        session.add(user)
        session.commit()
        session.refresh(user)

    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    token = jwt.encode({"sub": "route_test@example.com", "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}

    mock_forecast = {
        "hourly": {
            "time": [f"2026-10-03T{h:02d}:00" for h in range(24)],
            "temperature_2m": [68.0] * 24,
            "apparent_temperature": [68.0] * 24,
            "wind_speed_10m": [8.0] * 24,
            "wind_gusts_10m": [10.0] * 24,
            "precipitation_probability": [0.0] * 24,
            "weather_code": [0] * 24,
        }
    }

    with patch("app.main.client_instance.fetch_weather_batch", new_callable=AsyncMock) as mock_batch:
        mock_batch.return_value = [mock_forecast, mock_forecast, mock_forecast]

        payload = {
            "name": "Multi-Stop Route",
            "lat": 37.7749,
            "lon": -122.4194,
            "dest_name": "San Jose",
            "dest_lat": 37.3382,
            "dest_lon": -121.8863,
            "schedule_time": "08:00",
            "waypoints": [
                {"lat": 37.5630, "lon": -122.3255, "name": "San Mateo"}
            ],
            "min_temp_caution": 45.0,
            "min_temp_no_go": 38.0,
            "max_wind_caution": 15.0,
            "max_wind_no_go": 25.0,
            "rain_threshold": 30.0,
        }

        response = api_client.post("/check", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()

        assert "overall_status" in data
        assert "overall_score" in data
        assert data["overall_status"] == "Go"
        assert data["overall_score"] == 100

        # Segments
        assert "segments" in data
        assert len(data["segments"]) == 2  # Origin -> San Mateo, San Mateo -> San Jose
        assert data["segments"][0]["start_name"] == "Multi-Stop Route"
        assert data["segments"][0]["end_name"] == "San Mateo"
        assert data["segments"][1]["start_name"] == "San Mateo"
        assert data["segments"][1]["end_name"] == "San Jose"

        # Waypoint evaluations
        assert "waypoint_evaluations" in data
        assert len(data["waypoint_evaluations"]) == 3
        assert data["waypoint_evaluations"][0]["name"] == "Multi-Stop Route"
        assert data["waypoint_evaluations"][1]["name"] == "San Mateo"
        assert data["waypoint_evaluations"][2]["name"] == "San Jose"

        # Hazard pinpoints
        assert "hazard_pinpoints" in data
        assert isinstance(data["hazard_pinpoints"], list)


def test_post_assess_with_waypoints_and_hazards(api_client):
    clear_forecast = {
        "hourly": {
            "time": [f"2026-10-03T{h:02d}:00" for h in range(24)],
            "temperature_2m": [70.0] * 24,
            "apparent_temperature": [70.0] * 24,
            "wind_speed_10m": [5.0] * 24,
            "wind_gusts_10m": [7.0] * 24,
            "precipitation_probability": [0.0] * 24,
            "weather_code": [0] * 24,
        }
    }
    # Dangerous wind at second point
    windy_forecast = {
        "hourly": {
            "time": [f"2026-10-03T{h:02d}:00" for h in range(24)],
            "temperature_2m": [60.0] * 24,
            "apparent_temperature": [60.0] * 24,
            "wind_speed_10m": [32.0] * 24,  # > 25.0 No-Go
            "wind_gusts_10m": [45.0] * 24,
            "precipitation_probability": [0.0] * 24,
            "weather_code": [0] * 24,
        }
    }

    with patch("app.main.client_instance.fetch_weather_batch", new_callable=AsyncMock) as mock_batch:
        mock_batch.return_value = [clear_forecast, windy_forecast]

        payload = {
            "lat": 37.7749,
            "lon": -122.4194,
            "dest_lat": 37.5630,
            "dest_lon": -122.3255,
            "dest_name": "San Mateo",
            "departure_time": "08:00",
            "max_wind_caution": 15.0,
            "max_wind_no_go": 25.0,
        }

        response = api_client.post("/assess", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "No-Go"
        assert data["score"] == 0

        # Segments
        assert "segments" in data
        assert len(data["segments"]) == 1
        assert data["segments"][0]["status"] == "No-Go"

        # Waypoint evaluations
        assert "waypoint_evaluations" in data
        assert len(data["waypoint_evaluations"]) == 2

        # Hazard pinpoints
        assert "hazard_pinpoints" in data
        assert len(data["hazard_pinpoints"]) >= 1
        wind_hazards = [p for p in data["hazard_pinpoints"] if p["parameter"] == "wind_speed"]
        assert len(wind_hazards) == 1
        assert wind_hazards[0]["severity"] == "No-Go"
        assert wind_hazards[0]["value"] == 32.0
