from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
import json
from pywebpush import webpush, WebPushException

from app.database import get_session
from app.models import User
from app.notifications import dispatch_web_push_notification
from app.push.models import PushSubscription
from app.push.schemas import (
    PushSubscribeRequest,
    PushUnsubscribeRequest,
    VapidPublicKeyResponse,
)
from app.push.vapid import get_or_create_vapid_keys
from app.security import get_current_user

router = APIRouter(prefix="/push", tags=["Push Notifications"])

@router.get("/vapid-public-key", response_model=VapidPublicKeyResponse)
def get_vapid_public_key(current_user: User = Depends(get_current_user)):
    _, public_key = get_or_create_vapid_keys()
    return VapidPublicKeyResponse(public_key=public_key)

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
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    subs = session.exec(
        select(PushSubscription).where(PushSubscription.user_id == current_user.id)
    ).all()

    if not subs:
        raise HTTPException(status_code=400, detail="No push subscriptions found for user")

    res = dispatch_web_push_notification(
        user_id=current_user.id,
        title="Commute Check Test",
        body="Web Push Notifications are working perfectly! 🏍️",
        session=session,
        url="/dashboard"
    )
    return {"status": "sent", "delivered": res["delivered"], "failed": res["failed"]}
