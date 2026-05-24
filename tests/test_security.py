import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from app.main import app # Assuming app is imported
from app.database import get_session # Assuming get_session is defined
from app.models import User # Assuming User model is defined

# Setup an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@pytest.fixture(name="session")
def session_fixture():
    create_db_and_tables()
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine) # Clean up after tests

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        yield session
    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

# --- Security Helper Function Tests ---
def test_get_password_hash_failing():
    from app.security import get_password_hash
    password = "testpassword"
    hashed_password = get_password_hash(password)
    assert hashed_password != password
    assert isinstance(hashed_password, str)
    assert len(hashed_password) > 0

def test_verify_password_correct_failing():
    from app.security import get_password_hash, verify_password
    password = "testpassword"
    hashed_password = get_password_hash(password)
    assert verify_password(password, hashed_password) is True

def test_verify_password_incorrect_failing():
    from app.security import get_password_hash, verify_password
    password = "testpassword"
    wrong_password = "wrongpassword"
    hashed_password = get_password_hash(password)
    assert verify_password(wrong_password, hashed_password) is False

def test_create_access_token_failing():
    from app.security import create_access_token
    data = {"sub": "test@example.com"}
    token = create_access_token(data)
    assert isinstance(token, str)
    assert len(token) > 0

# --- API Endpoint Tests ---
def test_register_user_failing(client: TestClient):
    response = client.post(
        "/api/register",
        json={"email": "test@example.com", "password": "testpassword"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "User registered successfully"

    # Verify user exists in DB
    with Session(engine) as session:
        user = session.query(User).filter(User.email == "test@example.com").first()
        assert user is not None
        assert user.email == "test@example.com"
        assert user.hashed_password is not None
        assert user.hashed_password != "testpassword"

def test_register_duplicate_user_failing(client: TestClient):
    client.post("/api/register", json={"email": "duplicate@example.com", "password": "testpassword"})
    response = client.post(
        "/api/register",
        json={"email": "duplicate@example.com", "password": "anotherpassword"}
    )
    assert response.status_code == 400
    assert "User with this email already exists" in response.json()["detail"]

def test_login_user_success_failing(client: TestClient):
    # First register a user
    client.post("/api/register", json={"email": "login@example.com", "password": "loginpassword"})

    response = client.post(
        "/api/login",
        data={"username": "login@example.com", "password": "loginpassword"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_user_incorrect_password_failing(client: TestClient):
    # First register a user
    client.post("/api/register", json={"email": "badpass@example.com", "password": "correctpassword"})

    response = client.post(
        "/api/login",
        data={"username": "badpass@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"
