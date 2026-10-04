"""Stable VAPID identity across application restarts."""

import base64
import json
import os
from pathlib import Path
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

_VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
_VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")


def get_or_create_vapid_keys() -> Tuple[str, str]:
    global _VAPID_PRIVATE_KEY, _VAPID_PUBLIC_KEY
    if _VAPID_PRIVATE_KEY and _VAPID_PUBLIC_KEY:
        return _VAPID_PRIVATE_KEY, _VAPID_PUBLIC_KEY
    path = Path(os.getenv("VAPID_KEY_FILE", "vapid-keys.json"))
    if not path.exists():
        key = ec.generate_private_key(ec.SECP256R1())
        private = key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        public = key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        keys = [
            base64.urlsafe_b64encode(value).decode().rstrip("=")
            for value in (private, public)
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "w") as file:
                json.dump(keys, file)
    _VAPID_PRIVATE_KEY, _VAPID_PUBLIC_KEY = json.loads(path.read_text())
    return _VAPID_PRIVATE_KEY, _VAPID_PUBLIC_KEY
