# Commute Check

## Vision
A multi-user Go/No-Go decision engine for motorcycle riders that evaluates real-time weather forecasts against personalized risk tolerances to automate the morning "should I ride?" decision.

## Current State (v1.0 - Core MVP)
- **Shipped:** 2026-03-21
- **Core Engine:** FastAPI backend with async weather data fetching and a safety-first assessment algorithm.
- **Notification System:** Discord and generic webhook integration.
- **Web Dashboard:** SvelteKit frontend for real-time status and configuration.
- **Persistence:** SQLite/SQLModel integration with APScheduler for daily checks.
- **Infrastructure:** Fully containerized with Docker Compose.

## Next Milestone: v1.1 - Multi-User & Analytics
- Multi-user support with authentication (Phase 6).
- Historical logs and riding analytics (Phase 7).
- Enhanced weather visualizations in the UI.
- Support for multiple daily commute profiles.

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
