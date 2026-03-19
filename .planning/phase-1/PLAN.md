---
phase: 01-core-engine
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [requirements.txt, app/models.py, app/client.py, app/engine.py, app/main.py, tests/test_engine.py, tests/test_api.py]
autonomous: true
requirements: [ENG-DATA, ENG-ALGO, ENG-OUT, TECH-BACK, TECH-API, NFR-PERF]
must_haves:
  truths:
    - "API returns 'Go' for 70°F, 5mph wind, 0% rain"
    - "API returns 'No-Go' for 30°F (ice risk)"
    - "API returns 'No-Go' for 40mph wind (stability risk)"
    - "API returns 'No-Go' for 80% rain probability"
    - "Reasons explain why Caution or No-Go was triggered"
  artifacts:
    - path: "app/models.py"
      provides: "Pydantic models for Weather and Assessment"
    - path: "app/client.py"
      provides: "Async Open-Meteo client"
    - path: "app/engine.py"
      provides: "Penalty algorithm logic"
    - path: "app/main.py"
      provides: "FastAPI app and /assess endpoint"
  key_links:
    - from: "app/main.py"
      to: "app/client.py"
      via: "Dependency injection or instantiation"
    - from: "app/main.py"
      to: "app/engine.py"
      via: "Calling assess() with client data"
---

<objective>
Build the core weather assessment engine and expose it via a FastAPI endpoint.

Purpose: To transform raw weather data into actionable riding recommendations (Go/Caution/No-Go) using a safety-first penalty algorithm.
Output: A functional API service with 100% test coverage for safety scenarios.
</objective>

<execution_context>
@/home/will/.gemini/get-shit-done/workflows/execute-plan.md
@/home/will/.gemini/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phase-1/RESEARCH.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Foundation, Models, and Weather Client</name>
  <files>requirements.txt, app/models.py, app/client.py</files>
  <action>
    - Create `requirements.txt` with `fastapi`, `uvicorn`, `pydantic`, `httpx`, `pytest`.
    - Implement Pydantic models in `app/models.py`:
      - `HourlyWeather`: temperature, apparent_temp, wind_speed, wind_gusts, precip_prob, weather_code.
      - `WeatherResponse`: Model for Open-Meteo API response structure.
      - `AssessmentResult`: status (Enum: Go, Caution, No-Go), score (int), reasons (list[str]), recommendation (str).
    - Implement `WeatherClient` in `app/client.py` using `httpx.AsyncClient` to fetch hourly data from Open-Meteo (`https://api.open-meteo.com/v1/forecast`).
    - Use query parameters: `latitude`, `longitude`, `hourly=temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m,weather_code`, `timezone=auto`, `temperature_unit=fahrenheit`, `wind_speed_unit=mph`.
  </action>
  <verify>
    <automated>pip install -r requirements.txt && python -c "from app.models import AssessmentResult; from app.client import WeatherClient; print('Models and Client loaded')"</automated>
  </verify>
  <done>Basic project structure, models, and weather data integration are complete.</done>
</task>

<task type="auto">
  <name>Task 2: Assessment Engine Implementation</name>
  <files>app/engine.py</files>
  <action>
    - Implement the `AssessmentEngine` class in `app/engine.py`.
    - Implement the `assess(weather: HourlyWeather, thresholds: UserThresholds)` method with the penalty algorithm from RESEARCH.md:
      - Start score at 100.
      - Deduct 30 pts for temp < caution, 40 pts for wind > caution.
      - IMMEDIATE No-Go overrides for: temp < 35°F, wind > 35mph, rain prob > 50%, or dangerous WMO codes (Snow/Thunderstorms).
      - Map score to status: < 40 = No-Go, < 70 = Caution, else Go.
    - Return a populated `AssessmentResult`.
  </action>
  <verify>
    <automated>python -c "from app.engine import AssessmentEngine; from app.models import HourlyWeather; engine = AssessmentEngine(); print('Engine logic functional')"</automated>
  </verify>
  <done>Assessment logic correctly handles penalty deductions and safety overrides.</done>
</task>

<task type="auto">
  <name>Task 3: FastAPI Endpoint and Integration</name>
  <files>app/main.py</files>
  <action>
    - Create `app/main.py` and initialize a FastAPI app.
    - Implement GET `/assess` endpoint accepting `lat` and `lon` query parameters.
    - Wire the endpoint to fetch data via `WeatherClient` and process it via `AssessmentEngine`.
    - Use default thresholds from RESEARCH.md for now (will be user-configurable in Phase 4).
    - Return the structured JSON assessment.
  </action>
  <verify>
    <automated>python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 & PID=$!; sleep 2; curl -s "http://localhost:8000/assess?lat=45.52&lon=-122.67" | grep -q "status"; kill $PID</automated>
  </verify>
  <done>API successfully integrates weather fetching and assessment logic.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Comprehensive Safety Scenario Testing</name>
  <files>tests/test_engine.py, tests/test_api.py</files>
  <behavior>
    - Scenario 1: Perfect Day (75°F, 5mph wind, 0% rain) -> Go, 100 score.
    - Scenario 2: Ice Risk (30°F) -> No-Go, "Temperature below safety threshold".
    - Scenario 3: Gale Wind (40mph) -> No-Go, "Extreme wind speeds".
    - Scenario 4: High Rain (80%) -> No-Go, "High probability of rain".
    - Scenario 5: Chilly Morning (45°F) -> Caution, "Low temperature".
  </behavior>
  <action>
    - Implement unit tests in `tests/test_engine.py` for `AssessmentEngine` using `pytest`.
    - Implement integration tests in `tests/test_api.py` using `fastapi.testclient` to verify the endpoint with mocked weather data.
  </action>
  <verify>
    <automated>pytest tests/</automated>
  </verify>
  <done>All safety scenarios are verified with passing automated tests.</done>
</task>

</tasks>

<verification>
- Endpoint returns valid JSON with status and score.
- Safety overrides (Temp/Wind/Rain) correctly trigger "No-Go".
- All unit and integration tests pass.
- Async weather client handles external API calls without blocking.
</verification>

<success_criteria>
- The core engine is a reliable "Black Box" that takes coordinates and returns a safe riding decision.
- Code follows the async patterns and data models defined in RESEARCH.md.
- The project is ready for Phase 2 (Notifications).
</success_criteria>

<output>
After completion, create `.planning/phases/01-core-engine/01-01-SUMMARY.md`
</output>
