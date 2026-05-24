"""Ed25519 signing and verification utilities.

Used by:
- Cloud: sign license validation responses, trial responses
- Local: verify cloud signatures with embedded public key
"""

from __future__ import annotations

import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def generate_keypair() -> tuple[str, str]:
    """Generate a new Ed25519 keypair, return (private_b64url, public_b64url)."""
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    priv_raw = private.private_bytes_raw()
    pub_raw = public.public_bytes_raw()
    return (
        base64.urlsafe_b64encode(priv_raw).decode().rstrip("="),
        base64.urlsafe_b64encode(pub_raw).decode().rstrip("="),
    )


def sign_payload(payload: str, private_key_b64url: str) -> str:
    """Sign a string payload with Ed25519 private key. Returns 'ed25519:<sig>'."""
    key_bytes = _decode_key(private_key_b64url)
    if len(key_bytes) != 32:
        raise ValueError("Ed25519 private key must be 32 bytes")
    private = Ed25519PrivateKey.from_private_bytes(key_bytes)
    sig = private.sign(payload.encode())
    return "ed25519:" + base64.urlsafe_b64encode(sig).decode().rstrip("=")


def verify_signature(payload: str, signature_str: str, public_key_b64url: str) -> bool:
    """Verify an 'ed25519:<sig>' signature against a payload and public key."""
    if not signature_str.startswith("ed25519:"):
        return False
    try:
        sig_b64 = signature_str.split(":", 1)[1]
        sig_bytes = _b64url_decode(sig_b64)
        key_bytes = _decode_key(public_key_b64url)
        if len(key_bytes) != 32:
            return False
        public = Ed25519PublicKey.from_public_bytes(key_bytes)
        public.verify(sig_bytes, payload.encode())
        return True
    except (InvalidSignature, ValueError):
        return False


def _decode_key(value: str | bytes) -> bytes:
    """Decode a key from base64url or PEM format."""
    val = value.decode() if isinstance(value, bytes) else value
    val = val.strip().replace("\\n", "\n")
    if "BEGIN" in val:
        return _pem_to_raw_bytes(val)
    return _b64url_decode(val)


def _pem_to_raw_bytes(pem: str) -> bytes:
    """Extract raw key bytes from PEM. Returns raw bytes (may need post-processing)."""
    if "PRIVATE" in pem:
        key = serialization.load_pem_private_key(pem.encode(), password=None)
        if isinstance(key, Ed25519PrivateKey):
            return key.private_bytes_raw()
        raise ValueError("PEM key is not Ed25519")
    elif "PUBLIC" in pem:
        key = serialization.load_pem_public_key(pem.encode())
        if isinstance(key, Ed25519PublicKey):
            return key.public_bytes_raw()
        raise ValueError("PEM key is not Ed25519")
    raise ValueError("Unknown PEM format")


def _b64url_decode(s: str) -> bytes:
    """Decode base64url with padding restoration."""
    padding = (4 - len(s) % 4) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)
