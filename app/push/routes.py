from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import User
from app.notifications import dispatch_web_push_notification
from app.push.models import PushSubscription
from app.push.schemas import (
    PushSubscribeRequest,
    PushUnsubscribeRequest,
    VapidPublicKeyResponse,
    TestPushRequest,
)
from app.push.vapid import get_or_create_vapid_keys
from app.security import get_current_user

router = APIRouter(prefix="/push", tags=["Push Notifications"])


@router.get("/vapid-public-key", response_model=VapidPublicKeyResponse)
def get_vapid_public_key(current_user: User = Depends(get_current_user)):
    _, public_key = get_or_create_vapid_keys()
    return VapidPublicKeyResponse(public_key=public_key)


@router.get("/subscriptions", response_model=List[PushSubscription])
@router.get("", response_model=List[PushSubscription])
@router.get("/", response_model=List[PushSubscription])
def list_subscriptions(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """List all active push subscriptions for current user."""
    subs = session.exec(
        select(PushSubscription).where(PushSubscription.user_id == current_user.id)
    ).all()
    return subs


@router.post("/subscribe")
def subscribe(
    req: PushSubscribeRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    existing = session.exec(
        select(PushSubscription).where(PushSubscription.endpoint == req.endpoint)
    ).first()

    if existing:
        existing.user_id = current_user.id
        existing.p256dh = req.keys.p256dh
        existing.auth = req.keys.auth
        existing.user_agent = req.user_agent
        session.add(existing)
    else:
        sub = PushSubscription(
            user_id=current_user.id,
            endpoint=req.endpoint,
            p256dh=req.keys.p256dh,
            auth=req.keys.auth,
            user_agent=req.user_agent,
        )
        session.add(sub)

    session.commit()
    return {"status": "subscribed"}


@router.delete("/unsubscribe")
def unsubscribe(
    req: PushUnsubscribeRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    sub = session.exec(
        select(PushSubscription).where(
            PushSubscription.endpoint == req.endpoint,
            PushSubscription.user_id == current_user.id,
        )
    ).first()
    if sub:
        session.delete(sub)
        session.commit()
    return {"status": "unsubscribed"}


@router.post("/test")
def send_test_push(
    req: Optional[TestPushRequest] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    subs = session.exec(
        select(PushSubscription).where(PushSubscription.user_id == current_user.id)
    ).all()

    if not subs:
        raise HTTPException(
            status_code=400, detail="No push subscriptions found for user"
        )

    title = req.title if (req and req.title) else "Commute Check Test"
    body = (
        req.body
        if (req and req.body)
        else "Web Push Notifications are working perfectly! 🏍️"
    )
    url = req.url if (req and req.url) else "/#route-visualizer"
    has_route_hazard = (
        req.has_route_hazard if (req and req.has_route_hazard is not None) else False
    )
    hazard_count = req.hazard_count if (req and req.hazard_count is not None) else 0
    primary_hazard_location = (
        req.primary_hazard_location
        if (req and req.primary_hazard_location is not None)
        else ""
    )

    extra_data = dict(req.extra_data) if (req and req.extra_data) else {}
    if req and req.hazard_pinpoints:
        has_route_hazard = True
        hazard_count = len(req.hazard_pinpoints)
        if not primary_hazard_location:
            first_p = req.hazard_pinpoints[0]
            primary_hazard_location = (
                first_p.get("location")
                or first_p.get("location_name")
                or first_p.get("name")
                or ""
            )
        extra_data["hazard_pinpoints"] = req.hazard_pinpoints

    res = dispatch_web_push_notification(
        user_id=current_user.id,
        title=title,
        body=body,
        session=session,
        url=url,
        has_route_hazard=has_route_hazard,
        hazard_count=hazard_count,
        primary_hazard_location=primary_hazard_location,
        extra_data=extra_data if extra_data else None,
        assessment=req.assessment if req else None,
    )
    return {"status": "sent", "delivered": res["delivered"], "failed": res["failed"]}
