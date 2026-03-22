# Requirements: Commute Check (v1.2 - Multi-User & Analytics)

## Repository Maintenance

### 1. Repository Hygiene
- **[MAINT-GITIGNORE] Root Gitignore:** A comprehensive .gitignore at the root level to prevent committing secrets, binaries, and local databases.
- **[MAINT-README] README.md:** A professional README.md at the project root with description, tech stack, features, and setup instructions.

## Functional Requirements

### 1. Multi-User Support
- **[AUTH-SIGN] User Registration:** Users must be able to create an account.
- **[AUTH-LOGIN] User Login:** Secure login with JWT or sessions.
- **[AUTH-OWN] Data Ownership:** Users can only view and edit their own commute configurations and history.

### 2. History & Analytics
- **[HIST-LOG] Assessment Logs:** Store daily assessment results in the database automatically.
- **[HIST-UI] Analytics Dashboard:** Visualize historical trends (e.g., "Days ridden vs. driven this month").

### 3. Enhanced UI/UX
- **[UI-VIS] Weather Visualizations:** Graphical representation of the day's weather forecast.

## Traceability

| ID | Phase | Status |
|----|-------|--------|
| MAINT-GITIGNORE | Phase 10 | Completed |
| MAINT-README | Phase 10 | Completed |
| AUTH-SIGN | Phase 11 | Pending |
| AUTH-LOGIN | Phase 11 | Pending |
| AUTH-OWN | Phase 11 | Pending |
| HIST-LOG | Phase 12 | Pending |
| HIST-UI | Phase 12 | Pending |
| UI-VIS | Phase 13 | Pending |

---

For archived v1.1 requirements, see [milestones/v1.1-REQUIREMENTS.md](./milestones/v1.1-REQUIREMENTS.md).
