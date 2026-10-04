from datetime import datetime, date, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session, select
from jose import jwt

from app.main import app
from app.database import get_session
from app.models import (
    User,
    Commute,
    AssessmentHistory,
    AssessmentResult,
    Status,
    HourlyWeather,
)
from app.security import ALGORITHM, SECRET_KEY, get_password_hash
from app.analytics.service import record_assessment_run, get_daily_commute_stats


DATABASE_URL = "sqlite:///./test_integration_analytics.db"
engine = create_engine(DATABASE_URL, echo=False)


@pytest.fixture(autouse=True, scope="module")
def cleanup_test_db():
    yield
    engine.dispose()
    import os

    if os.path.exists("./test_integration_analytics.db"):
        try:
            os.remove("./test_integration_analytics.db")
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
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def make_user(session: Session, email: str = "rider@example.com") -> User:
    user = User(email=email, hashed_password=get_password_hash("secret123"))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def auth_headers(user: User) -> dict:
    payload = {
        "sub": user.email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=2),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


class TestIntegrationAssessmentRunRecording:
    """Tests persisting assessment runs without mocks."""

    def test_record_assessment_run_persists_in_db(self, session: Session):
        user = make_user(session, "runner@example.com")
        commute = Commute(
            name="Home to Office",
            lat=37.77,
            lon=-122.41,
            schedule_time="08:00",
            user_id=user.id,
        )
        session.add(commute)
        session.commit()
        session.refresh(commute)

        weather = HourlyWeather(
            temperature=68.0,
            apparent_temp=66.0,
            wind_speed=7.5,
            wind_gusts=10.0,
            precip_prob=5.0,
            weather_code=0,
        )
        assessment = AssessmentResult(
            status=Status.GO,
            score=92,
            reasons=["Clear skies", "Pleasant temperature"],
            recommendation="Enjoy your commute!",
            details=weather,
        )

        history = record_assessment_run(
            session=session,
            user_id=user.id,
            commute_id=commute.id,
            assessment=assessment,
            leg_type="outbound",
            commute_distance_km=18.5,
            duration_minutes=35.0,
        )

        assert history.id is not None
        assert history.user_id == user.id
        assert history.commute_id == commute.id
        assert history.overall_status == "Go"
        assert history.overall_score == 92.0
        assert history.commute_type is None
        assert history.commute_distance_km == 18.5
        assert history.duration_minutes == 35.0

        # Verify record exists in database
        saved = session.get(AssessmentHistory, history.id)
        assert saved is not None
        assert saved.commute_id == commute.id
        assert "Clear skies" in saved.weather_reasons


