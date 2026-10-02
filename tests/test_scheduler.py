import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlmodel import Session, SQLModel, create_engine
from app.main import (
    app,
    scheduler,
    schedule_commute_check,
    clear_commute_jobs,
    run_commute_check,
    get_session,
)
from app.models import Commute, Status, HourlyWeather, LegAssessment, UnitSystem
from app.notifications import NotificationService

TEST_DB_URL = "sqlite:///./test_scheduler.db"
test_engine = create_engine(TEST_DB_URL, echo=False, connect_args={"check_same_thread": False})


@pytest.fixture(autouse=True)
def clean_scheduler():
    # Setup: ensure scheduler jobs are clean for test IDs
    yield
    # Teardown: remove any test jobs
    for job in scheduler.get_jobs():
        if job.id.startswith("commute_check_test_") or job.id.startswith("commute_check_999"):
            scheduler.remove_job(job.id)


@pytest.fixture
def test_db_session():
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session
    SQLModel.metadata.drop_all(test_engine)


def test_schedule_commute_check_registers_both_jobs():
    commute = Commute(
        id=9991,
        name="Dual Leg Commute",
        lat=37.7749,
        lon=-122.4194,
        dest_name="Office",
        dest_lat=37.3861,
        dest_lon=-122.0839,
        schedule_time="08:15",
        return_schedule_time="17:45",
        days_of_week="mon-fri",
    )

    schedule_commute_check(commute)

    outbound_job = scheduler.get_job("commute_check_9991_outbound")
    return_job = scheduler.get_job("commute_check_9991_return")

    assert outbound_job is not None, "Outbound job must be registered"
    assert return_job is not None, "Return job must be registered"

    # Verify job parameters
    assert list(outbound_job.args) == [9991, "outbound"]
    assert list(return_job.args) == [9991, "return"]

    # Verify triggers
    trigger_out = outbound_job.trigger
    trigger_ret = return_job.trigger
    out_fields = {f.name: str(f) for f in trigger_out.fields}
    ret_fields = {f.name: str(f) for f in trigger_ret.fields}

    assert out_fields["hour"] == "8"
    assert out_fields["minute"] == "15"
    assert ret_fields["hour"] == "17"
    assert ret_fields["minute"] == "45"

    # Clean up
    clear_commute_jobs(9991)


def test_schedule_commute_check_single_leg_when_no_return_schedule():
    commute = Commute(
        id=9992,
        name="Single Leg Commute",
        lat=37.7749,
        lon=-122.4194,
        schedule_time="09:00",
        return_schedule_time=None,
        days_of_week="mon,wed,fri",
    )

    schedule_commute_check(commute)

    outbound_job = scheduler.get_job("commute_check_9992_outbound")
    return_job = scheduler.get_job("commute_check_9992_return")

    assert outbound_job is not None
    assert return_job is None

    out_fields = {f.name: str(f) for f in outbound_job.trigger.fields}
    assert out_fields["hour"] == "9"
    assert out_fields["minute"] == "0"

    clear_commute_jobs(9992)


def test_update_commute_reschedules_cleanly():
    commute = Commute(
        id=9993,
        name="Updating Commute",
        lat=37.7749,
        lon=-122.4194,
        schedule_time="07:30",
        return_schedule_time="16:30",
        days_of_week="mon-fri",
    )
    schedule_commute_check(commute)

    assert scheduler.get_job("commute_check_9993_outbound") is not None
    assert scheduler.get_job("commute_check_9993_return") is not None

    # Update return schedule time
    commute.return_schedule_time = "18:00"
    schedule_commute_check(commute)

    updated_ret = scheduler.get_job("commute_check_9993_return")
    assert updated_ret is not None
    ret_fields = {f.name: str(f) for f in updated_ret.trigger.fields}
    assert ret_fields["hour"] == "18"
    assert ret_fields["minute"] == "0"

    # Now remove return schedule time
    commute.return_schedule_time = None
    schedule_commute_check(commute)

    assert scheduler.get_job("commute_check_9993_outbound") is not None
    assert scheduler.get_job("commute_check_9993_return") is None, "Return job should be removed"

    clear_commute_jobs(9993)


