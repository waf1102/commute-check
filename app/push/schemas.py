from pydantic import BaseModel
from typing import Optional

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
