import apprise
import logging
import json
from typing import Dict, Any, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from pywebpush import webpush, WebPushException
from sqlmodel import Session, select

from .models import Status, AssessmentResult, User
from .push.models import PushSubscription
from .push.vapid import get_or_create_vapid_keys

logger = logging.getLogger(__name__)

def dispatch_web_push_notification(
    user_id: int,
    title: str,
    body: str,
    session: Session,
    url: str = "/dashboard"
) -> Dict[str, int]:
    """
    Sends WebPush notification payloads to active user PushSubscription entries.
    Deletes subscriptions if push endpoint returns 404 or 410 (Gone).
    """
    subs = session.exec(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    ).all()

    if not subs:
        return {"delivered": 0, "failed": 0}

    private_key, _ = get_or_create_vapid_keys()
    user = session.get(User, user_id)
    claims_sub = f"mailto:{user.email}" if user and user.email else "mailto:admin@commutecheck.com"

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url
    })

    delivered = 0
    failed = 0
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth}
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": claims_sub}
            )
            delivered += 1
        except WebPushException as ex:
            failed += 1
            status_code = getattr(ex.response, "status_code", None) if hasattr(ex, "response") else None
            if status_code in (404, 410):
                session.delete(sub)

    session.commit()
    return {"delivered": delivered, "failed": failed}

class NotificationService:
    def __init__(self):
        pass

    def _format_message(
        self,
        assessment: Any,
        leg_type: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Formats the assessment result into a title and body.
        Clearly specifies the leg type (Morning Outbound vs Evening Return) and specific risk factors.
        """
        resolved_leg = leg_type or getattr(assessment, "leg_type", None)
        leg_label = None
        if resolved_leg:
            leg_lower = str(resolved_leg).lower()
            if "outbound" in leg_lower or "morning" in leg_lower:
                leg_label = "Morning Outbound"
            elif "return" in leg_lower or "evening" in leg_lower:
                leg_label = "Evening Return"
            else:
                leg_label = str(resolved_leg)

        status_val = getattr(assessment.status, "value", str(assessment.status))
        if leg_label:
            title = f"🏍️ Commute Check ({leg_label}): {status_val}"
        else:
            title = f"🏍️ Commute Check: {status_val}"

        recommendation = getattr(assessment, "recommendation", None)
        if not recommendation:
            if status_val == Status.GO.value or assessment.status == Status.GO:
                recommendation = "Enjoy your ride!"
            elif status_val == Status.CAUTION.value or assessment.status == Status.CAUTION:
                recommendation = "Ride with caution. Wear appropriate gear."
            else:
                recommendation = "Riding not recommended."

        body = ""
        if leg_label:
            loc_name = getattr(assessment, "location_name", None)
            sched_time = getattr(assessment, "schedule_time", None)
            leg_header = f"Leg: {leg_label}"
            if loc_name:
                leg_header += f" ({loc_name})"
            if sched_time:
                leg_header += f" at {sched_time}"
            body += leg_header + "\n\n"

        body += recommendation + "\n\n"
        body += f"Score: {assessment.score}/100\n"

        weather = getattr(assessment, "details", None) or getattr(assessment, "weather", None)
        if weather:
            body += f"Temp: {weather.temperature}°F, Wind: {weather.wind_speed} mph, Rain: {weather.precip_prob}%\n"

        if assessment.reasons:
            reasons_str = "\n".join([f"• {r}" for r in assessment.reasons])
            body += f"\nRisk Factors:\n{reasons_str}"

        return title, body

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def send_notification(
        self,
        webhook_url: str,
        assessment: Any,
        leg_type: Optional[str] = None
    ) -> bool:
        """
        Sends a notification via Apprise to the provided URL.
        Retries up to 3 times with exponential backoff.
        """
        return self.send_notification_sync(webhook_url, assessment, leg_type=leg_type)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    def send_notification_sync(
        self,
        webhook_url: str,
        assessment: Any,
        leg_type: Optional[str] = None
    ) -> bool:
        """
        Sends a notification via Apprise to the provided URL.
        Retries up to 3 times with exponential backoff.
        """
        apobj = apprise.Apprise()
        
        # If it's a raw Discord/Slack URL, Apprise often needs the protocol prefix
        # but it can also handle some raw URLs if added correctly.
        if not (webhook_url.startswith("http://") or webhook_url.startswith("https://")) and "://" not in webhook_url:
            # If no protocol and not a standard URL, it might be an Apprise service ID
            pass
            
        apobj.add(webhook_url)
        
        title, body = self._format_message(assessment, leg_type=leg_type)
        
        # Map Status to Apprise notify type
        status_val = getattr(assessment.status, "value", str(assessment.status))
        notify_type = apprise.NotifyType.INFO
        if status_val == Status.GO.value or assessment.status == Status.GO:
            notify_type = apprise.NotifyType.SUCCESS
        elif status_val == Status.CAUTION.value or assessment.status == Status.CAUTION:
            notify_type = apprise.NotifyType.WARNING
        elif status_val == Status.NO_GO.value or assessment.status == Status.NO_GO:
            notify_type = apprise.NotifyType.FAILURE
            
        success = apobj.notify(
            body=body,
            title=title,
            notify_type=notify_type,
        )
        
        if not success:
            logger.error(f"Failed to send notification via Apprise to {webhook_url}")
            if len(apobj) > 0:
                raise Exception(f"Apprise failed to deliver notification to {webhook_url}")
              
        return success


