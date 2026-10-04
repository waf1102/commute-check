import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel
from sqlmodel.pool import StaticPool
from app.main import app
from app.database import get_session
from app.models import User, Commute
from app.security import ALGORITHM, SECRET_KEY, get_password_hash
from jose import jwt
from datetime import datetime, timedelta, timezone
import httpx

DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)


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


def create_user_and_token(session: Session):
    user = User(email="weather@example.com", hashed_password=get_password_hash("pass"))
    session.add(user)
    session.commit()
    session.refresh(user)

    commute1 = Commute(
        name="Work",
        lat=40.7128,
        lon=-74.0060,
        schedule_time="08:00",
        user_id=user.id,
        min_temp_caution=45.0,
        min_temp_no_go=38.0,
        max_wind_caution=15.0,
        max_wind_no_go=25.0,
        rain_threshold=30.0,
    )
    commute2 = Commute(
        name="Gym",
        lat=40.7306,
        lon=-73.9352,
        schedule_time="17:00",
        user_id=user.id,
        min_temp_caution=50.0,
        min_temp_no_go=40.0,
        max_wind_caution=20.0,
        max_wind_no_go=30.0,
        rain_threshold=40.0,
    )
    session.add(commute1)
    session.add(commute2)
    session.commit()
    session.refresh(commute1)
    session.refresh(commute2)

    token = jwt.encode(
        {"sub": user.email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return user, commute1, commute2, token


def test_weather_forecast_endpoint(client: TestClient, session: Session):
    user, commute1, commute2, token = create_user_and_token(session)

    with patch("app.client.fetch_weather", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {
            "hourly": {
                "time": ["2026-08-02T08:00", "2026-08-02T09:00"],
                "temperature_2m": [70.0, 72.0],
                "apparent_temperature": [71.0, 73.0],
                "wind_speed_10m": [8.0, 10.0],
                "precipitation_probability": [0, 5],
                "weather_code": [0, 0],
            }
        }

        response = client.get(
            "/weather/forecast", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "hourly" in data
        assert "thresholds" in data
        assert data["unit_system"] == "imperial"
        assert len(data["hourly"]) == 2
        assert data["thresholds"]["min_temp_caution"] == 45.0
        assert data["thresholds"]["min_temp_no_go"] == 38.0
        assert data["thresholds"]["max_wind_caution"] == 15.0
        assert data["thresholds"]["max_wind_no_go"] == 25.0
        assert data["thresholds"]["rain_threshold"] == 30.0
        assert data["hourly"][0]["temperature"] == 70.0
        assert data["hourly"][0]["apparent_temp"] == 71.0
        assert data["hourly"][0]["wind_speed"] == 8.0
        assert data["hourly"][0]["precip_prob"] == 0
        assert data["hourly"][0]["weather_code"] == 0


def test_weather_forecast_with_commute_id(client: TestClient, session: Session):
    user, commute1, commute2, token = create_user_and_token(session)

    with patch("app.client.fetch_weather", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {
            "hourly": {
                "time": ["2026-08-02T17:00"],
                "temperature_2m": [65.0],
                "apparent_temperature": [65.0],
                "wind_speed_10m": [12.0],
                "precipitation_probability": [10],
                "weather_code": [1],
            }
        }

        response = client.get(
            f"/weather/forecast?commute_id={commute2.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["thresholds"]["min_temp_caution"] == 50.0
        assert data["thresholds"]["rain_threshold"] == 40.0


def test_weather_forecast_metric_units(client: TestClient, session: Session):
    user, commute1, commute2, token = create_user_and_token(session)

    with patch("app.client.fetch_weather", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {
            "hourly": {
                "time": ["2026-08-02T08:00"],
                "temperature_2m": [21.0],
                "apparent_temperature": [21.5],
                "wind_speed_10m": [13.0],
                "precipitation_probability": [0],
                "weather_code": [0],
            }
        }

        response = client.get(
            "/weather/forecast?unit_system=metric",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["unit_system"] == "metric"
        assert data["hourly"][0]["temperature"] == 21.0


def test_weather_forecast_service_unavailable(client: TestClient, session: Session):
    user, commute1, commute2, token = create_user_and_token(session)

    with patch("app.client.fetch_weather", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = httpx.HTTPError("Service down")

        response = client.get(
            "/weather/forecast", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 502
        assert response.json()["detail"] == "Weather service unavailable"


def test_weather_forecast_none_guarding(client: TestClient, session: Session):
    user, commute1, commute2, token = create_user_and_token(session)

    with patch("app.client.fetch_weather", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {
            "hourly": {
                "time": ["2026-08-02T08:00"],
                "temperature_2m": [None],
                "apparent_temperature": [None],
                "wind_speed_10m": [None],
                "precipitation_probability": [None],
                "weather_code": [None],
            }
        }

        response = client.get(
            "/weather/forecast", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Weather forecast is incomplete"


def test_weather_forecast_no_commute(client: TestClient, session: Session):
    user = User(
        email="nocommute@example.com", hashed_password=get_password_hash("pass")
    )
    session.add(user)
    session.commit()
    token = jwt.encode(
        {"sub": user.email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    response = client.get(
        "/weather/forecast", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Commute configuration not found"


def test_weather_forecast_unauthenticated(client: TestClient):
    response = client.get("/weather/forecast")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_weather_client_caching():
    from app.client import WeatherClient

    client = WeatherClient()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json.return_value = {"hourly": {"temperature_2m": [70.0]}}
        mock_get.return_value = mock_response

        # First call fetches from remote
        res1 = await client.fetch_weather(40.0, -70.0)
        assert res1["hourly"]["temperature_2m"][0] == 70.0
        assert mock_get.call_count == 1

        # Second call hits TTLCache
        res2 = await client.fetch_weather(40.0, -70.0)
        assert res2["hourly"]["temperature_2m"][0] == 70.0
        assert mock_get.call_count == 1  # No extra HTTP call


from app.models import UnitSystem


def test_get_forecast_with_destination(client: TestClient, session: Session):
    user, commute1, commute2, token = create_user_and_token(session)

    with patch("app.client.fetch_weather", new_callable=AsyncMock) as mock_fetch:

        def side_effect(lat, lon, unit_system=UnitSystem.IMPERIAL):
            if lat == 37.7749:
                return {
                    "hourly": {
                        "time": ["2026-08-02T08:00"],
                        "temperature_2m": [70.0],
                        "apparent_temperature": [71.0],
                        "wind_speed_10m": [8.0],
                        "precipitation_probability": [0],
                        "weather_code": [0],
                    }
                }
            else:
                return {
                    "hourly": {
                        "time": ["2026-08-02T08:00"],
                        "temperature_2m": [65.0],
                        "apparent_temperature": [66.0],
                        "wind_speed_10m": [10.0],
                        "precipitation_probability": [5],
                        "weather_code": [0],
                    }
                }

        mock_fetch.side_effect = side_effect

        response = client.get(
            "/weather/forecast?lat=37.7749&lon=-122.4194&dest_lat=37.3861&dest_lon=-122.0839",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "hourly" in data
        assert "destination_hourly" in data
        assert data["destination_hourly"] is not None
        assert len(data["destination_hourly"]) == 1
        assert data["destination_hourly"][0]["temperature"] == 65.0
