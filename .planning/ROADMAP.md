# Roadmap: Commute Check

## Milestones

- [v1.0 - Core MVP](./milestones/v1.0-ROADMAP.md) - Shipped 2026-03-21.
- [v1.1 - Reliability & Polish](./milestones/v1.1-ROADMAP.md) - Shipped 2026-03-21.
- **v1.2 - Multi-User & Analytics** - Current Focus.

---

## Phases (v1.2)

- [x] **Phase 10: Repository Maintenance & Setup** - Create root .gitignore and repository management rules.
- [ ] **Phase 11: Authentication & Multi-User Support** - Implement user registration, login, and data isolation.
- [ ] **Phase 12: History & Analytics** - Store assessment history and provide visualizations (e.g., Days Ridden vs Driven).
- [ ] **Phase 13: Weather Visualizations** - Enhanced graphical representations in the UI.

---

## Phase Details

### Phase 10: Repository Maintenance & Setup
**Goal**: Establish a clean repository state by ignoring environment secrets, temporary files, and local databases.
**Requirements**: [MAINT-GITIGNORE, MAINT-README]
**Plans**: 1 plan
- [x] 10-01-PLAN.md — Root .gitignore and README.md creation

### Phase 11: Authentication & Multi-User Support
**Goal**: Implement user registration, login, and data isolation.
**Requirements**: [AUTH-01, AUTH-02, AUTH-03]
**Plans**: 4 plans
- [x] 11-01-PLAN.md — User Model & Auth API
- [ ] 11-02-PLAN.md — Data Isolation & Backend Logic
- [ ] 11-03-PLAN.md — Frontend Login/Register Pages
- [ ] 11-04-PLAN.md — UI Integration & Auth State

*(Other phase details for v1.2 will be planned via `/gsd:new-milestone` / `/gsd:plan-phase`)*
