"""Behavioural regressions for failures that used to pass the old golden path."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app, schedule_commute_check, scheduler
from app.database import get_session
from app.models import Commute, HourlyWeather, Status
from app.client import parse_hourly_at_time
from app.engine import AssessmentEngine
from app.assessment import departure_dates
from tests.helpers import forecast


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        app.dependency_overrides[get_session] = lambda: session
        yield TestClient(app)
        app.dependency_overrides.clear()
    engine.dispose()


def sign_in(client, email="rider@example.com"):
    response = client.post(
        "/api/register", json={"email": email, "password": "good-password"}
    )
    assert response.status_code == 200
    assert "hashed_password" not in response.text
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return response.json()["user"]["id"]


def config(**changes):
    return {
        "name": "Work",
        "origin_name": "Home",
        "lat": 40,
        "lon": -74,
        "dest_lat": 40.1,
        "dest_lon": -74.1,
        "dest_name": "Office",
        "schedule_time": "08:00",
        "timezone": "America/New_York",
        **changes,
    }


def test_browser_auth_contract_and_private_response(client):
    sign_in(client, " Rider@Example.com ")
    response = client.post(
        "/api/login",
        data={"username": "RIDER@example.com", "password": "good-password"},
    )
    assert response.status_code == 200
    assert client.get("/api/config").status_code == 200
    assert (
        client.post(
            "/api/login", data={"username": "rider@example.com", "password": "x" * 100}
        ).status_code
        == 401
    )


@pytest.mark.parametrize("use_body", [True, False])
def test_saved_check_never_exposes_another_users_commute(client, use_body):
    sign_in(client)
    commute_id = client.post("/api/config", json=config()).json()["id"]
    client.headers.pop("Authorization")
    url = "/api/check" if use_body else f"/api/check?commute_id={commute_id}"
    payload = {"commute_id": commute_id} if use_body else None
    assert client.post(url, json=payload).status_code == 401
    sign_in(client, "other@example.com")
    assert client.post(url, json=payload).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"lat": 91},
        {"lon": -181},
        {"schedule_time": "25:00"},
        {"schedule_time": "oops"},
        {"return_schedule_time": "18:90"},
        {"dest_lat": None},
        {"name": " "},
        {"timezone": "Not/AZone"},
        {"rain_threshold": 101},
        {"max_wind_no_go": 2},
        {"min_temp_no_go": 80},
        {"days_of_week": ""},
        {"waypoints": [{"lat": 99, "lon": 0}]},
    ],
)
def test_bad_settings_never_persist_or_schedule(client, changes):
    sign_in(client)
    response = client.post("/api/config", json=config(**changes))
    assert response.status_code == 422, response.text
    assert client.get("/api/config").json() == []
    assert scheduler.get_jobs() == []


def test_config_cannot_transfer_ownership(client):
    owner = sign_in(client)
    saved = client.post("/api/config", json=config()).json()
    other = sign_in(client, "other@example.com")
    assert other != owner
    assert (
        client.post("/api/config", json={**saved, "user_id": other}).status_code == 404
    )
    assert (
        client.post("/api/check", params={"commute_id": saved["id"]}).status_code == 404
    )
    assert (
        client.post(
            "/api/analytics/record-decision",
            json={"commute_id": saved["id"], "decision": "riding"},
        ).status_code
        == 404
    )


def test_saved_check_uses_limits_stops_and_both_legs(client):
    sign_in(client)
    saved = client.post(
        "/api/config",
        json=config(
            waypoints=[{"name": "Bridge", "lat": 40.05, "lon": -74.05}],
            max_wind_no_go=20,
        ),
    ).json()
    with patch(
        "app.main.client_instance.fetch_weather_batch",
        new_callable=AsyncMock,
        return_value=[forecast(), forecast(gusts=23), forecast()],
    ):
        result = client.post("/api/check", params={"commute_id": saved["id"]})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["overall_status"] == "No-Go"
    for leg in ["outbound_leg", "return_leg"]:
        assert data[leg]["waypoint_evaluations"][1]["name"] == "Bridge"
        assert data[leg]["status"] == "No-Go"
    assert data["return_leg"]["waypoint_evaluations"][0]["name"] == "Office"
    assert data["timezone"] == "America/New_York"


def test_incomplete_forecast_is_unavailable_not_go(client):
    sign_in(client)
    saved = client.post("/api/config", json=config()).json()
    broken = forecast()
    broken["hourly"]["wind_gusts_10m"] = []
    with patch(
        "app.main.client_instance.fetch_weather_batch",
        new_callable=AsyncMock,
        return_value=[forecast(), broken],
    ):
        response = client.post("/api/check", params={"commute_id": saved["id"]})
    assert response.status_code == 503
    assert "overall_status" not in response.json()


def test_single_trip_has_no_invented_return(client):
    sign_in(client)
    saved = client.post("/api/config", json=config(return_schedule_time=None)).json()
    with patch(
        "app.main.client_instance.fetch_weather_batch",
        new_callable=AsyncMock,
        return_value=[forecast(), forecast()],
    ):
        data = client.post("/api/check", params={"commute_id": saved["id"]}).json()
    assert data["return_leg"] is None


def test_weather_interpolates_and_does_not_reuse_another_date():
    data = forecast()
    data["hourly"]["temperature_2m"][8:10] = [60, 80]
    assert parse_hourly_at_time(data, "08:30").temperature == 70
    with pytest.raises(ValueError, match="outside"):
        parse_hourly_at_time(data, "2000-01-01T08:00")
    data["hourly"]["precipitation_probability"][8] = None
    with pytest.raises(ValueError, match="missing"):
        parse_hourly_at_time(data, "08:00")


def test_next_departure_uses_weekdays_timezone_and_overnight_return():
    commute = Commute(
        **config(
            days_of_week="mon,wed", schedule_time="22:00", return_schedule_time="06:00"
        )
    )
    # Tuesday at 05:00 New York: Monday's return is still ahead.
    outbound, returning = departure_dates(
        commute, datetime(2026, 10, 6, 9, tzinfo=timezone.utc)
    )
    assert outbound.isoformat() == "2026-10-05T22:00:00-04:00"
    assert returning.isoformat() == "2026-10-06T06:00:00-04:00"
    outbound, _ = departure_dates(
        commute, datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
    )
    assert outbound.date().isoformat() == "2026-10-07"


def test_scheduler_uses_commute_timezone():
    commute = Commute(id=17, **config())
    schedule_commute_check(commute)
    assert (
        str(scheduler.get_job("commute_check_17_outbound").trigger.timezone)
        == "America/New_York"
    )


@pytest.mark.parametrize(
    "gusts, code, expected",
    [
        (30, 0, Status.NO_GO),
        (20, 0, Status.CAUTION),
        (5, 66, Status.NO_GO),
        (5, 80, Status.GO),
    ],
)
def test_engine_gusts_and_freezing_rain(gusts, code, expected):
    weather = HourlyWeather(
        temperature=70,
        apparent_temp=70,
        wind_speed=5,
        wind_gusts=gusts,
        precip_prob=0,
        weather_code=code,
    )
    assert AssessmentEngine().assess(weather, Commute(**config())).status == expected


def test_decision_can_be_corrected_without_counting_twice(client):
    sign_in(client)
    first = client.post(
        "/api/analytics/record-decision",
        json={"decision": "riding", "date": "2026-10-01"},
    ).json()
    second = client.post(
        "/api/analytics/record-decision",
        json={"decision": "driving", "date": "2026-10-01"},
    ).json()
    assert first["id"] == second["id"]
    response = client.get(
        "/api/analytics/commute-stats/daily?start_date=2026-10-01&end_date=2026-10-01"
    )
    assert response.status_code == 200
    assert response.json()[0]["days_total"] == 1
    assert response.json()[0]["days_driven"] == 1


def test_overnight_return_is_scheduled_on_following_day():
    commute = Commute(
        id=17,
        **config(
            days_of_week="mon,wed", schedule_time="22:00", return_schedule_time="06:00"
        ),
    )
    schedule_commute_check(commute)
    job = scheduler.get_job("commute_check_17_return")
    fire = job.trigger.get_next_fire_time(
        None, datetime(2026, 10, 5, 4, tzinfo=timezone.utc)
    )
    assert fire.weekday() == 1  # Tuesday, after the Monday outbound.
    assert fire.hour == 6


def test_vapid_keys_survive_restart(monkeypatch, tmp_path):
    from app.push import vapid

    path = tmp_path / "keys.json"
    monkeypatch.setenv("VAPID_KEY_FILE", str(path))
    monkeypatch.setattr(vapid, "_VAPID_PRIVATE_KEY", "")
    monkeypatch.setattr(vapid, "_VAPID_PUBLIC_KEY", "")
    original = vapid.get_or_create_vapid_keys()
    vapid._VAPID_PRIVATE_KEY = vapid._VAPID_PUBLIC_KEY = ""
    assert vapid.get_or_create_vapid_keys() == original
    assert path.stat().st_mode & 0o777 == 0o600


def test_upgrade_preserves_existing_commutes_and_is_repeatable(monkeypatch, tmp_path):
    from app import database
    from sqlalchemy import text

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE commute (id INTEGER PRIMARY KEY, name VARCHAR, lat FLOAT, lon FLOAT)"
            )
        )
        connection.execute(
            text("INSERT INTO commute VALUES (1, 'Existing ride', 40, -74)")
        )
    monkeypatch.setattr(database, "engine", engine)
    database.create_db_and_tables()
    database.create_db_and_tables()
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name, origin_name, timezone FROM commute")
        ).one()
    assert tuple(row) == ("Existing ride", "Home", "UTC")
    engine.dispose()


def test_new_api_prefix_reaches_push_and_weather_routes(client):
    sign_in(client)
    assert client.get("/api/push/vapid-public-key").status_code == 200
    assert client.get("/api/weather/forecast").status_code == 404


def test_place_search_failure_is_actionable(client):
    from app.places import _cache

    _cache.clear()
    import httpx

    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("offline")):
        response = client.get("/api/places?q=Boston")
    assert response.status_code == 503
    assert "Try again" in response.json()["detail"]
