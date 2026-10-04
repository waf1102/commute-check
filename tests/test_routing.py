import os
import math
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine, Session, SQLModel, select
from sqlmodel.pool import StaticPool
from pydantic import ValidationError

from app.main import app, get_session
from app.models import Commute, Waypoint, User
from app.routing import (
    RoutingService,
    routing_service,
    haversine_distance,
    parse_coordinate,
    sort_and_parse_waypoints,
    calculate_haversine_fallback,
    RouteDirectionsRequest,
    RouteDirectionsResponse,
)
from app.security import get_password_hash, create_access_token


# --- Fixtures ---
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)


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


@pytest.fixture
def auth_headers(session: Session):
    user = User(
        email="routing_user@example.com", hashed_password=get_password_hash("pass")
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_access_token({"sub": user.email})
    return {"Authorization": f"Bearer {token}"}, user


# =====================================================================
# 1. Unit Tests: Haversine & Coordinate Parsing
# =====================================================================


def test_haversine_distance_known_coordinates():
    # Equator 0 to 1 degree longitude: approx 111.19 km
    dist = haversine_distance(0.0, 0.0, 0.0, 1.0)
    assert 111000 < dist < 112000

    # Same point distance should be 0
    assert haversine_distance(37.77, -122.41, 37.77, -122.41) == 0.0


def test_parse_coordinate_various_formats():
    # Tuple / list
    assert parse_coordinate((37.77, -122.41)) == (37.77, -122.41)
    assert parse_coordinate([37.77, -122.41]) == (37.77, -122.41)

    # Dict with lat / lon
    assert parse_coordinate({"lat": 37.77, "lon": -122.41}) == (37.77, -122.41)
    assert parse_coordinate({"latitude": 37.77, "longitude": -122.41}) == (
        37.77,
        -122.41,
    )
    assert parse_coordinate({"lat": 37.77, "lng": -122.41}) == (37.77, -122.41)

    # Object / Waypoint
    wp = Waypoint(name="Coffee", lat=37.77, lon=-122.41, order=1)
    assert parse_coordinate(wp) == (37.77, -122.41)


def test_parse_coordinate_invalid_bounds():
    with pytest.raises(ValueError, match="Latitude"):
        parse_coordinate((95.0, 10.0))

    with pytest.raises(ValueError, match="Latitude"):
        parse_coordinate((-91.0, 10.0))

    with pytest.raises(ValueError, match="Longitude"):
        parse_coordinate((10.0, 185.0))

    with pytest.raises(ValueError, match="Longitude"):
        parse_coordinate((10.0, -185.0))

    with pytest.raises(ValueError, match="Cannot parse coordinate"):
        parse_coordinate("invalid string coordinate")


def test_sort_and_parse_waypoints():
    wps = [
        {"name": "Third", "lat": 10.0, "lon": 20.0, "order": 3},
        {"name": "First", "lat": 12.0, "lon": 22.0, "order": 1},
        Waypoint(name="Second", lat=11.0, lon=21.0, order=2),
    ]
    sorted_wps = sort_and_parse_waypoints(wps)
    assert len(sorted_wps) == 3
    assert sorted_wps[0][2] == "First"
    assert sorted_wps[0][3] == 1
    assert sorted_wps[1][2] == "Second"
    assert sorted_wps[1][3] == 2
    assert sorted_wps[2][2] == "Third"
    assert sorted_wps[2][3] == 3


# =====================================================================
# 2. Unit Tests: OSRM Response Parsing & Route Directions
# =====================================================================


@pytest.mark.asyncio
async def test_osrm_response_parsing_success():
    mock_osrm_json = {
        "code": "Ok",
        "routes": [
            {
                "distance": 2500.0,
                "duration": 300.0,
                "weight": 300.0,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-122.41, 37.77],
                        [-122.415, 37.775],
                        [-122.42, 37.78],
                    ],
                },
                "legs": [
                    {"distance": 1000.0, "duration": 120.0, "summary": "Main St"},
                    {"distance": 1500.0, "duration": 180.0, "summary": "Market St"},
                ],
            }
        ],
        "waypoints": [],
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_osrm_json

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        service = RoutingService()
        result = await service.get_route_directions(
            origin=(37.77, -122.41),
            destination=(37.78, -122.42),
            waypoints=[{"name": "Stop 1", "lat": 37.775, "lon": -122.415, "order": 1}],
        )

        assert result.fallback is False
        assert result.total_distance == 2500.0
        assert result.total_duration == 300.0
        assert len(result.geometry) == 3
        assert result.geometry[0] == [-122.41, 37.77]
        assert len(result.legs) == 2
        assert result.legs[0].distance == 1000.0
        assert result.legs[0].duration == 120.0
        assert result.legs[1].distance == 1500.0
        assert result.legs[1].duration == 180.0
        assert result.leg_durations == [120.0, 180.0]


