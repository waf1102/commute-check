# Open-Meteo API Capabilities

**Researched:** October 2023
**Overall Confidence:** HIGH

## Overview
Open-Meteo is a weather API that provides free access (for non-commercial use < 10,000 calls/day) to high-resolution weather data. It does not require an API key for its standard forecast API.

## Key Parameters for Commute-Check
To assess motorcycle riding conditions, the following hourly parameters are most relevant:

| Parameter | API Key | Description | Unit (Default) |
|-----------|---------|-------------|----------------|
| **Temperature** | `temperature_2m` | Air temperature at 2 meters above ground. | Celsius (°C) |
| **Apparent Temp** | `apparent_temperature` | "Feels like" temperature (Wind Chill/Heat Index). | Celsius (°C) |
| **Precip Probability** | `precipitation_probability` | Probability of at least 0.1mm precipitation. | Percentage (%) |
| **Precip Amount** | `precipitation` | Total liquid water (rain/snow) in previous hour. | Millimeters (mm) |
| **Wind Speed** | `wind_speed_10m` | Wind speed at 10 meters above ground. | km/h |
| **Weather Code** | `weather_code` | WMO interpretation code (see below). | Code (int) |

## WMO Weather Codes (Relevant to Riding)
| Code | Meaning | Riding Impact |
|------|---------|---------------|
| 0 | Clear sky | Ideal |
| 1, 2, 3 | Mainly clear, partly cloudy, and overcast | Safe |
| 51, 53, 55 | Drizzle: Light, moderate, and dense intensity | Caution (Visibility/Traction) |
| 61, 63, 65 | Rain: Slight, moderate and heavy intensity | Caution/Danger (Heavy rain = Danger) |
| 71, 73, 75 | Snow fall: Slight, moderate, and heavy intensity | Danger (Ice risk) |
| 80, 81, 82 | Rain showers: Slight, moderate, and violent | Caution/Danger |
| 95, 96, 99 | Thunderstorm: Slight, moderate, heavy | Danger (Wind/Rain/Lightning) |

## API Request Configuration
### Base URL
`https://api.open-meteo.com/v1/forecast`

### Recommended Query Parameters
- `latitude`, `longitude`: Target location.
- `hourly=temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m,weather_code`: Request all necessary data.
- `timezone=auto`: Ensures `time` array is in the local time of the location.
- `temperature_unit=fahrenheit` (Optional): If imperial is preferred.
- `wind_speed_unit=mph` (Optional): If imperial is preferred.
- `forecast_days=1` (or more): Limit data to necessary range.

### Example Request
```text
https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&hourly=temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m,weather_code&timezone=auto
```

## Implementation Considerations
- **No API Key:** Simplifies development and reduces secrets management.
- **Latency:** Generally very low; suitable for real-time checks.
- **Data Freshness:** Updated every few hours depending on the weather model used.
- **Rate Limits:** 10,000/day for free tier. High enough for personal or small group use.

## Sources
- [Open-Meteo Documentation](https://open-meteo.com/en/docs)
- [WMO Weather Codes](https://open-meteo.com/en/docs#weather_code)
