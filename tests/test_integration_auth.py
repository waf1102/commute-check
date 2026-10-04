import os
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlmodel import Session, SQLModel, create_engine, select

from app.database import get_session
from app.main import app
from app.models import User
from app.security import ALGORITHM, SECRET_KEY, create_access_token, get_password_hash

TEST_DB_FILE = "./test_integration_auth.db"
DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"
engine = create_engine(
    DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
)


@pytest.fixture(autouse=True, scope="module")
def cleanup_test_db():
    yield
    engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass


@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_registration_success(client: TestClient, session: Session):
    """Test user registration with valid JSON payload."""
    payload = {"email": "newuser@example.com", "password": "supersecurepassword"}
    response = client.post("/api/register", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "User registered successfully"
    assert "user" in data
    assert data["user"]["email"] == "newuser@example.com"
    assert "id" in data["user"]
    assert (
        "hashed_password" not in data["user"]
        or data["user"]["hashed_password"] != "supersecurepassword"
    )

    # Verify user exists in the database
    db_user = session.exec(
        select(User).where(User.email == "newuser@example.com")
    ).first()
    assert db_user is not None
    assert db_user.email == "newuser@example.com"


def test_registration_duplicate_email_returns_400(client: TestClient):
    """Test duplicate registration returns HTTP 400 with user-friendly error message."""
    payload = {"email": "duplicate@example.com", "password": "password123"}
    resp1 = client.post("/api/register", json=payload)
    assert resp1.status_code == 200

    resp2 = client.post("/api/register", json=payload)
    assert resp2.status_code == 400
    assert resp2.json()["detail"] == "User with this email already exists"


def test_login_json_payload_email_success(client: TestClient):
    """Test login with JSON payload {email, password} returns JWT and user info."""
    # Register first
    client.post(
        "/api/register",
        json={"email": "jsonlogin@example.com", "password": "mypassword"},
    )

    # Login via JSON body with email field
    response = client.post(
        "/api/login", json={"email": "jsonlogin@example.com", "password": "mypassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert data["user"]["email"] == "jsonlogin@example.com"
    assert isinstance(data["user"]["id"], int)


def test_login_json_payload_username_success(client: TestClient):
    """Test login with JSON payload {username, password} returns JWT and user info."""
    client.post(
        "/api/register",
        json={"email": "userlogin@example.com", "password": "mypassword"},
    )

    response = client.post(
        "/api/login",
        json={"username": "userlogin@example.com", "password": "mypassword"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "userlogin@example.com"


def test_login_form_data_success(client: TestClient):
    """Test login with standard OAuth2 application/x-www-form-urlencoded form data."""
    client.post(
        "/api/register",
        json={"email": "formlogin@example.com", "password": "mypassword"},
    )

    response = client.post(
        "/api/login",
        data={"username": "formlogin@example.com", "password": "mypassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "formlogin@example.com"


def test_login_invalid_password(client: TestClient):
    """Test login with incorrect password returns 401."""
    registered = client.post(
        "/api/register",
        json={"email": "wrongpass@example.com", "password": "correct-password"},
    )
    assert registered.status_code == 200

    response = client.post(
        "/api/login", json={"email": "wrongpass@example.com", "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_login_nonexistent_user(client: TestClient):
    """Test login with non-existent email returns 401."""
    response = client.post(
        "/api/login", json={"email": "nobody@example.com", "password": "somepassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_existing_mixed_case_account_can_still_sign_in(
    client: TestClient, session: Session
):
    legacy = User(
        email="Rider@Example.com",
        hashed_password=get_password_hash("existing-password"),
    )
    session.add(legacy)
    session.commit()
    response = client.post(
        "/api/login",
        json={"email": "rider@example.com", "password": "existing-password"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "Rider@Example.com"
    duplicate = client.post(
        "/api/register", json={"email": "RIDER@example.com", "password": "new-password"}
    )
    assert duplicate.status_code == 400


def test_login_missing_credentials(client: TestClient):
    """Test login with missing fields returns 400 Bad Request."""
    response = client.post("/api/login", json={})
    assert response.status_code == 400
    assert "required" in response.json()["detail"].lower()


def test_auth_me_endpoint_success(client: TestClient):
    """Test /api/auth/me and /api/me return the authenticated user record."""
    reg = client.post(
        "/api/register", json={"email": "profile@example.com", "password": "mypassword"}
    )
    user_id = reg.json()["user"]["id"]

    login_resp = client.post(
        "/api/login", json={"email": "profile@example.com", "password": "mypassword"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test /api/auth/me
    resp_me = client.get("/api/auth/me", headers=headers)
    assert resp_me.status_code == 200
    me_data = resp_me.json()
    assert me_data["id"] == user_id
    assert me_data["email"] == "profile@example.com"
    assert "hashed_password" not in me_data

    # Test /api/me alias
    resp_me_alias = client.get("/api/me", headers=headers)
    assert resp_me_alias.status_code == 200
    assert resp_me_alias.json()["id"] == user_id


def test_auth_me_unauthenticated(client: TestClient):
    """Test /api/auth/me without authorization header returns 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_auth_me_invalid_token(client: TestClient):
    """Test /api/auth/me with invalid or malformed token returns 401."""
    response = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer invalid_malformed_token"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_auth_me_expired_token(client: TestClient):
    """Test /api/auth/me with expired token returns 401."""
    client.post(
        "/api/register", json={"email": "expired@example.com", "password": "password"}
    )

    # Create expired token
    to_encode = {
        "sub": "expired@example.com",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
    }
    expired_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_auth_me_deleted_user(client: TestClient, session: Session):
    """Test /api/auth/me when the user represented in JWT no longer exists in DB."""
    client.post(
        "/api/register", json={"email": "deleted@example.com", "password": "password"}
    )
    login_resp = client.post(
        "/api/login", json={"email": "deleted@example.com", "password": "password"}
    )
    token = login_resp.json()["access_token"]

    # Delete user from DB
    user = session.exec(select(User).where(User.email == "deleted@example.com")).first()
    session.delete(user)
    session.commit()

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_complete_auth_session_flow(client: TestClient):
    """Complete golden-path integration test exercising full authentication and session lifecycle."""
    # 1. Register
    reg_resp = client.post(
        "/api/register",
        json={"email": "golden@example.com", "password": "SecurePassword99!"},
    )
    assert reg_resp.status_code == 200

    # 2. Duplicate registration check
    dup_resp = client.post(
        "/api/register",
        json={"email": "golden@example.com", "password": "SecurePassword99!"},
    )
    assert dup_resp.status_code == 400

    # 3. Login with JSON payload
    login_resp = client.post(
        "/api/login",
        json={"email": "golden@example.com", "password": "SecurePassword99!"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    token = login_data["access_token"]
    user_id = login_data["user"]["id"]
    assert token and user_id

    # 4. Use token to fetch user profile via /api/auth/me
    auth_headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/api/auth/me", headers=auth_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["id"] == user_id
    assert me_resp.json()["email"] == "golden@example.com"

    # 5. Access protected resource /config
    config_resp = client.get("/config", headers=auth_headers)
    assert config_resp.status_code == 200
