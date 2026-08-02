import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel
from app.main import app
from app.database import get_session
from app.models import User, Commute
from app.security import ALGORITHM, SECRET_KEY, get_password_hash
from jose import jwt
from datetime import datetime, timedelta, timezone

DATABASE_URL = "sqlite:///./test_weather.db"
engine = create_engine(DATABASE_URL, echo=False)

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
    
    commute = Commute(
        name="Work",
        lat=40.7128,
        lon=-74.0060,
        schedule_time="08:00",
        user_id=user.id,
        min_temp_caution=45.0,
        min_temp_no_go=38.0,
        max_wind_caution=15.0,
        max_wind_no_go=25.0,
        rain_threshold=30.0
    )
    session.add(commute)
    session.commit()
    session.refresh(commute)

    token = jwt.encode({"sub": user.email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, SECRET_KEY, algorithm=ALGORITHM)
    return user, commute, token

def test_weather_forecast_endpoint(client: TestClient, session: Session):
    user, commute, token = create_user_and_token(session)
    
    with patch("app.client.fetch_weather", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {
            "hourly": {
                "time": ["2026-08-02T08:00", "2026-08-02T09:00"],
                "temperature_2m": [70.0, 72.0],
                "apparent_temperature": [71.0, 73.0],
                "wind_speed_10m": [8.0, 10.0],
                "precipitation_probability": [0, 5],
                "weather_code": [0, 0]
            }
        }
        
        response = client.get("/weather/forecast", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert "hourly" in data
        assert "thresholds" in data
        assert "unit_system" in data
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

def test_weather_forecast_no_commute(client: TestClient, session: Session):
    user = User(email="nocommute@example.com", hashed_password=get_password_hash("pass"))
    session.add(user)
    session.commit()
    token = jwt.encode({"sub": user.email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, SECRET_KEY, algorithm=ALGORITHM)

    response = client.get("/weather/forecast", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Commute configuration not found"

def test_weather_forecast_unauthenticated(client: TestClient):
    response = client.get("/weather/forecast")
    assert response.status_code == 401
