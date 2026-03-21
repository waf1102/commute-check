---
phase: 3
type: execute
wave: 1
depends_on: [Phase 1, Phase 2]
files_modified: [frontend/**/*, app/main.py]
autonomous: true
requirements: [UI-STATUS, UI-FORM, TECH-FRONT, TECH-STYLE]
must_haves:
  truths:
    - "Dashboard displays status icon (🟢/🟡/🔴) and recommendation"
    - "Settings form allows updating thresholds (temp, wind, rain)"
    - "Frontend is responsive and mobile-friendly"
    - "CORS is configured in FastAPI to allow frontend requests"
  artifacts:
    - path: "frontend/"
      provides: "SvelteKit application"
    - path: "frontend/src/routes/+page.svelte"
      provides: "Dashboard overview"
    - path: "frontend/src/routes/settings/+page.svelte"
      provides: "Threshold configuration form"
---

<objective>
Build the SvelteKit frontend to provide a user-friendly dashboard for weather assessments and a settings interface for threshold management.

Purpose: To bridge the gap between the raw API and the end-user with a modern, responsive UI.
Output: A functional SvelteKit application integrated with the FastAPI backend.
</objective>

<execution_context>
@/home/will/.gemini/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phase-3/RESEARCH.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Scaffold SvelteKit Project</name>
  <files>frontend/</files>
  <action>
    - Initialize SvelteKit in the `frontend/` directory using `npm create svelte@latest`.
    - Select "Skeleton project", "TypeScript", and no extra libraries for now.
    - Install dependencies: `npm install`.
    - Configure `svelte.config.js` with `adapter-node`.
    - Create a global `src/app.css` for Vanilla CSS styling.
  </action>
  <verify>
    <automated>cd frontend && npm run build</automated>
  </verify>
  <done>SvelteKit project is scaffolded and buildable.</done>
</task>

<task type="auto">
  <name>Task 2: Configure CORS in FastAPI</name>
  <files>app/main.py</files>
  <action>
    - Import `CORSMiddleware` from `fastapi.middleware.cors`.
    - Add `CORSMiddleware` to `app` in `app/main.py`.
    - Allow `http://localhost:5173` (SvelteKit dev) and `http://localhost:3000` (SvelteKit prod).
  </action>
  <verify>
    <automated>python -c "from app.main import app; print('CORS configured')"</automated>
  </verify>
  <done>Backend correctly handles CORS requests from the frontend.</done>
</task>

<task type="auto">
  <name>Task 3: Implement Dashboard (UI-STATUS)</name>
  <files>frontend/src/routes/+page.svelte, frontend/src/routes/+page.ts</files>
  <action>
    - Create `+page.ts` to fetch assessment data from the FastAPI `/assess` endpoint.
    - Implement `+page.svelte` to display:
        - Large status icon (🟢, 🟡, 🔴) based on `status`.
        - Recommendation text.
        - Detailed weather metrics (Score, Temp, Wind, Rain Prob).
    - Use Vanilla CSS for a card-based layout.
  </action>
  <verify>
    <manual>Start both backend and frontend, then visit http://localhost:5173.</manual>
  </verify>
  <done>Dashboard displays live assessment data.</done>
</task>

<task type="auto">
  <name>Task 4: Implement Settings Form (UI-FORM)</name>
  <files>frontend/src/routes/settings/+page.svelte</files>
  <action>
    - Create a `/settings` route.
    - Implement a form to manage:
        - Minimum Temperature (Caution/No-Go).
        - Maximum Wind Speed (Caution/No-Go).
        - Rain Probability Threshold.
        - Webhook URL.
    - Use `localStorage` to persist these settings on the client side for now (Phase 4 will move this to SQLite).
  </action>
  <verify>
    <manual>Update a threshold in the UI and verify it persists on page reload.</manual>
  </verify>
  <done>Settings form allows user customization and persists locally.</done>
</task>

</tasks>

<verification>
- Dashboard correctly renders assessment results.
- Settings form successfully updates and persists thresholds.
- UI is responsive on mobile devices.
- No CORS errors between frontend and backend.
</verification>

<success_criteria>
- A functional, aesthetically pleasing UI that provides clear "Go/No-Go" decisions.
- Ready for Phase 4 (Persistence & Scheduler).
</success_criteria>
