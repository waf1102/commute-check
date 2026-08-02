# Commute Check (Superpowers Framework)

## Vision & Core Value
A weather-based Go/No-Go decision engine for motorcycle riders that evaluates real-time weather forecasts against personalized risk tolerances to automate morning safety assessments.

## Current State (v1.2 - Multi-User & Analytics)
- **Engine**: FastAPI backend with async weather data fetching, retries (`tenacity`), and caching.
- **Authentication**: JWT-based user authentication with bcrypt password hashing and SQLModel persistence.
- **Notification System**: Apprise integration (Discord, Telegram, Slack, etc.) with multi-commute scheduling.
- **History & Analytics**: `AssessmentHistory` persistence, analytics endpoints, and Chart.js frontend visualization for commute history.
- **Frontend Dashboard**: SvelteKit dashboard with units toggle (C/F), geolocation picker, and auth management.
- **Infrastructure**: Dockerized with SQLite persistence.

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, SQLModel, Pydantic, Tenacity, Apprise
- **Frontend**: SvelteKit, TypeScript, Chart.js / Svelte-ChartJS, TailwindCSS
- **Database**: SQLite (SQLModel ORM)
- **External Services**: Open-Meteo API
- **Development Methodology**: Superpowers (Socratic Brainstorming, TDD Red-Green-Refactor, Subagent-Driven Execution, Automated Code Review)

## Core Milestones
- **v1.0 Core MVP** (Shipped 2026-03-21): Core decision engine and weather check.
- **v1.1 Reliability & Polish** (Shipped 2026-03-21): Resilience, Apprise notifications, units toggle.
- **v1.2 Multi-User & Analytics** (In Progress): Multi-user auth, assessment history, riding analytics, weather visualizations.
