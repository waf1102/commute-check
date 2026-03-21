import httpx
import logging
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
from .models import Status, AssessmentResult

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.discord_color_map = {
            Status.GO: 3066993,
            Status.CAUTION: 16776960,
            Status.NO_GO: 15158332
        }

    def _format_discord_payload(self, assessment: AssessmentResult) -> Dict[str, Any]:
        """
        Formats the assessment result into a Discord rich embed payload.
        """
        color = self.discord_color_map.get(assessment.status, 3066993)
        
        fields = [
            {"name": "Score", "value": f"{assessment.score}/100", "inline": True},
        ]
        
        if assessment.details:
            fields.extend([
                {"name": "Temperature", "value": f"{assessment.details.temperature}°F", "inline": True},
                {"name": "Wind", "value": f"{assessment.details.wind_speed} mph", "inline": True},
                {"name": "Rain Prob", "value": f"{assessment.details.precip_prob}%", "inline": True},
            ])
            
        if assessment.reasons:
            reasons_str = "\n".join([f"• {r}" for r in assessment.reasons])
            fields.append({"name": "Reasons", "value": reasons_str, "inline": False})

        return {
            "embeds": [
                {
                    "title": f"🏍️ Commute Check: {assessment.status.value}",
                    "description": assessment.recommendation,
                    "color": color,
                    "fields": fields
                }
            ]
        }

    def _format_generic_payload(self, assessment: AssessmentResult) -> Dict[str, Any]:
        """
        Formats the assessment result into a generic JSON payload.
        """
        return assessment.model_dump()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def send_notification(self, webhook_url: str, assessment: AssessmentResult) -> bool:
        """
        Sends a notification to the provided webhook URL.
        Detects Discord URLs and formats accordingly.
        Retries up to 3 times with exponential backoff.
        """
        is_discord = "discord.com/api/webhooks" in webhook_url
        
        if is_discord:
            payload = self._format_discord_payload(assessment)
        else:
            payload = self._format_generic_payload(assessment)

        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
            return True

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    def send_notification_sync(self, webhook_url: str, assessment: AssessmentResult) -> bool:
        """
        Sends a notification to the provided webhook URL.
        Detects Discord URLs and formats accordingly.
        Retries up to 3 times with exponential backoff.
        """
        is_discord = "discord.com/api/webhooks" in webhook_url
        
        if is_discord:
            payload = self._format_discord_payload(assessment)
        else:
            payload = self._format_generic_payload(assessment)

        with httpx.Client() as client:
            response = client.post(webhook_url, json=payload)
            response.raise_for_status()
            return True
