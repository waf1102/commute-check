import apprise
import logging
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
from .models import Status, AssessmentResult

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        pass

    def _format_message(self, assessment: AssessmentResult) -> tuple[str, str]:
        """
        Formats the assessment result into a title and body.
        """
        title = f"🏍️ Commute Check: {assessment.status.value}"
        
        body = assessment.recommendation + "\n\n"
        body += f"Score: {assessment.score}/100\n"
        
        if assessment.details:
            body += f"Temp: {assessment.details.temperature}°F, Wind: {assessment.details.wind_speed} mph, Rain: {assessment.details.precip_prob}%\n"
            
        if assessment.reasons:
            reasons_str = "\n".join([f"• {r}" for r in assessment.reasons])
            body += f"\nReasons:\n{reasons_str}"
            
        return title, body

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def send_notification(self, webhook_url: str, assessment: AssessmentResult) -> bool:
        """
        Sends a notification via Apprise to the provided URL.
        Retries up to 3 times with exponential backoff.
        """
        # Apprise is synchronous, we'll run it in the current thread for now
        # as it's called from an async context in the scheduler.
        return self.send_notification_sync(webhook_url, assessment)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    def send_notification_sync(self, webhook_url: str, assessment: AssessmentResult) -> bool:
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
        
        title, body = self._format_message(assessment)
        
        # Map Status to Apprise notify type
        notify_type = apprise.NotifyType.INFO
        if assessment.status == Status.GO:
            notify_type = apprise.NotifyType.SUCCESS
        elif assessment.status == Status.CAUTION:
            notify_type = apprise.NotifyType.WARNING
        elif assessment.status == Status.NO_GO:
            notify_type = apprise.NotifyType.FAILURE
            
        success = apobj.notify(
            body=body,
            title=title,
            notify_type=notify_type,
        )
        
        if not success:
             # If apobj has no services, it returns False.
             # If it fails to send, it returns False.
             logger.error(f"Failed to send notification via Apprise to {webhook_url}")
             # We raise an exception to trigger tenacity retry if it failed
             if len(apobj) > 0:
                 raise Exception(f"Apprise failed to deliver notification to {webhook_url}")
             
        return success