def test_clear_commute_jobs_removes_both_jobs():
    commute = Commute(
        id=9994,
        name="To Delete",
        lat=37.7749,
        lon=-122.4194,
        schedule_time="08:00",
        return_schedule_time="17:00",
    )
    schedule_commute_check(commute)

    assert scheduler.get_job("commute_check_9994_outbound") is not None
    assert scheduler.get_job("commute_check_9994_return") is not None

    clear_commute_jobs(9994)

    assert scheduler.get_job("commute_check_9994_outbound") is None
    assert scheduler.get_job("commute_check_9994_return") is None


def test_notification_formatting_specifies_leg_type_and_risk_factors():
    service = NotificationService()

    # Outbound leg assessment with risk factors
    outbound_assessment = LegAssessment(
        leg_type="outbound",
        location_name="Home -> Office",
        schedule_time="08:30",
        status=Status.CAUTION,
        score=60,
        reasons=["High wind/gusts", "Low temperature"],
        weather=HourlyWeather(
            temperature=42.0,
            apparent_temp=38.0,
            wind_speed=20.0,
            wind_gusts=28.0,
            precip_prob=15.0,
            weather_code=0,
        ),
    )

    out_title, out_body = service._format_message(outbound_assessment)
    assert "Morning Outbound" in out_title
    assert "Caution" in out_title
    assert "Leg: Morning Outbound" in out_body
    assert "Home -> Office" in out_body
    assert "at 08:30" in out_body
    assert "Risk Factors:" in out_body
    assert "• High wind/gusts" in out_body
    assert "• Low temperature" in out_body

    # Return leg assessment with rain risk
    return_assessment = LegAssessment(
        leg_type="return",
        location_name="Office -> Home",
        schedule_time="17:30",
        status=Status.NO_GO,
        score=25,
        reasons=["High probability of rain"],
        weather=HourlyWeather(
            temperature=55.0,
            apparent_temp=54.0,
            wind_speed=10.0,
            wind_gusts=15.0,
            precip_prob=80.0,
            weather_code=61,
        ),
    )

    ret_title, ret_body = service._format_message(return_assessment)
    assert "Evening Return" in ret_title
    assert "No-Go" in ret_title
    assert "Leg: Evening Return" in ret_body
    assert "Office -> Home" in ret_body
    assert "at 17:30" in ret_body
    assert "Risk Factors:" in ret_body
    assert "• High probability of rain" in ret_body


@pytest.mark.asyncio
async def test_run_commute_check_evaluates_outbound_and_return_legs():
    commute = Commute(
        id=9995,
        user_id=1,
        name="Daily Commute",
        lat=37.7749,
        lon=-122.4194,
        dest_name="Tech Hub",
        dest_lat=37.3861,
        dest_lon=-122.0839,
        schedule_time="08:00",
        return_schedule_time="17:00",
        webhook_url="https://webhook.example.com/alerts",
        unit_system=UnitSystem.IMPERIAL,
    )

    raw_origin = {
        "hourly": {
            "time": [f"2026-10-01T{h:02d}:00" for h in range(24)],
            "temperature_2m": [70.0] * 24,
            "apparent_temperature": [70.0] * 24,
            "wind_speed_10m": [8.0] * 24,
            "precipitation_probability": [0.0] * 24,
            "weather_code": [0] * 24,
        }
    }
    raw_dest = {
        "hourly": {
            "time": [f"2026-10-01T{h:02d}:00" for h in range(24)],
            "temperature_2m": [40.0] * 24,  # Cold at destination
            "apparent_temperature": [36.0] * 24,
            "wind_speed_10m": [22.0] * 24,
            "precipitation_probability": [40.0] * 24,
            "weather_code": [0] * 24,
        }
    }

    with patch("app.main.Session") as mock_session_cls, \
         patch("app.main.app_client.fetch_route_weather", new_callable=AsyncMock) as mock_fetch, \
         patch("app.main.notification_service_instance.send_notification", new_callable=AsyncMock) as mock_send_notif, \
         patch("app.main.dispatch_web_push_notification") as mock_push:

        mock_session = MagicMock()
        mock_session.get.return_value = commute
        mock_session_cls.return_value.__enter__.return_value = mock_session
        mock_fetch.return_value = (raw_origin, raw_dest)

        # 1. Test Outbound Leg
        outbound_result = await run_commute_check(9995, leg_type="outbound")
        assert outbound_result is not None
        assert outbound_result.leg_type == "outbound"
        assert outbound_result.schedule_time == "08:00"
        mock_fetch.assert_called_with(
            commute.lat, commute.lon, commute.dest_lat, commute.dest_lon, commute.unit_system
        )
        # Webhook received outbound leg assessment
        assert mock_send_notif.called
        send_args = mock_send_notif.call_args[0]
        assert send_args[0] == commute.webhook_url
        assert send_args[1].leg_type == "outbound"
        assert mock_send_notif.call_args[1]["leg_type"] == "outbound"

        # Web Push received outbound title
        assert mock_push.called
        push_title = mock_push.call_args[0][1]
        assert "Morning Outbound" in push_title

        # 2. Test Return Leg
        mock_send_notif.reset_mock()
        mock_push.reset_mock()

        return_result = await run_commute_check(9995, leg_type="return")
        assert return_result is not None
        assert return_result.leg_type == "return"
        assert return_result.schedule_time == "17:00"

        # Webhook received return leg assessment
        assert mock_send_notif.called
        send_args = mock_send_notif.call_args[0]
        assert send_args[1].leg_type == "return"
        assert mock_send_notif.call_args[1]["leg_type"] == "return"

        # Web Push received return title
        assert mock_push.called
        push_title = mock_push.call_args[0][1]
        assert "Evening Return" in push_title


