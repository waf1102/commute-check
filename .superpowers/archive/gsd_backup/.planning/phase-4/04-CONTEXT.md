# Phase 4: Persistence & Scheduler (SQLite/APScheduler) - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Move from a request-response tool to an automated, persistent system. This phase delivers database storage for user settings and automated background task scheduling to trigger weather assessments daily.

</domain>

<decisions>
## Implementation Decisions

### Database Implementation
- ORM Choice: SQLModel — Native to FastAPI, merges Pydantic & SQLAlchemy
- Model Scope: Single `UserConfig` table — Simplest for MVP
- Secret Handling: Basic symmetric encryption

### Scheduler Implementation
- Scheduler Engine: APScheduler `AsyncIOScheduler` — Runs inside FastAPI lifespan
- Job Persistence: SQLite Job Store — Survives app restarts (NFR-RELI)
- Failure Handling: Log and continue — Prevents crashing the scheduler

### Claude's Discretion
None

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/models.py`: Existing Pydantic models (UserThresholds) can be adapted to SQLModel.
- `app/engine.py`: Assessment logic is ready to be called by the scheduler.
- `app/notifications.py`: Notification delivery logic is ready.

### Established Patterns
- FastAPI dependency injection and background tasks (currently used for notifications).
- Async/await for IO operations.

### Integration Points
- `app/main.py`: Lifespan events need to be added to start/stop the scheduler.
- API endpoints: Need to be updated to read/write from the database instead of defaults.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>