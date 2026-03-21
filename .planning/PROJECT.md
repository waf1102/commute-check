# Commute Check

## Vision
A multi-user Go/No-Go decision engine for motorcycle riders that evaluates real-time weather forecasts against personalized risk tolerances to automate the morning "should I ride?" decision.

## Current State (v1.0 - Core MVP)
- **Shipped:** 2026-03-21
- **Core Engine:** FastAPI backend with async weather data fetching.
- **Notification System:** Discord/webhook integration.
- **Web Dashboard:** SvelteKit frontend for monitoring.
- **Infrastructure:** Dockerized with SQLite persistence.

## Next Milestone: v1.1 - Reliability & Polish
- **Goal:** Harden the system and improve the single-user experience.
- **Resilience:** Retry logic for weather API and webhooks; weather data caching.
- **Enhanced Notifications:** Webhook testing tool and scheduling by day of the week.
- **UI/UX Polish:** Improved location picker (map or search), temperature unit selection (F/C), and mobile optimization.
- **Notification Ecosystem:** Integrate `Apprise` for 50+ service support (Telegram, Slack, etc.).

## Future Milestone: v1.2 - Multi-User & Analytics
- Multi-user support with authentication (Phase 6).
- Historical logs and riding analytics (Phase 7).
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

