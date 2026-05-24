from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel, select
from app.main import app
from app.database import get_session
from app.models import User, AssessmentHistory, AssessmentResult, CommuteType, UnitSystem
from app.security import ALGORITHM, SECRET_KEY, get_password_hash
from jose import jwt
from datetime import datetime, timedelta, date, timezone
import pytest

# Setup in-memory SQLite for testing
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, echo=False)

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

def create_assessment_history(session: Session, user: User, commute_type: CommuteType, timestamp: datetime, score: float):
    assessment_result = AssessmentResult(
        commute_type=commute_type,
        score=score,
        details={"temp": 20, "wind": 5},
        commute_id=1, # Dummy commute_id
        user_id=user.id,
        unit_system=UnitSystem.IMPERIAL
    )
    history_entry = AssessmentHistory(
        user_id=user.id,
        timestamp=timestamp,
        commute_type=commute_type,
        assessment_result=assessment_result
    )
    session.add(history_entry)
    session.commit()
    session.refresh(history_entry)
    return history_entry


def test_get_daily_commute_stats_authenticated_success(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    
    # Seed data
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    # User's data
    create_assessment_history(session, user, CommuteType.RIDING, two_days_ago.replace(hour=8), 80.0)
    create_assessment_history(session, user, CommuteType.DRIVING, two_days_ago.replace(hour=17), 50.0)
    create_assessment_history(session, user, CommuteType.RIDING, yesterday.replace(hour=8), 90.0)
    create_assessment_history(session, user, CommuteType.RIDING, yesterday.replace(hour=18), 70.0)
    create_assessment_history(session, user, CommuteType.DRIVING, today.replace(hour=8), 60.0)

    start_date = (two_days_ago - timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    response = client.get(f"/analytics/commute-stats/daily?user_id={user.id}&start_date={start_date}&end_date={end_date}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) >= 3 # At least for the three days with data

    # Check data for two days ago
    day_two_ago_data = next((item for item in data if item["date"] == two_days_ago.strftime("%Y-%m-%d")), None)
    assert day_two_ago_data is not None
    assert day_two_ago_data["days_ridden"] == 1
    assert day_two_ago_data["days_driven"] == 1
    assert day_two_ago_data["days_total"] == 2
    assert day_two_ago_data["avg_score"] == pytest.approx(65.0)

    # Check data for yesterday
    day_yesterday_data = next((item for item in data if item["date"] == yesterday.strftime("%Y-%m-%d")), None)
    assert day_yesterday_data is not None
    assert day_yesterday_data["days_ridden"] == 2
    assert day_yesterday_data["days_driven"] == 0
    assert day_yesterday_data["days_total"] == 2
    assert day_yesterday_data["avg_score"] == pytest.approx(80.0) # (90+70)/2

    # Check data for today
    day_today_data = next((item for item in data if item["date"] == today.strftime("%Y-%m-%d")), None)
    assert day_today_data is not None
    assert day_today_data["days_ridden"] == 0
    assert day_today_data["days_driven"] == 1
    assert day_today_data["days_total"] == 1
    assert day_today_data["avg_score"] == pytest.approx(60.0)

def test_get_daily_commute_stats_authenticated_no_data(authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    end_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")

    response = client.get(f"/analytics/commute-stats/daily?user_id={user.id}&start_date={start_date}&end_date={end_date}")
    
    assert response.status_code == 200
    assert response.json() == []

def test_get_daily_commute_stats_unauthenticated(client: TestClient, session: Session):
    user = create_test_user(session)
    start_date = date.today().strftime("%Y-%m-%d")
    end_date = date.today().strftime("%Y-%m-%d")

    response = client.get(f"/analytics/commute-stats/daily?user_id={user.id}&start_date={start_date}&end_date={end_date}")
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

def test_get_daily_commute_stats_idor_protection(authenticated_client: tuple[TestClient, User], other_user_authenticated_client: tuple[TestClient, User], session: Session):
    client, user = authenticated_client
    _, other_user = other_user_authenticated_client # Get other user, but use 'client' from authenticated_client

    start_date = date.today().strftime("%Y-%m-%d")
    end_date = date.today().strftime("%Y-%m-%d")

    # Attempt to access other user's data using the authenticated client
    response = client.get(f"/analytics/commute-stats/daily?user_id={other_user.id}&start_date={start_date}&end_date={end_date}")
    
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to access analytics for this user."
