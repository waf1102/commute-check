# Feature Landscape

**Project:** Commute-Check
**Researched:** October 2023

## Table Stakes
Features users expect from a motorcycle commute checker.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Instant Weather Summary** | Core purpose. | Low | Fetch and display current/hourly data. |
| **Safety Assessment (Traffic Light)** | Visual indicator (Green/Yellow/Red). | Med | Based on researched thresholds. |
| **Hourly Forecast (Commute Times)** | Riders care about *when* they ride (AM/PM). | Med | Show specific windows (e.g., 8am and 5pm). |
| **Wind & Gust Warning** | Critical for motorcycle stability. | Low | Use Open-Meteo `wind_speed_10m`. |
| **Apparent Temp (Wind Chill)** | Riders feel wind chill, not ambient temp. | Low | Use Open-Meteo `apparent_temperature`. |

## Differentiators
Features that set Commute-Check apart.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Custom Safety Thresholds** | Personalized for bike weight/skill. | Med | Allow users to override defaults. |
| **"Next Good Window" Suggestion** | Proactive commute planning. | High | Scan next 24h for best riding window. |
| **Gear Recommendations** | "Wear your heavy jacket" based on temp. | Med | Logic-based advice for gear. |
| **Multi-Location (Home/Work)** | Commute is a route, not a point. | Med | Compare weather at both ends. |

## Anti-Features
Features to explicitly NOT build (for now).

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Turn-by-turn Navigation** | Too complex; Google/Apple Maps do it better. | Provide "Open in Google Maps" link. |
| **Social Network for Riders** | Scope creep; focus on utility. | Keep as a single-user tool. |
| **Detailed Maintenance Tracking** | Different domain; bloats the app. | Focus on weather/safety. |

## Feature Dependencies
```
Open-Meteo API Connection → Assessment Engine → UI Traffic Light
User Location → API Fetching
User Preferences → Assessment Engine Customization
```

## MVP Recommendation
Prioritize:
1. **API Integration:** Connect to Open-Meteo using browser geolocation.
2. **Assessment Engine:** Implement the default thresholds (Wind, Temp, Rain).
3. **Commute Window UI:** Show AM/PM status specifically for the next commute.

Defer: **Custom Thresholds** and **Next Good Window** until core engine is validated.

## Sources
- [Motorcycle Community Forums (Feature requests/Common pain points)](https://www.reddit.com/r/motorcycles/)
