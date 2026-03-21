# Requirements: Commute Check (v1.1 - Reliability & Polish)

## Functional Requirements

### 1. Enhanced Reliability & Resilience
- **[RELI-RETRY] Retry Logic:** Implement exponential backoff for weather API fetches and outgoing notifications (using `tenacity`).
- **[RELI-CACHE] Weather Caching:** Cache weather responses for 15-30 minutes to reduce API load and improve dashboard speed.
- **[RELI-VAL] Input Validation:** Ensure all settings inputs (lat/lon, thresholds) are strictly validated on the backend.

### 2. Advanced Scheduling & Notifications
- **[USER-DAYS] Schedule Days:** Users must be able to select specific days of the week for notifications (e.g., Mon-Fri only).
- **[NOTIF-TEST] Webhook Test Tool:** A button in the UI to send a "test" notification immediately to the configured webhook.
- **[NOTIF-APPRISE] Expanded Notifications:** Support 50+ services (Telegram, Slack, Push) via `Apprise` integration.

### 3. UI/UX Improvements
- **[UI-LOC] Location Picker:** Replace manual lat/lon entry with a more intuitive search or map-based picker.
- **[UI-UNITS] Unit Selection:** Users can choose between Celsius and Fahrenheit for all temperature displays and thresholds.
- **[UI-MOBILE] Mobile Optimization:** Improved layout for mobile browsers (PWA-ready).

### 4. Logic & Engine Refinement
- **[ENG-REFINE] Multiple Commutes:** Basic support for multiple commute profiles (e.g., Morning and Evening) within the single-user setup.
- **[ENG-SYNC] Real-time Sync:** Settings saved in the UI should immediately update the background scheduler jobs without a server restart.

## Non-Functional Requirements
- **[NFR-ROBUST] Robustness:** The system should gracefully handle 3rd party API outages without crashing or losing configuration.
- **[NFR-CONS] Consistency:** Ensure the UI and backend are always in sync regarding the current configuration.

## Traceability

| ID | Phase | Status |
|----|-------|--------|
| RELI-RETRY | Phase 6 | Pending |
| RELI-CACHE | Phase 6 | Pending |
| USER-DAYS | Phase 7 | Pending |
| NOTIF-TEST | Phase 7 | Pending |
| NOTIF-APPRISE| Phase 7 | Pending |
| UI-LOC | Phase 8 | Pending |
| UI-UNITS | Phase 8 | Pending |
| UI-MOBILE | Phase 8 | Pending |
| ENG-REFINE | Phase 9 | Pending |
| ENG-SYNC | Phase 6 | Pending |

---

For archived v1.0 requirements, see [milestones/v1.0-REQUIREMENTS.md](./milestones/v1.0-REQUIREMENTS.md).
For future v1.2 requirements, see [milestones/v1.2-REQUIREMENTS.md](./milestones/v1.2-REQUIREMENTS.md).
