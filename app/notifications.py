import asyncio
import apprise
import logging
import json
from typing import Dict, Any, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from pywebpush import webpush
from sqlmodel import Session, select

from .models import Status, User
from .push.models import PushSubscription
from .push.vapid import get_or_create_vapid_keys

logger = logging.getLogger(__name__)


def _safe_get(obj: Any, *keys: str, default: Any = None) -> Any:
    """
    Safely retrieves the first found key from an object or dictionary,
    supporting nested payloads ('assessment', 'data', 'result', etc.).
    Never raises AttributeError or KeyError.
    """
    if obj is None:
        return default

    # First check direct keys on obj
    for key in keys:
        if isinstance(obj, dict):
            if key in obj and obj[key] is not None:
                return obj[key]
        else:
            val = getattr(obj, key, None)
            if val is not None:
                return val

    # If not found directly, check nested payload containers
    nested_containers = (
        "assessment",
        "data",
        "result",
        "assessment_result",
        "payload",
        "leg_assessment",
        "outbound_leg",
        "return_leg",
        "route_assessment",
    )
    for container in nested_containers:
        nested_obj = None
        if isinstance(obj, dict):
            nested_obj = obj.get(container)
        else:
            nested_obj = getattr(obj, container, None)

        if nested_obj is not None and not isinstance(nested_obj, (str, int, float, bool)):
            val = _safe_get(nested_obj, *keys, default=None)
            if val is not None:
                return val

    return default


