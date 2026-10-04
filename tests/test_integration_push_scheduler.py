import os
import json
import sqlite3
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone
from jose import jwt
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from pywebpush import WebPushException

from app.main import app, scheduler, run_commute_check
from app.database import get_session
from app.models import User, Commute, UnitSystem, Status, AssessmentHistory
from app.push.models import PushSubscription
from app.security import ALGORITHM, SECRET_KEY, get_password_hash

INTEG_DB_URL = "sqlite:///./test_integration_push_scheduler.db"
integ_engine = create_engine(
    INTEG_DB_URL, echo=False, connect_args={"check_same_thread": False}
)


@pytest.fixture(autouse=True, scope="module")
def cleanup_integration_db():
    yield
    integ_engine.dispose()
    if os.path.exists("./test_integration_push_scheduler.db"):
        try:
            os.remove("./test_integration_push_scheduler.db")
        except OSError:
            pass


@pytest.fixture(autouse=True)
def clean_scheduler_jobs():
    yield
    for job in scheduler.get_jobs():
        if "commute_check_" in job.id:
            try:
                scheduler.remove_job(job.id)
            except Exception:
                pass


@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(integ_engine)
    with Session(integ_engine) as session:
        yield session
    SQLModel.metadata.drop_all(integ_engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def create_user_and_token(
    session: Session, email: str = "rider_push@example.com"
) -> tuple[User, str, dict]:
    user = User(email=email, hashed_password=get_password_hash("securepass123"))
    session.add(user)
    session.commit()
    session.refresh(user)

    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    token = jwt.encode(
        {"sub": user.email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM
    )
    headers = {"Authorization": f"Bearer {token}"}
    return user, token, headers


# =========================================================================
# 1. Push Router Prefix Mismatch & Endpoint Verification
# =========================================================================


def test_api_push_endpoints_return_200_no_404(client: TestClient, session: Session):
    """
    Verify all /api/push/... endpoints respond with 200 and do not return 404 Not Found.
    """
    user, token, headers = create_user_and_token(session, "test_prefix@example.com")

    # 1. GET /api/push/vapid-public-key
    res_key = client.get("/api/push/vapid-public-key", headers=headers)
    assert res_key.status_code == 200
    assert "public_key" in res_key.json()
    assert len(res_key.json()["public_key"]) > 20

    # 2. POST /api/push/subscribe
    sub_payload = {
        "endpoint": "https://push.example.com/api/devices/dev-1",
        "keys": {"p256dh": "p256dh_key_data", "auth": "auth_key_data"},
        "user_agent": "IntegrationTestBrowser/1.0",
    }
    res_sub = client.post("/api/push/subscribe", json=sub_payload, headers=headers)
    assert res_sub.status_code == 200
    assert res_sub.json() == {"status": "subscribed"}

    # 3. GET /api/push/subscriptions
    res_list = client.get("/api/push/subscriptions", headers=headers)
    assert res_list.status_code == 200
    subs = res_list.json()
    assert len(subs) == 1
    assert subs[0]["endpoint"] == sub_payload["endpoint"]
    assert subs[0]["user_agent"] == "IntegrationTestBrowser/1.0"

    # 4. POST /api/push/test
    with patch("app.notifications.webpush") as mock_webpush:
        res_test = client.post("/api/push/test", headers=headers)
        assert res_test.status_code == 200
        assert res_test.json()["delivered"] == 1
        assert mock_webpush.called

    # 5. DELETE /api/push/unsubscribe
    unsub_payload = {"endpoint": "https://push.example.com/api/devices/dev-1"}
    res_unsub = client.request(
        "DELETE", "/api/push/unsubscribe", json=unsub_payload, headers=headers
    )
    assert res_unsub.status_code == 200
    assert res_unsub.json() == {"status": "unsubscribed"}

    # 6. Also verify legacy /push/... paths remain functional
    res_legacy_key = client.get("/push/vapid-public-key", headers=headers)
    assert res_legacy_key.status_code == 200


def test_api_push_requires_authentication(client: TestClient):
    """Verify push endpoints reject unauthenticated requests."""
    assert client.get("/api/push/vapid-public-key").status_code == 401
    assert (
        client.post(
            "/api/push/subscribe",
            json={"endpoint": "a", "keys": {"p256dh": "b", "auth": "c"}},
        ).status_code
        == 401
    )
    assert client.get("/api/push/subscriptions").status_code == 401
    assert (
        client.request(
            "DELETE", "/api/push/unsubscribe", json={"endpoint": "a"}
        ).status_code
        == 401
    )
    assert client.post("/api/push/test").status_code == 401


# =========================================================================
# 2. Push Subscription Lifecycle, Persistence & Error Handling
# =========================================================================


def test_push_subscription_persistence_and_update(client: TestClient, session: Session):
    """
    Ensure PushSubscription records persist endpoint, auth keys, user_agent, and user_id in SQLite,
    and updates existing subscriptions on repeat subscribe calls.
    """
    user, _, headers = create_user_and_token(session, "persist_user@example.com")

    # Initial subscription
    sub_payload = {
        "endpoint": "https://push.example.com/endpoint_alpha",
        "keys": {"p256dh": "initial_p256dh", "auth": "initial_auth"},
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64)",
    }
    res = client.post("/api/push/subscribe", json=sub_payload, headers=headers)
    assert res.status_code == 200

    # Verify directly in SQLite
    db_sub = session.exec(
        select(PushSubscription).where(
            PushSubscription.endpoint == sub_payload["endpoint"]
        )
    ).first()
    assert db_sub is not None
    assert db_sub.user_id == user.id
    assert db_sub.p256dh == "initial_p256dh"
    assert db_sub.auth == "initial_auth"
    assert db_sub.user_agent == "Mozilla/5.0 (X11; Linux x86_64)"
    assert db_sub.created_at is not None

    # Resubscribe with new keys on same endpoint
    updated_payload = {
        "endpoint": "https://push.example.com/endpoint_alpha",
        "keys": {"p256dh": "rotated_p256dh", "auth": "rotated_auth"},
        "user_agent": "Mozilla/5.0 UpdatedBrowser",
    }
    res_update = client.post(
        "/api/push/subscribe", json=updated_payload, headers=headers
    )
    assert res_update.status_code == 200

    # Verify updated in DB without duplicates
    subs = session.exec(
        select(PushSubscription).where(
            PushSubscription.endpoint == sub_payload["endpoint"]
        )
    ).all()
    assert len(subs) == 1
    assert subs[0].p256dh == "rotated_p256dh"
    assert subs[0].auth == "rotated_auth"
    assert subs[0].user_agent == "Mozilla/5.0 UpdatedBrowser"


def test_push_pruning_on_410_gone_and_404_not_found(session: Session):
    """
    Verify dispatch_web_push_notification automatically prunes subscriptions from SQLite
    when webpush encounters HTTP 410 Gone or 404 Not Found, while keeping valid subscriptions.
    """
    from app.notifications import dispatch_web_push_notification

    user = User(email="prune_test@example.com", hashed_password="hashedpassword")
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create 3 subscriptions:
    # 1. 410 Gone (expired)
    # 2. 404 Not Found (invalid endpoint)
    # 3. Valid active subscription
    sub_410 = PushSubscription(
        user_id=user.id,
        endpoint="https://push.example.com/expired-410",
        p256dh="dh1",
        auth="auth1",
    )
    sub_404 = PushSubscription(
        user_id=user.id,
        endpoint="https://push.example.com/dead-404",
        p256dh="dh2",
        auth="auth2",
    )
    sub_valid = PushSubscription(
        user_id=user.id,
        endpoint="https://push.example.com/active-valid",
        p256dh="dh3",
        auth="auth3",
    )
    session.add_all([sub_410, sub_404, sub_valid])
    session.commit()

    def mock_webpush_side_effect(subscription_info, **kwargs):
        endpoint = subscription_info["endpoint"]
        if "410" in endpoint:
            mock_resp = MagicMock()
            mock_resp.status_code = 410
            raise WebPushException("Push endpoint has expired", response=mock_resp)
        elif "404" in endpoint:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            raise WebPushException("Push endpoint not found", response=mock_resp)
        else:
            return MagicMock(status_code=201)

    with patch("app.notifications.webpush", side_effect=mock_webpush_side_effect):
        results = dispatch_web_push_notification(
            user_id=user.id,
            title="Prune Test",
            body="Checking subscription cleanup",
            session=session,
        )

        assert results["delivered"] == 1
        assert results["failed"] == 2

    # Verify dead subscriptions were pruned and valid one remains
    remaining = session.exec(
        select(PushSubscription).where(PushSubscription.user_id == user.id)
    ).all()
    endpoints = [s.endpoint for s in remaining]
    assert "https://push.example.com/expired-410" not in endpoints
    assert "https://push.example.com/dead-404" not in endpoints
    assert "https://push.example.com/active-valid" in endpoints
    assert len(remaining) == 1


def test_push_pruning_on_string_exception_format(session: Session):
    """
    Verify subscription pruning works when WebPushException carries status in message or string representation.
    """
    from app.notifications import dispatch_web_push_notification

    user = User(email="str_prune@example.com", hashed_password="hashedpassword")
    session.add(user)
    session.commit()
    session.refresh(user)

    sub = PushSubscription(
        user_id=user.id,
        endpoint="https://push.example.com/string-410",
        p256dh="dh_str",
        auth="auth_str",
    )
    session.add(sub)
    session.commit()

    with patch(
        "app.notifications.webpush",
        side_effect=WebPushException("Response 410 Gone from push service"),
    ):
        results = dispatch_web_push_notification(
            user_id=user.id,
            title="Prune String Test",
            body="Testing string representation pruning",
            session=session,
        )
        assert results["failed"] == 1

    remaining = session.exec(
        select(PushSubscription).where(PushSubscription.endpoint == sub.endpoint)
    ).first()
    assert remaining is None


def test_api_push_test_with_localized_hazard_details(
    client: TestClient, session: Session
):
    """
    Ensure POST /api/push/test sends a test payload with localized hazard details when requested.
    """
    _, _, headers = create_user_and_token(session, "hazard_test_user@example.com")

    # Subscribe
    client.post(
        "/api/push/subscribe",
        json={
            "endpoint": "https://push.example.com/hazard_subscriber",
            "keys": {"p256dh": "dh_h", "auth": "au_h"},
        },
        headers=headers,
    )

    hazard_pinpoint = {
        "location": "Bay Bridge Tower 2",
        "hazard": "Severe crosswinds",
        "value": "35 mph",
        "time": "08:20 AM",
    }

    test_request_data = {
        "title": "⚠️ Commute Safety Warning",
        "body": "Commute Check: Caution for Morning Commute. ⚠️ Severe crosswinds (35 mph) near Bay Bridge Tower 2 at ~08:20 AM.",
        "url": "/#route-visualizer",
        "has_route_hazard": True,
        "hazard_count": 1,
        "primary_hazard_location": "Bay Bridge Tower 2",
        "hazard_pinpoints": [hazard_pinpoint],
    }

    with patch("app.notifications.webpush") as mock_webpush:
        res = client.post("/api/push/test", json=test_request_data, headers=headers)
        assert res.status_code == 200
        assert res.json()["delivered"] == 1
        assert mock_webpush.called

        # Verify dispatched JSON payload structure
        call_kwargs = mock_webpush.call_args[1]
        sent_data = json.loads(call_kwargs["data"])
        assert sent_data["title"] == "⚠️ Commute Safety Warning"
        assert sent_data["has_route_hazard"] is True
        assert sent_data["hazard_count"] == 1
        assert sent_data["primary_hazard_location"] == "Bay Bridge Tower 2"
        assert sent_data["hazard_pinpoints"] == [hazard_pinpoint]
        assert "Bay Bridge Tower 2" in sent_data["body"]


# =========================================================================
# 3. APScheduler Background Commute Checks & Dual-Leg Execution
# =========================================================================


def test_apscheduler_dual_leg_registration_and_update(
    client: TestClient, session: Session
):
    """
    Verify APScheduler dual-leg job registration:
    - Commute creation registers outbound and return cron jobs.
    - Commute update reschedules both jobs.
    - Commute deletion removes both jobs.
    """
    _, _, headers = create_user_and_token(session, "sched_user@example.com")

    # 1. Create commute
    commute_payload = {
        "name": "Integration Work Commute",
        "lat": 37.7749,
        "lon": -122.4194,
        "dest_name": "Palo Alto Campus",
        "dest_lat": 37.4419,
        "dest_lon": -122.1430,
        "schedule_time": "08:15",
        "return_schedule_time": "17:45",
        "days_of_week": "mon-fri",
        "unit_system": "imperial",
    }
    create_res = client.post("/api/commutes", json=commute_payload, headers=headers)
    assert create_res.status_code == 200
    commute_id = create_res.json()["id"]

    outbound_job_id = f"commute_check_{commute_id}_outbound"
    return_job_id = f"commute_check_{commute_id}_return"

    outbound_job = scheduler.get_job(outbound_job_id)
    return_job = scheduler.get_job(return_job_id)
    assert outbound_job is not None, "Outbound cron job should be registered"
    assert return_job is not None, "Return cron job should be registered"

    out_fields = {f.name: str(f) for f in outbound_job.trigger.fields}
    ret_fields = {f.name: str(f) for f in return_job.trigger.fields}
    assert out_fields["hour"] == "8"
    assert out_fields["minute"] == "15"
    assert ret_fields["hour"] == "17"
    assert ret_fields["minute"] == "45"

    # 2. Update commute schedule times
    updated_payload = dict(commute_payload)
    updated_payload["schedule_time"] = "09:00"
    updated_payload["return_schedule_time"] = "18:30"
    update_res = client.put(
        f"/api/commutes/{commute_id}", json=updated_payload, headers=headers
    )
    assert update_res.status_code == 200

    outbound_job = scheduler.get_job(outbound_job_id)
    return_job = scheduler.get_job(return_job_id)
    assert outbound_job is not None
    assert return_job is not None

    out_fields = {f.name: str(f) for f in outbound_job.trigger.fields}
    ret_fields = {f.name: str(f) for f in return_job.trigger.fields}
    assert out_fields["hour"] == "9"
    assert out_fields["minute"] == "0"
    assert ret_fields["hour"] == "18"
    assert ret_fields["minute"] == "30"

    # 3. Delete commute -> removes jobs
    del_res = client.delete(f"/api/commutes/{commute_id}", headers=headers)
    assert del_res.status_code == 200
    assert scheduler.get_job(outbound_job_id) is None
    assert scheduler.get_job(return_job_id) is None


@pytest.mark.asyncio
async def test_run_commute_check_dual_leg_execution_end_to_end(session: Session):
    """
    Verify run_commute_check executes route assessment, logs AssessmentHistory,
    triggers Apprise webhook if configured, and dispatches Web Push notifications.
    """
    user = User(email="scheduler_e2e@example.com", hashed_password="hashed_pass")
    session.add(user)
    session.commit()
    session.refresh(user)

    commute = Commute(
        user_id=user.id,
        name="Silicon Valley Highway Run",
        lat=37.7749,
        lon=-122.4194,
        dest_name="San Jose Tech Park",
        dest_lat=37.3382,
        dest_lon=-121.8863,
        schedule_time="07:45",
        return_schedule_time="16:30",
        webhook_url="https://webhook.example.com/alerts",
        unit_system=UnitSystem.IMPERIAL,
    )
    session.add(commute)

    # Register a push subscription for the user
    sub = PushSubscription(
        user_id=user.id,
        endpoint="https://push.example.com/sched_e2e_device",
        p256dh="dh_sched",
        auth="auth_sched",
    )
    session.add(sub)
    session.commit()
    session.refresh(commute)

    # Weather payload mock
    from tests.helpers import forecast

    mock_hourly = forecast(temperature=65, wind=12, gusts=14, rain=5)

    with (
        patch("app.main.engine", integ_engine),
        patch(
            "app.main.client_instance.fetch_weather_batch", new_callable=AsyncMock
        ) as mock_weather,
        patch(
            "app.main.notification_service_instance.send_notification",
            new_callable=AsyncMock,
        ) as mock_webhook,
        patch("app.notifications.webpush") as mock_webpush,
    ):
        mock_weather.return_value = (mock_hourly, mock_hourly)

        # 1. Execute Outbound Leg
        outbound_res = await run_commute_check(commute.id, leg_type="outbound")
        assert outbound_res is not None
        assert outbound_res.leg_type == "outbound"
        assert outbound_res.score is not None

        # Verify Apprise webhook called for outbound leg
        assert mock_webhook.called
        assert mock_webhook.call_args[1]["leg_type"] == "outbound"

        # Verify Web Push dispatched to user's device
        assert mock_webpush.called
        push_call_kwargs = mock_webpush.call_args[1]
        sent_push = json.loads(push_call_kwargs["data"])
        assert "Morning Outbound" in sent_push["title"]

        # Verify AssessmentHistory record logged in SQLite
        history_out = session.exec(
            select(AssessmentHistory)
            .where(AssessmentHistory.commute_id == commute.id)
            .where(AssessmentHistory.leg_type == "outbound")
        ).all()
        assert len(history_out) >= 1
        assert history_out[0].user_id == user.id

        # 2. Execute Return Leg
        mock_webhook.reset_mock()
        mock_webpush.reset_mock()

        return_res = await run_commute_check(commute.id, leg_type="return")
        assert return_res is not None
        assert return_res.leg_type == "return"

        # Verify Apprise webhook called for return leg
        assert mock_webhook.called
        assert mock_webhook.call_args[1]["leg_type"] == "return"

        # Verify Web Push dispatched with Evening Return title
        assert mock_webpush.called
        sent_push_ret = json.loads(mock_webpush.call_args[1]["data"])
        assert "Evening Return" in sent_push_ret["title"]

        # Verify AssessmentHistory record logged for return leg
        history_ret = session.exec(
            select(AssessmentHistory)
            .where(AssessmentHistory.commute_id == commute.id)
            .where(AssessmentHistory.leg_type == "return")
        ).all()
        assert len(history_ret) >= 1


@pytest.mark.asyncio
async def test_scheduler_resilience_to_database_locks(session: Session):
    """
    Verify scheduler handles database locks without uncaught exceptions or crashing.
    """
    user = User(email="dblock_user@example.com", hashed_password="hashed_pass")
    session.add(user)
    session.commit()
    session.refresh(user)

    commute = Commute(
        user_id=user.id,
        name="DB Lock Test Commute",
        lat=37.7749,
        lon=-122.4194,
        schedule_time="08:00",
    )
    session.add(commute)
    session.commit()
    session.refresh(commute)

    # Simulate database lock when opening Session
    with patch(
        "app.main.Session", side_effect=sqlite3.OperationalError("database is locked")
    ):
        res = await run_commute_check(commute.id, leg_type="outbound")
        assert res is None, "Should handle database lock gracefully and return None"


@pytest.mark.asyncio
async def test_scheduler_resilience_to_network_offline(session: Session):
    """
    Verify scheduler handles network offline errors from weather service without crashing.
    """
    user = User(email="neterror_user@example.com", hashed_password="hashed_pass")
    session.add(user)
    session.commit()
    session.refresh(user)

    commute = Commute(
        user_id=user.id,
        name="Network Error Test Commute",
        lat=37.7749,
        lon=-122.4194,
        schedule_time="08:00",
    )
    session.add(commute)
    session.commit()
    session.refresh(commute)

    with (
        patch("app.main.engine", integ_engine),
        patch(
            "app.main.client_instance.fetch_weather_batch", new_callable=AsyncMock
        ) as mock_fetch,
    ):
        # Simulate network failure / connection timeout
        mock_fetch.side_effect = ConnectionError(
            "Weather API endpoint unreachable (offline)"
        )

        res = await run_commute_check(commute.id, leg_type="outbound")
        assert res is None, (
            "Should handle network offline error gracefully without crashing"
        )
