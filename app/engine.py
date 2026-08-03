from typing import Optional, List, Tuple
from .models import Status, HourlyWeather, AssessmentResult, Commute, LegAssessment, RouteAssessmentResult

STATUS_SEVERITY = {
    Status.NO_GO: 3,
    Status.CAUTION: 2,
    Status.GO: 1,
}


def _worst_status(status1: Status, status2: Optional[Status] = None) -> Status:
    if status2 is None:
        return status1
    return status1 if STATUS_SEVERITY[status1] >= STATUS_SEVERITY[status2] else status2


def _combine_reasons(reasons1: List[str], reasons2: Optional[List[str]] = None) -> List[str]:
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
    def assess(self, weather: HourlyWeather, thresholds: Commute) -> AssessmentResult:
        score = 100
        reasons = []
        status = Status.GO

        # 1. Temperature Check (Apparent Temp)
        if weather.apparent_temp < thresholds.min_temp_no_go:
            return AssessmentResult(
                status=Status.NO_GO,
                score=0,
                reasons=["Temperature below safety threshold (ice risk)"],
                recommendation="Do not ride. High risk of ice and hypothermia.",
                details=weather
            )
        if weather.apparent_temp < thresholds.min_temp_caution:
            score -= 30
            reasons.append("Low temperature")

        # 2. Wind Check
        if weather.wind_speed > thresholds.max_wind_no_go:
            return AssessmentResult(
                status=Status.NO_GO,
                score=0,
                reasons=["Extreme wind speeds"],
                recommendation="Do not ride. High risk of being blown off course.",
                details=weather
            )
        if weather.wind_speed > thresholds.max_wind_caution:
            score -= 40
            reasons.append("High wind/gusts")

        # 3. Precipitation Check
        if weather.precip_prob > thresholds.rain_threshold:
            return AssessmentResult(
                status=Status.NO_GO,
                score=min(score, 30),
                reasons=["High probability of rain"],
                recommendation="Do not ride. Visibility and traction significantly reduced.",
                details=weather
            )
        if weather.precip_prob > 20: # Minor caution for some rain
            score -= 10
            reasons.append("Moderate rain probability")

        # 4. Dangerous Weather Codes (WMO)
        # 71+ is snow, 95+ is thunderstorm
        if weather.weather_code >= 71:
             return AssessmentResult(
                status=Status.NO_GO,
                score=0,
                reasons=["Dangerous weather conditions (snow/storm)"],
                recommendation="Do not ride. Extreme weather conditions.",
                details=weather
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

        return AssessmentResult(
            status=status,
            score=max(0, score),
            reasons=reasons if reasons else ["Clear conditions"],
            recommendation=recommendation,
            details=weather
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

    def assess_route(
        self,
        origin_outbound_weather: HourlyWeather,
        dest_outbound_weather: Optional[HourlyWeather] = None,
        dest_return_weather: Optional[HourlyWeather] = None,
        origin_return_weather: Optional[HourlyWeather] = None,
        commute: Optional[Commute] = None,
    ) -> RouteAssessmentResult:
        thresholds = commute if commute is not None else Commute(lat=0.0, lon=0.0, schedule_time="08:00")

        # 1. Outbound leg evaluation
        outbound_eval = self._assess_single_or_dual_weather(origin_outbound_weather, dest_outbound_weather, thresholds)
        outbound_status, outbound_score, outbound_reasons, outbound_weather = outbound_eval

        origin_name = commute.name if commute and commute.name else "Origin"
        dest_name = commute.dest_name if commute and commute.dest_name else None
        outbound_location = f"{origin_name} -> {dest_name}" if dest_name else origin_name
        outbound_time = commute.schedule_time if commute and commute.schedule_time else "08:00"

        outbound_leg = LegAssessment(
            leg_type="outbound",
            location_name=outbound_location,
            schedule_time=outbound_time,
            status=outbound_status,
            score=outbound_score,
            reasons=outbound_reasons,
            weather=outbound_weather,
        )

        # 2. Return leg evaluation (if dest_return_weather or origin_return_weather provided)
        return_leg = None
        return_eval = self._assess_single_or_dual_weather(dest_return_weather, origin_return_weather, thresholds)
        if return_eval is not None:
            return_status, return_score, return_reasons, return_weather = return_eval
            return_time = commute.return_schedule_time if commute and commute.return_schedule_time else "17:00"
            return_location = f"{dest_name} -> {origin_name}" if dest_name else origin_name

            return_leg = LegAssessment(
                leg_type="return",
                location_name=return_location,
                schedule_time=return_time,
                status=return_status,
                score=return_score,
                reasons=return_reasons,
                weather=return_weather,
            )

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
        )
