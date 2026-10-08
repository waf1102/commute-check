# 🏍️ Commute Check

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![SvelteKit](https://img.shields.io/badge/SvelteKit-2.0+-orange.svg)](https://kit.svelte.dev/)
[![Docker](https://img.shields.io/badge/Docker-enabled-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Commute Check** is an intelligent weather decision assistant for motorcyclists, cyclists, and daily commuters. Instead of constantly checking weather apps and guessing conditions hours ahead, Commute Check answers one simple question before you head out: **"Should I ride today?"**

It evaluates hyper-local weather forecasts against your personalized comfort thresholds across both legs of your journey—your trip to work in the morning and your ride back home in the evening.

---

## ✨ Features

- **Two-Leg Journey Analysis:** Evaluates separate forecasts for your outbound morning commute and your evening return ride.
- **Personalized Risk Thresholds:** Set your limits for temperature (min/max), rain probability and precipitation rate, wind speed, and wind gusts.
- **Route-Aware Forecasts:** Weather is sampled and interpolated along your route (origin, destination, and any intermediate stops) using OSRM routing and Open-Meteo.
- **Smart Recommendations:** Provides clear Go / Caution / No-Go recommendations based on the worst conditions encountered on each trip.
- **Push Notifications:** Optional web push notifications sent before your scheduled departure times so you know what to wear or if you need to take an alternative route.
- **PWA & Mobile Ready:** Responsive modern interface built with SvelteKit, installable as a Progressive Web App (PWA).

---

## 🚀 How It Works & How to Use

1. **Sign Up / Log In:** Create an account to store your personal routes and preferences.
2. **Configure Your Route & Times:**
   - Set your starting location, destination, and any stops along the way.
   - Choose your commute days (e.g., Monday through Friday) and set departure times for outbound and return trips.
3. **Set Your Weather Limits:** Customize your comfort zones (minimum/maximum temperature, wind tolerance, and rain limits) under **Settings**.
4. **Check Your Commute:**
   - View an immediate breakdown of both legs of your trip.
   - If conditions on either leg exceed your limits, the app highlights the risk factors (e.g., heavy rain, high wind gusts, freezing temperatures).
5. **(Optional) Enable Notifications:** Enable web push notifications to receive departure alerts directly on your device.

---

## 🛠️ Quick Start & Setup

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) or [Podman](https://podman.io/) (recommended for containerized setup), **OR**
- Python 3.11+ and Node.js 22+ (for running directly from source).

### Configuration

Copy the example environment file and configure your secret key:

```sh
cp .env.example .env
```

Open `.env` and set `SECRET_KEY` to a secure random string (generate one with `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`).

---

### Running with Containers

Choose your preferred container engine below:

<details>
<summary><strong>🐳 Docker Instructions</strong></summary>

#### Running with Docker Compose

1. **Build and start services in the background:**
   ```sh
   docker compose up --build -d
   ```

2. **Access the application:**
   - Frontend UI: [http://localhost:3000](http://localhost:3000)
   - Backend API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

3. **Useful Docker commands:**
   - View application logs:
     ```sh
     docker compose logs -f
     ```
   - Stop the application:
     ```sh
     docker compose down
     ```

> **Note:** SQLite databases and push keys are persisted in the named volume `commute_data`. Do not use `docker compose down -v` unless you want to wipe application data.

</details>

<details>
<summary><strong>🦭 Podman Instructions</strong></summary>

#### Running with Podman Compose

Commute Check works seamlessly with rootless Podman.

1. **Build and start services using Podman Compose:**
   ```sh
   podman compose up --build -d
   ```
   *(Alternatively, if using `podman-compose` CLI plugin: `podman-compose up --build -d`)*

2. **Access the application:**
   - Frontend UI: [http://localhost:3000](http://localhost:3000)
   - Backend API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

3. **Useful Podman commands:**
   - View container logs:
     ```sh
     podman compose logs -f
     ```
   - Stop containers:
     ```sh
     podman compose down
     ```

> **Tip for Rootless Podman:** Container volumes are mapped within your user namespace. Persistent data is preserved in the `commute_data` volume across restarts.

</details>

---

### Local Development Setup

If you prefer running the backend and frontend directly on your host system:

1. **Backend (FastAPI):**
   ```sh
   # Set up Python virtual environment
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

   # Start the API server
   uvicorn app.main:app --reload --port 8000
   ```

2. **Frontend (SvelteKit):**
   ```sh
   # In a separate terminal
   cd frontend
   npm ci
   npm run dev
   ```

3. **Open the app:**
   - Navigate to [http://localhost:5173](http://localhost:5173). The frontend automatically proxies `/api/*` requests to `http://localhost:8000`.

---

## 🧪 Testing & Verification

For developers contributing to Commute Check:

- **Run backend tests:**
  ```sh
  pytest -q
  ```
- **Run frontend checks and unit tests:**
  ```sh
  cd frontend
  npm run check
  npm test
  ```
- **Run end-to-end browser tests:**
  ```sh
  cd frontend
  npx playwright install chromium
  npm run test:e2e
  ```

---

## 📚 Architecture & Attribution

- **Architecture Details:** See [docs/architecture.md](docs/architecture.md) for architectural design and data flow.
- **API Reference:** See [docs/api.md](docs/api.md) for endpoint specifications.
- **Weather Data:** Provided by [Open-Meteo](https://open-meteo.com/en/docs).
- **Routing & Geocoding:** Provided by [OSRM](http://project-osrm.org/) and [GeoNames](https://www.geonames.org/).

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
