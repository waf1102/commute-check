import os
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.main import app, get_session
from app.models import Status

DATABASE_URL = "sqlite:///./test_e2e.db"
engine = create_engine(DATABASE_URL, echo=False)


@pytest.fixture(autouse=True, scope="module")
def cleanup_e2e_db():
    yield
    engine.dispose()
    if os.path.exists("./test_e2e.db"):
        try:
            os.remove("./test_e2e.db")
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


def test_golden_path_user_journey(client: TestClient):
    """
    End-to-End Golden Path Test:
    1. Register user via /api/register
    2. Login via /api/login and retrieve JWT access token
    3. Configure commute with waypoints via /api/commutes
    4. Fetch saved commute to verify persistence
    5. Query route directions for the waypoints via /api/route/directions
    6. Run route assessment (with external weather mocked) via /api/check
    7. Record decision (ride vs drive) in analytics via /api/analytics/record-decision
    8. Query analytics stats via /api/analytics/commute-stats/daily
    9. Update commute thresholds via /api/commutes/{id}
    10. Delete commute via /api/commutes/{id}
    """
    # 1. Register
    reg_payload = {"email": "rider@example.com", "password": "securepassword123"}
    reg_resp = client.post("/api/register", json=reg_payload)
    assert reg_resp.status_code == 200, reg_resp.text
    user_id = reg_resp.json()["user"]["id"]

    # 2. Login
    login_resp = client.post(
        "/api/login",
        data={"username": "rider@example.com", "password": "securepassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Commute with Waypoints
    commute_payload = {
        "name": "Morning Coastal Commute",
        "lat": 37.7749,
        "lon": -122.4194,
        "dest_name": "Downtown Office",
        "dest_lat": 37.7891,
        "dest_lon": -122.4014,
        "schedule_time": "08:30",
        "waypoints": [
            {"name": "Scenic Overlook", "lat": 37.7800, "lon": -122.4100, "order": 0}
        ],
        "rain_threshold": 25.0,
        "max_wind_caution": 20.0,
        "max_wind_no_go": 35.0,
    }
    create_resp = client.post(
        "/api/commutes", json=commute_payload, headers=auth_headers
    )
    assert create_resp.status_code == 200, create_resp.text
    commute_data = create_resp.json()
    commute_id = commute_data["id"]
    assert len(commute_data["waypoints"]) == 1
    assert commute_data["waypoints"][0]["name"] == "Scenic Overlook"

    # 4. Fetch Saved Commute
    list_resp = client.get("/api/commutes", headers=auth_headers)
    assert list_resp.status_code == 200
    commutes = list_resp.json()
    assert any(c["id"] == commute_id for c in commutes)

    # 5. Route Directions API
    directions_payload = {
        "origin": {"lat": 37.7749, "lon": -122.4194},
        "destination": {"lat": 37.7891, "lon": -122.4014},
        "waypoints": [{"lat": 37.7800, "lon": -122.4100}],
    }
    dir_resp = client.post(
        "/api/route/directions", json=directions_payload, headers=auth_headers
    )
    assert dir_resp.status_code == 200
    route_info = dir_resp.json()
    assert "geometry" in route_info
    assert route_info["total_distance"] > 0
    assert route_info["total_duration"] > 0

    # 6. Route Assessment (Mock external WeatherClient at network boundary)
    from tests.helpers import forecast

    mock_forecast = forecast(65)
    with patch(
        "app.main.client_instance.fetch_weather_batch",
        new_callable=AsyncMock,
        return_value=[mock_forecast, mock_forecast, mock_forecast],
    ):
        check_resp = client.post(
            f"/api/check?commute_id={commute_id}", headers=auth_headers
        )
        assert check_resp.status_code == 200, check_resp.text
        assessment = check_resp.json()
        assert assessment["overall_status"] == Status.GO.value
        assert len(assessment["outbound_leg"]["waypoint_evaluations"]) == 3
        assert len(assessment["return_leg"]["waypoint_evaluations"]) == 3
        assert (
            assessment["return_leg"]["waypoint_evaluations"][1]["name"]
            == "Scenic Overlook"
        )

    # 7. Record Decision in Analytics
    decision_payload = {
        "commute_id": commute_id,
        "decision": "riding",
        "commute_distance_km": route_info["total_distance"] / 1000.0,
        "duration_minutes": route_info["total_duration"] / 60.0,
    }
    decision_resp = client.post(
        "/api/analytics/record-decision", json=decision_payload, headers=auth_headers
    )
    assert decision_resp.status_code == 200
    record_data = decision_resp.json()
    assert record_data["commute_type"] == "riding"

    # 8. Query Analytics Stats (use UTC date for consistent database comparison)
    today_utc = datetime.now(timezone.utc).date()
    start_str = (today_utc - timedelta(days=1)).isoformat()
    end_str = (today_utc + timedelta(days=1)).isoformat()
    stats_resp = client.get(
        f"/api/analytics/commute-stats/daily?user_id={user_id}&start_date={start_str}&end_date={end_str}",
        headers=auth_headers,
    )
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert len(stats) >= 1
    assert stats[0]["days_ridden"] >= 1

    # 9. Update Commute Preferences
    update_payload = {
        "name": "Morning Coastal Commute (Updated)",
        "lat": 37.7749,
        "lon": -122.4194,
        "schedule_time": "08:30",
        "rain_threshold": 15.0,
    }
    put_resp = client.put(
        f"/api/commutes/{commute_id}", json=update_payload, headers=auth_headers
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["rain_threshold"] == 15.0

    # 10. Delete Commute
    del_resp = client.delete(f"/api/commutes/{commute_id}", headers=auth_headers)
    assert del_resp.status_code == 200

    # Verify deleted
    verify_resp = client.get("/api/commutes", headers=auth_headers)
    assert not any(c["id"] == commute_id for c in verify_resp.json())
