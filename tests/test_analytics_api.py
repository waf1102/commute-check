from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel, select
from app.main import app
from app.database import get_session
from app.models import User, AssessmentHistory, CommuteType
from app.security import ALGORITHM, SECRET_KEY, get_password_hash
from jose import jwt
import os
from datetime import datetime, timedelta, date, timezone
import pytest

# Setup in-memory SQLite for testing
DATABASE_URL = "sqlite:///./test_analytics.db"
engine = create_engine(DATABASE_URL, echo=False)

@pytest.fixture(autouse=True, scope="module")
def cleanup_test_db():
    yield
    engine.dispose()
    if os.path.exists("./test_analytics.db"):
        try:
            os.remove("./test_analytics.db")
        except OSError:
            pass

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

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
    create_db_and_tables()
    hashed_password = get_password_hash(password)
    user = User(email=email, hashed_password=hashed_password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def get_auth_token(email: str = "test@example.com") -> str:
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

def create_assessment_history(session: Session, user: User, commute_type: CommuteType, timestamp: datetime, duration: float = 30.0, distance: float = 15.0):
    history_entry = AssessmentHistory(
        user_id=user.id,
        timestamp=timestamp,
        commute_type=commute_type.value,
        commute_distance_km=distance,
        duration_minutes=duration
    )
    session.add(history_entry)
    session.commit()
    session.refresh(history_entry)
    return history_entry

def test_get_daily_commute_stats_authenticated_success(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client

    today = datetime.now(timezone.utc)
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    create_assessment_history(session, user, CommuteType.RIDING, two_days_ago.replace(hour=8), 30.0, 15.0)
    create_assessment_history(session, user, CommuteType.DRIVING, two_days_ago.replace(hour=17), 45.0, 20.0)
    create_assessment_history(session, user, CommuteType.RIDING, yesterday.replace(hour=8), 30.0, 15.0)

    start_date = two_days_ago.strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    response = client.get(f"/analytics/commute-stats/daily?user_id={user.id}&start_date={start_date}&end_date={end_date}")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2

def test_get_daily_commute_stats_unauthenticated(client: TestClient, session: Session):
    user = create_test_user(session)
    start_date = date.today().strftime("%Y-%m-%d")
    end_date = date.today().strftime("%Y-%m-%d")

    response = client.get(f"/analytics/commute-stats/daily?user_id={user.id}&start_date={start_date}&end_date={end_date}")
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

def test_get_daily_commute_stats_idor_protection(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    other_user = create_test_user(session, email="other@example.com")

    start_date = date.today().strftime("%Y-%m-%d")
    end_date = date.today().strftime("%Y-%m-%d")

    # Attempt to access other user's data using the authenticated client
    response = client.get(f"/analytics/commute-stats/daily?user_id={other_user.id}&start_date={start_date}&end_date={end_date}")
    
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to access analytics for this user."

def test_record_decision_riding_success(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    payload = {
        "decision": "riding",
        "commute_distance_km": 12.0,
        "duration_minutes": 25.0,
    }
    response = client.post("/api/analytics/record-decision", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user.id
    assert data["commute_type"] == "riding"
    assert data["commute_distance_km"] == 12.0
    assert data["duration_minutes"] == 25.0

def test_record_decision_driving_updates_existing_record(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    from app.models import Commute
    from app.analytics.service import record_assessment_run

    commute = Commute(name="Daily Route", lat=37.77, lon=-122.41, schedule_time="08:00", user_id=user.id)
    session.add(commute)
    session.commit()
    session.refresh(commute)

    # Simulate scheduler auto-logging an assessment without decision
    history = record_assessment_run(
        session,
        user_id=user.id,
        commute_id=commute.id,
        overall_status="Go",
        overall_score=88.0,
        leg_type="outbound",
    )

    # User records driving decision
    payload = {
        "assessment_history_id": history.id,
        "decision": "driving",
        "commute_distance_km": 15.0,
        "duration_minutes": 35.0,
    }
    response = client.post("/api/analytics/record-decision", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == history.id
    assert data["commute_type"] == "driving"
    assert data["overall_score"] == 88.0

def test_record_decision_invalid_choice(authenticated_client: tuple[TestClient, User]):
    client, _ = authenticated_client
    response = client.post("/api/analytics/record-decision", json={"decision": "helicopter"})
    assert response.status_code == 400
    assert "Invalid decision" in response.json()["detail"]

def test_record_decision_unauthenticated(client: TestClient):
    response = client.post("/api/analytics/record-decision", json={"decision": "riding"})
    assert response.status_code == 401

def test_record_decision_idor_protection(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    other_user = create_test_user(session, email="victim@example.com")
    from app.analytics.service import record_assessment_run

    other_history = record_assessment_run(
        session,
        user_id=other_user.id,
        overall_status="Go",
        overall_score=90.0,
    )

    response = client.post("/api/analytics/record-decision", json={
        "assessment_history_id": other_history.id,
        "decision": "driving"
    })
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]

