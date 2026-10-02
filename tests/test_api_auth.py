from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel
from app.main import app
from app.database import get_session
from app.models import User, Commute, CommuteCreate
from app.security import ALGORITHM, SECRET_KEY, create_access_token, get_password_hash
from jose import jwt
from datetime import datetime, timedelta, timezone
import os
import pytest

# Setup in-memory SQLite for testing
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, echo=False)

@pytest.fixture(autouse=True, scope="module")
def cleanup_test_db():
    yield
    engine.dispose()
    if os.path.exists("./test.db"):
        try:
            os.remove("./test.db")
        except OSError:
            pass

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session_override():
    with Session(engine) as session:
        yield session

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

@pytest.fixture
def other_user_authenticated_client(client: TestClient, session: Session):
    user = create_test_user(session, email="other@example.com")
    token = get_auth_token(email=user.email)
    client.headers = {"Authorization": f"Bearer {token}"}
    return client, user

def test_get_current_user_valid_token(authenticated_client: TestClient):
    # This test directly verifies behavior that will be implemented in app/security.py
    # For now, it will fail because get_current_user is not yet implemented or wired.
    # We will mock the dependency later for other tests if needed, but for now we want to test the actual implementation.
    # The actual implementation relies on app.security.get_current_user which we cannot directly test with the client,
    # but the endpoints that use it will implicitly test it.
    # The framework will raise an HTTPException if authentication fails.
    # This test will pass once app.security.get_current_user is implemented and used in an endpoint.
    pass # Placeholder for implicit testing via endpoints

def test_get_current_user_invalid_token(client: TestClient):
    response = client.get("/config", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"

def test_read_config_authenticated(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    # Create a commute for the authenticated user
    commute_data = CommuteCreate(name="Home", lat=1.0, lon=2.0, schedule_time="08:00")
    commute = Commute.model_validate(commute_data, update={"user_id": user.id})
    session.add(commute)
    session.commit()
    session.refresh(commute)

    # Create a commute for another user
    other_user = create_test_user(session, email="other@test.com", password="otherpassword")
    other_commute_data = CommuteCreate(name="Work", lat=3.0, lon=4.0, schedule_time="09:00")
    other_commute = Commute.model_validate(other_commute_data, update={"user_id": other_user.id})
    session.add(other_commute)
    session.commit()
    session.refresh(other_commute)

    response = client.get("/config")
    assert response.status_code == 200
    commutes = response.json()
    assert len(commutes) == 1
    assert commutes[0]["name"] == "Home"
    assert commutes[0]["user_id"] == user.id

def test_read_config_unauthenticated(client: TestClient):
    response = client.get("/config")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_create_config_authenticated(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    commute_data = {
        "name": "New Commute",
        "lat": 10.0,
        "lon": 20.0,
        "schedule_time": "07:30"
    }
    response = client.post("/config", json=commute_data)
    assert response.status_code == 200
    created_commute = response.json()
    assert created_commute["name"] == "New Commute"
    assert created_commute["user_id"] == user.id

    # Verify it's in the DB with the correct user_id
    db_commute = session.get(Commute, created_commute["id"])
    assert db_commute is not None
    assert db_commute.user_id == user.id

def test_create_config_unauthenticated(client: TestClient):
    commute_data = {
        "name": "New Commute",
        "lat": 10.0,
        "lon": 20.0,
        "schedule_time": "07:30"
    }
    response = client.post("/config", json=commute_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_delete_config_authenticated_owner(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    commute_data = CommuteCreate(name="To Delete", lat=1.0, lon=2.0, schedule_time="08:00")
    commute = Commute.model_validate(commute_data, update={"user_id": user.id})
    session.add(commute)
    session.commit()
    session.refresh(commute)

    response = client.delete(f"/config/{commute.id}")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"

    # Verify it's deleted from DB
    db_commute = session.get(Commute, commute.id)
    assert db_commute is None

def test_delete_config_authenticated_not_owner(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    # Create commute for another user
    other_user = create_test_user(session, email="another@test.com", password="anotherpassword")
    other_commute_data = CommuteCreate(name="Other Commute", lat=3.0, lon=4.0, schedule_time="09:00")
    other_commute = Commute.model_validate(other_commute_data, update={"user_id": other_user.id})
    session.add(other_commute)
    session.commit()
    session.refresh(other_commute)

    response = client.delete(f"/config/{other_commute.id}")
    assert response.status_code == 404 # Should be 404 or 403, depending on implementation
    assert "not found" in response.json()["detail"].lower() or "not authorized" in response.json()["detail"].lower()

    # Verify it's NOT deleted from DB
    db_commute = session.get(Commute, other_commute.id)
    assert db_commute is not None

def test_delete_config_unauthenticated(client: TestClient, session: Session):
    commute_data = CommuteCreate(name="To Delete", lat=1.0, lon=2.0, schedule_time="08:00")
    commute = Commute.model_validate(commute_data, update={"user_id": create_test_user(session).id})
    session.add(commute)
    session.commit()
    session.refresh(commute)

    response = client.delete(f"/config/{commute.id}")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

# Test for updating a commute
def test_update_config_authenticated_owner(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    # Create a commute for the user
    commute_data = CommuteCreate(name="Old Name", lat=1.0, lon=1.0, schedule_time="08:00")
    commute = Commute.model_validate(commute_data, update={"user_id": user.id})
    session.add(commute)
    session.commit()
    session.refresh(commute)

    updated_data = commute.model_dump()
    updated_data["name"] = "New Name"
    updated_data["id"] = commute.id

    response = client.post("/config", json=updated_data)
    assert response.status_code == 200
    updated_commute = response.json()
    assert updated_commute["name"] == "New Name"
    assert updated_commute["id"] == commute.id
    assert updated_commute["user_id"] == user.id

    db_commute = session.get(Commute, commute.id)
    assert db_commute.name == "New Name"

def test_update_config_authenticated_not_owner(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    # Create commute for another user
    other_user = create_test_user(session, email="another_update@test.com", password="anotherpassword")
    other_commute_data = CommuteCreate(name="Other Commute", lat=3.0, lon=4.0, schedule_time="09:00")
    other_commute = Commute.model_validate(other_commute_data, update={"user_id": other_user.id})
    session.add(other_commute)
    session.commit()
    session.refresh(other_commute)

    updated_data = other_commute.model_dump()
    updated_data["name"] = "Attempted Tamper"
    updated_data["id"] = other_commute.id

    response = client.post("/config", json=updated_data)
    assert response.status_code == 404 # Should be 404 or 403
    assert "not found" in response.json()["detail"].lower() or "not authorized" in response.json()["detail"].lower()

    db_commute = session.get(Commute, other_commute.id)
    assert db_commute.name == "Other Commute" # Should not be updated

def test_update_config_unauthenticated(client: TestClient, session: Session):
    commute_data = CommuteCreate(name="Original Name", lat=1.0, lon=1.0, schedule_time="08:00")
    commute = Commute.model_validate(commute_data, update={"user_id": create_test_user(session).id})
    session.add(commute)
    session.commit()
    session.refresh(commute)

    updated_data = commute.model_dump()
    updated_data["name"] = "Should Not Change"
    updated_data["id"] = commute.id

    response = client.post("/config", json=updated_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
