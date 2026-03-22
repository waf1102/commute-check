# Commute Check

**Commute Check** is a weather-based decision engine designed to help motorcyclists (and other weather-sensitive commuters) decide if it's a "Go" or "No-Go" day for riding. It evaluates real-time weather forecasts against customizable thresholds (temperature, rain, wind) to provide an automated assessment for your daily commute.

## 🚀 Features

- **Weather-Driven Decisions**: Automated assessments using Open-Meteo API.
- **Customizable Thresholds**: Set your personal comfort levels for temperature, precipitation, and wind.
- **Automated Scheduling**: Cron-based assessments to notify you before your commute starts.
- **Multi-Platform Notifications**: Integration via Apprise (Slack, Discord, Email, Pushover, etc.).
- **Modern Dashboard**: A SvelteKit-powered UI for real-time assessments and configuration.
- **Geolocation Support**: Precision location picking with fallback mechanisms.
- **Unit Flexibility**: Support for both Metric (°C, km/h) and Imperial (°F, mph) systems.

## 🛠️ Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLModel (SQLAlchemy/Pydantic), APScheduler.
- **Frontend**: SvelteKit, TypeScript, Vanilla CSS.
- **Database**: SQLite.
- **Infrastructure**: Docker & Docker Compose.
- **Notifications**: Apprise.

## 🏁 Getting Started

### Prerequisites

- [Docker](https://www.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)

### Quick Start

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-repo/commute-check.git
    cd commute-check
    ```

2.  **Start the services**:
    ```bash
    docker-compose up -d
    ```

3.  **Access the application**:
    -   **Frontend**: `http://localhost:5173`
    -   **Backend API**: `http://localhost:8000/docs`

## 📊 Project Status

We are currently in **Milestone v1.2: Multi-User & History**.

- [x] **v1.0: MVP** (Core assessment engine, basic UI, SQLite persistence).
- [x] **v1.1: Resilience & Polish** (Retries, Caching, Units, Geolocation Fallback, Apprise Notifications).
- [ ] **v1.2: Multi-User & Analytics** (Authentication, assessment history, weather visualizations).

---

Built for riders, by riders. 🏍️
