import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel
from app.main import app, get_session
from unittest.mock import patch
from app.models import Commute, HourlyWeather, User, CommuteCreate
from app.security import ALGORITHM, SECRET_KEY, create_access_token, get_password_hash
from jose import jwt
from datetime import datetime, timedelta, timezone

DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session_override():
    with Session(engine) as session:
        yield session

app.dependency_overrides[get_session] = get_session_override

@pytest.fixture(name="session")
def session_fixture():
    create_db_and_tables()
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="client")
def client_fixture(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def create_test_user(session: Session, email: str = "test@example.com", password: str = "testpassword") -> User:
    hashed_password = get_password_hash(password)
    user = User(email=email, hashed_password=hashed_password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def get_auth_token(email: str = "test@example.com", password: str = "testpassword") -> str:
    access_token_expires = timedelta(minutes=30)
    to_encode = {"sub": email}
    expire = datetime.now(timezone.utc) + access_token_expires
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@pytest.fixture
def authenticated_client(client: TestClient, session: Session):
    user = create_test_user(session)
    token = get_auth_token(email=user.email)
    client.headers = {"Authorization": f"Bearer {token}"}
    return client, user

def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_read_config_not_found(authenticated_client: tuple[TestClient, User]):
    client, user = authenticated_client
    response = client.get("/config")
    assert response.status_code == 200
    assert response.json() == []

def test_create_and_read_config(authenticated_client: tuple[TestClient, User]):
    client, user = authenticated_client
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
    assert created_config["user_id"] == user.id

    # Read the configuration
    response = client.get("/config")
    assert response.status_code == 200
    read_config = response.json()[0] # Access the first element of the list
    assert read_config["name"] == config_data["name"]
    assert read_config["lat"] == config_data["lat"]
    assert read_config["user_id"] == user.id

def test_update_config(authenticated_client: tuple[TestClient, User]):
    client, user = authenticated_client
    # Create an initial configuration
    initial_config = {
        "name": "Initial Commute",
        "lat": 1.1,
        "lon": 2.2,
        "webhook_url": "https://example.com/initial",
        "schedule_time": "09:00"
    }
    initial_config_response = client.post("/config", json=initial_config)
    assert initial_config_response.status_code == 200
    initial_commute = initial_config_response.json()
    initial_commute_id = initial_commute["id"]

    # Update the configuration
    updated_config = {
        "id": initial_commute_id, # Include the ID for update
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
    retrieved_config = response.json()[0] # Access the first element of the list
    assert retrieved_config["name"] == updated_config["name"]
    assert retrieved_config["schedule_time"] == updated_config["schedule_time"]
    assert retrieved_config["user_id"] == user.id

def test_assess_endpoint(client: TestClient):
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
