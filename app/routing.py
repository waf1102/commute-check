import logging
import math
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from pydantic import BaseModel, Field

from app.models import Waypoint

logger = logging.getLogger(__name__)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on the Earth (in meters).
    Uses the spherical law / haversine formula with mean Earth radius R = 6,371,000 meters.
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def parse_coordinate(pt: Any) -> Tuple[float, float]:
    """
    Extracts (lat, lon) from various coordinate representations:
    - (lat, lon) or [lat, lon]
    - dict with keys lat/latitude and lon/lng/longitude
    - object with lat/latitude and lon/longitude attributes
    """
    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
        lat, lon = float(pt[0]), float(pt[1])
    elif isinstance(pt, dict):
        lat = pt.get("lat") if "lat" in pt else pt.get("latitude")
        lon = (
            pt.get("lon")
            if "lon" in pt
            else (pt.get("lng") if "lng" in pt else pt.get("longitude"))
        )
        if lat is None or lon is None:
            raise ValueError(f"Coordinate dict must contain lat/lon or latitude/longitude: {pt}")
        lat, lon = float(lat), float(lon)
    elif hasattr(pt, "lat") and hasattr(pt, "lon"):
        lat, lon = float(pt.lat), float(pt.lon)
    elif hasattr(pt, "latitude") and hasattr(pt, "longitude"):
        lat, lon = float(pt.latitude), float(pt.longitude)
    else:
        raise ValueError(f"Cannot parse coordinate from {pt}")

    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"Longitude must be between -180 and 180, got {lon}")

    return lat, lon


def sort_and_parse_waypoints(waypoints: Optional[List[Any]]) -> List[Tuple[float, float, str, int]]:
    """
    Parses waypoints and sorts them by order.
    Returns list of (lat, lon, name, order).
    """
    if not waypoints:
        return []

    parsed = []
    for wp in waypoints:
        if isinstance(wp, Waypoint):
            parsed.append((wp.lat, wp.lon, wp.name, wp.order))
        elif isinstance(wp, dict):
            lat, lon = parse_coordinate(wp)
            name = str(wp.get("name", ""))
            order = int(wp.get("order", 0))
            parsed.append((lat, lon, name, order))
        else:
            lat, lon = parse_coordinate(wp)
            name = str(getattr(wp, "name", ""))
            order = int(getattr(wp, "order", 0))
            parsed.append((lat, lon, name, order))

    return sorted(parsed, key=lambda item: item[3])


class RouteLeg(BaseModel):
    distance: float  # meters
    duration: float  # seconds
    summary: Optional[str] = ""

    def __getitem__(self, item):
        return getattr(self, item)


class RouteDirectionsResponse(BaseModel):
    geometry: List[List[float]]  # GeoJSON coordinate array [[lon, lat], ...]
    total_distance: float  # meters
    total_duration: float  # seconds
    distance: Optional[float] = None
    duration: Optional[float] = None
    legs: List[RouteLeg] = Field(default_factory=list)
    leg_breakdowns: List[RouteLeg] = Field(default_factory=list)
    leg_durations: List[float] = Field(default_factory=list)
    fallback: bool = False

    def __init__(self, **data):
        if "total_distance" in data and "distance" not in data:
            data["distance"] = data["total_distance"]
        elif "distance" in data and "total_distance" not in data:
            data["total_distance"] = data["distance"]

        if "total_duration" in data and "duration" not in data:
            data["duration"] = data["total_duration"]
        elif "duration" in data and "total_duration" not in data:
            data["total_duration"] = data["duration"]

        if "legs" in data and not data.get("leg_breakdowns"):
            data["leg_breakdowns"] = data["legs"]
        elif "leg_breakdowns" in data and not data.get("legs"):
            data["legs"] = data["leg_breakdowns"]

        if "legs" in data and not data.get("leg_durations"):
            durations = []
            for l in data["legs"]:
                dur = (
                    l.duration
                    if hasattr(l, "duration")
                    else (l.get("duration", 0.0) if isinstance(l, dict) else 0.0)
                )
                durations.append(float(dur))
            data["leg_durations"] = durations

        super().__init__(**data)

    def __getitem__(self, item):
        return getattr(self, item)


class RouteDirectionsRequest(BaseModel):
    origin: Optional[Any] = None
    destination: Optional[Any] = None
    waypoints: Optional[List[Any]] = Field(default_factory=list)
    origin_lat: Optional[float] = None
    origin_lon: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lon: Optional[float] = None


def calculate_haversine_fallback(
    all_points: List[Tuple[float, float]],
    speed_kmh: float = 50.0,
) -> RouteDirectionsResponse:
    """
    Perform haversine linear interpolation across points with average speed (default 50 km/h).
    all_points is a list of (lat, lon) tuples in order: [origin, *waypoints, destination].
    """
    speed_mps = (speed_kmh * 1000.0) / 3600.0

    legs: List[RouteLeg] = []
    leg_durations: List[float] = []
    total_distance = 0.0
    total_duration = 0.0

    for i in range(len(all_points) - 1):
        lat1, lon1 = all_points[i]
        lat2, lon2 = all_points[i + 1]
        dist = haversine_distance(lat1, lon1, lat2, lon2)
        dur = dist / speed_mps if speed_mps > 0 else 0.0

        total_distance += dist
        total_duration += dur
        legs.append(RouteLeg(distance=dist, duration=dur))
        leg_durations.append(dur)

    geometry = [[lon, lat] for lat, lon in all_points]

    return RouteDirectionsResponse(
        geometry=geometry,
        total_distance=total_distance,
        total_duration=total_duration,
        legs=legs,
        leg_durations=leg_durations,
        fallback=True,
    )


