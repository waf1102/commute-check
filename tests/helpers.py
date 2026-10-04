from datetime import datetime, timedelta, timezone


def forecast(temperature=70, wind=5, gusts=8, rain=0, code=0):
    """Nine complete days so checks never depend on today's date or the network."""
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    count = 216
    return {
        "timezone": "UTC",
        "hourly": {
            "time": [
                (start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
                for i in range(count)
            ],
            "temperature_2m": [temperature] * count,
            "apparent_temperature": [temperature] * count,
            "wind_speed_10m": [wind] * count,
            "wind_gusts_10m": [gusts] * count,
            "precipitation_probability": [rain] * count,
            "weather_code": [code] * count,
        },
    }
