# Commute Check API Reference (v2.0)

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

## 2. Commute Configuration & Waypoint Management

Authentication required (`Authorization: Bearer <token>`).

### `GET /config` or `GET /api/config`
Retrieve all configured commutes for the authenticated user, including intermediate route waypoints.

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
      "waypoints": [
        {
          "name": "Bay Bridge Overpass",
          "lat": 37.7983,
          "lon": -122.3778,
          "order": 1
        }
      ],
      "schedule_time": "08:00",
      "return_schedule_time": "17:30",
      "days_of_week": "mon,wed,thu",
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
Create a new commute or update an existing commute configuration with intermediate waypoints.

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

## 3. Route Directions & Polylines

### `POST /api/route/directions`
Fetch route polyline geometry, total distance, total duration, and leg breakdowns between waypoints via OSRM (with haversine fallback).

- **Request Body**:
  ```json
  {
    "origin": { "lat": 37.7749, "lon": -122.4194, "name": "Home" },
    "destination": { "lat": 37.7891, "lon": -122.4014, "name": "Office" },
    "waypoints": [
      { "lat": 37.7983, "lon": -122.3778, "name": "Bridge", "order": 1 }
    ]
  }
  ```
- **Response (`200 OK`)**:
  ```json
  {
    "coordinates": [
      [-122.4194, 37.7749],
      [-122.3778, 37.7983],
      [-122.4014, 37.7891]
    ],
    "distance_meters": 14250.0,
    "duration_seconds": 1380.0,
    "legs": [
      {
        "from_index": 0,
        "to_index": 1,
        "distance_meters": 7100.0,
        "duration_seconds": 680.0
      },
      {
        "from_index": 1,
        "to_index": 2,
        "distance_meters": 7150.0,
        "duration_seconds": 700.0
      }
    ],
    "fallback_used": false
  }
  ```

---

## 4. Route Safety Check & Hazard Assessments

### `POST /check` or `POST /api/check`
Run an along-the-route safety evaluation across origin, intermediate waypoints, and destination legs with time-interpolated weather matching.

- **Request Body**:
  ```json
  {
    "commute_id": 1,
    "lat": 37.7749,
    "lon": -122.4194,
    "dest_name": "Downtown HQ",
    "dest_lat": 37.7891,
    "dest_lon": -122.4014,
    "waypoints": [
      { "lat": 37.7983, "lon": -122.3778, "name": "Summit Pass", "order": 1 }
    ],
    "schedule_time": "08:00",
    "return_schedule_time": "17:30",
    "unit_system": "imperial"
  }
  ```
- **Response (`200 OK`)**:
  ```json
  {
    "overall_status": "Caution",
    "overall_score": 75,
    "outbound_leg": {
      "leg_type": "outbound",
      "location_name": "Origin",
      "schedule_time": "08:00",
      "status": "Caution",
      "score": 75,
      "reasons": ["Wind gusts above 25 mph expected near Summit Pass"],
      "weather": { ... },
      "segments": [
        {
          "segment_index": 0,
          "name": "Origin to Summit Pass",
          "estimated_arrival": "08:12",
          "status": "Caution",
          "reasons": ["High wind gusts (27.5 mph)"],
          "weather": { ... }
        },
        {
          "segment_index": 1,
          "name": "Summit Pass to Downtown HQ",
          "estimated_arrival": "08:25",
          "status": "Go",
          "reasons": [],
          "weather": { ... }
        }
      ],
      "hazard_pinpoints": [
        {
          "lat": 37.7983,
          "lon": -122.3778,
          "location_name": "Summit Pass",
          "estimated_time": "08:12",
          "parameter": "wind_gusts",
          "value": 27.5,
          "threshold": 25.0,
          "severity": "caution",
          "message": "High wind gusts (27.5 mph) near Summit Pass at ~08:12"
        }
      ]
    },
    "return_leg": {
      "leg_type": "return",
      "location_name": "Downtown HQ",
      "schedule_time": "17:30",
      "status": "Go",
      "score": 90,
      "reasons": [],
      "weather": { ... },
      "segments": [ ... ],
      "hazard_pinpoints": []
    },
    "recommendation": "Caution advised on morning commute: high wind gusts expected near Summit Pass at approximately 08:12."
  }
  ```

---

## 5. Weather Visualizations & Timeline

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

## 6. Web Push Notifications

Authentication required (`Authorization: Bearer <token>`).

### `GET /push/vapid-public-key`
Retrieve the server's VAPID public key in Base64Url format.

### `POST /push/subscribe`
Register a browser push subscription for the logged-in user.

### `DELETE /push/unsubscribe`
Remove an existing push subscription.

### `POST /push/test`
Send an instant test notification to all registered subscriptions for the authenticated user, supporting mid-route hazard payloads.

---

## 7. History & Analytics

Authentication required (`Authorization: Bearer <token>`).

### `GET /analytics/commute-stats/daily`
Retrieve daily aggregated riding statistics and assessment logs within a date range.

### `POST /analytics/record-decision`
Record or update whether the user rode or drove for their commute.

---

## 8. System Health

### `GET /health`
Liveness probe.
- **Response (`200 OK`)**: `{"status": "healthy"}`
