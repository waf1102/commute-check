# Phase 1: Core Weather & Assessment Engine - Research

**Researched:** 2023-10-27
**Domain:** Weather Integration & Safety Assessment
**Confidence:** HIGH

## Summary
Phase 1 focuses on building the core logic of Commute-Check using **FastAPI** to interface with the **Open-Meteo API**. The engine will fetch hourly weather data and apply a "Water-tight" penalty algorithm to determine a Go/No-Go status for motorcycle riding.

**Primary recommendation:** Use `httpx` for asynchronous API calls to Open-Meteo and implement a class-based `AssessmentEngine` to handle the scoring logic independently of the API layer.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | ^0.100.0 | API Framework | High performance, async-first, excellent Pydantic integration. |
| httpx | ^0.24.0 | HTTP Client | Native async support for non-blocking API calls. |
| Pydantic | ^2.0.0 | Data Validation | Strict typing for API requests and Open-Meteo responses. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|--------------|
| Pytest | ^7.4.0 | Testing | Validating the penalty algorithm against edge cases. |
| Uvicorn | ^0.23.0 | ASGI Server | Running the FastAPI application. |

## Open-Meteo API Configuration

### Endpoint
`https://api.open-meteo.com/v1/forecast`

### Required Parameters (Hourly)
- `latitude`, `longitude`: User location.
- `hourly`: `temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m,weather_code`.
- `timezone`: `auto` (Critical for matching local commute times).
- `temperature_unit`: `fahrenheit` (Optional, per requirements).
- `wind_speed_unit`: `mph` (Optional, per requirements).

## Architecture Patterns

### Penalty Algorithm Implementation
The algorithm starts with 100 points and applies deductions.
**Red Flag Overrides:** Any single critical condition forces a "No-Go" status regardless of the score.

```python
class AssessmentEngine:
    def assess(self, weather: HourlyData, thresholds: UserThresholds) -> AssessmentResult:
        score = 100
        reasons = []
        status = "Go"

        # 1. Temperature Check (Apparent Temp)
        if weather.apparent_temp < thresholds.min_temp_no_go:
            return AssessmentResult(status="No-Go", reasons=["Temperature below safety threshold"])
        if weather.apparent_temp < thresholds.min_temp_caution:
            score -= 30
            reasons.append("Low temperature")

        # 2. Wind Check
        if weather.wind_speed > thresholds.max_wind_no_go:
            return AssessmentResult(status="No-Go", reasons=["Extreme wind speeds"])
        if weather.wind_speed > thresholds.max_wind_caution:
            score -= 40
            reasons.append("High wind gusts")

        # 3. Precipitation Check
        if weather.precip_prob > thresholds.rain_threshold:
            status = "No-Go"
            reasons.append("High probability of rain")

        # Final Status Mapping
        if score < 40: status = "No-Go"
        elif score < 70: status = "Caution"
        
        return AssessmentResult(status=status, score=score, reasons=reasons)
```

## JSON Output Structure
The API should return a structured assessment for the requested window:
```json
{
  "status": "Caution",
  "score": 65,
  "summary": "Low temperature and moderate wind gusts detected.",
  "details": {
    "temperature": 42.5,
    "apparent_temperature": 34.2,
    "wind_speed": 18.5,
    "precip_probability": 10,
    "weather_code": 3
  },
  "recommendation": "Wear thermal layers and be cautious of crosswinds."
}
```

## Riding Safety Thresholds (from research)
| Factor | Caution (Yellow) | No-Go (Red) | Rationale |
|--------|------------------|-------------|-----------|
| **Temp** | 40°F - 60°F | < 35°F | Ice risk and hypothermia below freezing. |
| **Wind** | 20 - 30 mph | > 35 mph | Stability issues for light/medium bikes. |
| **Rain** | Light drizzle | Heavy Rain / TS | Traction loss and visibility reduction. |

## Common Pitfalls
- **Apparent Temp:** Never use ambient temp for riding; wind chill at 60mph is significantly colder.
- **Wind Gusts:** Average wind speed often hides dangerous gusts; always check `wind_gusts_10m`.
- **WMO Codes:** Codes 95+ (Thunderstorms) and 71+ (Snow) should be immediate Red Flags.

## Validation Architecture
- **Framework:** Pytest
- **Command:** `pytest tests/`
- **Gaps:** Need a mock for Open-Meteo responses to test the `AssessmentEngine` without hitting the live API.
