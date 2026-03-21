from .models import Status, HourlyWeather, AssessmentResult, Commute

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
