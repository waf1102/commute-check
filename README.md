# Commute Check

Commute Check is a weather-based Go/No-Go decision engine for motorcycle riders that evaluates real-time weather forecasts against personalized risk tolerances to automate the morning "should I ride?" decision.

## 🚀 Key Features

- **Weather Assessment Engine:** Evaluates forecasts from Open-Meteo against customizable thresholds (temp, wind, rain, etc.) using a context-aware penalty algorithm for "miserable conditions."
- **Automated Scheduling:** Daily automated commute checks with support for specific days of the week.
- **Multi-Platform Notifications:** Alerts delivered via Discord, Telegram, Slack, and dozens of other platforms via [Apprise](https://github.com/caronc/apprise) integration.
- **Web Dashboard:** SvelteKit-powered UI for monitoring assessments, setting thresholds, and configuring notifications.
- **Interactive Geolocation:** Built-in location picker with multi-stage fallback (High Accuracy -> Standard) to ensure precise weather data.
- **Unit Customization:** Dynamic support for both Celsius/Fahrenheit and Metric/Imperial units.

## 🛠️ Tech Stack

- **Backend:** Python with [FastAPI](https://fastapi.tiangolo.com/)
- **Frontend:** [SvelteKit](https://kit.svelte.dev/)
- **Database:** [SQLite](https://www.sqlite.org/) with [SQLModel](https://sqlmodel.tiangolo.com/)
- **Scheduler:** [APScheduler](https://apscheduler.agronholm.info/)
- **API:** Open-Meteo for free, high-quality weather data
- **Infrastructure:** Docker and Docker Compose

## 🚦 Getting Started

### Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Quick Start

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/commute-check.git
    cd commute-check
    ```

2.  **Start the application:**
    ```bash
    docker-compose up -d
    ```

3.  **Access the services:**
    - **Dashboard:** [http://localhost:3000](http://localhost:3000)
    - **API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)

## 📈 Current Status

The project has recently reached **Milestone v1.1 - Reliability & Polish**, achieving 100% completion for its core reliability features including retries, caching, and unit selection.

**Currently focused on Milestone v1.2 - Multi-User & Analytics:**
- [x] Repository Maintenance & Root .gitignore
- [ ] Authentication & Multi-User Support
- [ ] Historical Logs & Riding Analytics
- [ ] Advanced Weather Visualizations

See the `.planning/` directory for detailed requirements and roadmaps.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
