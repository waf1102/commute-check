import math
from typing import List, Tuple, Optional, Union
from datetime import datetime, timedelta


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth in kilometers.
    """
    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class RoutingService:
    DEFAULT_SPEED_KMH = 50.0  # Default average commute speed in km/h

    def __init__(self, default_speed_kmh: float = 50.0):
        self.default_speed_kmh = default_speed_kmh

    def calculate_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """
        Calculate distance between two (lat, lon) coordinates in kilometers.
        """
        return haversine_distance(coord1[0], coord1[1], coord2[0], coord2[1])

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
