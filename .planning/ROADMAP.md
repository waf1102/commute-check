# Roadmap: Commute Check

## Phases

- [ ] **Phase 1: Core Weather & Assessment Engine** - Build the foundational logic using FastAPI and Open-Meteo integration.
- [ ] **Phase 2: Notification System (Webhooks)** - Implement Discord/Generic webhook formatting and delivery.
- [ ] **Phase 3: User Configuration UI (SvelteKit)** - Create the web dashboard for status overview and settings management.
- [ ] **Phase 4: Persistence & Scheduler (SQLite/APScheduler)** - Implement database storage and automated background task scheduling.
- [ ] **Phase 5: Containerization (Docker)** - Package the application for easy deployment and portability.

## Phase Details

### Phase 1: Core Weather & Assessment Engine
**Goal**: Build a functional FastAPI service that transforms raw weather data into riding recommendations.
**Depends on**: None
**Requirements**: ENG-DATA, ENG-ALGO, ENG-OUT, TECH-BACK, TECH-API, NFR-PERF
**Success Criteria**:
  1. API endpoint successfully fetches and parses hourly forecast data from Open-Meteo.
  2. Penalty algorithm correctly flags "No-Go" conditions based on input thresholds.
  3. API returns a structured JSON assessment (Go/Caution/No-Go) with human-readable justifications.
**Plans**:
- [ ] 01-01-PLAN.md — Core Engine foundation, models, logic, and API.

### Phase 2: Notification System (Webhooks)
**Goal**: Enable the system to push assessments to external messaging platforms.
**Depends on**: Phase 1
**Requirements**: NOTIF-PAY, NOTIF-CONT, USER-WEBHOOK
**Success Criteria**:
  1. System generates a formatted Discord embed with color-coded status icons (🟢, 🟡, 🔴).
  2. Notifications successfully reach a test Discord channel via webhook URL.
  3. Assessment summary in the notification matches the engine output exactly.
**Plans**: TBD

### Phase 3: User Configuration UI (SvelteKit)
**Goal**: Provide a mobile-friendly interface for users to monitor weather and manage settings.
**Depends on**: Phase 1
**Requirements**: UI-STATUS, UI-FORM, TECH-FRONT
**Success Criteria**:
  1. Dashboard displays current riding recommendation and weather summary.
  2. Users can update thresholds and location via a web form.
  3. UI handles API errors (e.g., weather service down) gracefully with user-facing alerts.
**Plans**: TBD

### Phase 4: Persistence & Scheduler (SQLite/APScheduler)
**Goal**: Move from a request-response tool to an automated, persistent system.
**Depends on**: Phase 2, Phase 3
**Requirements**: USER-LOC, USER-SCHED, USER-THRES, NOTIF-TRIG, NFR-RELI, NFR-SEC, TECH-DB, UI-HIST
**Success Criteria**:
  1. User configurations are saved to SQLite and persist across service restarts.
  2. APScheduler reliably triggers assessments at user-defined daily times.
  3. Sensitive data (webhook URLs) is stored securely in the database.
**Plans**: TBD

### Phase 5: Containerization (Docker)
**Goal**: Ensure the application is portable and easy to self-host.
**Depends on**: Phase 4
**Requirements**: NFR-PORT
**Success Criteria**:
  1. Application runs successfully within a multi-container Docker environment (Backend + Frontend).
  2. SQLite database is persisted via Docker volumes.
  3. Environment variables manage all sensitive configuration (no hardcoded secrets).
**Plans**: TBD

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Engine | 0/1 | In progress | - |
| 2. Notifications | 0/0 | Not started | - |
| 3. Web UI | 0/0 | Not started | - |
| 4. Persistence | 0/0 | Not started | - |
| 5. Docker | 0/0 | Not started | - |
