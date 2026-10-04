# Architecture

Commute Check has two processes: a SvelteKit Node server and a FastAPI server with SQLite. Keep one backend process so scheduled notifications run once.

## Request path

The browser calls `/api/*` on the frontend origin. `frontend/src/hooks.server.ts` forwards requests to `BACKEND_URL` (default `http://127.0.0.1:8000`). Docker uses `http://backend:8000`. The gateway forwards authentication, returns upstream status codes and disables caching of API responses. It works in development and in the production Node build.

Authentication uses a bearer token in browser local storage. Pages render on the client (`+layout.ts`) so server rendering cannot race local authentication. Registration and form-encoded login both return tokens. A 401 clears the local token. Password hashes never appear in registration responses. This deliberately keeps the existing authentication architecture; it does not provide token revocation, password reset or email verification.

## Forecast calculation

`app/assessment.py` is the shared path for `/api/check` and scheduled notifications:

1. Find the relevant scheduled day in the commute's IANA time zone. Include an overnight return still ahead of the user.
2. Build coordinates from the origin, ordered stops and destination. Fetch complete forecasts concurrently, deduplicating repeated coordinates.
3. Obtain road travel durations from `app/routing.py`. Reverse the points and request separate return directions, since road travel times can differ by direction.
4. Carry full dated, timezone-aware departure and arrival timestamps into the engine. `app/client.py` matches these to each location's local forecast and interpolates numeric values between hours. Missing fields and out-of-range times raise errors.
5. Evaluate each point with the saved limits. Gusts affect the verdict. Freezing rain, snow and thunderstorms trigger avoidance; ordinary rain showers are not misclassified as snow.
6. Use the worst checked point for each leg, and the worse leg for the overall result. Return the assessment date, time zone, check time and whether travel times were estimated.

The provider cache holds raw forecasts for 15 minutes. Weather availability and routing availability have different policies: missing weather aborts the assessment; missing routing permits a clearly labelled distance-based travel estimate. Route geometry is not treated as proof that weather has been measured along every road.

The older `/assess`, route-directions and hourly-forecast APIs remain available for compatibility. New UI work should use the saved-commute `/check` contract.

## Persistence and scheduling

- `CommuteCreate` / `CommuteConfig` validate API input. The SQLModel table is not used as an unrestricted request body. Owner IDs always come from authentication.
- A blank return time is stored as SQL NULL without falling back to 17:00.
- `create_db_and_tables` makes additive, repeatable upgrades for origin names and time zones. It does not backfill a guessed local time zone.
- Each commute has outbound and optional return APScheduler jobs. Cron triggers use the saved time zone; overnight returns shift the chosen weekdays by one day. Save replaces jobs, delete removes them.
- Assessment history is recorded separately from ride/drive decisions. Re-recording a daily decision corrects it instead of adding another ride. Daily aggregation uses Python rather than a dataframe library.
- VAPID keys are loaded from environment variables or persisted to `VAPID_KEY_FILE` (default `vapid-keys.json`, mode 0600). Preserve the key pair and subscription database together across restarts.

## Frontend structure

- `routes/+page.svelte`: welcome/setup states, selected commute, loading/retry states and the two-leg forecast. Request generations prevent late responses from replacing a different commute's forecast.
- `routes/settings/+page.svelte`: places, times and preferences, with optional advanced controls. Unsaved edits have navigation protection. Saving opens the saved commute's forecast.
- `lib/components/PlacePicker.svelte`: explicit place search, geolocation and a coordinate fallback. Network and permission failures remain visible.
- `lib/commute.ts`: typed settings, consistent defaults, unit conversion and display labels.
- `lib/api.ts`: typed requests and a single error-handling boundary.
- `routes/history/+page.svelte`: optional daily ride log and a readable table.
- `service-worker.ts`: static assets and push events. API responses are never cached across users or presented as fresh while offline.

The UI intentionally omits numeric “safety” gauges and decorative charts. Those numbers do not make road safety measurable. The code no longer ships Chart.js or Leaflet to display the primary weather check.

## Tests

`tests/test_regressions.py` targets auth contracts, invalid configuration, ownership, saved stops and thresholds, missing weather, units/time semantics, one-way trips, daily decisions, key persistence and additive upgrades. Existing engine, routing, push and API coverage remains.

Vitest covers UI state transitions, failed saves, unit conversion and stale response protection. Playwright runs against `tests/browser_server.py`, which replaces external providers but retains the real HTTP, auth, validation and SQLite layers. Its database is temporary and isolated from personal data. Desktop and phone-sized Chromium tests include axe checks and retain traces on failure.