class TestIntegrationDecisionRecording:
    """Tests ride/drive decision recording contract and matching."""

    def test_record_decision_updates_todays_unassigned_assessment(
        self, client: TestClient, session: Session
    ):
        user = make_user(session, "decision1@example.com")
        headers = auth_headers(user)

        # Pre-populate an unassigned morning assessment
        history = record_assessment_run(
            session=session,
            user_id=user.id,
            overall_status="Caution",
            overall_score=68.0,
            commute_distance_km=22.0,
            duration_minutes=40.0,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        assert history.commute_type is None

        # User submits 'riding' decision from History page
        resp = client.post(
            "/api/analytics/record-decision",
            json={"decision": "riding"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == history.id
        assert data["commute_type"] == "riding"
        assert data["overall_score"] == 68.0

        # Verify DB is updated
        session.refresh(history)
        assert history.commute_type == "riding"

    def test_record_decision_creates_fresh_entry_when_no_unassigned_exists(
        self, client: TestClient, session: Session
    ):
        user = make_user(session, "fresh@example.com")
        headers = auth_headers(user)

        # No existing assessment run today; user logs 'driving'
        resp = client.post(
            "/api/analytics/record-decision",
            json={
                "decision": "driving",
                "commute_distance_km": 14.0,
                "duration_minutes": 30.0,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["commute_type"] == "driving"
        assert data["commute_distance_km"] == 14.0
        assert data["duration_minutes"] == 30.0
        assert data["user_id"] == user.id

        # Verify DB has new record
        records = session.exec(
            select(AssessmentHistory).where(AssessmentHistory.user_id == user.id)
        ).all()
        assert len(records) == 1
        assert records[0].commute_type == "driving"

    def test_record_decision_direct_update_by_assessment_history_id(
        self, client: TestClient, session: Session
    ):
        user = make_user(session, "direct_id@example.com")
        headers = auth_headers(user)

        past_time = datetime.now(timezone.utc) - timedelta(days=3)
        history = record_assessment_run(
            session=session,
            user_id=user.id,
            timestamp=past_time,
            overall_status="Go",
            overall_score=85.0,
        )

        resp = client.post(
            "/api/analytics/record-decision",
            json={
                "assessment_history_id": history.id,
                "decision": "riding",
                "commute_distance_km": 16.0,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == history.id
        assert data["commute_type"] == "riding"
        assert data["commute_distance_km"] == 16.0

    def test_decision_aliases_and_normalization(
        self, client: TestClient, session: Session
    ):
        user = make_user(session, "aliases@example.com")
        headers = auth_headers(user)

        for alias in ["rode", "bike", "bicycle", "motorcycle"]:
            resp = client.post(
                "/api/analytics/record-decision",
                json={"decision": alias},
                headers=headers,
            )
            assert resp.status_code == 200
            assert resp.json()["commute_type"] == "riding"

        for alias in ["drive", "drove", "car"]:
            resp = client.post(
                "/api/analytics/record-decision",
                json={"decision": alias},
                headers=headers,
            )
            assert resp.status_code == 200
            assert resp.json()["commute_type"] == "driving"

    def test_invalid_decision_validation(self, client: TestClient, session: Session):
        user = make_user(session, "invalid_dec@example.com")
        headers = auth_headers(user)

        resp = client.post(
            "/api/analytics/record-decision",
            json={"decision": "helicopter"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Invalid decision" in resp.json()["detail"]

        resp_empty = client.post(
            "/api/analytics/record-decision", json={}, headers=headers
        )
        assert resp_empty.status_code == 422

    def test_idor_protection_on_decision_recording(
        self, client: TestClient, session: Session
    ):
        victim = make_user(session, "victim@example.com")
        attacker = make_user(session, "attacker@example.com")
        attacker_headers = auth_headers(attacker)

        victim_history = record_assessment_run(
            session=session, user_id=victim.id, overall_status="Go", overall_score=90.0
        )

        resp = client.post(
            "/api/analytics/record-decision",
            json={"assessment_history_id": victim_history.id, "decision": "driving"},
            headers=attacker_headers,
        )
        assert resp.status_code == 403
        assert "Not authorized" in resp.json()["detail"]


class TestIntegrationTimezoneHandling:
    """Tests date and timezone normalization across day boundaries."""

    def test_evening_assessment_across_utc_midnight_matches_decision(
        self, client: TestClient, session: Session
    ):
        """
        Simulate user in EDT (UTC-4).
        At 23:30 local EDT on Oct 3, UTC time is 03:30 Oct 4.
        Decision logged for that commute correctly associates with the assessment.
        """
        user = make_user(session, "tz_evening@example.com")
        headers = auth_headers(user)

        # EDT is UTC-4: 2026-10-03 23:30 EDT == 2026-10-04 03:30 UTC
        edt_tz = timezone(timedelta(hours=-4))
        evening_local = datetime(2026, 10, 3, 23, 30, tzinfo=edt_tz)
        evening_utc = evening_local.astimezone(timezone.utc)

        history = record_assessment_run(
            session=session,
            user_id=user.id,
            timestamp=evening_utc,
            overall_status="Caution",
            overall_score=70.0,
            commute_distance_km=20.0,
        )

        # Log decision with date="2026-10-03" and EDT timestamp
        resp = client.post(
            "/api/analytics/record-decision",
            json={
                "decision": "riding",
                "date": "2026-10-03",
                "timestamp": evening_local.isoformat(),
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == history.id
        assert data["commute_type"] == "riding"

    def test_different_day_assessment_not_matched_for_today(
        self, client: TestClient, session: Session
    ):
        """Assessments from 3 days ago should not be matched when logging today."""
        user = make_user(session, "tz_different_day@example.com")
        headers = auth_headers(user)

        three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
        old_history = record_assessment_run(
            session=session,
            user_id=user.id,
            timestamp=three_days_ago,
            overall_status="No-Go",
            overall_score=35.0,
        )

        resp = client.post(
            "/api/analytics/record-decision",
            json={"decision": "driving"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Created a new record, did not overwrite old assessment from 3 days ago
        assert data["id"] != old_history.id
        session.refresh(old_history)
        assert old_history.commute_type is None


class TestIntegrationDailyCommuteStats:
    """Tests GET /api/analytics/commute-stats/daily contract, query params, and calculations."""

    def test_get_daily_stats_without_user_id_query_param(
        self, client: TestClient, session: Session
    ):
        """Tests that user_id is optional and defaults to authenticated user."""
        user = make_user(session, "no_param@example.com")
        headers = auth_headers(user)

        today = datetime.now(timezone.utc)
        record_assessment_run(
            session=session,
            user_id=user.id,
            timestamp=today,
            commute_type="riding",
            commute_distance_km=15.0,
            duration_minutes=30.0,
            overall_score=85.0,
        )

        start_date = today.date().strftime("%Y-%m-%d")
        end_date = today.date().strftime("%Y-%m-%d")

        # Call WITHOUT user_id query param
        resp = client.get(
            f"/api/analytics/commute-stats/daily?start_date={start_date}&end_date={end_date}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["days_ridden"] == 1
        assert data[0]["days_driven"] == 0
        assert data[0]["days_total"] == 1
        assert data[0]["avg_score"] == 85.0
        assert data[0]["total_distance_km"] == 15.0

    def test_get_daily_stats_with_empty_user_id_query_param(
        self, client: TestClient, session: Session
    ):
        """Tests that ?user_id= (empty string from frontend unpopulated store) does not cause 422."""
        user = make_user(session, "empty_param@example.com")
        headers = auth_headers(user)

        today = datetime.now(timezone.utc)
        record_assessment_run(
            session=session,
            user_id=user.id,
            timestamp=today,
            commute_type="driving",
            commute_distance_km=25.0,
            duration_minutes=45.0,
            overall_score=78.0,
        )

        start_date = today.date().strftime("%Y-%m-%d")
        end_date = today.date().strftime("%Y-%m-%d")

        # Call with user_id= (empty)
        resp = client.get(
            f"/api/analytics/commute-stats/daily?user_id=&start_date={start_date}&end_date={end_date}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["days_driven"] == 1
        assert data[0]["days_ridden"] == 0
        assert data[0]["total_distance_km"] == 25.0

    def test_get_daily_stats_idor_protection(
        self, client: TestClient, session: Session
    ):
        user = make_user(session, "main_user@example.com")
        other = make_user(session, "other_user@example.com")
        headers = auth_headers(user)

        start_date = date.today().strftime("%Y-%m-%d")
        end_date = date.today().strftime("%Y-%m-%d")

        resp = client.get(
            f"/api/analytics/commute-stats/daily?user_id={other.id}&start_date={start_date}&end_date={end_date}",
            headers=headers,
        )
        assert resp.status_code == 403
        assert "Not authorized" in resp.json()["detail"]

    def test_empty_date_range_and_zero_decision_days_no_500_error(
        self, client: TestClient, session: Session
    ):
        """Ensures empty ranges or days without decisions return empty list or defaults without 500."""
        user = make_user(session, "empty_stats@example.com")
        headers = auth_headers(user)

        # Empty range (start > end)
        resp1 = client.get(
            "/api/analytics/commute-stats/daily?start_date=2026-10-10&end_date=2026-10-01",
            headers=headers,
        )
        assert resp1.status_code == 422

        # Date range where user has no records
        resp2 = client.get(
            "/api/analytics/commute-stats/daily?start_date=2020-01-01&end_date=2020-01-07",
            headers=headers,
        )
        assert resp2.status_code == 200
        assert resp2.json() == []

        # Date with an assessment run but NO decision (zero-decision day)
        target_day = datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc)
        record_assessment_run(
            session=session,
            user_id=user.id,
            timestamp=target_day,
            commute_type=None,
            overall_score=95.0,
        )
        resp3 = client.get(
            "/api/analytics/commute-stats/daily?start_date=2026-05-15&end_date=2026-05-15",
            headers=headers,
        )
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert len(data3) == 1
        assert data3[0]["days_ridden"] == 0
        assert data3[0]["days_driven"] == 0
        assert data3[0]["days_total"] == 0
        assert data3[0]["avg_score"] == 95.0
        assert data3[0]["total_distance_km"] == 0.0
        assert "time_saved_minutes" not in data3[0]
        assert "fuel_saved_gallons" not in data3[0]

    def test_daily_stats_aggregation_and_savings_calculations(
        self, client: TestClient, session: Session
    ):
        """
        Validates calculation of days_ridden, days_driven, total_distance_km,
        time_saved_minutes, and fuel_saved_gallons.
        """
        user = make_user(session, "calc_user@example.com")
        headers = auth_headers(user)

        test_day = datetime(2026, 9, 20, 8, 0, tzinfo=timezone.utc)

        # Commute 1: Riding 20 km in 40 minutes, score 80
        record_assessment_run(
            session=session,
            user_id=user.id,
            timestamp=test_day,
            commute_type="riding",
            commute_distance_km=20.0,
            duration_minutes=40.0,
            overall_score=80.0,
        )

        # Commute 2: Driving 30 km in 50 minutes, score 60
        record_assessment_run(
            session=session,
            user_id=user.id,
            timestamp=test_day + timedelta(hours=9),
            commute_type="driving",
            commute_distance_km=30.0,
            duration_minutes=50.0,
            overall_score=60.0,
        )

        resp = client.get(
            "/api/analytics/commute-stats/daily?start_date=2026-09-20&end_date=2026-09-20",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        stats = data[0]

        assert stats["days_ridden"] == 1
        assert stats["days_driven"] == 1
        assert stats["days_total"] == 2
        assert stats["avg_score"] == 70.0  # (80 + 60) / 2
        assert stats["total_distance_km"] == 50.0  # 20 + 30

        # Weather and distance cannot establish fuel consumption or time saved.
        assert "time_saved_minutes" not in stats
        assert "fuel_saved_gallons" not in stats
