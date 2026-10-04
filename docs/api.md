# API contracts

The browser-facing prefix is `/api`. Interactive request and response schemas are at the backend's `/docs`. Most old unprefixed routes remain aliases; new integrations should use `/api`.

Except for registration, login, place search, quick assessment and route directions, supply:

```http
Authorization: Bearer <access_token>
```

Errors use FastAPI's `detail` field: a message for operational errors, or a list of validation problems for HTTP 422. A weather failure is HTTP 503, never an invented “Go” result.

## Accounts

`POST /api/register` takes JSON `{ "email": "rider@example.com", "password": "at-least-8-characters" }`. Emails are trimmed and lowercased. Passwords must have at least 8 characters and at most 72 UTF-8 bytes (bcrypt's limit). Returns `access_token`, `token_type`, `message`, and public user `id`/`email`.

`POST /api/login` accepts form encoding (used by the frontend) or JSON with `email`/`username` and `password`:

```sh
curl -X POST http://localhost:8000/api/login \
  --data-urlencode 'username=rider@example.com' \
  --data-urlencode 'password=your-password'
```

Returns `access_token`, `token_type: "bearer"`, and public user `id`/`email`. `GET /api/auth/me` (also `/api/me`) returns the authenticated user's public profile. Tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30). There is no refresh endpoint.

## Saved commutes

| Method | Path | Behaviour |
| --- | --- | --- |
| GET | `/api/config` | List the authenticated user's commutes |
| POST | `/api/config` | Create, or update the owned commute identified by `id` |
| GET / PUT | `/api/config/{id}` | Read / update an owned commute |
| DELETE | `/api/config/{id}` | Delete the owned commute and its scheduled jobs |
| GET / POST | `/api/commutes` | List / create aliases |
| PUT / DELETE | `/api/commutes/{id}` | Update / delete aliases |

The singular `/api/commute` and unprefixed CRUD paths remain compatibility aliases.

Example settings:

```json
{
  "name": "Work ride",
  "origin_name": "Home",
  "lat": 42.36,
  "lon": -71.06,
  "dest_name": "Office",
  "dest_lat": 42.37,
  "dest_lon": -71.12,
  "timezone": "America/New_York",
  "schedule_time": "08:00",
  "return_schedule_time": "17:00",
  "days_of_week": "mon,tue,wed,thu,fri",
  "unit_system": "imperial",
  "min_temp_caution": 45,
  "min_temp_no_go": 38,
  "max_wind_caution": 15,
  "max_wind_no_go": 25,
  "rain_threshold": 30,
  "waypoints": [],
  "webhook_url": null
}
```

Times use `HH:MM` in the saved time zone. Set `return_schedule_time` to **null** for one-way trips. Coordinates must be valid pairs. Days accept weekday names, ranges or `*`. A stop has `name`, `lat`, `lon`, and `order`; at most eight intermediate stops are accepted. Limits must be finite and ordered: colder avoidance temperature, higher avoidance wind speed. Rain is 0–100 percent. Send limits in the selected unit system; the frontend converts values when switching units.

`POST /api/config` validates a complete settings document. Include the returned `id` when editing; a nonexistent or unowned ID returns 404. `user_id` from the request never changes ownership.

## Check a saved commute

```http
POST /api/check?commute_id=123&save_history=true
Authorization: Bearer <access_token>
```

The frontend sends `commute_id` as a query parameter; a JSON `{ "commute_id": 123 }` body is also accepted. Saved checks require authentication and ownership. The saved settings, including units, thresholds and stops, are loaded on the server. An ad hoc JSON settings body with coordinates can be checked without an account. GET is retained as an alias.

The response contains `overall_status` (`Go`, `Caution`, `No-Go`), `recommendation`, `outbound_leg`, optional `return_leg`, `assessment_date`, `checked_at`, `timezone` and `routing_estimated`. Each leg includes dated departure time, status, reasons, representative weather, checked waypoints, segments and hazard details. `overall_score` and legacy duplicate fields remain for API compatibility; the UI does not present a numeric score as a safety guarantee.

## Supporting endpoints

- `GET /api/places?q=Boston`: up to six named town/city/postal-code matches, each with `name`, `lat`, `lon` and `timezone`. Search failure returns 503; no match is `[]`.
- `GET /api/weather/forecast?commute_id=123`: hourly forecast data for an owned commute. Retained for integrations; the main UI uses `/check`.
- `POST /api/route/directions`: origin, destination and optional waypoints; returns geometry, durations and a `fallback` flag.
- `GET` or `POST /api/assess`: legacy quick weather assessment without saved-commute scheduling. Prefer `/check` for normal use.
- `POST /api/test-webhook`: authenticated settings body with `webhook_url`; reports delivery failures instead of silently claiming success.
- `GET /api/push/vapid-public-key`; `POST /api/push/subscribe`; `DELETE /api/push/unsubscribe`; `POST /api/push/test`: browser notification lifecycle. Subscription includes `endpoint` and `keys` (`p256dh`, `auth`).
- `GET /api/push/subscriptions`: the authenticated user's subscriptions.
- `POST /api/analytics/record-decision`: `{ "decision": "riding", "date": "2026-10-04" }` (or `driving`). The browser supplies its local calendar date. Repeated daily submissions correct the prior decision. An optional `commute_id` must belong to the user.
- `GET /api/analytics/commute-stats/daily?start_date=2026-10-01&end_date=2026-10-31`: daily records for the authenticated user; no user ID is needed. Date ranges are limited to one year. A legacy explicit `user_id` is accepted only if it matches the authenticated user.
- `GET /health`: backend liveness check (not a provider connectivity check).
