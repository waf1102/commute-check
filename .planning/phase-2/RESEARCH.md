# Research: Phase 2 Notification System (Webhooks)

## Goal
Implement a robust notification system that can send riding assessments to Discord and generic webhooks.

## Requirements Mapping
- **[NOTIF-PAY] Payload:** Structured JSON for Discord (Embeds) and a simple flat JSON for generic webhooks.
- **[NOTIF-CONT] Content:** 
  - Status Indicator (🟢 Go, 🟡 Caution, 🔴 No-Go).
  - Score (0-100).
  - Reasons for the assessment.
  - Recommendation text.
  - Current weather details (temp, wind, rain).

## Technical Research

### 1. Discord Webhooks (Embeds)
Discord supports rich embeds via a JSON payload.

**Key Payload Structure:**
```json
{
  "embeds": [
    {
      "title": "🏍️ Commute Check: [Status]",
      "description": "[Recommendation]",
      "color": [Decimal Color Code],
      "fields": [
        { "name": "Score", "value": "85/100", "inline": true },
        { "name": "Temperature", "value": "55°F", "inline": true },
        { "name": "Wind", "value": "12 mph", "inline": true },
        { "name": "Rain Prob", "value": "10%", "inline": true },
        { "name": "Reasons", "value": "• Low temperature\n• Clear skies" }
      ],
      "timestamp": "2026-03-20T08:00:00Z"
    }
  ]
}
```

**Color Mappings (Decimal):**
- **Go (Green):** `3066993` (#2ecc71)
- **Caution (Yellow):** `16776960` (#ffff00)
- **No-Go (Red):** `15158332` (#e74c3c)

### 2. Generic Webhooks
For non-Discord integrations, we will provide a standard JSON payload that mirrors our internal `AssessmentResult` model.

**Payload:**
```json
{
  "status": "Go",
  "score": 100,
  "reasons": ["Clear conditions"],
  "recommendation": "Enjoy your ride!",
  "details": {
    "temperature": 75.0,
    "wind_speed": 5.0,
    "precip_prob": 0.0
  }
}
```

### 3. Implementation Strategy (FastAPI)
- Use `httpx.AsyncClient` for non-blocking webhook delivery.
- Create a `NotificationService` in `app/notifications.py`.
- Support both Discord and Generic formats based on the webhook URL (detect `discord.com/api/webhooks` or similar).

## Pitfalls & Considerations
- **Rate Limiting:** Discord has rate limits. Since this is a once-per-day commute check, this shouldn't be an issue for individual users.
- **Error Handling:** If the webhook fails, the system should log the error but not crash the main process.
- **Security:** In Phase 4, webhooks will be stored in a database. For Phase 2, we will test with an environment variable `TEST_WEBHOOK_URL`.

## Success Criteria
1. `NotificationService` correctly formats the payload based on the assessment result.
2. The service successfully sends a Discord embed to a test channel.
3. The service successfully sends a JSON payload to a generic endpoint (e.g., RequestBin or a mock server).
