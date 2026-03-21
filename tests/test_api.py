import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel
from app.main import app, get_session
from unittest.mock import patch
from app.models import Commute, HourlyWeather

DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})

def get_session_override():
    with Session(engine) as session:
        yield session

app.dependency_overrides[get_session] = get_session_override

@pytest.fixture(scope="function", autouse=True)
def setup_teardown_database():
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_read_config_not_found():
    response = client.get("/config")
    assert response.status_code == 404
    assert response.json() == {"detail": "Configuration not found"}

def test_create_and_read_config():
    # Create a new configuration
    config_data = {
        "name": "My Test Commute",
        "lat": 47.6062,
        "lon": -122.3321,
        "webhook_url": "https://example.com/webhook",
        "schedule_time": "08:00",
        "min_temp_caution": 50,
        "min_temp_no_go": 40,
        "max_wind_caution": 15,
        "max_wind_no_go": 25,
        "rain_threshold": 20
    }
    response = client.post("/config", json=config_data)
    assert response.status_code == 200
    created_config = response.json()
    assert created_config["name"] == config_data["name"]
    assert "id" in created_config

    # Read the configuration
    response = client.get("/config")
    assert response.status_code == 200
    read_config = response.json()
    assert read_config["name"] == config_data["name"]
    assert read_config["lat"] == config_data["lat"]

def test_update_config():
    # Create an initial configuration
    initial_config = {
        "name": "Initial Commute",
        "lat": 1.1,
        "lon": 2.2,
        "webhook_url": "https://example.com/initial",
        "schedule_time": "09:00"
    }
    client.post("/config", json=initial_config)

    # Update the configuration
    updated_config = {
        "name": "Updated Commute",
        "lat": 3.3,
        "lon": 4.4,
        "webhook_url": "https://example.com/updated",
        "schedule_time": "10:00"
    }
    response = client.post("/config", json=updated_config)
    assert response.status_code == 200

    # Verify the update
    response = client.get("/config")
    assert response.status_code == 200
    retrieved_config = response.json()
    assert retrieved_config["name"] == updated_config["name"]
    assert retrieved_config["schedule_time"] == updated_config["schedule_time"]

def test_assess_endpoint():
    dummy_weather = HourlyWeather(
        temperature=70.0,
        apparent_temp=72.0,
        wind_speed=5.0,
        wind_gusts=10.0,
        precip_prob=0,
        weather_code=0
    )
    
    with patch("app.main.client_instance.get_hourly_weather", return_value=dummy_weather):
        response = client.get("/assess?lat=47.6062&lon=-122.3321")
        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert "reasons" in data
        assert "details" in data
        assert data["details"]["temperature"] == 70.0

# The old test_assess_commute is removed as per the plan.
