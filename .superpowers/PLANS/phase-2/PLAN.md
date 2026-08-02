---
phase: 2
type: execute
wave: 1
depends_on: [Phase 1]
files_modified: [app/notifications.py, app/main.py, tests/test_notifications.py]
autonomous: true
requirements: [NOTIF-PAY, NOTIF-CONT, USER-WEBHOOK]
must_haves:
  truths:
    - "Service detects Discord URLs and formats a rich embed"
    - "Service sends flat JSON for generic webhook URLs"
    - "Embed colors match status: Go=Green, Caution=Yellow, No-Go=Red"
    - "Failed webhook requests are handled gracefully (logged, not crashed)"
  artifacts:
    - path: "app/notifications.py"
      provides: "NotificationService for webhook delivery"
    - path: "tests/test_notifications.py"
      provides: "Unit tests for payload formatting and delivery mocking"
---

<objective>
Implement the Notification System to deliver riding assessments via Discord and generic webhooks.

Purpose: To push the assessment result to the user's preferred platform (e.g., Discord) at the right time.
Output: A `NotificationService` that handles payload formatting and delivery.
</objective>

<execution_context>
@/home/will/.gemini/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phase-2/RESEARCH.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement NotificationService and Formatting Logic</name>
  <files>app/notifications.py</files>
  <action>
    - Create `app/notifications.py`.
    - Implement `NotificationService` class.
    - Implement `_format_discord_payload(assessment: AssessmentResult)`:
        - Use rich embeds as researched in RESEARCH.md.
        - Map statuses to decimal color codes: Green (3066993), Yellow (16776960), Red (15158332).
        - Include fields for Score, Temp, Wind, and Rain Prob.
    - Implement `_format_generic_payload(assessment: AssessmentResult)`:
        - Return the assessment result as a standard JSON dictionary.
    - Implement `send_notification(webhook_url: str, assessment: AssessmentResult)`:
        - Detect Discord URLs (`discord.com/api/webhooks`).
        - Use `httpx.AsyncClient` to POST the correctly formatted payload.
        - Handle HTTP errors gracefully.
  </action>
  <verify>
    <automated>python -c "from app.notifications import NotificationService; from app.models import Status, AssessmentResult, HourlyWeather; service = NotificationService(); print('Service loaded')"</automated>
  </verify>
  <done>NotificationService is implemented with Discord and Generic payload support.</done>
</task>

<task type="auto">
  <name>Task 2: Update API to optionally trigger notifications</name>
  <files>app/main.py</files>
  <action>
    - Update `app/main.py` to instantiate `NotificationService`.
    - Add an optional `webhook_url` query parameter to the `/assess` endpoint.
    - If `webhook_url` is provided, call `service.send_notification()` asynchronously.
  </action>
  <verify>
    <automated>PYTHONPATH=. pytest tests/test_api.py</automated>
  </verify>
  <done>API now supports an optional webhook trigger.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Notification System Testing</name>
  <files>tests/test_notifications.py</files>
  <behavior>
    - Mock `httpx.AsyncClient.post` to verify correct payloads are sent.
    - Test Discord URL detection.
    - Test payload formatting for all three statuses (Go, Caution, No-Go).
    - Test error handling for failed webhook requests.
  </behavior>
  <action>
    - Implement unit tests for `NotificationService`.
  </action>
  <verify>
    <automated>PYTHONPATH=. pytest tests/test_notifications.py</automated>
  </verify>
  <done>All notification scenarios are verified with mocked network calls.</done>
</task>

</tasks>

<verification>
- Discord payloads contain rich embeds with correct color codes.
- Generic payloads contain standard JSON.
- `NotificationService` is robust against network failures.
</verification>

<success_criteria>
- The system can reliably notify users on Discord and other platforms.
- Code is ready for Phase 3 (Web UI Dashboard).
</success_criteria>
