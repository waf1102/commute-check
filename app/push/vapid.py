import os
from typing import Tuple
from pywebpush import webpush, WebPushException
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import base64

_VAPID_PRIVATE_KEY: str = os.getenv("VAPID_PRIVATE_KEY", "")
_VAPID_PUBLIC_KEY: str = os.getenv("VAPID_PUBLIC_KEY", "")

def get_or_create_vapid_keys() -> Tuple[str, str]:
    global _VAPID_PRIVATE_KEY, _VAPID_PUBLIC_KEY
    if _VAPID_PRIVATE_KEY and _VAPID_PUBLIC_KEY:
        return _VAPID_PRIVATE_KEY, _VAPID_PUBLIC_KEY

    # Generate EC P-256 keypair for VAPID
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    _VAPID_PRIVATE_KEY = base64.urlsafe_b64encode(private_bytes).decode('utf-8')
    _VAPID_PUBLIC_KEY = base64.urlsafe_b64encode(public_bytes).decode('utf-8')
    return _VAPID_PRIVATE_KEY, _VAPID_PUBLIC_KEY
