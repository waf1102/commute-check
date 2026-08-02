# Architecture Patterns

**Project:** Commute-Check
**Researched:** October 2023

## Recommended Architecture: Client-Side Assessment Engine
The app will be a Next.js application where most of the business logic (weather assessment) lives on the client side to minimize server costs and maximize responsiveness.

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **LocationProvider** | Geolocation and storage of home/work coords. | Browser API |
| **WeatherService** | Fetches data from Open-Meteo. | Open-Meteo API |
| **AssessmentEngine** | Applies thresholds (Wind, Temp, Rain) to raw data. | WeatherService |
| **CommuteDisplay** | Renders the "Traffic Light" and details. | AssessmentEngine |
| **PreferencesStore** | Stores custom thresholds and bike info (Zustand). | LocalStorage |

### Data Flow
1. **User opens app** → Geolocation fetched.
2. **WeatherService** → Requests hourly data for location.
3. **AssessmentEngine** → Merges WeatherData with PreferencesStore thresholds.
4. **Logic** → Calculates "Safety Score" for each hour.
5. **UI** → Renders Green/Yellow/Red status for specific commute times.

## Patterns to Follow

### Pattern 1: Strategy Pattern for Assessment
**What:** Encapsulate different safety checks (Wind, Temp, Rain) into independent assessment strategies.
**When:** To make the engine extensible and easy to test.
**Example:**
```typescript
interface SafetyCheck {
  assess(data: HourlyWeather): PenaltyScore;
}

const windCheck: SafetyCheck = (data) => data.wind_speed > 30 ? 80 : 0;
```

### Pattern 2: Unit-Aware Display
Always store data in a base unit (e.g., Celsius/Metric) and only convert at the UI layer to prevent calculation errors across different units.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Hardcoded Thresholds
**What:** Writing `if (temp < 40)` directly in the UI.
**Why bad:** Makes it impossible for users to customize their safety limits (e.g., a rider in Alaska vs. Florida).
**Instead:** Always pull thresholds from a configuration/preferences object.

## Scalability Considerations

| Concern | 100 users | 10K users | 1M users |
|---------|-----------|-----------|-----------|
| **API Costs** | $0 (Open-Meteo free) | Still $0 (with 10k limit) | Would require paid API tier. |
| **Server Load** | Negligible (Next.js SSR) | Moderate | High (Needs edge caching for weather). |

## Sources
- [Clean Architecture for Frontend](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Next.js App Router Architecture](https://nextjs.org/docs/app/building-your-application/rendering)
