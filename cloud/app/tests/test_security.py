"""Tests for Ed25519 security utilities."""

from cloud.app.core.security import (
    generate_keypair,
    sign_payload,
    verify_signature,
)


def test_generate_keypair():
    priv, pub = generate_keypair()
    assert len(priv) > 0
    assert len(pub) > 0
    assert priv != pub


def test_sign_and_verify(test_keypair):
    priv, pub = test_keypair
    sig = sign_payload("hello world", priv)
    assert sig.startswith("ed25519:")
    assert verify_signature("hello world", sig, pub)


def test_tampered_payload_fails(test_keypair):
    priv, pub = test_keypair
    sig = sign_payload("hello world", priv)
    assert not verify_signature("hello WORLD", sig, pub)


def test_wrong_public_key_fails(test_keypair):
    priv, _ = test_keypair
    _, wrong_pub = generate_keypair()
    sig = sign_payload("hello world", priv)
    assert not verify_signature("hello world", sig, wrong_pub)