# =====================================================================
# 3. Unit Tests: Error Handling & Haversine Linear Fallback
# =====================================================================


@pytest.mark.asyncio
async def test_fallback_when_osrm_times_out():
    origin = (37.77, -122.41)
    destination = (37.78, -122.42)

    with patch(
        "httpx.AsyncClient.get", side_effect=httpx.TimeoutException("OSRM timed out")
    ):
        service = RoutingService()
        result = await service.get_route_directions(origin, destination)

        assert result.fallback is True
        # Haversine distance between origin and destination
        expected_dist = haversine_distance(37.77, -122.41, 37.78, -122.42)
        assert abs(result.total_distance - expected_dist) < 0.1

        # 50 km/h = 13.8888... m/s
        expected_dur = expected_dist / (50000.0 / 3600.0)
        assert abs(result.total_duration - expected_dur) < 0.1

        # Geometry contains the coordinates [[lon, lat], ...]
        assert len(result.geometry) == 2
        assert result.geometry[0] == [-122.41, 37.77]
        assert result.geometry[1] == [-122.42, 37.78]

        assert len(result.legs) == 1
        assert abs(result.legs[0].distance - expected_dist) < 0.1
        assert abs(result.legs[0].duration - expected_dur) < 0.1
        assert len(result.leg_durations) == 1


@pytest.mark.asyncio
async def test_fallback_when_osrm_returns_500():
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 500

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        service = RoutingService()
        result = await service.get_route_directions((37.77, -122.41), (37.78, -122.42))
        assert result.fallback is True
        assert result.total_distance > 0
        assert result.total_duration > 0


@pytest.mark.asyncio
async def test_fallback_when_osrm_returns_non_ok_code():
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": "NoRoute", "message": "No route found"}

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        service = RoutingService()
        result = await service.get_route_directions((37.77, -122.41), (37.78, -122.42))
        assert result.fallback is True


def test_haversine_fallback_multi_waypoint_calculations():
    points = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]
    result = calculate_haversine_fallback(points, speed_kmh=50.0)

    leg0_dist = haversine_distance(0.0, 0.0, 0.0, 1.0)
    leg1_dist = haversine_distance(0.0, 1.0, 0.0, 2.0)
    speed_mps = (50.0 * 1000.0) / 3600.0

    assert result.fallback is True
    assert abs(result.total_distance - (leg0_dist + leg1_dist)) < 0.01
    assert abs(result.total_duration - ((leg0_dist + leg1_dist) / speed_mps)) < 0.01
    assert len(result.legs) == 2
    assert abs(result.legs[0].distance - leg0_dist) < 0.01
    assert abs(result.legs[1].distance - leg1_dist) < 0.01
    assert result.geometry == [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]


# =====================================================================
# 4. Integration Tests: Waypoints Persistence & Schema Validation
# =====================================================================


def test_waypoint_model_validation():
    # Valid waypoint
    wp = Waypoint(name="Valid Stop", lat=45.0, lon=90.0, order=1)
    assert wp.name == "Valid Stop"
    assert wp.lat == 45.0
    assert wp.lon == 90.0
    assert wp.order == 1

    # Invalid latitude
    with pytest.raises(ValidationError):
        Waypoint(name="Bad Lat", lat=91.0, lon=0.0, order=1)

    with pytest.raises(ValidationError):
        Waypoint(name="Bad Lat Neg", lat=-91.0, lon=0.0, order=1)

    # Invalid longitude
    with pytest.raises(ValidationError):
        Waypoint(name="Bad Lon", lat=0.0, lon=181.0, order=1)

    with pytest.raises(ValidationError):
        Waypoint(name="Bad Lon Neg", lat=0.0, lon=-181.0, order=1)


