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
    url: str = "/#route-visualizer",
    has_route_hazard: bool = False,
    hazard_count: int = 0,
    primary_hazard_location: str = "",
    extra_data: Optional[Dict[str, Any]] = None,
    assessment: Optional[Any] = None,
) -> Dict[str, int]:
    """
    Sends WebPush notification payloads to active user PushSubscription entries.
    Includes route hazard metadata (has_route_hazard, hazard_count, primary_hazard_location).
    Deletes subscriptions if push endpoint returns 404 or 410 (Gone).
    """
    subs = session.exec(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    ).all()

    if not subs:
        return {"delivered": 0, "failed": 0}

    # Extract hazard metadata from assessment if passed and not explicitly provided
    if assessment is not None:
        pinpoints = NotificationService.extract_hazard_pinpoints(assessment)
        if pinpoints and not has_route_hazard:
            has_route_hazard = True
            hazard_count = len(pinpoints)
            first_p = pinpoints[0]
            primary_hazard_location = (
                first_p.get("location")
                or first_p.get("location_name")
                or first_p.get("name")
                or ""
            )

    private_key, _ = get_or_create_vapid_keys()
    user = session.get(User, user_id)
    claims_sub = f"mailto:{user.email}" if user and user.email else "mailto:admin@commutecheck.com"

    payload_dict = {
        "title": title,
        "body": body,
        "url": url,
        "has_route_hazard": bool(has_route_hazard),
        "hazard_count": int(hazard_count),
        "primary_hazard_location": str(primary_hazard_location or ""),
    }
    if extra_data:
        payload_dict.update(extra_data)

    payload = json.dumps(payload_dict)

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

    @staticmethod
    def extract_hazard_pinpoints(assessment: Any) -> List[Dict[str, Any]]:
        """
        Extracts hazard pinpoints or waypoint risks from an assessment object or dict.
        Returns a list of standardized dicts with hazard, location, encounter time, etc.
        """
        raw_pinpoints = None
        if isinstance(assessment, dict):
            raw_pinpoints = (
                assessment.get("hazard_pinpoints")
                or assessment.get("waypoint_risks")
                or assessment.get("waypoint_hazards")
                or assessment.get("waypoints")
            )
        else:
            raw_pinpoints = (
                getattr(assessment, "hazard_pinpoints", None)
                or getattr(assessment, "waypoint_risks", None)
                or getattr(assessment, "waypoint_hazards", None)
                or getattr(assessment, "waypoints", None)
            )

        if not raw_pinpoints:
            return []

        standardized: List[Dict[str, Any]] = []
        for item in raw_pinpoints:
            if isinstance(item, dict):
                p = dict(item)
            elif hasattr(item, "model_dump"):
                p = item.model_dump()
            elif hasattr(item, "__dict__"):
                p = dict(item.__dict__)
            else:
                p = {"description": str(item)}

            # Skip safe waypoints that don't represent hazards
            status = p.get("status")
            if status is not None:
                st_val = getattr(status, "value", str(status)).lower()
                if st_val == "go" and not p.get("hazard") and not p.get("hazard_type") and not p.get("parameter"):
                    continue

            standardized.append(p)

        return standardized

    def format_hazard_alert(
        self,
        assessment: Any,
        leg_type: Optional[str] = None,
        pinpoints: Optional[List[Dict[str, Any]]] = None,
        commute_name: Optional[str] = None
    ) -> str:
        """
        Formats concise and actionable mid-route hazard alerts.
        Example:
        'Commute Check: Caution for Morning Commute. ⚠️ High wind gusts (28 mph) near Summit Pass at ~08:25 AM.'
        """
        if pinpoints is None:
            pinpoints = self.extract_hazard_pinpoints(assessment)

        status_val = getattr(getattr(assessment, "status", None), "value", None)
        if not status_val:
            status_val = str(getattr(assessment, "status", "Caution"))

        # Resolve leg or commute label
        resolved_name = commute_name or getattr(assessment, "commute_name", None)
        if not resolved_name and isinstance(assessment, dict):
            resolved_name = assessment.get("commute_name")

        if not resolved_name:
            resolved_leg = leg_type or getattr(assessment, "leg_type", None)
            if not resolved_leg and isinstance(assessment, dict):
                resolved_leg = assessment.get("leg_type")

            if resolved_leg:
                leg_lower = str(resolved_leg).lower()
                if "morning" in leg_lower or "outbound" in leg_lower:
                    resolved_name = "Morning Commute"
                elif "evening" in leg_lower or "return" in leg_lower:
                    resolved_name = "Evening Commute"
                else:
                    resolved_name = str(resolved_leg)
            else:
                resolved_name = "Commute"

        header = f"Commute Check: {status_val} for {resolved_name}."

        alerts = []
        for p in pinpoints:
            # 1. Location
            location = (
                p.get("location")
                or p.get("location_name")
                or p.get("name")
                or p.get("place")
                or ""
            )

            # 2. Encounter time
            encounter_time = (
                p.get("encounter_time")
                or p.get("time")
                or p.get("estimated_time")
                or p.get("timestamp")
                or p.get("eta")
                or ""
            )

            # 3. Hazard parameter and value
            hazard = (
                p.get("hazard")
                or p.get("hazard_type")
                or p.get("parameter")
                or p.get("reason")
                or p.get("description")
                or ""
            )
            value = (
                p.get("value")
                or p.get("detail")
                or p.get("wind_speed")
                or p.get("precip_prob")
                or p.get("temperature")
                or ""
            )

            hazard_lower = str(hazard).lower()
            val_str = str(value).strip() if value is not None else ""

            # Standardize hazard representation
            if "wind" in hazard_lower:
                if val_str and "mph" not in val_str.lower() and "km/h" not in val_str.lower() and "kt" not in val_str.lower():
                    val_str = f"{val_str} mph"
                if "gust" in hazard_lower:
                    base_h = "High wind gusts"
                else:
                    base_h = "High wind gusts" if not hazard or hazard_lower == "wind" else hazard
                if val_str and f"({val_str})" not in base_h and val_str not in base_h:
                    hazard_text = f"{base_h} ({val_str})"
                else:
                    hazard_text = base_h
            elif "rain" in hazard_lower or "precip" in hazard_lower:
                if val_str and "%" not in val_str and "mm" not in val_str.lower() and "in" not in val_str.lower():
                    val_str = f"{val_str}%"
                base_h = "Heavy rain" if (not hazard or hazard_lower in ("rain", "precipitation", "precip")) else hazard
                if val_str and f"({val_str})" not in base_h and val_str not in base_h:
                    hazard_text = f"{base_h} ({val_str})"
                else:
                    hazard_text = base_h
            elif "temp" in hazard_lower or "cold" in hazard_lower or "freeze" in hazard_lower or "ice" in hazard_lower:
                if val_str and "°" not in val_str and "f" not in val_str.lower() and "c" not in val_str.lower():
                    val_str = f"{val_str}°F"
                base_h = "Low temperature" if (not hazard or hazard_lower in ("temperature", "temp", "low temp", "low_temperature", "low temperature")) else hazard
                if val_str and f"({val_str})" not in base_h and val_str not in base_h:
                    hazard_text = f"{base_h} ({val_str})"
                else:
                    hazard_text = base_h
            else:
                base_h = hazard or "Adverse weather conditions"
                if val_str and f"({val_str})" not in base_h and val_str not in base_h:
                    hazard_text = f"{base_h} ({val_str})"
                else:
                    hazard_text = base_h

            if hazard_text:
                hazard_text = hazard_text[0].upper() + hazard_text[1:]

            # Format location
            if location:
                loc_clean = str(location).strip()
                loc_str = loc_clean if (loc_clean.lower().startswith("near ") or loc_clean.lower().startswith("at ")) else f"near {loc_clean}"
            else:
                loc_str = ""

            # Format encounter time
            if encounter_time:
                time_clean = str(encounter_time).strip()
                if time_clean.lower().startswith("at "):
                    t_str = time_clean
                elif time_clean.startswith("~"):
                    t_str = f"at {time_clean}"
                else:
                    t_str = f"at ~{time_clean}"
            else:
                t_str = ""

            clause_parts = ["⚠️", hazard_text]
            if loc_str:
                clause_parts.append(loc_str)
            if t_str:
                clause_parts.append(t_str)

            clause = " ".join(clause_parts).strip()
            if not clause.endswith("."):
                clause += "."
            alerts.append(clause)

        if alerts:
            return f"{header} {' '.join(alerts)}"
        return header

    def _format_message(
        self,
        assessment: Any,
        leg_type: Optional[str] = None,
        commute_name: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Formats the assessment result into a title and body.
        Clearly specifies the leg type (Morning Outbound vs Evening Return) and specific risk factors.
        When AssessmentResult contains hazard_pinpoints or waypoint risks, formats concise and actionable mid-route alerts.
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

        # If hazard pinpoints or waypoint risks are present, format concise mid-route alert body
        pinpoints = self.extract_hazard_pinpoints(assessment)
        if pinpoints:
            hazard_body = self.format_hazard_alert(assessment, leg_type=leg_type, pinpoints=pinpoints, commute_name=commute_name)
            return title, hazard_body

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


