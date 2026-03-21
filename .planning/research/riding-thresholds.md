# Motorcycle Riding Safety Thresholds

**Researched:** October 2023
**Overall Confidence:** MEDIUM (Varies by rider skill and motorcycle type)

## Default Threshold Recommendations
Based on common safety standards, these thresholds provide a baseline for the assessment engine's "Green/Yellow/Red" system.

### 1. Temperature & Wind Chill (Apparent Temperature)
| Range | Category | Penalty Logic | Rationale |
|-------|----------|---------------|-----------|
| 60°F – 85°F (15°C – 29°C) | **Ideal (Green)** | 0% | Maximum comfort and tire grip. |
| 40°F – 60°F (4°C – 15°C) | **Caution (Yellow)** | 20-40% | Reduced tire grip, risk of numbness affecting reaction time. |
| < 35°F (< 2°C) | **Danger (Red)** | 100% | High risk of black ice and hypothermia. |
| > 95°F (> 35°C) | **Caution/Danger** | 40-60% | High risk of heat exhaustion and rider fatigue. |

### 2. Wind Speed
| Range (MPH) | Category | Penalty Logic | Rationale |
|-------------|----------|---------------|-----------|
| < 20 mph | **Safe (Green)** | 0% | Manageable for most bikes. |
| 20 – 30 mph | **Caution (Yellow)** | 50% | Challenging for light bikes (125-500cc). Gusts are problematic. |
| 30 – 50 mph | **Danger (Red)** | 80% | Significant lean required. High risk of being pushed across lanes. |
| > 50 mph | **Critical (Red)** | 100% | Unsafe for almost all motorcycles. |

### 3. Precipitation & Road Conditions
| Precipitation | Category | Penalty Logic | Rationale |
|---------------|----------|---------------|-----------|
| Drizzle/Light Rain | **Caution (Yellow)** | 30% | Reduced traction and visibility. |
| Moderate/Heavy Rain | **Danger (Red)** | 70% | Hydroplaning risk, severe visibility reduction. |
| Snow/Sleet/Hail | **Critical (Red)** | 100% | Zero traction, dangerous impact (hail). |
| First 15 mins of Rain | **Caution (Yellow)** | 50% | Road oils rise to surface (hard to detect via API). |

### 4. Visibility (Approximated via Weather Codes)
| Condition | Category | Penalty Logic | Rationale |
|-----------|----------|---------------|-----------|
| Fog | **Caution (Yellow)** | 40% | Reduced visual distance. |
| Heavy Fog/Thunderstorms | **Danger (Red)** | 100% | Extremely poor visibility and chaotic conditions. |

## Assessment Engine Logic Recommendations

### Penalty Algorithm
The "Safety Score" (0–100%) can be calculated by applying the highest single penalty OR a weighted sum.

- **Option A (Highest Penalty):** If any single factor is "Danger (Red)", the entire ride is flagged as red.
- **Option B (Compound Risk):** 40°F (Yellow) + 25mph Wind (Yellow) = Red (Compound risk).

**Recommendation:** Use a "Water-tight" approach.
1. Start at 100 points.
2. Deduct points for each factor.
3. If points < 70, status = "Caution".
4. If points < 40, status = "Danger".
5. IF ANY factor is individually in the "Danger" range, force status = "Danger" regardless of other points.

### Contextual Modifiers (User Customization)
The engine should allow users to modify thresholds based on:
- **Bike Weight:** Heavier bikes (Goldwing) handle wind better than light bikes (Ninja 400).
- **Skill Level:** Beginners need tighter thresholds.
- **Gear:** Heated gear allows lower temperature thresholds.

## Sources
- [Motorcycle Safety Foundation (MSF) Guidelines](https://www.msf-usa.org/)
- [Reddit R/Motorcycles Community Consensus](https://www.reddit.com/r/motorcycles/)
- [VikingBags Weather Riding Guide](https://www.vikingbags.com/)
- [Zenith Motorcycles Safety Advisory](https://www.zenithmotorcycles.co.uk/)
