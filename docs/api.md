# Commute Check API Reference

The Commute Check backend provides a RESTful HTTP API built with FastAPI. All JSON responses use standard camelCase or snake_case models as documented below.

Base URL: `http://localhost:8000` (or `/api` when routed via frontend proxy)

---

## 1. Authentication Endpoints

### `POST /api/register`
Create a new user account.

- **Request Body**:
  ```json
  {
    "email": "rider@example.com",
    "password": "SecurePassword123"
  }
  ```
- **Responses**:
  - `200 OK`:
    ```json
    {
      "access_token": "eyJhbGciOi...",
      "token_type": "bearer"
    }
    ```
  - `400 Bad Request`: Email already registered.

### `POST /api/login`
Authenticate and obtain a JWT bearer token.

- **Request Body**: Form URL-encoded or JSON with `email` (or `username`) and `password`.
- **Response**:
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer"
  }
  ```

---

## 2. Commute Configuration & Management

Authentication required (`Authorization: Bearer <token>`).

### `GET /config` or `GET /api/config`
Retrieve all configured commutes for the authenticated user.

- **Response (`200 OK`)**: Array of `Commute` objects.
  ```json
  [
    {
      "id": 1,
      "user_id": 1,
      "name": "Daily Work Commute",
      "lat": 37.7749,
      "lon": -122.4194,
      "dest_name": "Downtown HQ",
      "dest_lat": 37.7891,
      "dest_lon": -122.4014,
      "schedule_time": "08:00",
      "return_schedule_time": "17:30",
      "days_of_week": "mon-fri",
      "min_temp_caution": 45.0,
      "min_temp_no_go": 38.0,
      "max_wind_caution": 18.0,
      "max_wind_no_go": 28.0,
      "rain_threshold": 30.0,
      "unit_system": "imperial",
      "webhook_url": "discord://..."
    }
  ]
  ```

### `POST /config` or `POST /api/config`
Create a new commute or update an existing commute configuration.

- **Request Body**: `Commute` schema (include `id` to update).
- **Response (`200 OK`)**: Created or updated `Commute` object.

### `DELETE /config/{commute_id}` or `DELETE /api/config/{commute_id}`
Delete a commute configuration and automatically cancel its scheduled background job.

- **Response (`200 OK`)**:
  ```json
  { "message": "Commute deleted successfully" }
  ```

### `POST /test-webhook` or `POST /api/test-webhook`
Send a test assessment notification to the webhook URL specified in the payload.

- **Request Body**: `CommuteCreate` payload.
- **Response (`200 OK`)**: `AssessmentResult` object.

---

## 3. Route Check & Weather Assessments

### `POST /check` or `POST /api/check`
Run a real-time safety assessment across origin and destination legs.

- **Request Body** (optional if parameters passed as query):
  ```json
  {
    "commute_id": 1,
    "lat": 37.7749,
    "lon": -122.4194,
    "dest_name": "Downtown HQ",
    "dest_lat": 37.7891,
    "dest_lon": -122.4014,
    "schedule_time": "08:00",
    "return_schedule_time": "17:30",
    "unit_system": "imperial"
  }
  ```
- **Response (`200 OK`)**:
  ```json
  {
    "overall_status": "Go",
    "overall_score": 85,
    "outbound_leg": {
      "leg_type": "outbound",
      "location_name": "Origin",
      "schedule_time": "08:00",
      "status": "Go",
      "score": 90,
      "reasons": [],
      "weather": {
        "temperature": 58.2,
        "apparent_temp": 58.0,
        "wind_speed": 7.5,
        "wind_gusts": 10.2,
        "precip_prob": 5.0,
        "weather_code": 1
      }
    },
    "return_leg": {
      "leg_type": "return",
      "location_name": "Downtown HQ",
      "schedule_time": "17:30",
      "status": "Caution",
      "score": 75,
      "reasons": ["Wind gusts above 20 mph expected"],
      "weather": {
        "temperature": 62.0,
        "apparent_temp": 61.5,
        "wind_speed": 14.0,
        "wind_gusts": 22.0,
        "precip_prob": 15.0,
        "weather_code": 2
      }
    },
    "recommendation": "Conditions acceptable for morning commute; caution advised on evening return due to wind gusts."
  }
  ```

---

## 4. Weather Visualizations & Timeline

### `GET /weather/forecast`
Retrieve hourly forecasts and configured thresholds for dashboard chart rendering.

- **Query Parameters**:
  - `commute_id` (optional `int`)
  - `unit_system` (`imperial` | `metric`, default: `imperial`)
  - `dest_lat` (optional `float`)
  - `dest_lon` (optional `float`)
- **Response (`200 OK`)**:
  ```json
  {
    "unit_system": "imperial",
    "thresholds": {
      "min_temp_caution": 45.0,
      "min_temp_no_go": 38.0,
      "max_wind_caution": 15.0,
      "max_wind_no_go": 25.0,
      "rain_threshold": 30.0
    },
    "hourly": [ ... ],
    "destination_hourly": [ ... ]
  }
  ```

---

## 5. Web Push Notifications

Authentication required (`Authorization: Bearer <token>`).

### `GET /push/vapid-public-key`
Retrieve the server's VAPID public key in Base64Url format.

### `POST /push/subscribe`
Register a browser push subscription for the logged-in user.

- **Request Body**:
  ```json
  {
    "endpoint": "https://fcm.googleapis.com/fcm/send/...",
    "keys": {
      "p256dh": "BLba4...",
      "auth": "8u3..."
    },
    "user_agent": "Mozilla/5.0..."
  }
  ```

### `DELETE /push/unsubscribe`
Remove an existing push subscription.

### `POST /push/test`
Send an instant test notification to all registered subscriptions for the authenticated user.

---

## 6. History & Analytics

Authentication required (`Authorization: Bearer <token>`).

### `GET /analytics/commute-stats/daily`
Retrieve daily aggregated riding statistics and assessment logs within a date range.

- **Query Parameters**:
  - `user_id` (`int`, required): Must match authenticated user ID.
  - `start_date` (`YYYY-MM-DD`, required): Start of report period.
  - `end_date` (`YYYY-MM-DD`, required): End of report period.
- **Response (`200 OK`)**: Array of `DailyCommuteStats` objects:
  ```json
  [
    {
      "date": "2026-10-01",
      "days_ridden": 1,
      "days_driven": 0,
      "days_total": 1,
      "avg_score": 88.5
    }
  ]
  ```

### `POST /analytics/record-decision` (also `/api/analytics/record-decision`)
Record or update whether the user rode or drove for their commute.

- **Request Body**: `DecisionRecordRequest` schema:
  ```json
  {
    "commute_id": 1,
    "decision": "riding",
    "commute_distance_km": 15.0,
    "duration_minutes": 30.0,
    "assessment_history_id": 42,
    "notes": "Clear morning ride"
  }
  ```
- **Response (`200 OK`)**: `DecisionRecordResponse` schema:
  ```json
  {
    "id": 42,
    "user_id": 1,
    "commute_id": 1,
    "commute_type": "riding",
    "timestamp": "2026-10-01T12:00:00Z",
    "leg_type": "outbound",
    "overall_status": "Go",
    "overall_score": 88.5,
    "commute_distance_km": 15.0,
    "duration_minutes": 30.0,
    "created_at": "2026-10-01T12:00:00Z"
  }
  ```

---


## 7. System Health

### `GET /health`
Liveness probe.
- **Response (`200 OK`)**: `{"status": "healthy"}`