class RoutingService:
    OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
    TIMEOUT = 3.0
    FALLBACK_SPEED_KMH = 50.0
    DEFAULT_SPEED_KMH = 50.0

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 3.0,
        default_speed_kmh: float = 50.0,
    ):
        self.base_url = (base_url or self.OSRM_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.default_speed_kmh = default_speed_kmh

    def calculate_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """
        Calculate distance between two (lat, lon) coordinates in kilometers.
        """
        return haversine_distance(coord1[0], coord1[1], coord2[0], coord2[1]) / 1000.0

    def calculate_segment_duration(
        self,
        coord1: Tuple[float, float],
        coord2: Tuple[float, float],
        speed_kmh: Optional[float] = None,
    ) -> float:
        """
        Calculate segment duration in minutes given coordinates and travel speed.
        """
        speed = speed_kmh if speed_kmh and speed_kmh > 0 else self.default_speed_kmh
        distance_km = self.calculate_distance(coord1, coord2)
        return (distance_km / speed) * 60.0

    def compute_segment_durations(
        self,
        coordinates: List[Tuple[float, float]],
        speed_kmh: Optional[float] = None,
    ) -> List[float]:
        """
        Compute travel duration in minutes for each segment between consecutive coordinates.
        For N coordinates, returns N - 1 durations.
        """
        if len(coordinates) < 2:
            return []
        durations = []
        for i in range(len(coordinates) - 1):
            dur = self.calculate_segment_duration(coordinates[i], coordinates[i + 1], speed_kmh)
            durations.append(round(dur, 2))
        return durations

    def compute_etas(
        self,
        departure_time: str,
        segment_durations: List[float],
    ) -> List[str]:
        """
        Given a departure time (e.g., '08:00' or ISO 8601 string) and segment durations in minutes,
        compute the estimated arrival time (ETA) at the origin and at each waypoint.
        For K segment durations, returns K + 1 formatted timestamps.
        """
        is_iso = "T" in departure_time
        has_seconds = (
            len(departure_time.split(":") if not is_iso else departure_time.split("T")[1].split(":")) > 2
        )

        try:
            if is_iso:
                base_dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
            else:
                parts = departure_time.strip().split(":")
                hour = int(parts[0])
                minute = int(parts[1])
                second = int(parts[2]) if len(parts) > 2 else 0
                now = datetime.now()
                base_dt = datetime(now.year, now.month, now.day, hour, minute, second)
        except Exception:
            base_dt = datetime(2026, 1, 1, 8, 0, 0)

        etas = []
        current_dt = base_dt

        def format_dt(dt: datetime) -> str:
            if is_iso:
                return dt.isoformat()
            if has_seconds:
                return dt.strftime("%H:%M:%S")
            return dt.strftime("%H:%M")

        etas.append(format_dt(current_dt))
        for dur in segment_durations:
            current_dt += timedelta(minutes=dur)
            etas.append(format_dt(current_dt))

        return etas

    async def get_route_directions(
        self_or_cls,
        origin: Any,
        destination: Any,
        waypoints: Optional[List[Any]] = None,
    ) -> RouteDirectionsResponse:
        """
        Calculates route directions via OSRM public API with 3.0s timeout.
        If OSRM fails or times out, falls back to haversine linear interpolation with 50 km/h average speed.
        Supports invocation as an instance method or class method.
        """
        if isinstance(self_or_cls, type):
            instance = self_or_cls()
        else:
            instance = self_or_cls

        return await instance._get_route_directions_impl(origin, destination, waypoints)

    async def _get_route_directions_impl(
        self,
        origin: Any,
        destination: Any,
        waypoints: Optional[List[Any]] = None,
    ) -> RouteDirectionsResponse:
        origin_coord = parse_coordinate(origin)
        dest_coord = parse_coordinate(destination)
        sorted_wps = sort_and_parse_waypoints(waypoints)

        all_points = [origin_coord] + [(wp[0], wp[1]) for wp in sorted_wps] + [dest_coord]

        coords_str = ";".join(f"{lon},{lat}" for lat, lon in all_points)
        url = f"{self.base_url}/route/v1/driving/{coords_str}?overview=full&geometries=geojson"

        try:
            timeout_cfg = httpx.Timeout(self.timeout, connect=self.timeout)
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                response = await client.get(url)

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    route = data["routes"][0]
                    geometry = route.get("geometry", {}).get("coordinates", [])
                    total_distance = float(route.get("distance", 0.0))
                    total_duration = float(route.get("duration", 0.0))
                    legs_raw = route.get("legs", [])

                    legs = [
                        RouteLeg(
                            distance=float(leg.get("distance", 0.0)),
                            duration=float(leg.get("duration", 0.0)),
                            summary=str(leg.get("summary", "")),
                        )
                        for leg in legs_raw
                    ]
                    leg_durations = [float(leg.get("duration", 0.0)) for leg in legs_raw]

                    return RouteDirectionsResponse(
                        geometry=geometry,
                        total_distance=total_distance,
                        total_duration=total_duration,
                        legs=legs,
                        leg_durations=leg_durations,
                        fallback=False,
                    )
                else:
                    logger.warning(f"OSRM returned non-Ok code: {data.get('code')}")
            else:
                logger.warning(f"OSRM request failed with status code {response.status_code}")
        except Exception as e:
            logger.warning(f"OSRM routing query failed or timed out: {e}")

        return calculate_haversine_fallback(all_points, speed_kmh=self.FALLBACK_SPEED_KMH)


routing_service = RoutingService()
