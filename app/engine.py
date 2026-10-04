from typing import Optional, List, Tuple, Union
from .models import (
    Status,
    HourlyWeather,
    AssessmentResult,
    Commute,
    LegAssessment,
    RouteAssessmentResult,
    HazardPinpoint,
    WaypointEvaluation,
    RouteSegment,
)
from .routing import RoutingService

STATUS_SEVERITY = {
    Status.NO_GO: 3,
    Status.CAUTION: 2,
    Status.GO: 1,
}


def _worst_status(status1: Status, status2: Optional[Status] = None) -> Status:
    if status2 is None:
        return status1
    return status1 if STATUS_SEVERITY[status1] >= STATUS_SEVERITY[status2] else status2


def _combine_reasons(
    reasons1: List[str], reasons2: Optional[List[str]] = None
) -> List[str]:
    combined = list(reasons1)
    if reasons2:
        combined.extend(reasons2)
    non_clear = [r for r in combined if r != "Clear conditions"]
    if non_clear:
        seen = set()
        unique_reasons = []
        for r in non_clear:
            if r not in seen:
                seen.add(r)
                unique_reasons.append(r)
        return unique_reasons
    return ["Clear conditions"]


class AssessmentEngine:
    def __init__(self, routing_service: Optional[RoutingService] = None):
        self.routing_service = routing_service or RoutingService()

    def detect_hazard_pinpoints(
        self,
        weather: HourlyWeather,
        thresholds: Commute,
        coordinates: Tuple[float, float],
        estimated_time: str,
    ) -> List[HazardPinpoint]:
        pinpoints: List[HazardPinpoint] = []
        lat, lon = coordinates

        # 1. Temperature Check
        if weather.apparent_temp < thresholds.min_temp_no_go:
            pinpoints.append(
                HazardPinpoint(
                    lat=lat,
                    lon=lon,
                    estimated_time=estimated_time,
                    parameter="temperature",
                    value=weather.apparent_temp,
                    threshold=thresholds.min_temp_no_go,
                    warning_message="Temperature below safety threshold (ice risk)",
                    severity=Status.NO_GO,
                )
            )
        elif weather.apparent_temp < thresholds.min_temp_caution:
            pinpoints.append(
                HazardPinpoint(
                    lat=lat,
                    lon=lon,
                    estimated_time=estimated_time,
                    parameter="temperature",
                    value=weather.apparent_temp,
                    threshold=thresholds.min_temp_caution,
                    warning_message="Low temperature",
                    severity=Status.CAUTION,
                )
            )

        # 2. Wind Speed & Gusts Check
        if max(weather.wind_speed, weather.wind_gusts) > thresholds.max_wind_no_go:
            pinpoints.append(
                HazardPinpoint(
                    lat=lat,
                    lon=lon,
                    estimated_time=estimated_time,
                    parameter="wind_speed",
                    value=weather.wind_speed,
                    threshold=thresholds.max_wind_no_go,
                    warning_message="Extreme wind speeds",
                    severity=Status.NO_GO,
                )
            )
        elif max(weather.wind_speed, weather.wind_gusts) > thresholds.max_wind_caution:
            pinpoints.append(
                HazardPinpoint(
                    lat=lat,
                    lon=lon,
                    estimated_time=estimated_time,
                    parameter="wind_speed",
                    value=weather.wind_speed,
                    threshold=thresholds.max_wind_caution,
                    warning_message="High wind/gusts",
                    severity=Status.CAUTION,
                )
            )

        if weather.wind_gusts > thresholds.max_wind_no_go:
            pinpoints.append(
                HazardPinpoint(
                    lat=lat,
                    lon=lon,
                    estimated_time=estimated_time,
                    parameter="wind_gusts",
                    value=weather.wind_gusts,
                    threshold=thresholds.max_wind_no_go,
                    warning_message="Extreme wind gusts",
                    severity=Status.NO_GO,
                )
            )
        elif weather.wind_gusts > thresholds.max_wind_caution:
            pinpoints.append(
                HazardPinpoint(
                    lat=lat,
                    lon=lon,
                    estimated_time=estimated_time,
                    parameter="wind_gusts",
                    value=weather.wind_gusts,
                    threshold=thresholds.max_wind_caution,
                    warning_message="High wind/gusts",
                    severity=Status.CAUTION,
                )
            )

        # 3. Precipitation Check
        if weather.precip_prob > thresholds.rain_threshold:
            pinpoints.append(
                HazardPinpoint(
                    lat=lat,
                    lon=lon,
                    estimated_time=estimated_time,
                    parameter="precipitation_probability",
                    value=weather.precip_prob,
                    threshold=thresholds.rain_threshold,
                    warning_message="High probability of rain",
                    severity=Status.NO_GO,
                )
            )

        # 4. Dangerous Weather Code
        if weather.weather_code in {56, 57, 66, 67, 71, 73, 75, 77, 85, 86, 95, 96, 99}:
            pinpoints.append(
                HazardPinpoint(
                    lat=lat,
                    lon=lon,
                    estimated_time=estimated_time,
                    parameter="weather_code",
                    value=float(weather.weather_code),
                    threshold=71.0,
                    warning_message="Dangerous weather conditions (snow/storm)",
                    severity=Status.NO_GO,
                )
            )

        return pinpoints

    def assess(self, weather: HourlyWeather, thresholds: Commute) -> AssessmentResult:
        score = 100
        reasons = []
        status = Status.GO

        time_str = thresholds.schedule_time or "08:00"
        coords = (thresholds.lat, thresholds.lon)
        hazards = self.detect_hazard_pinpoints(weather, thresholds, coords, time_str)

        # 1. Temperature Check (Apparent Temp)
        if weather.apparent_temp < thresholds.min_temp_no_go:
            wp_eval = WaypointEvaluation(
                index=0,
                name=thresholds.name or "Origin",
                lat=thresholds.lat,
                lon=thresholds.lon,
                estimated_arrival_time=time_str,
                weather=weather,
                status=Status.NO_GO,
                score=0,
                reasons=["Temperature below safety threshold (ice risk)"],
                hazard_pinpoints=hazards,
            )
            return AssessmentResult(
                status=Status.NO_GO,
                score=0,
                reasons=["Temperature below safety threshold (ice risk)"],
                recommendation="Do not ride. High risk of ice and hypothermia.",
                details=weather,
                segments=[],
                waypoint_evaluations=[wp_eval],
                hazard_pinpoints=hazards,
            )
        if weather.apparent_temp < thresholds.min_temp_caution:
            score -= 30
            reasons.append("Low temperature")

        # 2. Wind Check
        if max(weather.wind_speed, weather.wind_gusts) > thresholds.max_wind_no_go:
            wp_eval = WaypointEvaluation(
                index=0,
                name=thresholds.name or "Origin",
                lat=thresholds.lat,
                lon=thresholds.lon,
                estimated_arrival_time=time_str,
                weather=weather,
                status=Status.NO_GO,
                score=0,
                reasons=["Extreme wind speeds"],
                hazard_pinpoints=hazards,
            )
            return AssessmentResult(
                status=Status.NO_GO,
                score=0,
                reasons=["Extreme wind speeds"],
                recommendation="Do not ride. High risk of being blown off course.",
                details=weather,
                segments=[],
                waypoint_evaluations=[wp_eval],
                hazard_pinpoints=hazards,
            )
        if max(weather.wind_speed, weather.wind_gusts) > thresholds.max_wind_caution:
            score -= 40
            reasons.append("High wind/gusts")

        # 3. Precipitation Check
        if weather.precip_prob > thresholds.rain_threshold:
            wp_eval = WaypointEvaluation(
                index=0,
                name=thresholds.name or "Origin",
                lat=thresholds.lat,
                lon=thresholds.lon,
                estimated_arrival_time=time_str,
                weather=weather,
                status=Status.NO_GO,
                score=min(score, 30),
                reasons=["High probability of rain"],
                hazard_pinpoints=hazards,
            )
            return AssessmentResult(
                status=Status.NO_GO,
                score=min(score, 30),
                reasons=["High probability of rain"],
                recommendation="Do not ride. Visibility and traction significantly reduced.",
                details=weather,
                segments=[],
                waypoint_evaluations=[wp_eval],
                hazard_pinpoints=hazards,
            )
        if weather.precip_prob > 20:  # Minor caution for some rain
            score -= 10
            reasons.append("Moderate rain probability")

        # 4. Dangerous Weather Codes (WMO)
        # 71+ is snow, 95+ is thunderstorm
        if weather.weather_code in {56, 57, 66, 67, 71, 73, 75, 77, 85, 86, 95, 96, 99}:
            wp_eval = WaypointEvaluation(
                index=0,
                name=thresholds.name or "Origin",
                lat=thresholds.lat,
                lon=thresholds.lon,
                estimated_arrival_time=time_str,
                weather=weather,
                status=Status.NO_GO,
                score=0,
                reasons=["Dangerous weather conditions (snow/storm)"],
                hazard_pinpoints=hazards,
            )
            return AssessmentResult(
                status=Status.NO_GO,
                score=0,
                reasons=["Dangerous weather conditions (snow/storm)"],
                recommendation="Do not ride. Extreme weather conditions.",
                details=weather,
                segments=[],
                waypoint_evaluations=[wp_eval],
                hazard_pinpoints=hazards,
            )

        # Final Status Mapping based on score
        if score <= 40:
            status = Status.NO_GO
        elif score <= 70:
            status = Status.CAUTION
        else:
            status = Status.GO

        recommendation = "Enjoy your ride!"
        if status == Status.CAUTION:
            recommendation = "Ride with caution. Wear appropriate gear."
        elif status == Status.NO_GO:
            recommendation = "Riding not recommended."

        wp_eval = WaypointEvaluation(
            index=0,
            name=thresholds.name or "Origin",
            lat=thresholds.lat,
            lon=thresholds.lon,
            estimated_arrival_time=time_str,
            weather=weather,
            status=status,
            score=max(0, score),
            reasons=reasons if reasons else ["Clear conditions"],
            hazard_pinpoints=hazards,
        )

        return AssessmentResult(
            status=status,
            score=max(0, score),
            reasons=reasons if reasons else ["Clear conditions"],
            recommendation=recommendation,
            details=weather,
            segments=[],
            waypoint_evaluations=[wp_eval],
            hazard_pinpoints=hazards,
        )

    def _assess_single_or_dual_weather(
        self,
        w1: Optional[HourlyWeather],
        w2: Optional[HourlyWeather],
        thresholds: Commute,
    ) -> Optional[Tuple[Status, int, List[str], HourlyWeather]]:
        if w1 is None and w2 is None:
            return None

        if w1 is not None and w2 is not None:
            res1 = self.assess(w1, thresholds)
            res2 = self.assess(w2, thresholds)
            score = min(res1.score, res2.score)
            status = _worst_status(res1.status, res2.status)
            reasons = _combine_reasons(res1.reasons, res2.reasons)
            weather = w2 if res2.score < res1.score else w1
            return status, score, reasons, weather
        elif w1 is not None:
            res1 = self.assess(w1, thresholds)
            return res1.status, res1.score, res1.reasons, w1
        else:
            res2 = self.assess(w2, thresholds)
            return res2.status, res2.score, res2.reasons, w2

    def assess_timed_route(
        self,
        coordinates: List[Tuple[float, float]],
        departure_time: str = "08:00",
        weather_data: Optional[List[Union[dict, HourlyWeather]]] = None,
        commute: Optional[Commute] = None,
        segment_durations: Optional[List[float]] = None,
        speed_kmh: Optional[float] = None,
        waypoint_names: Optional[List[str]] = None,
    ) -> RouteAssessmentResult:
        """
        Time-interpolated assessment along route waypoints.
        Computes ETA at each waypoint using RoutingService segment durations,
        samples hourly weather at ETA, scores segments, identifies hazard pinpoints,
        and computes composite route safety status reflecting the worst segment.
        """
        if not coordinates:
            raise ValueError("coordinates cannot be empty")

        if not coordinates or not weather_data or len(weather_data) != len(coordinates):
            raise ValueError("A complete forecast is required for every route location")
        thresholds = (
            commute
            if commute is not None
            else Commute(
                lat=coordinates[0][0],
                lon=coordinates[0][1],
                schedule_time=departure_time,
            )
        )

        # 1. Compute segment durations and ETAs
        if segment_durations is None:
            segment_durations = self.routing_service.compute_segment_durations(
                coordinates, speed_kmh=speed_kmh
            )
        else:
            segment_durations = list(segment_durations)

        etas = self.routing_service.compute_etas(departure_time, segment_durations)

        # 2. Sample weather and evaluate each waypoint
        from .client import parse_hourly_at_time

        waypoint_evaluations: List[WaypointEvaluation] = []
        all_hazards: List[HazardPinpoint] = []

        for i, coord in enumerate(coordinates):
            eta = etas[i]
            if weather_data and i < len(weather_data):
                item = weather_data[i]
                if isinstance(item, HourlyWeather):
                    sample_weather = item
                else:
                    sample_weather = parse_hourly_at_time(item, target_time=eta)
            else:
                raise ValueError("Forecast missing for a route location")

            wp_thresh = thresholds.model_copy(
                update={"lat": coord[0], "lon": coord[1], "schedule_time": eta}
            )
            wp_eval_res = self.assess(sample_weather, wp_thresh)
            wp_hazards = self.detect_hazard_pinpoints(
                sample_weather, thresholds, coord, eta
            )

            wp_name = (
                waypoint_names[i]
                if waypoint_names and i < len(waypoint_names)
                else (
                    thresholds.name
                    if i == 0
                    else (
                        thresholds.dest_name
                        if i == len(coordinates) - 1 and thresholds.dest_name
                        else f"Waypoint {i}"
                    )
                )
            )

            wp_eval = WaypointEvaluation(
                index=i,
                name=wp_name,
                lat=coord[0],
                lon=coord[1],
                estimated_arrival_time=eta,
                weather=sample_weather,
                status=wp_eval_res.status,
                score=wp_eval_res.score,
                reasons=wp_eval_res.reasons,
                hazard_pinpoints=wp_hazards,
            )
            for hazard in wp_hazards:
                hazard.location = wp_name
                hazard.location_name = wp_name
            waypoint_evaluations.append(wp_eval)
            for h in wp_hazards:
                if h not in all_hazards:
                    all_hazards.append(h)

        # 3. Score Segments
        segments: List[RouteSegment] = []
        for i in range(len(coordinates) - 1):
            wp_start = waypoint_evaluations[i]
            wp_end = waypoint_evaluations[i + 1]

            seg_status = _worst_status(wp_start.status, wp_end.status)
            seg_score = min(wp_start.score, wp_end.score)
            seg_reasons = _combine_reasons(wp_start.reasons, wp_end.reasons)

            seg_hazards = list(wp_start.hazard_pinpoints)
            for h in wp_end.hazard_pinpoints:
                if h not in seg_hazards:
                    seg_hazards.append(h)

            seg_dist = self.routing_service.calculate_distance(
                coordinates[i], coordinates[i + 1]
            )
            dur = segment_durations[i] if i < len(segment_durations) else 0.0
            seg_weather = (
                wp_end.weather if wp_end.score < wp_start.score else wp_start.weather
            )

            seg = RouteSegment(
                segment_index=i,
                start_lat=coordinates[i][0],
                start_lon=coordinates[i][1],
                end_lat=coordinates[i + 1][0],
                end_lon=coordinates[i + 1][1],
                start_name=wp_start.name,
                end_name=wp_end.name,
                distance_km=round(seg_dist, 2),
                duration_minutes=round(dur, 2),
                start_time=etas[i],
                end_time=etas[i + 1],
                status=seg_status,
                score=seg_score,
                reasons=seg_reasons,
                hazard_pinpoints=seg_hazards,
                weather=seg_weather,
            )
            segments.append(seg)

        # 4. Composite route safety status (reflects the worst segment)
        if segments:
            overall_status = Status.GO
            for seg in segments:
                overall_status = _worst_status(overall_status, seg.status)
            overall_score = min(seg.score for seg in segments)
        elif waypoint_evaluations:
            overall_status = waypoint_evaluations[0].status
            overall_score = waypoint_evaluations[0].score
        else:
            overall_status = Status.GO
            overall_score = 100

        recommendation = "Enjoy your ride!"
        if overall_status == Status.CAUTION:
            recommendation = "Ride with caution. Wear appropriate gear."
        elif overall_status == Status.NO_GO:
            recommendation = "Riding not recommended."

        origin_name = waypoint_evaluations[0].name if waypoint_evaluations else "Origin"
        dest_name = (
            waypoint_evaluations[-1].name if len(waypoint_evaluations) > 1 else None
        )
        location_name = f"{origin_name} -> {dest_name}" if dest_name else origin_name

        worst_weather = (
            min(waypoint_evaluations, key=lambda w: w.score).weather
            if waypoint_evaluations
            else HourlyWeather(
                temperature=70,
                apparent_temp=70,
                wind_speed=0,
                wind_gusts=0,
                precip_prob=0,
                weather_code=0,
            )
        )

        outbound_reasons = []
        for w in waypoint_evaluations:
            outbound_reasons = _combine_reasons(outbound_reasons, w.reasons)

        outbound_leg = LegAssessment(
            leg_type="outbound",
            location_name=location_name,
            schedule_time=departure_time,
            status=overall_status,
            score=overall_score,
            reasons=outbound_reasons,
            weather=worst_weather,
            segments=segments,
            waypoint_evaluations=waypoint_evaluations,
            hazard_pinpoints=all_hazards,
        )

        return RouteAssessmentResult(
            overall_status=overall_status,
            overall_score=overall_score,
            outbound_leg=outbound_leg,
            return_leg=None,
            recommendation=recommendation,
            segments=segments,
            waypoint_evaluations=waypoint_evaluations,
            hazard_pinpoints=all_hazards,
        )

    # Alias for method
    assess_route_waypoints = assess_timed_route

    def assess_route(
        self,
        origin_outbound_weather: Optional[HourlyWeather] = None,
        dest_outbound_weather: Optional[HourlyWeather] = None,
        dest_return_weather: Optional[HourlyWeather] = None,
        origin_return_weather: Optional[HourlyWeather] = None,
        commute: Optional[Commute] = None,
        *,
        waypoints: Optional[List[Tuple[float, float]]] = None,
        departure_time: Optional[str] = None,
        weather_data: Optional[List[Union[dict, HourlyWeather]]] = None,
        segment_durations: Optional[List[float]] = None,
        speed_kmh: Optional[float] = None,
        waypoint_names: Optional[List[str]] = None,
    ) -> RouteAssessmentResult:
        # If multi-waypoint parameters provided, delegate to assess_timed_route
        if waypoints is not None or (
            weather_data is not None and len(weather_data) > 2
        ):
            coords = waypoints or []
            dep_time = departure_time or (commute.schedule_time if commute else "08:00")
            return self.assess_timed_route(
                coordinates=coords,
                departure_time=dep_time,
                weather_data=weather_data,
                commute=commute,
                segment_durations=segment_durations,
                speed_kmh=speed_kmh,
                waypoint_names=waypoint_names,
            )

        thresholds = (
            commute
            if commute is not None
            else Commute(lat=0.0, lon=0.0, schedule_time="08:00")
        )
        outbound_time = (
            commute.schedule_time if commute and commute.schedule_time else "08:00"
        )

        # 1. Outbound leg evaluation
        outbound_eval = self._assess_single_or_dual_weather(
            origin_outbound_weather, dest_outbound_weather, thresholds
        )
        outbound_status, outbound_score, outbound_reasons, outbound_weather = (
            outbound_eval
        )

        origin_name = commute.name if commute and commute.name else "Origin"
        dest_name = commute.dest_name if commute and commute.dest_name else None
        outbound_location = (
            f"{origin_name} -> {dest_name}" if dest_name else origin_name
        )

        # Construct waypoint evaluations and segments for outbound leg
        outbound_waypoints: List[WaypointEvaluation] = []
        outbound_segments: List[RouteSegment] = []
        outbound_hazards: List[HazardPinpoint] = []

        if origin_outbound_weather:
            origin_hazards = self.detect_hazard_pinpoints(
                origin_outbound_weather,
                thresholds,
                (thresholds.lat, thresholds.lon),
                outbound_time,
            )
            outbound_hazards.extend(origin_hazards)
            res = self.assess(origin_outbound_weather, thresholds)
            outbound_waypoints.append(
                WaypointEvaluation(
                    index=0,
                    name=origin_name,
                    lat=thresholds.lat,
                    lon=thresholds.lon,
                    estimated_arrival_time=outbound_time,
                    weather=origin_outbound_weather,
                    status=res.status,
                    score=res.score,
                    reasons=res.reasons,
                    hazard_pinpoints=origin_hazards,
                )
            )

        if (
            dest_outbound_weather
            and thresholds.dest_lat is not None
            and thresholds.dest_lon is not None
        ):
            # Estimate destination ETA based on distance and default speed
            dist = self.routing_service.calculate_distance(
                (thresholds.lat, thresholds.lon),
                (thresholds.dest_lat, thresholds.dest_lon),
            )
            dur = self.routing_service.calculate_segment_duration(
                (thresholds.lat, thresholds.lon),
                (thresholds.dest_lat, thresholds.dest_lon),
            )
            etas = self.routing_service.compute_etas(outbound_time, [dur])
            dest_eta = etas[1] if len(etas) > 1 else outbound_time

            dest_thresh = thresholds.model_copy(
                update={
                    "lat": thresholds.dest_lat,
                    "lon": thresholds.dest_lon,
                    "schedule_time": dest_eta,
                }
            )
            dest_hazards = self.detect_hazard_pinpoints(
                dest_outbound_weather,
                dest_thresh,
                (thresholds.dest_lat, thresholds.dest_lon),
                dest_eta,
            )
            for h in dest_hazards:
                if h not in outbound_hazards:
                    outbound_hazards.append(h)

            dest_res = self.assess(dest_outbound_weather, dest_thresh)
            dest_wp = WaypointEvaluation(
                index=1,
                name=dest_name or "Destination",
                lat=thresholds.dest_lat,
                lon=thresholds.dest_lon,
                estimated_arrival_time=dest_eta,
                weather=dest_outbound_weather,
                status=dest_res.status,
                score=dest_res.score,
                reasons=dest_res.reasons,
                hazard_pinpoints=dest_hazards,
            )
            outbound_waypoints.append(dest_wp)

            seg_status = _worst_status(outbound_waypoints[0].status, dest_wp.status)
            seg_score = min(outbound_waypoints[0].score, dest_wp.score)
            seg_reasons = _combine_reasons(
                outbound_waypoints[0].reasons, dest_wp.reasons
            )
            seg_weather = (
                dest_wp.weather
                if dest_wp.score < outbound_waypoints[0].score
                else outbound_waypoints[0].weather
            )

            outbound_segments.append(
                RouteSegment(
                    segment_index=0,
                    start_lat=thresholds.lat,
                    start_lon=thresholds.lon,
                    end_lat=thresholds.dest_lat,
                    end_lon=thresholds.dest_lon,
                    start_name=origin_name,
                    end_name=dest_name or "Destination",
                    distance_km=round(dist, 2),
                    duration_minutes=round(dur, 2),
                    start_time=outbound_time,
                    end_time=dest_eta,
                    status=seg_status,
                    score=seg_score,
                    reasons=seg_reasons,
                    hazard_pinpoints=outbound_hazards,
                    weather=seg_weather,
                )
            )

        outbound_leg = LegAssessment(
            leg_type="outbound",
            location_name=outbound_location,
            schedule_time=outbound_time,
            status=outbound_status,
            score=outbound_score,
            reasons=outbound_reasons,
            weather=outbound_weather,
            segments=outbound_segments,
            waypoint_evaluations=outbound_waypoints,
            hazard_pinpoints=outbound_hazards,
        )

        # 2. Return leg evaluation (if dest_return_weather or origin_return_weather provided)
        return_leg = None
        all_segments = list(outbound_segments)
        all_waypoints = list(outbound_waypoints)
        all_hazards = list(outbound_hazards)

        return_eval = self._assess_single_or_dual_weather(
            dest_return_weather, origin_return_weather, thresholds
        )
        if return_eval is not None:
            return_status, return_score, return_reasons, return_weather = return_eval
            return_time = (
                commute.return_schedule_time
                if commute and commute.return_schedule_time
                else "17:00"
            )
            return_location = (
                f"{dest_name} -> {origin_name}" if dest_name else origin_name
            )

            return_waypoints: List[WaypointEvaluation] = []
            return_segments: List[RouteSegment] = []
            return_hazards: List[HazardPinpoint] = []

            # Return start (Dest if dual)
            ret_start_coord = (
                (thresholds.dest_lat, thresholds.dest_lon)
                if thresholds.dest_lat is not None
                else (thresholds.lat, thresholds.lon)
            )
            ret_end_coord = (thresholds.lat, thresholds.lon)

            if (
                dest_return_weather
                and thresholds.dest_lat is not None
                and thresholds.dest_lon is not None
            ):
                d_hazards = self.detect_hazard_pinpoints(
                    dest_return_weather, thresholds, ret_start_coord, return_time
                )
                return_hazards.extend(d_hazards)
                d_res = self.assess(dest_return_weather, thresholds)
                return_waypoints.append(
                    WaypointEvaluation(
                        index=0,
                        name=dest_name or "Destination",
                        lat=ret_start_coord[0],
                        lon=ret_start_coord[1],
                        estimated_arrival_time=return_time,
                        weather=dest_return_weather,
                        status=d_res.status,
                        score=d_res.score,
                        reasons=d_res.reasons,
                        hazard_pinpoints=d_hazards,
                    )
                )

            if origin_return_weather:
                dur = self.routing_service.calculate_segment_duration(
                    ret_start_coord, ret_end_coord
                )
                etas = self.routing_service.compute_etas(return_time, [dur])
                orig_eta = etas[1] if len(etas) > 1 else return_time

                o_hazards = self.detect_hazard_pinpoints(
                    origin_return_weather, thresholds, ret_end_coord, orig_eta
                )
                for h in o_hazards:
                    if h not in return_hazards:
                        return_hazards.append(h)
                o_res = self.assess(origin_return_weather, thresholds)
                return_waypoints.append(
                    WaypointEvaluation(
                        index=len(return_waypoints),
                        name=origin_name,
                        lat=ret_end_coord[0],
                        lon=ret_end_coord[1],
                        estimated_arrival_time=orig_eta,
                        weather=origin_return_weather,
                        status=o_res.status,
                        score=o_res.score,
                        reasons=o_res.reasons,
                        hazard_pinpoints=o_hazards,
                    )
                )

            if len(return_waypoints) > 1:
                dist = self.routing_service.calculate_distance(
                    ret_start_coord, ret_end_coord
                )
                dur = self.routing_service.calculate_segment_duration(
                    ret_start_coord, ret_end_coord
                )
                seg_status = _worst_status(
                    return_waypoints[0].status, return_waypoints[1].status
                )
                seg_score = min(return_waypoints[0].score, return_waypoints[1].score)
                seg_reasons = _combine_reasons(
                    return_waypoints[0].reasons, return_waypoints[1].reasons
                )
                seg_weather = (
                    return_waypoints[1].weather
                    if return_waypoints[1].score < return_waypoints[0].score
                    else return_waypoints[0].weather
                )

                return_segments.append(
                    RouteSegment(
                        segment_index=len(all_segments),
                        start_lat=ret_start_coord[0],
                        start_lon=ret_start_coord[1],
                        end_lat=ret_end_coord[0],
                        end_lon=ret_end_coord[1],
                        start_name=dest_name or "Destination",
                        end_name=origin_name,
                        distance_km=round(dist, 2),
                        duration_minutes=round(dur, 2),
                        start_time=return_time,
                        end_time=return_waypoints[1].estimated_arrival_time,
                        status=seg_status,
                        score=seg_score,
                        reasons=seg_reasons,
                        hazard_pinpoints=return_hazards,
                        weather=seg_weather,
                    )
                )

            return_leg = LegAssessment(
                leg_type="return",
                location_name=return_location,
                schedule_time=return_time,
                status=return_status,
                score=return_score,
                reasons=return_reasons,
                weather=return_weather,
                segments=return_segments,
                waypoint_evaluations=return_waypoints,
                hazard_pinpoints=return_hazards,
            )

            for h in return_hazards:
                if h not in all_hazards:
                    all_hazards.append(h)
            all_segments.extend(return_segments)
            all_waypoints.extend(return_waypoints)

        # 3. Overall status and score
        if return_leg is not None:
            overall_status = _worst_status(outbound_leg.status, return_leg.status)
            overall_score = min(outbound_leg.score, return_leg.score)
        else:
            overall_status = outbound_leg.status
            overall_score = outbound_leg.score

        # 4. Overall recommendation
        recommendation = "Enjoy your ride!"
        if overall_status == Status.CAUTION:
            recommendation = "Ride with caution. Wear appropriate gear."
        elif overall_status == Status.NO_GO:
            recommendation = "Riding not recommended."

        return RouteAssessmentResult(
            overall_status=overall_status,
            overall_score=overall_score,
            outbound_leg=outbound_leg,
            return_leg=return_leg,
            recommendation=recommendation,
            segments=all_segments,
            waypoint_evaluations=all_waypoints,
            hazard_pinpoints=all_hazards,
        )
