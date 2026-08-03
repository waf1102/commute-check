import os
from typing import Tuple
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
    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )

    _VAPID_PRIVATE_KEY = base64.urlsafe_b64encode(priv_bytes).decode('utf-8').rstrip('=')
    _VAPID_PUBLIC_KEY = base64.urlsafe_b64encode(pub_bytes).decode('utf-8').rstrip('=')
    return _VAPID_PRIVATE_KEY, _VAPID_PUBLIC_KEY