def _extract_status(assessment: Any, default: str = "Caution") -> str:
    """
    Safely extracts and normalizes the status string from an assessment
    whether it is a dict, nested dict, Pydantic model, or arbitrary object.
    Never raises AttributeError or KeyError.
    """
    if assessment is None:
        return default

    raw_status = None
    if isinstance(assessment, dict):
        raw_status = assessment.get("status")
        if raw_status is None:
            raw_status = assessment.get("overall_status")
        if raw_status is None:
            # Check nested containers
            for container in (
                "assessment",
                "data",
                "result",
                "assessment_result",
                "payload",
                "leg_assessment",
                "outbound_leg",
                "return_leg",
                "route_assessment",
            ):
                nested = assessment.get(container)
                if isinstance(nested, dict):
                    raw_status = nested.get("status") or nested.get("overall_status")
                    if raw_status is not None:
                        break
                elif nested is not None:
                    raw_status = getattr(nested, "status", None) or getattr(nested, "overall_status", None)
                    if raw_status is not None:
                        break
    else:
        raw_status = getattr(assessment, "status", None)
        if raw_status is None:
            raw_status = getattr(assessment, "overall_status", None)
        if raw_status is None:
            for container in (
                "assessment",
                "data",
                "result",
                "assessment_result",
                "payload",
                "leg_assessment",
                "outbound_leg",
                "return_leg",
                "route_assessment",
            ):
                nested = getattr(assessment, container, None)
                if isinstance(nested, dict):
                    raw_status = nested.get("status") or nested.get("overall_status")
                    if raw_status is not None:
                        break
                elif nested is not None:
                    raw_status = getattr(nested, "status", None) or getattr(nested, "overall_status", None)
                    if raw_status is not None:
                        break

    if raw_status is None:
        return default

    # If raw_status is a dict, e.g. {"value": "Caution"} or {"status": "Caution"}
    if isinstance(raw_status, dict):
        raw_status = (
            raw_status.get("value")
            or raw_status.get("status")
            or raw_status.get("name")
            or default
        )

    # If raw_status has a .value (like Enum / Status)
    if hasattr(raw_status, "value"):
        raw_status = raw_status.value

    st_str = str(raw_status).strip()
    st_lower = st_str.lower()
    if st_lower in ("go", "status.go", "safe", "ok"):
        return Status.GO.value
    elif st_lower in ("caution", "status.caution", "warning", "warn"):
        return Status.CAUTION.value
    elif st_lower in ("no-go", "no_go", "nogo", "status.no_go", "danger", "stop", "fail", "failed"):
        return Status.NO_GO.value

    return st_str if st_str else default


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
        if pinpoints:
            has_route_hazard = True
            hazard_count = len(pinpoints)
            if not primary_hazard_location:
                first_p = pinpoints[0]
                primary_hazard_location = (
                    first_p.get("location")
                    or first_p.get("location_name")
                    or first_p.get("name")
                    or first_p.get("place")
                    or ""
                )

    # Fallback title/body from assessment if missing
    if assessment is not None and (not title or not body):
        auto_title, auto_body = NotificationService()._format_message(assessment)
        if not title:
            title = auto_title
        if not body:
            body = auto_body

    private_key, _ = get_or_create_vapid_keys()
    user = session.get(User, user_id)
    claims_sub = (
        f"mailto:{user.email}"
        if user and user.email
        else "mailto:admin@commutecheck.com"
    )

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
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": claims_sub},
            )
            delivered += 1
        except Exception as ex:
            failed += 1
            status_code = getattr(ex, "status_code", None)
            response = getattr(ex, "response", None)
            if status_code is None and response is not None:
                status_code = getattr(
                    response, "status_code", getattr(response, "status", None)
                )
            message = str(ex).lower()
            expired = (
                status_code in (404, 410)
                or ("410" in message and "gone" in message)
                or (
                    "404" in message
                    and ("not found" in message or "endpoint" in message)
                )
            )
            if expired:
                session.delete(sub)
            else:
                logger.warning("Push delivery failed for subscription %s", sub.id)

    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Could not persist push subscription changes")
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
        if assessment is None:
            return []

        raw_pinpoints = None
        if isinstance(assessment, list):
            raw_pinpoints = assessment
        elif isinstance(assessment, dict):
            raw_pinpoints = (
                assessment.get("hazard_pinpoints")
                or assessment.get("waypoint_risks")
                or assessment.get("waypoint_hazards")
                or assessment.get("route_hazards")
                or assessment.get("hazards")
                or assessment.get("waypoints")
            )
            if not raw_pinpoints:
                # Check nested containers
                for container in (
                    "assessment",
                    "data",
                    "result",
                    "assessment_result",
                    "payload",
                    "leg_assessment",
                    "outbound_leg",
                    "return_leg",
                    "route_assessment",
                ):
                    nested = assessment.get(container)
                    if nested is not None:
                        nested_pinpoints = NotificationService.extract_hazard_pinpoints(nested)
                        if nested_pinpoints:
                            return nested_pinpoints
        else:
            raw_pinpoints = (
                getattr(assessment, "hazard_pinpoints", None)
                or getattr(assessment, "waypoint_risks", None)
                or getattr(assessment, "waypoint_hazards", None)
                or getattr(assessment, "route_hazards", None)
                or getattr(assessment, "hazards", None)
                or getattr(assessment, "waypoints", None)
            )
            if not raw_pinpoints:
                for container in (
                    "assessment",
                    "data",
                    "result",
                    "assessment_result",
                    "payload",
                    "leg_assessment",
                    "outbound_leg",
                    "return_leg",
                    "route_assessment",
                ):
                    nested = getattr(assessment, container, None)
                    if nested is not None:
                        nested_pinpoints = NotificationService.extract_hazard_pinpoints(nested)
                        if nested_pinpoints:
                            return nested_pinpoints

        if not raw_pinpoints:
            # Also check waypoint_evaluations or segments if available
            evals = _safe_get(assessment, "waypoint_evaluations", default=None)
            if evals and isinstance(evals, list):
                collected = []
                for ev in evals:
                    sub_pts = NotificationService.extract_hazard_pinpoints(ev)
                    collected.extend(sub_pts)
                if collected:
                    return collected

            segs = _safe_get(assessment, "segments", default=None)
            if segs and isinstance(segs, list):
                collected = []
                for seg in segs:
                    sub_pts = NotificationService.extract_hazard_pinpoints(seg)
                    collected.extend(sub_pts)
                if collected:
                    return collected

            return []

        if isinstance(raw_pinpoints, dict):
            raw_pinpoints = [raw_pinpoints]

        standardized: List[Dict[str, Any]] = []
        for item in raw_pinpoints:
            if item is None:
                continue
            if isinstance(item, dict):
                p = dict(item)
            elif hasattr(item, "model_dump") and callable(item.model_dump):
                p = item.model_dump()
            elif hasattr(item, "dict") and callable(item.dict):
                p = item.dict()
            elif hasattr(item, "__dict__"):
                p = dict(item.__dict__)
            else:
                p = {"description": str(item)}

            # Skip safe waypoints that don't represent hazards
            status = p.get("status") or p.get("severity")
            if status is not None:
                if isinstance(status, dict):
                    st_val = str(status.get("value") or status.get("status") or "").lower()
                elif hasattr(status, "value"):
                    st_val = str(status.value).lower()
                else:
                    st_val = str(status).lower()

                if (
                    st_val in ("go", "safe", "ok", "status.go")
                    and not p.get("hazard")
                    and not p.get("hazard_type")
                    and not p.get("parameter")
                    and not p.get("parameter_breached")
                    and not p.get("reason")
                ):
                    continue

            # Aliasing normalization
            if "location" in p and "location_name" not in p:
                p["location_name"] = p["location"]
            elif "location_name" in p and "location" not in p:
                p["location"] = p["location_name"]

            if "hazard" in p and "parameter" not in p:
                p["parameter"] = p["hazard"]
            elif "parameter" in p and "hazard" not in p:
                p["hazard"] = p["parameter"]

            if "time" in p and "encounter_time" not in p:
                p["encounter_time"] = p["time"]
            elif "encounter_time" in p and "time" not in p:
                p["time"] = p["encounter_time"]

            standardized.append(p)

        return standardized

    def format_hazard_alert(
        self,
        assessment: Any,
        leg_type: Optional[str] = None,
        pinpoints: Optional[List[Dict[str, Any]]] = None,
        commute_name: Optional[str] = None,
    ) -> str:
        """
        Formats concise and actionable mid-route hazard alerts.
        Example:
        'Commute Check: Caution for Morning Commute. ⚠️ High wind gusts (28 mph) near Summit Pass at ~08:25 AM.'
        """
        if pinpoints is None:
            pinpoints = self.extract_hazard_pinpoints(assessment)

        status_val = _extract_status(assessment, default="Caution")

        # Resolve leg or commute label
        resolved_name = commute_name or _safe_get(assessment, "commute_name")

        if not resolved_name:
            resolved_leg = leg_type or _safe_get(assessment, "leg_type")

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
                or p.get("estimated_arrival_time")
                or p.get("timestamp")
                or p.get("eta")
                or ""
            )

            # 3. Hazard parameter and value
            hazard = (
                p.get("hazard")
                or p.get("hazard_type")
                or p.get("parameter")
                or p.get("parameter_breached")
                or p.get("reason")
                or p.get("description")
                or p.get("warning_message")
                or p.get("title")
                or ""
            )
            value = None
            for k in (
                "value",
                "detail",
                "wind_speed",
                "wind_gusts",
                "precip_prob",
                "temperature",
            ):
                if p.get(k) is not None and p.get(k) != "":
                    value = p.get(k)
                    break

            hazard_lower = str(hazard).lower()
            val_str = str(value).strip() if value is not None else ""

            # Standardize hazard representation
            if "wind" in hazard_lower:
                if (
                    val_str
                    and "mph" not in val_str.lower()
                    and "km/h" not in val_str.lower()
                    and "kt" not in val_str.lower()
                ):
                    val_str = f"{val_str} mph"
                if "gust" in hazard_lower:
                    base_h = "High wind gusts"
                else:
                    base_h = (
                        "High wind gusts"
                        if not hazard or hazard_lower == "wind"
                        else hazard
                    )
                if val_str and f"({val_str})" not in base_h and val_str not in base_h:
                    hazard_text = f"{base_h} ({val_str})"
                else:
                    hazard_text = base_h
            elif "rain" in hazard_lower or "precip" in hazard_lower:
                if (
                    val_str
                    and "%" not in val_str
                    and "mm" not in val_str.lower()
                    and "in" not in val_str.lower()
                ):
                    val_str = f"{val_str}%"
                base_h = (
                    "Heavy rain"
                    if (
                        not hazard
                        or hazard_lower in ("rain", "precipitation", "precip")
                    )
                    else hazard
                )
                if val_str and f"({val_str})" not in base_h and val_str not in base_h:
                    hazard_text = f"{base_h} ({val_str})"
                else:
                    hazard_text = base_h
            elif (
                "temp" in hazard_lower
                or "cold" in hazard_lower
                or "freeze" in hazard_lower
                or "ice" in hazard_lower
            ):
                if (
                    val_str
                    and "°" not in val_str
                    and "f" not in val_str.lower()
                    and "c" not in val_str.lower()
                ):
                    val_str = f"{val_str}°F"
                base_h = (
                    "Low temperature"
                    if (
                        not hazard
                        or hazard_lower
                        in (
                            "temperature",
                            "temp",
                            "low temp",
                            "low_temperature",
                            "low temperature",
                        )
                    )
                    else hazard
                )
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
                loc_str = (
                    loc_clean
                    if (
                        loc_clean.lower().startswith("near ")
                        or loc_clean.lower().startswith("at ")
                    )
                    else f"near {loc_clean}"
                )
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
        commute_name: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Formats the assessment result into a title and body.
        Clearly specifies the leg type (Morning Outbound vs Evening Return) and specific risk factors.
        When AssessmentResult contains hazard_pinpoints or waypoint risks, formats concise and actionable mid-route alerts.
        """
        resolved_leg = leg_type or _safe_get(assessment, "leg_type")
        leg_label = None
        if resolved_leg:
            leg_lower = str(resolved_leg).lower()
            if "outbound" in leg_lower or "morning" in leg_lower:
                leg_label = "Morning Outbound"
            elif "return" in leg_lower or "evening" in leg_lower:
                leg_label = "Evening Return"
            else:
                leg_label = str(resolved_leg)

        status_val = _extract_status(assessment, default="Caution")
        if leg_label:
            title = f"🏍️ Commute Check ({leg_label}): {status_val}"
        else:
            title = f"🏍️ Commute Check: {status_val}"

        # If hazard pinpoints or waypoint risks are present, format concise mid-route alert body
        pinpoints = self.extract_hazard_pinpoints(assessment)
        if pinpoints:
            hazard_body = self.format_hazard_alert(
                assessment,
                leg_type=leg_type,
                pinpoints=pinpoints,
                commute_name=commute_name,
            )
            return title, hazard_body

        recommendation = _safe_get(assessment, "recommendation")
        if not recommendation:
            if status_val == Status.GO.value:
                recommendation = "Enjoy your ride!"
            elif status_val == Status.CAUTION.value:
                recommendation = "Ride with caution. Wear appropriate gear."
            else:
                recommendation = "Riding not recommended."

        body = ""
        if leg_label:
            loc_name = _safe_get(assessment, "location_name")
            sched_time = _safe_get(assessment, "schedule_time")
            leg_header = f"Leg: {leg_label}"
            if loc_name:
                leg_header += f" ({loc_name})"
            if sched_time:
                leg_header += f" at {sched_time}"
            body += leg_header + "\n\n"

        body += recommendation + "\n\n"
        score = _safe_get(assessment, "score", "overall_score")
        if score is not None:
            body += f"Score: {score}/100\n"

        weather = _safe_get(assessment, "details", "weather")
        if weather:
            temp = _safe_get(weather, "temperature")
            wind = _safe_get(weather, "wind_speed")
            precip = _safe_get(weather, "precip_prob")
            parts = []
            if temp is not None:
                parts.append(f"Temp: {temp}°F")
            if wind is not None:
                parts.append(f"Wind: {wind} mph")
            if precip is not None:
                parts.append(f"Rain: {precip}%")
            if parts:
                body += ", ".join(parts) + "\n"

        reasons = _safe_get(assessment, "reasons", default=[])
        if reasons:
            if isinstance(reasons, str):
                reasons = [reasons]
            reasons_str = "\n".join([f"• {r}" for r in reasons if r])
            if reasons_str:
                body += f"\nRisk Factors:\n{reasons_str}"

        return title, body

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def send_notification(
        self,
        webhook_url: str,
        assessment: Any,
        leg_type: Optional[str] = None,
        commute_name: Optional[str] = None,
    ) -> bool:
        """
        Sends a notification via Apprise to the provided URL.
        Retries up to 3 times with exponential backoff.
        """
        return await asyncio.to_thread(
            self.send_notification_sync,
            webhook_url,
            assessment,
            leg_type=leg_type,
            commute_name=commute_name,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def send_notification_sync(
        self,
        webhook_url: str,
        assessment: Any,
        leg_type: Optional[str] = None,
        commute_name: Optional[str] = None,
    ) -> bool:
        """
        Sends a notification via Apprise to the provided URL.
        Retries up to 3 times with exponential backoff.
        """
        apobj = apprise.Apprise()

        # If it's a raw Discord/Slack URL, Apprise often needs the protocol prefix
        # but it can also handle some raw URLs if added correctly.
        if (
            not (
                webhook_url.startswith("http://") or webhook_url.startswith("https://")
            )
            and "://" not in webhook_url
        ):
            # If no protocol and not a standard URL, it might be an Apprise service ID
            pass

        apobj.add(webhook_url)

        title, body = self._format_message(
            assessment, leg_type=leg_type, commute_name=commute_name
        )

        # Map Status to Apprise notify type
        status_val = _extract_status(assessment, default="Caution")
        notify_type = apprise.NotifyType.INFO
        if status_val == Status.GO.value:
            notify_type = apprise.NotifyType.SUCCESS
        elif status_val == Status.CAUTION.value:
            notify_type = apprise.NotifyType.WARNING
        elif status_val == Status.NO_GO.value:
            notify_type = apprise.NotifyType.FAILURE

        success = apobj.notify(
            body=body,
            title=title,
            notify_type=notify_type,
        )

        if not success:
            logger.error("Failed to send notification via Apprise")
            if len(apobj) > 0:
                raise RuntimeError("Apprise failed to deliver notification")

        return success
