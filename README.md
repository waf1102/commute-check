# Commute Check

A small weather app for deciding whether to ride to work. Save your starting place, destination, departure times and commute days. Then check one recommendation, with separate forecasts for the trip out and the trip back.

The app compares the forecast with your temperature, wind and rain limits. It checks saved stops too. It does **not** predict road surface conditions or guarantee a safe ride.

## Use it

1. Create an account.
2. Search for your town or postal code, or use your current location. Choose a destination.
3. Set your departure times and commute days, then select **Save and check weather**.
4. Before leaving, check both trips. The overall recommendation uses the worse trip. Refresh if you have left the page open.

Weather limits, intermediate stops and notifications are optional settings. Switching units converts your limits. Uncheck the return trip for a one-way commute. A return time earlier than the outbound time means the following day.

## Run locally

Requires Python 3.11+ and Node 22. Internet access is needed for place searches and real forecasts.

From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `SECRET_KEY` in `.env` to a random value (generate one with `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`). Keep it private and stable across restarts.

Start the API:

```sh
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. The frontend forwards `/api/*` to the Python server; no browser API URL or separate proxy is needed. To use a different API server, set `BACKEND_URL` when starting the frontend. API documentation is at http://localhost:8000/docs.

## Docker

After configuring `.env`:

```sh
docker compose up --build -d
```

Open **http://localhost:3000**. SQLite databases and push keys are stored in the `commute_data` volume. Back up that volume before upgrading. Do not use `docker compose down -v` unless you intend to delete the data.

For a public installation, use HTTPS and set `ORIGIN` to the public frontend URL. HTTPS (or localhost) is required for browser location and push notifications. Run **one backend process**: it owns the notification scheduler. This is a small self-hosted app, without password reset or email verification; apply access controls and rate limits at your reverse proxy if exposing it publicly.

## Verify changes

```sh
pytest -q
cd frontend
npm run check
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The browser tests start a real FastAPI server, an isolated SQLite database and the frontend gateway. Only weather, routing and place providers are replaced. They cover registration, place selection, saving, both trips, one-way trips, metric units, unavailable forecasts, sign-in after reload, unsaved edits and correcting the ride log, on desktop and phone-sized Chromium. They also check accessibility with axe. They do not verify real notification delivery or Safari/iOS behaviour.

Backend tests must not make external HTTP requests. Forecast fixtures cover multiple days; tests should not depend on today's actual weather. `npm test` runs once; `npm run test:watch` watches. Format the frontend with `npm run format`; Python files use `ruff format app tests` (Ruff 0.16.10).

## Forecast behaviour and limits

- Checks use the next scheduled commute day, or today's commute if the return trip is still ahead. Both times use the commute's saved time zone.
- Weather is sampled at the origin, destination and optional stops, interpolated at estimated arrival times. This is **not continuous coverage of every road segment**.
- Road travel times come from OSRM, without traffic or time spent at stops. If routing fails, a distance-based estimate is used and labelled on the result.
- Open-Meteo responses are cached for up to 15 minutes. “Checked” is the assessment time, not the forecast's publication time.
- A failed or incomplete weather response shows “Forecast unavailable.” Personal forecasts are not served from an offline cache.
- Notifications run at the saved departure times. Provider or network failures can prevent delivery; check the app if no notification arrives.
- Location search finds towns/cities/postal codes, not street addresses. Use current location or exact coordinates for precision.

Existing SQLite databases gain `origin_name` and `timezone` columns automatically, without replacing rows. Older commutes default to UTC because their intended time zone was never stored: review **Your commute → Time zone** after upgrading. Also review weather limits if you changed units in the old interface; the app cannot reliably infer what those old numbers meant.

See [architecture](docs/architecture.md) and [API contracts](docs/api.md) for maintenance details. Weather and geocoding are provided by [Open-Meteo](https://open-meteo.com/en/docs), with [GeoNames](https://www.geonames.org/) location data. Check provider terms before commercial deployment.
