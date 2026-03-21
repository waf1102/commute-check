import os
from cryptography.fernet import Fernet

# It's crucial to load the key from environment variables for security.
# The key should be a 32-byte URL-safe base64-encoded string.
key = os.getenv("ENCRYPTION_KEY")
if not key:
    raise ValueError("ENCRYPTION_KEY not found in environment variables. Please set it.")

f = Fernet(key.encode())

def encrypt_data(data: str) -> bytes:
    """Encrypts a string and returns the encrypted data as bytes."""
    if not isinstance(data, str):
        raise TypeError("Data to encrypt must be a string.")
    return f.encrypt(data.encode('utf-8'))

def decrypt_data(encrypted_data: bytes) -> str:
    """Decrypts data and returns it as a string."""
    if not isinstance(encrypted_data, bytes):
        raise TypeError("Encrypted data must be bytes.")
    return f.decrypt(encrypted_data).decode('utf-8')
