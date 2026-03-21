# Domain Pitfalls

**Project:** Commute-Check
**Researched:** October 2023

## Critical Pitfalls

### Pitfall 1: Ambient vs. Apparent Temp
**What goes wrong:** Using standard air temperature (`temperature_2m`) to assess rider safety in cold weather.
**Why it happens:** Most weather apps show ambient temp by default.
**Consequences:** A rider sees 40°F (Yellow) and thinks it's okay, but at 60mph the "Feels Like" is 25°F (Danger).
**Prevention:** Use `apparent_temperature` as the primary metric for the assessment engine.

### Pitfall 2: Neglecting Wind Gusts
**What goes wrong:** Only checking average wind speed.
**Consequences:** 15mph average (Green) with 40mph gusts (Danger) will surprise a rider and potentially cause an accident.
**Prevention:** Always include `wind_gusts_10m` in the Open-Meteo request and apply a heavy penalty to high gusts.

### Pitfall 3: The "Oil on Road" Rule
**What goes wrong:** Relying solely on API rain amounts to determine road slickness.
**Why it happens:** APIs can't see the road surface.
**Consequences:** Light rain after a long dry spell creates a "greasy" road (oils rising), which is more dangerous than a heavy rain that washed the road clean.
**Prevention:** Implement a "Caution" flag whenever any rain is detected after a dry period (if historical data is available) or simply penalize the first hour of any rain event more heavily.

## Moderate Pitfalls

### Pitfall 1: Coordinate Inaccuracy
**What goes wrong:** Assuming weather at "Home" is the same as weather at "Work" (e.g., city vs. mountain pass).
**Prevention:** If possible, allow users to input both Home and Work coordinates and check the *worst* weather of the two for their commute window.

### Pitfall 2: Timezone Misalignment
**What goes wrong:** Comparing UTC weather data to local commute times.
**Prevention:** Use `&timezone=auto` in Open-Meteo to ensure the `time` array matches the local clock of the rider.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| **API Integration** | Rate limiting / Caching. | Implement React Query with `staleTime: 15m`. |
| **Assessment Logic** | "Penalty Stacking" (everything makes it Red). | Use weighted penalties instead of simple additive ones. |
| **UI Design** | Information Overload. | Lead with a simple Green/Yellow/Red status; hide details behind a "Why?" button. |

## Sources
- [Motorcycle Safety Foundation (MSF) Tips](https://www.msf-usa.org/library/tips-and-notecards/)
- [Open-Meteo API Documentation](https://open-meteo.com/en/docs)
