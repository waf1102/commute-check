import os
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from jose import jwt
from sqlmodel import create_engine, Session, SQLModel, select

from app.main import app, scheduler, clear_commute_jobs
from app.database import get_session
from app.models import Commute, CommuteCreate, User, Waypoint
from app.security import ALGORITHM, SECRET_KEY, get_password_hash


INTEGRATION_DB_URL = "sqlite:///./test_integration_commute.db"
integration_engine = create_engine(INTEGRATION_DB_URL, echo=False)


@pytest.fixture(autouse=True, scope="module")
def cleanup_integration_db():
    SQLModel.metadata.create_all(integration_engine)
    yield
    integration_engine.dispose()
    if os.path.exists("./test_integration_commute.db"):
        try:
            os.remove("./test_integration_commute.db")
        except OSError:
            pass


@pytest.fixture(name="session")
def session_fixture():
    with Session(integration_engine) as session:
        yield session
        # Clean up database tables between tests
        session.exec(select(Commute)).all()
        for c in session.exec(select(Commute)).all():
            clear_commute_jobs(c.id)
            session.delete(c)
        for u in session.exec(select(User)).all():
            session.delete(u)
        session.commit()


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def make_user(session: Session, email: str = "user@example.com") -> tuple[User, dict]:
    user = User(email=email, hashed_password=get_password_hash("password123"))
    session.add(user)
    session.commit()
    session.refresh(user)

    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    token = jwt.encode(
        {"sub": user.email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM
    )
    headers = {"Authorization": f"Bearer {token}"}
    return user, headers


# ============================================================================
# 1. Full CRUD & Route Aliases Integration Test
# ============================================================================


def test_commute_crud_lifecycle_across_route_aliases(
    client: TestClient, session: Session
):
    """
    Verify full CRUD lifecycle across all registered route aliases:
    /config, /api/config, /commutes, /api/commutes, /commute, /api/commute
    """
    user, headers = make_user(session, email="crud_aliases@example.com")

    # 1. Create commute via /api/commutes
    create_payload = {
        "name": "Morning Ride",
        "lat": 37.7749,
        "lon": -122.4194,
        "dest_name": "Financial District",
        "dest_lat": 37.7946,
        "dest_lon": -122.3999,
        "schedule_time": "08:00",
        "return_schedule_time": "17:30",
        "days_of_week": "mon-fri",
        "waypoints": [
            {
                "id": "wp-1",
                "name": "Coffee Stop",
                "lat": 37.7800,
                "lon": -122.4100,
                "order": 0,
                "status": "active",
            },
            {
                "id": "wp-2",
                "name": "Park View",
                "lat": 37.7850,
                "lon": -122.4050,
                "order": 1,
                "status": "active",
            },
        ],
    }

    create_resp = client.post("/api/commutes", json=create_payload, headers=headers)
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    cid = created["id"]
    assert created["name"] == "Morning Ride"
    assert created["user_id"] == user.id
    assert len(created["waypoints"]) == 2
    assert created["waypoints"][0]["name"] == "Coffee Stop"

    # 2. Test GET list across all route aliases: /config, /api/config, /commutes, /api/commutes, /commute, /api/commute
    for endpoint in [
        "/config",
        "/api/config",
        "/commutes",
        "/api/commutes",
        "/commute",
        "/api/commute",
    ]:
        list_resp = client.get(endpoint, headers=headers)
        assert list_resp.status_code == 200, f"Failed at {endpoint}: {list_resp.text}"
        data = list_resp.json()
        assert len(data) == 1
        assert data[0]["id"] == cid
        assert data[0]["name"] == "Morning Ride"

    # 3. Test GET single commute across all route aliases
    for endpoint in [
        f"/commutes/{cid}",
        f"/api/commutes/{cid}",
        f"/config/{cid}",
        f"/api/config/{cid}",
        f"/commute/{cid}",
        f"/api/commute/{cid}",
    ]:
        get_resp = client.get(endpoint, headers=headers)
        assert get_resp.status_code == 200, f"Failed at {endpoint}: {get_resp.text}"
        commute_item = get_resp.json()
        assert commute_item["id"] == cid
        assert commute_item["name"] == "Morning Ride"

    # 4. Test PUT update across route aliases (e.g. /api/commutes/{cid})
    update_payload = dict(create_payload)
    update_payload["name"] = "Updated Morning Ride"
    update_payload["schedule_time"] = "08:15"
    put_resp = client.put(f"/api/commutes/{cid}", json=update_payload, headers=headers)
    assert put_resp.status_code == 200, put_resp.text
    assert put_resp.json()["name"] == "Updated Morning Ride"
    assert put_resp.json()["schedule_time"] == "08:15"

    # 5. Test update via POST /config with commute id
    config_update_payload = dict(update_payload)
    config_update_payload["id"] = cid
    config_update_payload["name"] = "Updated Via Config"
    post_config_resp = client.post(
        "/config", json=config_update_payload, headers=headers
    )
    assert post_config_resp.status_code == 200, post_config_resp.text
    assert post_config_resp.json()["name"] == "Updated Via Config"
    assert post_config_resp.json()["id"] == cid

    # Verify directly in SQLite DB
    db_commute = session.get(Commute, cid)
    assert db_commute is not None
    assert db_commute.name == "Updated Via Config"

    # 6. Test DELETE across route aliases
    del_resp = client.delete(f"/commutes/{cid}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json() == {"status": "deleted"}

    # Verify deleted from DB
    session.expire_all()
    assert session.get(Commute, cid) is None

    # Verify list is empty
    assert len(client.get("/api/commutes", headers=headers).json()) == 0


# ============================================================================
# 2. Waypoint Persistence, Reordering, and CRUD Lifecycle
# ============================================================================


def test_waypoints_persistence_and_reordering(client: TestClient, session: Session):
    """
    Verify that adding, updating, reordering, and deleting waypoints correctly
    persists in SQLite without data corruption or type coercion bugs.
    """
    user, headers = make_user(session, email="waypoints_test@example.com")

    # Step 1: Create commute with 3 waypoints
    initial_waypoints = [
        {
            "id": "wp-101",
            "name": "Alpha Stop",
            "lat": 40.7100,
            "lon": -74.0100,
            "order": 0,
            "status": "pending",
        },
        {
            "id": "wp-102",
            "name": "Beta Stop",
            "lat": 40.7200,
            "lon": -74.0050,
            "order": 1,
            "status": "pending",
        },
        {
            "id": "wp-103",
            "name": "Gamma Stop",
            "lat": 40.7300,
            "lon": -74.0000,
            "order": 2,
            "status": "pending",
        },
    ]
    payload = {
        "name": "Waypoint Commute",
        "lat": 40.7000,
        "lon": -74.0200,
        "schedule_time": "08:30",
        "waypoints": initial_waypoints,
    }

    create_res = client.post("/api/commutes", json=payload, headers=headers)
    assert create_res.status_code == 200, create_res.text
    created = create_res.json()
    cid = created["id"]

    # Verify in DB fresh session
    session.expire_all()
    db_commute = session.get(Commute, cid)
    assert db_commute is not None
    assert len(db_commute.waypoints) == 3
    assert [w.name for w in db_commute.waypoints] == [
        "Alpha Stop",
        "Beta Stop",
        "Gamma Stop",
    ]
    assert [w.order for w in db_commute.waypoints] == [0, 1, 2]
    assert db_commute.waypoints[0].id == "wp-101"
    assert db_commute.waypoints[0].status == "pending"

    # Step 2: Reorder waypoints (Gamma -> Alpha -> Beta)
    reordered_waypoints = [
        {
            "id": "wp-103",
            "name": "Gamma Stop",
            "lat": 40.7300,
            "lon": -74.0000,
            "order": 0,
            "status": "pending",
        },
        {
            "id": "wp-101",
            "name": "Alpha Stop",
            "lat": 40.7100,
            "lon": -74.0100,
            "order": 1,
            "status": "pending",
        },
        {
            "id": "wp-102",
            "name": "Beta Stop",
            "lat": 40.7200,
            "lon": -74.0050,
            "order": 2,
            "status": "pending",
        },
    ]
    update_payload = dict(payload)
    update_payload["waypoints"] = reordered_waypoints

    update_res = client.put(
        f"/api/commutes/{cid}", json=update_payload, headers=headers
    )
    assert update_res.status_code == 200, update_res.text
    updated = update_res.json()
    assert [w["name"] for w in updated["waypoints"]] == [
        "Gamma Stop",
        "Alpha Stop",
        "Beta Stop",
    ]
    assert [w["order"] for w in updated["waypoints"]] == [0, 1, 2]

    # Verify retrieved from GET endpoint
    get_res = client.get(f"/api/commutes/{cid}", headers=headers)
    assert get_res.status_code == 200
    assert [w["name"] for w in get_res.json()["waypoints"]] == [
        "Gamma Stop",
        "Alpha Stop",
        "Beta Stop",
    ]

    # Step 3: Modify waypoint details (change Beta Stop to Delta Stop with new coordinates)
    modified_waypoints = [
        {
            "id": "wp-103",
            "name": "Gamma Stop",
            "lat": 40.7300,
            "lon": -74.0000,
            "order": 0,
            "status": "pending",
        },
        {
            "id": "wp-101",
            "name": "Alpha Stop",
            "lat": 40.7100,
            "lon": -74.0100,
            "order": 1,
            "status": "pending",
        },
        {
            "id": "wp-104",
            "name": "Delta Stop",
            "lat": 40.7450,
            "lon": -73.9900,
            "order": 2,
            "status": "verified",
        },
    ]
    update_payload["waypoints"] = modified_waypoints
    put_mod_res = client.put(
        f"/api/commutes/{cid}", json=update_payload, headers=headers
    )
    assert put_mod_res.status_code == 200
    assert put_mod_res.json()["waypoints"][2]["name"] == "Delta Stop"
    assert put_mod_res.json()["waypoints"][2]["lat"] == 40.7450
    assert put_mod_res.json()["waypoints"][2]["status"] == "verified"

    # Step 4: Clear all waypoints (delete waypoints by sending empty list)
    update_payload["waypoints"] = []
    put_clear_res = client.put(
        f"/api/commutes/{cid}", json=update_payload, headers=headers
    )
    assert put_clear_res.status_code == 200
    assert put_clear_res.json()["waypoints"] == []

    # Verify SQLite DB has empty waypoints
    session.expire_all()
    refreshed_commute = session.get(Commute, cid)
    assert refreshed_commute.waypoints == []

    # Step 5: Add a new waypoint to previously cleared commute
    new_single_waypoint = [
        {
            "id": "wp-fresh",
            "name": "Fresh Waypoint",
            "lat": 40.7500,
            "lon": -73.9800,
            "order": 0,
        }
    ]
    update_payload["waypoints"] = new_single_waypoint
    put_fresh_res = client.put(
        f"/api/commutes/{cid}", json=update_payload, headers=headers
    )
    assert put_fresh_res.status_code == 200
    assert len(put_fresh_res.json()["waypoints"]) == 1
    assert put_fresh_res.json()["waypoints"][0]["name"] == "Fresh Waypoint"


# ============================================================================
# 3. Schedule Normalization Integration Test
# ============================================================================


def test_days_of_week_schedule_normalization(client: TestClient, session: Session):
    """
    Verify day-of-week schedule normalization handles all valid formats
    (e.g. 'mon-fri', 'mon,wed,fri', '*', 'Monday, Wednesday, Friday')
    and rejects invalid formats.
    """
    user, headers = make_user(session, email="schedule_norm@example.com")

    valid_cases = [
        ("mon-fri", "mon-fri"),
        ("mon,wed,fri", "mon,wed,fri"),
        ("*", "*"),
        ("Monday, Wednesday, Friday", "mon,wed,fri"),
        ("MON-FRI", "mon-fri"),
        ("0-4", "0-4"),
        ("sat,sun", "sat,sun"),
        ("tue-thu,sat", "tue-thu,sat"),
    ]

    for input_val, expected_val in valid_cases:
        payload = {
            "name": f"Commute {input_val}",
            "lat": 51.5074,
            "lon": -0.1278,
            "schedule_time": "08:00",
            "days_of_week": input_val,
        }
        res = client.post("/api/commutes", json=payload, headers=headers)
        assert res.status_code == 200, (
            f"Failed on valid days_of_week '{input_val}': {res.text}"
        )
        data = res.json()
        assert data["days_of_week"] == expected_val

    # Test invalid days_of_week
    invalid_cases = [
        "invalid_day",
        "mon-xyz",
        "mon,,fri",
        "",
        "   ",
        "mon-fri-sat",
        "weekend",
    ]
    for invalid_val in invalid_cases:
        payload = {
            "name": f"Invalid Commute {invalid_val}",
            "lat": 51.5074,
            "lon": -0.1278,
            "schedule_time": "08:00",
            "days_of_week": invalid_val,
        }
        res = client.post("/api/commutes", json=payload, headers=headers)
        assert res.status_code == 422, (
            f"Should have rejected invalid days_of_week '{invalid_val}'"
        )


# ============================================================================
# 4. Realistic Threshold Validations Integration Test
# ============================================================================


def test_threshold_and_coordinate_validations(client: TestClient, session: Session):
    """
    Verify threshold validations: ensure min/max temperatures, wind speeds,
    rain threshold, coordinates, and times accept realistic numeric values
    and reject unrealistic or invalid inputs.
    """
    user, headers = make_user(session, email="thresholds_test@example.com")

    # Valid realistic thresholds
    valid_payload = {
        "name": "Realistic Thresholds",
        "lat": 34.0522,
        "lon": -118.2437,
        "schedule_time": "07:45",
        "return_schedule_time": "16:45",
        "min_temp_caution": 40.0,
        "min_temp_no_go": 32.0,
        "max_wind_caution": 20.0,
        "max_wind_no_go": 35.0,
        "rain_threshold": 45.0,
    }
    res = client.post("/api/commutes", json=valid_payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["min_temp_caution"] == 40.0
    assert data["min_temp_no_go"] == 32.0
    assert data["max_wind_caution"] == 20.0
    assert data["max_wind_no_go"] == 35.0
    assert data["rain_threshold"] == 45.0

    # Invalid rain_threshold (> 100 or < 0)
    for bad_rain in [-5.0, 105.0]:
        bad_payload = dict(valid_payload, rain_threshold=bad_rain)
        res = client.post("/api/commutes", json=bad_payload, headers=headers)
        assert res.status_code == 422, f"Expected 422 for rain_threshold={bad_rain}"

    # Invalid wind threshold (< 0 or > 200)
    for bad_wind in [-1.0, 250.0]:
        bad_payload = dict(valid_payload, max_wind_caution=bad_wind)
        res = client.post("/api/commutes", json=bad_payload, headers=headers)
        assert res.status_code == 422, f"Expected 422 for max_wind_caution={bad_wind}"

    # Invalid temperatures (< -100 or > 150)
    for bad_temp in [-120.0, 180.0]:
        bad_payload = dict(valid_payload, min_temp_no_go=bad_temp)
        res = client.post("/api/commutes", json=bad_payload, headers=headers)
        assert res.status_code == 422, f"Expected 422 for min_temp_no_go={bad_temp}"

    # Invalid coordinates (lat < -90 or > 90, lon < -180 or > 180)
    bad_lat = dict(valid_payload, lat=95.0)
    assert (
        client.post("/api/commutes", json=bad_lat, headers=headers).status_code == 422
    )

    bad_lon = dict(valid_payload, lon=-190.0)
    assert (
        client.post("/api/commutes", json=bad_lon, headers=headers).status_code == 422
    )

    # Invalid schedule_time format
    for bad_time in ["25:00", "08:60", "invalid", "8am"]:
        bad_schedule = dict(valid_payload, schedule_time=bad_time)
        assert (
            client.post("/api/commutes", json=bad_schedule, headers=headers).status_code
            == 422
        )


# ============================================================================
# 5. Multi-Commute User Isolation Integration Test
# ============================================================================


def test_multi_commute_user_isolation(client: TestClient, session: Session):
    """
    Ensure users can only list, update, and delete their own commutes.
    Ensure spoofed user_id is ignored and user attribution is strictly enforced.
    """
    user_a, headers_a = make_user(session, email="alice@example.com")
    user_b, headers_b = make_user(session, email="bob@example.com")

    # User A creates Commute A
    payload_a = {
        "name": "Alice Commute",
        "lat": 37.77,
        "lon": -122.41,
        "schedule_time": "08:00",
    }
    res_a = client.post("/api/commutes", json=payload_a, headers=headers_a)
    assert res_a.status_code == 200
    cid_a = res_a.json()["id"]

    # User B creates Commute B
    payload_b = {
        "name": "Bob Commute",
        "lat": 40.71,
        "lon": -74.00,
        "schedule_time": "09:00",
    }
    res_b = client.post("/api/commutes", json=payload_b, headers=headers_b)
    assert res_b.status_code == 200
    cid_b = res_b.json()["id"]

    # 1. Listing isolation
    list_a = client.get("/api/commutes", headers=headers_a).json()
    assert len(list_a) == 1
    assert list_a[0]["id"] == cid_a
    assert list_a[0]["name"] == "Alice Commute"

    list_b = client.get("/api/commutes", headers=headers_b).json()
    assert len(list_b) == 1
    assert list_b[0]["id"] == cid_b
    assert list_b[0]["name"] == "Bob Commute"

    # 2. Get single commute isolation
    # Alice trying to view Bob's commute
    res_a_view_b = client.get(f"/api/commutes/{cid_b}", headers=headers_a)
    assert res_a_view_b.status_code == 404

    # Bob trying to view Alice's commute
    res_b_view_a = client.get(f"/api/commutes/{cid_a}", headers=headers_b)
    assert res_b_view_a.status_code == 404

    # 3. Update isolation
    # Alice trying to update Bob's commute via PUT
    res_a_put_b = client.put(
        f"/api/commutes/{cid_b}",
        json={
            "name": "Alice Hacked Bob",
            "lat": 1.0,
            "lon": 1.0,
            "schedule_time": "12:00",
        },
        headers=headers_a,
    )
    assert res_a_put_b.status_code == 404

    # Verify Bob's commute was NOT changed
    session.expire_all()
    bob_commute = session.get(Commute, cid_b)
    assert bob_commute.name == "Bob Commute"

    # Alice trying to update Bob's commute via POST /config with Bob's id
    res_a_post_b = client.post(
        "/config",
        json={
            "id": cid_b,
            "name": "Alice Hijack Bob",
            "lat": 1.0,
            "lon": 1.0,
            "schedule_time": "12:00",
        },
        headers=headers_a,
    )
    assert res_a_post_b.status_code == 404

    # 4. Delete isolation
    # Alice trying to delete Bob's commute
    res_a_del_b = client.delete(f"/api/commutes/{cid_b}", headers=headers_a)
    assert res_a_del_b.status_code == 404

    # Verify Bob's commute is still in DB
    session.expire_all()
    assert session.get(Commute, cid_b) is not None

    # 5. User ID attribution spoofing test:
    # Alice sends payload with user_id set to Bob's ID -> should still be owned by Alice
    spoof_payload = {
        "name": "Alice Spoofed Commute",
        "lat": 37.77,
        "lon": -122.41,
        "schedule_time": "08:30",
        "user_id": user_b.id,
    }
    spoof_res = client.post("/api/commutes", json=spoof_payload, headers=headers_a)
    assert spoof_res.status_code == 200
    spoof_commute = spoof_res.json()
    assert spoof_commute["user_id"] == user_a.id  # Must be Alice!


# ============================================================================
# 6. Scheduler Job Synchronization Integration Test
# ============================================================================


def test_scheduler_synchronization_lifecycle(client: TestClient, session: Session):
    """
    Ensure scheduler jobs (schedule_commute_check) are synchronized
    when commutes are created, updated, or deleted.
    """
    user, headers = make_user(session, email="scheduler_sync@example.com")

    # 1. Create commute with outbound and return schedule
    payload = {
        "name": "Scheduled Commute",
        "lat": 37.7749,
        "lon": -122.4194,
        "dest_name": "Office",
        "dest_lat": 37.7849,
        "dest_lon": -122.4094,
        "schedule_time": "08:15",
        "return_schedule_time": "17:45",
        "days_of_week": "mon-fri",
    }

    create_res = client.post("/api/commutes", json=payload, headers=headers)
    assert create_res.status_code == 200
    cid = create_res.json()["id"]

    outbound_job = scheduler.get_job(f"commute_check_{cid}_outbound")
    return_job = scheduler.get_job(f"commute_check_{cid}_return")
    assert outbound_job is not None, f"Outbound job for commute {cid} not scheduled"
    assert return_job is not None, f"Return job for commute {cid} not scheduled"

    out_fields = {f.name: str(f) for f in outbound_job.trigger.fields}
    assert out_fields["hour"] == "8"
    assert out_fields["minute"] == "15"

    ret_fields = {f.name: str(f) for f in return_job.trigger.fields}
    assert ret_fields["hour"] == "17"
    assert ret_fields["minute"] == "45"

    # 2. Update commute schedule times (outbound 09:30, return 18:00)
    updated_payload = dict(payload)
    updated_payload["schedule_time"] = "09:30"
    updated_payload["return_schedule_time"] = "18:00"

    update_res = client.put(
        f"/api/commutes/{cid}", json=updated_payload, headers=headers
    )
    assert update_res.status_code == 200

    updated_out = scheduler.get_job(f"commute_check_{cid}_outbound")
    updated_ret = scheduler.get_job(f"commute_check_{cid}_return")
    assert updated_out is not None
    assert updated_ret is not None

    out_fields = {f.name: str(f) for f in updated_out.trigger.fields}
    assert out_fields["hour"] == "9"
    assert out_fields["minute"] == "30"

    ret_fields = {f.name: str(f) for f in updated_ret.trigger.fields}
    assert ret_fields["hour"] == "18"
    assert ret_fields["minute"] == "0"

    # 3. Delete commute and verify both jobs cleared
    del_res = client.delete(f"/api/commutes/{cid}", headers=headers)
    assert del_res.status_code == 200

    assert scheduler.get_job(f"commute_check_{cid}_outbound") is None
    assert scheduler.get_job(f"commute_check_{cid}_return") is None
