# Commute Check

## Vision
A multi-user Go/No-Go decision engine for motorcycle riders that evaluates real-time weather forecasts against personalized risk tolerances to automate the morning "should I ride?" decision.

## Current State (v1.1 - Reliability & Polish)
- **Shipped:** 2026-03-21
- **Core Engine:** FastAPI backend with async weather data fetching, retries, and caching.
- **Notification System:** Apprise integration (Discord, Telegram, Slack, etc.) with day-of-week scheduling and multi-commute support.
- **Web Dashboard:** SvelteKit frontend for monitoring with dynamic units (C/F) and geolocation picker.
- **Infrastructure:** Dockerized with SQLite persistence and APScheduler.

## Next Milestone: v1.2 - Multi-User & Analytics
- Multi-user support with authentication (Phase 10).
- Historical logs and riding analytics (Phase 11).
- Advanced weather visualizations in the UI.

## Future Milestones
- Native Mobile App (Optional)

## Tech Stack
- **Backend & API:** Python with FastAPI.
- **Frontend:** SvelteKit.
- **Database:** SQLite (SQLModel).
- **External APIs:** Open-Meteo.
- **Deployment:** Docker.

## Key Features
- **User Configuration Web UI:** Dashboard for location, notification time, and weather thresholds.
- **Webhook Integration:** Discord/generic webhook support.
- **Assessment Engine:** Context-aware penalty algorithm for "miserable conditions."
- **Automated Scheduler:** Daily automated commute checks.

