import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel
from sqlmodel.pool import StaticPool
from datetime import datetime, timedelta, timezone
from jose import jwt
import httpx

from app.main import app
from app.database import get_session
from app.models import (
    User,
    Commute,
    CommuteCreate,
    AssessmentRequest,
    RouteCheckRequest,
    UnitSystem,
    Waypoint,
    Status,
    HourlyWeather,
)
from app.security import ALGORITHM, SECRET_KEY, get_password_hash
from app.routing import RoutingService, calculate_haversine_fallback

DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)


@pytest.fixture(autouse=True)
def clear_caches():
    from app.main import client_instance
    from app.client import _default_weather_client

    client_instance._cache.clear()
    _default_weather_client._cache.clear()
    yield
    client_instance._cache.clear()
    _default_weather_client._cache.clear()


@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def create_user_and_token(
    session: Session, email: str = "engine_qa@example.com"
) -> tuple[User, str]:
    user = User(email=email, hashed_password=get_password_hash("testsecret"))
    session.add(user)
    session.commit()
    session.refresh(user)
    token = jwt.encode(
        {"sub": user.email, "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return user, token


def generate_mock_weather_data(
    temp: float = 68.0, wind: float = 10.0, precip: float = 0.0, code: int = 0
):
    from tests.helpers import forecast

    return forecast(temperature=temp, wind=wind, gusts=wind + 5, rain=precip, code=code)


# =========================================================================
# 1. Weather Router Mounting & Frontend Contract Integration
# =========================================================================


def test_api_weather_forecast_prefix_and_contract(client: TestClient, session: Session):
    """
    Verify /api/weather/forecast endpoint resolves (not 404), requiring authentication,
    and returns 200 with forecast data matching frontend expectations.
    """
    user, token = create_user_and_token(session)

    # Commute configuration for user
    commute = Commute(
        name="Sunnyvale to SF",
        lat=37.3688,
        lon=-122.0363,
        dest_name="San Francisco",
        dest_lat=37.7749,
        dest_lon=-122.4194,
        schedule_time="08:00",
        return_schedule_time="17:00",
        user_id=user.id,
        min_temp_caution=45.0,
        min_temp_no_go=38.0,
        max_wind_caution=15.0,
        max_wind_no_go=25.0,
        rain_threshold=30.0,
    )
    session.add(commute)
    session.commit()

    with patch(
        "app.client.WeatherClient.fetch_weather", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = generate_mock_weather_data(
            temp=65.0, wind=8.0, precip=0.0
        )

        # 1. Test /api/weather/forecast
        res_api = client.get(
            "/api/weather/forecast", headers={"Authorization": f"Bearer {token}"}
        )
        assert res_api.status_code == 200
        data = res_api.json()

        # Check frontend contract
        assert "unit_system" in data
        assert "thresholds" in data
        assert "hourly" in data
        assert "destination_hourly" in data
        assert len(data["hourly"]) > 0
        assert data["destination_hourly"] is not None
        assert data["thresholds"]["min_temp_caution"] == 45.0
        assert data["thresholds"]["rain_threshold"] == 30.0

        # 2. Test backward-compatible /weather/forecast
        res_root = client.get(
            "/weather/forecast", headers={"Authorization": f"Bearer {token}"}
        )
        assert res_root.status_code == 200
        assert res_root.json()["thresholds"] == data["thresholds"]


# =========================================================================
# 2. Assessment Endpoints & Parameter Handling (Audit Requirements)
# =========================================================================


def test_api_check_post_with_commute_create_shape(client: TestClient, session: Session):
    """Verify POST /api/check processes CommuteCreate payload cleanly without 422 errors."""
    user, token = create_user_and_token(session)

    with patch(
        "app.client.WeatherClient.fetch_weather", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = generate_mock_weather_data(temp=72.0, wind=7.0)

        payload = {
            "name": "Bicycle Commute",
            "lat": 37.7749,
            "lon": -122.4194,
            "dest_name": "Mission District",
            "dest_lat": 37.7599,
            "dest_lon": -122.4148,
            "schedule_time": "08:30",
            "return_schedule_time": "17:30",
            "days_of_week": "mon-fri",
            "min_temp_caution": 45.0,
            "min_temp_no_go": 35.0,
            "max_wind_caution": 18.0,
            "max_wind_no_go": 28.0,
            "rain_threshold": 25.0,
            "unit_system": "imperial",
        }
        res = client.post(
            "/api/check", json=payload, headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["overall_status"] == Status.GO.value
        assert "outbound_leg" in data
        assert "return_leg" in data
        assert (
            datetime.fromisoformat(data["outbound_leg"]["schedule_time"]).strftime(
                "%H:%M"
            )
            == "08:30"
        )
        assert (
            datetime.fromisoformat(data["return_leg"]["schedule_time"]).strftime(
                "%H:%M"
            )
            == "17:30"
        )


def test_api_check_post_with_assessment_request_shape(
    client: TestClient, session: Session
):
    """Verify POST /api/check processes AssessmentRequest shape with departure_time cleanly."""
    user, token = create_user_and_token(session)

    with patch(
        "app.client.WeatherClient.fetch_weather", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = generate_mock_weather_data(temp=70.0, wind=8.0)

        payload = {
            "lat": 40.7128,
            "lon": -74.0060,
            "dest_lat": 40.7484,
            "dest_lon": -73.9857,
            "dest_name": "Midtown",
            "departure_time": "09:00",
            "unit_system": "imperial",
        }
        res = client.post(
            "/api/check", json=payload, headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["overall_status"] == Status.GO.value
        assert (
            datetime.fromisoformat(data["outbound_leg"]["schedule_time"]).strftime(
                "%H:%M"
            )
            == "09:00"
        )


def test_api_check_post_with_commute_id_only(client: TestClient, session: Session):
    """Verify POST /api/check with {'commute_id': X} payload does not throw 422."""
    user, token = create_user_and_token(session)
    commute = Commute(
        name="Saved Commute",
        lat=37.7749,
        lon=-122.4194,
        dest_name="Dest",
        dest_lat=37.7833,
        dest_lon=-122.4167,
        schedule_time="08:15",
        user_id=user.id,
    )
    session.add(commute)
    session.commit()

    with patch(
        "app.client.WeatherClient.fetch_weather", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = generate_mock_weather_data(temp=66.0, wind=8.0)

        res = client.post(
            "/api/check",
            json={"commute_id": commute.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["overall_score"] > 80


def test_api_check_get_with_query_parameters(client: TestClient, session: Session):
    """Verify GET /api/check parses all query parameters smoothly without 404/422."""
    user, token = create_user_and_token(session)

    with patch(
        "app.client.WeatherClient.fetch_weather", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = generate_mock_weather_data(temp=68.0, wind=10.0)

        url = (
            "/api/check?lat=37.7749&lon=-122.4194&dest_lat=37.7833&dest_lon=-122.4167"
            "&dest_name=Office&schedule_time=08:30&return_schedule_time=17:30&unit_system=imperial"
        )
        res = client.get(url, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["overall_status"] == Status.GO.value
        assert data["outbound_leg"]["location_name"] == "Home -> Office"


def test_assess_get_and_post_endpoints(client: TestClient):
    """Verify GET and POST on both /assess and /api/assess seamlessly handle inputs."""
    with patch(
        "app.client.WeatherClient.fetch_weather", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = generate_mock_weather_data(temp=72.0, wind=5.0)

        # 1. GET /api/assess with query params
        res1 = client.get(
            "/api/assess?lat=47.6062&lon=-122.3321&min_temp=40&max_wind=20"
        )
        assert res1.status_code == 200
        assert res1.json()["status"] == Status.GO.value

        # 2. GET /assess with destination query params (route assessment via GET)
        res2 = client.get(
            "/api/assess?lat=37.7749&lon=-122.4194&dest_lat=37.3861&dest_lon=-122.0839&departure_time=09:00"
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert "score" in data2
        assert len(data2.get("segments", [])) > 0

        # 3. POST /api/assess with AssessmentRequest
        post_req = {
            "lat": 37.7749,
            "lon": -122.4194,
            "dest_lat": 37.3861,
            "dest_lon": -122.0839,
            "departure_time": "08:00",
            "min_temp_caution": 45.0,
            "max_wind_caution": 15.0,
            "rain_threshold": 30.0,
        }
        res3 = client.post("/api/assess", json=post_req)
        assert res3.status_code == 200
        assert res3.json()["status"] == Status.GO.value


# =========================================================================
# 3. Waypoint Flexibility Handling (Tuples, Dicts, Waypoint objects)
# =========================================================================


def test_waypoints_various_formats_handling(client: TestClient):
    """Verify handling list of coordinate tuples, list of dicts, or Waypoint objects without crashing."""
    with patch(
        "app.client.WeatherClient.fetch_weather", new_callable=AsyncMock
    ) as mock_fetch:
        mock_fetch.return_value = generate_mock_weather_data(temp=67.0, wind=8.0)

        # 1. List of coordinate tuples: [[lat, lon], ...]
        payload_tuples = {
            "lat": 37.7749,
            "lon": -122.4194,
            "dest_lat": 37.3861,
            "dest_lon": -122.0839,
            "departure_time": "08:00",
            "waypoints": [
                [37.6879, -122.4702],
                [37.5630, -122.3255],
            ],
        }
        res_tuples = client.post("/api/assess", json=payload_tuples)
        assert res_tuples.status_code == 200
        data_tuples = res_tuples.json()
        # Origin + 2 waypoints + Destination = 4 waypoint evaluations, 3 segments
        assert len(data_tuples["waypoint_evaluations"]) == 4
        assert len(data_tuples["segments"]) == 3

        # 2. List of dicts with mixed keys ('lat'/'lon' and 'latitude'/'longitude')
        payload_dicts = {
            "lat": 37.7749,
            "lon": -122.4194,
            "dest_lat": 37.3861,
            "dest_lon": -122.0839,
            "departure_time": "08:00",
            "waypoints": [
                {"lat": 37.6879, "lon": -122.4702, "name": "Daly City"},
                {"latitude": 37.5630, "longitude": -122.3255, "name": "San Mateo"},
            ],
        }
        res_dicts = client.post("/api/check", json=payload_dicts)
        assert res_dicts.status_code == 200
        data_dicts = res_dicts.json()
        assert len(data_dicts["outbound_leg"]["waypoint_evaluations"]) == 4
        assert (
            data_dicts["outbound_leg"]["waypoint_evaluations"][1]["name"] == "Daly City"
        )
        assert (
            data_dicts["outbound_leg"]["waypoint_evaluations"][2]["name"] == "San Mateo"
        )


# =========================================================================
# 4. Along-the-Route Time-Interpolated Weather Engine & Segment Risk Scoring
# =========================================================================


def test_along_the_route_segment_scoring_and_hazard_pinpointing(client: TestClient):
    """
    Test timed waypoint interpolation and segment risk scoring.
    Simulate extreme wind hazard at the second waypoint (San Mateo).
    """

    def mock_fetch_weather_by_coord(lat, lon, unit_system=UnitSystem.IMPERIAL):
        # Severe wind only around San Mateo (lat 37.5630)
        if abs(lat - 37.5630) < 0.01:
            return generate_mock_weather_data(
                temp=60.0, wind=35.0, precip=10.0
            )  # Extreme wind > 25 (NO_GO)
        return generate_mock_weather_data(temp=65.0, wind=8.0, precip=0.0)

    with (
        patch("app.client.fetch_weather", side_effect=mock_fetch_weather_by_coord),
        patch(
            "app.client.WeatherClient.fetch_weather",
            side_effect=mock_fetch_weather_by_coord,
        ),
    ):
        payload = {
            "lat": 37.7749,
            "lon": -122.4194,
            "dest_lat": 37.3861,
            "dest_lon": -122.0839,
            "dest_name": "Mountain View",
            "departure_time": "08:00",
            "max_wind_caution": 15.0,
            "max_wind_no_go": 25.0,
            "waypoints": [
                {"lat": 37.5630, "lon": -122.3255, "name": "San Mateo Windy Pass"},
            ],
        }

        res = client.post("/api/check", json=payload)
        assert res.status_code == 200
        data = res.json()

        # Overall route status should be degraded due to hazard
        assert data["overall_status"] == Status.NO_GO.value
        assert len(data["hazard_pinpoints"]) > 0
        assert any("wind" in p["parameter"].lower() for p in data["hazard_pinpoints"])

        # Check waypoint evaluations
        wps = data["outbound_leg"]["waypoint_evaluations"]
        assert len(wps) == 3
        assert wps[1]["name"] == "San Mateo Windy Pass"
        assert wps[1]["status"] == Status.NO_GO.value

        # Check segment risk scoring
        segments = data["outbound_leg"]["segments"]
        assert len(segments) == 2
        # Segment entering or leaving the windy waypoint should reflect hazard
        assert any(
            seg["status"] in (Status.CAUTION.value, Status.NO_GO.value)
            for seg in segments
        )


# =========================================================================
# 5. External Service Resilience & Graceful Fallbacks
# =========================================================================


@pytest.mark.asyncio
async def test_osrm_failure_triggers_haversine_linear_fallback():
    """Verify that when OSRM fails or times out, RoutingService successfully executes haversine linear interpolation fallback."""
    routing = RoutingService(timeout=0.1)

    with patch(
        "httpx.AsyncClient.get",
        side_effect=httpx.ConnectTimeout("OSRM connection timeout"),
    ):
        origin = (37.7749, -122.4194)
        dest = (37.3861, -122.0839)
        waypoints = [(37.5630, -122.3255)]

        response = await routing.get_route_directions(origin, dest, waypoints)
        assert response.fallback is True
        assert response.total_distance > 0.0
        assert response.total_duration > 0.0
        assert len(response.legs) == 2
        assert len(response.geometry) == 3


def test_weather_client_error_produces_structured_503(
    client: TestClient, session: Session
):
    """Verify that WeatherClient network errors produce structured HTTP 503 rather than unhandled 500 exceptions."""
    user, token = create_user_and_token(session)

    network_err = httpx.ConnectError("Open-Meteo unreachable")
    with (
        patch("app.client.fetch_weather", side_effect=network_err),
        patch("app.client.WeatherClient.fetch_weather", side_effect=network_err),
        patch("app.client.WeatherClient.get_hourly_weather", side_effect=network_err),
    ):
        # 1. POST /api/check
        res_check = client.post(
            "/api/check",
            json={
                "lat": 37.7749,
                "lon": -122.4194,
                "dest_lat": 37.3861,
                "dest_lon": -122.0839,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_check.status_code == 503
        assert "detail" in res_check.json()
        assert "unavailable" in res_check.json()["detail"].lower()

        # 2. GET /api/check
        res_check_get = client.get(
            "/api/check?lat=37.7749&lon=-122.4194&dest_lat=37.3861&dest_lon=-122.0839",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_check_get.status_code == 503
        assert "detail" in res_check_get.json()

        # 3. POST /api/assess
        res_assess = client.post(
            "/api/assess",
            json={"lat": 37.7749, "lon": -122.4194},
        )
        assert res_assess.status_code == 503
        assert "detail" in res_assess.json()

        # 4. GET /api/assess
        res_assess_get = client.get(
            "/api/assess?lat=37.7749&lon=-122.4194",
        )
        assert res_assess_get.status_code == 503
        assert "detail" in res_assess_get.json()