def test_commute_waypoints_sorting_and_persistence(session: Session):
    # Pass waypoints out of order
    raw_waypoints = [
        {"name": "Stop 3", "lat": 37.79, "lon": -122.43, "order": 3},
        {"name": "Stop 1", "lat": 37.77, "lon": -122.41, "order": 1},
        {"name": "Stop 2", "lat": 37.78, "lon": -122.42, "order": 2},
    ]

    commute = Commute(
        name="Scenic Commute",
        lat=37.76,
        lon=-122.40,
        schedule_time="08:30",
        waypoints=raw_waypoints,
    )

    # Verify auto-sorting before saving
    assert [w.order for w in commute.waypoints] == [1, 2, 3]
    assert [w.name for w in commute.waypoints] == ["Stop 1", "Stop 2", "Stop 3"]

    session.add(commute)
    session.commit()
    session.refresh(commute)

    commute_id = commute.id
    assert commute_id is not None

    # Retrieve from fresh query
    saved = session.get(Commute, commute_id)
    assert saved is not None
    assert len(saved.waypoints) == 3
    assert [w.order for w in saved.waypoints] == [1, 2, 3]
    assert [w.name for w in saved.waypoints] == ["Stop 1", "Stop 2", "Stop 3"]
    assert isinstance(saved.waypoints[0], Waypoint)


def test_config_endpoints_waypoints_serialization(
    client: TestClient, auth_headers: tuple
):
    headers, user = auth_headers

    payload = {
        "name": "Route With Waypoints",
        "lat": 37.7749,
        "lon": -122.4194,
        "dest_lat": 37.8044,
        "dest_lon": -122.2712,
        "dest_name": "Oakland Office",
        "schedule_time": "08:00",
        "waypoints": [
            {"name": "Drop off", "lat": 37.785, "lon": -122.395, "order": 2},
            {"name": "Coffee", "lat": 37.779, "lon": -122.410, "order": 1},
        ],
    }

    # POST /config
    post_res = client.post("/config", json=payload, headers=headers)
    assert post_res.status_code == 200
    created = post_res.json()
    assert "waypoints" in created
    assert len(created["waypoints"]) == 2
    # Verify waypoints were sorted by order
    assert created["waypoints"][0]["name"] == "Coffee"
    assert created["waypoints"][0]["order"] == 1
    assert created["waypoints"][1]["name"] == "Drop off"
    assert created["waypoints"][1]["order"] == 2

    # GET /config
    get_res = client.get("/config", headers=headers)
    assert get_res.status_code == 200
    commutes = get_res.json()
    assert len(commutes) == 1
    fetched = commutes[0]
    assert len(fetched["waypoints"]) == 2
    assert fetched["waypoints"][0]["name"] == "Coffee"
    assert fetched["waypoints"][1]["name"] == "Drop off"

    # Update commute with updated waypoints
    commute_id = created["id"]
    update_payload = {
        "id": commute_id,
        "name": "Updated Route",
        "lat": 37.7749,
        "lon": -122.4194,
        "schedule_time": "08:00",
        "waypoints": [{"name": "Gym", "lat": 37.790, "lon": -122.400, "order": 1}],
    }
    update_res = client.post("/config", json=update_payload, headers=headers)
    assert update_res.status_code == 200
    updated = update_res.json()
    assert len(updated["waypoints"]) == 1
    assert updated["waypoints"][0]["name"] == "Gym"


# =====================================================================
# 5. Route Directions API Endpoint Tests
# =====================================================================


def test_api_route_directions_endpoint_success(client: TestClient):
    mock_osrm_json = {
        "code": "Ok",
        "routes": [
            {
                "distance": 1800.0,
                "duration": 240.0,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-122.41, 37.77], [-122.42, 37.78]],
                },
                "legs": [{"distance": 1800.0, "duration": 240.0, "summary": ""}],
            }
        ],
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_osrm_json

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        payload = {
            "origin": {"lat": 37.77, "lon": -122.41},
            "destination": {"lat": 37.78, "lon": -122.42},
            "waypoints": [],
        }
        res = client.post("/api/route/directions", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["total_distance"] == 1800.0
        assert data["total_duration"] == 240.0
        assert len(data["geometry"]) == 2
        assert len(data["legs"]) == 1
        assert len(data["leg_breakdowns"]) == 1
        assert data["fallback"] is False


def test_api_route_directions_endpoint_fallback(client: TestClient):
    with patch(
        "httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection failed")
    ):
        payload = {
            "origin": [37.77, -122.41],
            "destination": [37.78, -122.42],
            "waypoints": [
                {"lat": 37.775, "lon": -122.415, "order": 1, "name": "Midpoint"}
            ],
        }
        res = client.post("/api/route/directions", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["fallback"] is True
        assert data["total_distance"] > 0
        assert data["total_duration"] > 0
        assert len(data["geometry"]) == 3
        assert len(data["legs"]) == 2
        assert len(data["leg_durations"]) == 2


def test_api_route_directions_missing_coordinates(client: TestClient):
    res = client.post("/api/route/directions", json={})
    assert res.status_code == 400
    assert "Both origin and destination" in res.json()["detail"]
