# Commute Check 🏍️

**Commute Check** is an automated, weather-based decision engine designed to help motorcyclists and weather-sensitive commuters decide if conditions are safe for riding (**Go**, **Caution**, or **No-Go**). It continuously evaluates real-time and forecasted meteorological data against personalized safety thresholds for both morning outbound and evening return commutes.

---

## 🚀 Key Features

- **Automated Weather Assessments**: Real-time evaluations powered by the Open-Meteo API.
- **Customizable Safety Thresholds**: Tailor temperature cutoffs, maximum wind speeds/gusts, and precipitation limits to your equipment and riding comfort.
- **Multi-Route & Destination Weather (v1.4)**: Independent evaluations for Outbound and Return commute legs with distinct coordinates and departure times.
- **Rich Weather Visualizations (v1.3)**: Interactive Chart.js timeline with dual Y-axes (temperature/wind speed vs. rain probability) and real-time risk gauge cards.
- **Progressive Web App (PWA) & Native Web Push (v1.3)**: Installable on iOS/Android/Desktop with offline forecast caching and direct VAPID-authenticated browser push notifications.
- **Multi-Platform Webhook Notifications**: Integration via Apprise (Discord, Slack, Email, Pushover, Telegram, etc.).
- **User Authentication & Multi-Tenancy (v1.2)**: Secure JWT-based authentication for isolated commute profiles and personal preferences.
- **Assessment History & Analytics (v1.2)**: Track riding history, decision logs, and monthly trends.
- **Geolocation Support**: Browser location auto-detection with high-accuracy and standard fallback mechanisms.
- **Dual Unit Systems**: Support for Imperial (°F, mph) and Metric (°C, km/h).

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLModel (SQLAlchemy 2.0 / Pydantic v2), APScheduler, SQLite.
- **Frontend**: SvelteKit 2, Svelte 5 (Runes), TypeScript, Chart.js, Service Worker PWA.
- **Notifications**: PyWebPush (VAPID) and Apprise.
- **Weather Source**: Open-Meteo API.
- **Infrastructure**: Docker & Docker Compose.

---

## 🏁 Getting Started

### Prerequisites

- **Python**: Python 3.11 or later
- **Node.js**: Node 20 or later (with `npm`)
- **Docker**: (Optional) Docker & Docker Compose

---

### Local Development Setup

#### 1. Backend

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be accessible at:
- **API Base**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`

#### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be accessible at: `http://localhost:5173`

---

### Running with Docker Compose

```bash
# Build and start all services in the background
docker-compose up -d

# View service logs
docker-compose logs -f
```

- **Frontend UI**: `http://localhost:3000`
- **Backend API**: `http://localhost:8000`

---

## 🧪 Testing

### Backend Tests (pytest)

```bash
# Run all unit and integration tests
pytest tests/ -v
```

### Frontend Tests (vitest & svelte-check)

```bash
cd frontend

# Run unit tests
npm test

# Run TypeScript & Svelte compiler checks
npm run check

# Verify production build
npm run build
```

---

## 📚 Documentation

Detailed documentation is available in the [`docs/`](docs/) directory:
- [Architecture & Design Guide](docs/architecture.md)
- [API Reference](docs/api.md)

---

## 📊 Project Milestones

- [x] **v1.0: Core MVP** (Weather assessment engine, basic UI, SQLite persistence, APScheduler).
- [x] **v1.1: Resilience & Notifications** (Apprise webhooks, geolocation fallbacks, retry logic, TTL caching).
- [x] **v1.2: Multi-User & Analytics** (JWT authentication, user-isolated commutes, decision history & analytics).
- [x] **v1.3: Visualizations & PWA** (Interactive Chart.js timeline, risk gauges, installable PWA, VAPID Web Push).
- [x] **v1.4: Multi-Route & Destination Weather** (Origin & destination coordinates, dual-leg outbound/return schedules, leg risk cards).

---

Built for riders, by riders. 🏍️