@pytest.mark.asyncio
async def test_run_commute_check_error_handling():
    # 1. Non-existent commute
    with patch("app.main.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.get.return_value = None
        mock_session_cls.return_value.__enter__.return_value = mock_session

        res = await run_commute_check(999999)
        assert res is None

    # 2. Weather service error
    with patch("app.main.Session") as mock_session_cls, \
         patch("app.main.app_client.fetch_route_weather", new_callable=AsyncMock) as mock_fetch:
        mock_session = MagicMock()
        mock_session.get.return_value = Commute(id=9998, lat=0.0, lon=0.0, schedule_time="08:00")
        mock_session_cls.return_value.__enter__.return_value = mock_session
        mock_fetch.side_effect = RuntimeError("Open-Meteo network timeout")

        res = await run_commute_check(9998)
        assert res is None


def test_scheduler_api_crud_lifecycle():
    from fastapi.testclient import TestClient
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from app.security import ALGORITHM, SECRET_KEY, get_password_hash
    from app.models import User

    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        user = User(email="sched_api@example.com", hashed_password=get_password_hash("testpass"))
        session.add(user)
        session.commit()
        session.refresh(user)

        expire = datetime.now(timezone.utc) + timedelta(minutes=30)
        token = jwt.encode({"sub": user.email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

    prev_override = app.dependency_overrides.get(get_session)
    app.dependency_overrides[get_session] = lambda: Session(test_engine)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    try:
        # 1. POST /commutes - Creates commute and schedules both jobs
        payload = {
            "name": "API Commute",
            "lat": 40.7128,
            "lon": -74.0060,
            "dest_name": "Midtown",
            "dest_lat": 40.7589,
            "dest_lon": -73.9851,
            "schedule_time": "08:15",
            "return_schedule_time": "17:45",
            "days_of_week": "mon-fri"
        }
        res = client.post("/commutes", json=payload, headers=headers)
        assert res.status_code == 200
        created = res.json()
        cid = created["id"]

        outbound_job = scheduler.get_job(f"commute_check_{cid}_outbound")
        return_job = scheduler.get_job(f"commute_check_{cid}_return")
        assert outbound_job is not None
        assert return_job is not None

        # 2. PUT /commutes/{cid} - Updates commute and reschedules jobs
        updated_payload = dict(payload)
        updated_payload["return_schedule_time"] = "18:30"
        res = client.put(f"/commutes/{cid}", json=updated_payload, headers=headers)
        assert res.status_code == 200

        updated_return_job = scheduler.get_job(f"commute_check_{cid}_return")
        assert updated_return_job is not None
        ret_fields = {f.name: str(f) for f in updated_return_job.trigger.fields}
        assert ret_fields["hour"] == "18"
        assert ret_fields["minute"] == "30"

        # 3. DELETE /commutes/{cid} - Deletes commute and clears both jobs
        res = client.delete(f"/commutes/{cid}", headers=headers)
        assert res.status_code == 200

        assert scheduler.get_job(f"commute_check_{cid}_outbound") is None
        assert scheduler.get_job(f"commute_check_{cid}_return") is None

    finally:
        if prev_override is not None:
            app.dependency_overrides[get_session] = prev_override
        else:
            app.dependency_overrides.pop(get_session, None)
        SQLModel.metadata.drop_all(test_engine)

