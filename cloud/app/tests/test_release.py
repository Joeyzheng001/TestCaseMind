"""Test release updater verification and knowledge search endpoint."""

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from cloud.app.main import app


# ── Knowledge search ──

@pytest.mark.asyncio
async def test_knowledge_search_no_db():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/knowledge/search", json={"query": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == []


# ── SHA256 verification ──

def test_verify_sha256_match():
    from src.updater import verify_sha256
    content = b"hello world"
    expected = hashlib.sha256(content).hexdigest()
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(content)
        tmp = Path(f.name)
    try:
        assert verify_sha256(tmp, expected) is True
    finally:
        tmp.unlink()


def test_verify_sha256_mismatch():
    from src.updater import verify_sha256
    content = b"hello world"
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(content)
        tmp = Path(f.name)
    try:
        assert verify_sha256(tmp, "badhash") is False
    finally:
        tmp.unlink()


# ── Release signature verification ──

def test_verify_release_signature_valid(test_keypair):
    """Valid signature passes verification."""
    from src.updater import verify_release_signature

    priv_b64, pub_b64 = test_keypair
    from cloud.app.core.security import sign_payload

    release = {
        "version": "2.0.0",
        "url": "https://cdn.example.com/release.zip",
        "sha256": "abc123",
    }
    payload = f"{release['version']}|{release['url']}|{release['sha256']}"
    release["signature"] = sign_payload(payload, priv_b64)

    # Monkey-patch LicenseManager to return our test public key
    with patch("src.updater.LicenseManager") as mock_mgr:
        mock_mgr.return_value.public_key = pub_b64
        mock_mgr.return_value._verify_signature.return_value = (True, "")
        assert verify_release_signature(release) is True


def test_verify_release_signature_invalid(test_keypair):
    """Tampered release fails verification."""
    from src.updater import verify_release_signature

    priv_b64, pub_b64 = test_keypair
    from cloud.app.core.security import sign_payload

    release = {
        "version": "2.0.0",
        "url": "https://cdn.example.com/release.zip",
        "sha256": "abc123",
    }
    payload = f"{release['version']}|{release['url']}|{release['sha256']}"
    release["signature"] = sign_payload(payload, priv_b64)
    # Tamper with the URL
    release["url"] = "https://evil.com/malware.zip"

    with patch("src.updater.LicenseManager") as mock_mgr:
        mock_mgr.return_value.public_key = pub_b64
        mock_mgr.return_value._verify_signature.return_value = (False, "bad sig")
        assert verify_release_signature(release) is False


def test_verify_release_no_signature():
    """Missing signature returns False."""
    from src.updater import verify_release_signature
    release = {"version": "2.0.0", "url": "...", "sha256": "abc"}
    with patch("src.updater.LicenseManager") as mock_mgr:
        mock_mgr.return_value.public_key = "somekey"
        assert verify_release_signature(release) is False


def test_verify_release_no_public_key():
    """Missing public key returns False."""
    from src.updater import verify_release_signature
    release = {"version": "2.0.0", "url": "...", "sha256": "abc", "signature": "xx"}
    with patch("src.updater.LicenseManager") as mock_mgr:
        mock_mgr.return_value.public_key = None
        assert verify_release_signature(release) is False


# ── get_local_version ──

def test_get_local_version_exists(tmp_path):
    from src.updater import get_local_version
    ver_file = tmp_path / "web" / "version.txt"
    ver_file.parent.mkdir()
    ver_file.write_text("3.2.1")
    assert get_local_version(tmp_path) == "3.2.1"


def test_get_local_version_missing(tmp_path):
    from src.updater import get_local_version
    assert get_local_version(tmp_path) == "1.0.0"
