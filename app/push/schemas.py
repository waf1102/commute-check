from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class PushKeysSchema(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeRequest(BaseModel):
    endpoint: str
    keys: PushKeysSchema
    user_agent: Optional[str] = None


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


class VapidPublicKeyResponse(BaseModel):
    public_key: str


class TestPushRequest(BaseModel):
    title: Optional[str] = "Commute Check Test"
    body: Optional[str] = "Web Push Notifications are working perfectly! 🏍️"
    url: Optional[str] = "/#route-visualizer"
    has_route_hazard: Optional[bool] = False
    hazard_count: Optional[int] = 0
    primary_hazard_location: Optional[str] = ""
    hazard_pinpoints: Optional[List[Dict[str, Any]]] = None
    extra_data: Optional[Dict[str, Any]] = None
