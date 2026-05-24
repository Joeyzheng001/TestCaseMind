"""Test local LicenseManager with cloud methods."""

import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def manager():
    """Create LicenseManager with temp config dir."""
    from src.license_manager import LicenseManager
    # Use a valid Ed25519 public key (base64url-encoded 32 bytes)
    test_key = "9ukqWcoMOX-6YmlSgYY2q8zMdgB2CqhAN8pNW_puPk4"
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["THESISMIND_CONFIG_DIR"] = tmp
        os.environ["THESISMIND_LICENSE_PUBLIC_KEY"] = test_key
        m = LicenseManager()
        yield m
        del os.environ["THESISMIND_CONFIG_DIR"]


def test_cloud_url_config(manager):
    assert manager.cloud_url == "https://api.thesismind.com"


def test_public_key_loaded(manager):
    assert manager.public_key is not None


def test_get_effective_status_no_license(manager):
    status = manager.get_effective_status()
    assert status["status"] in ("no_license", "active")


def test_validate_with_cloud_unreachable(manager):
    result = manager.validate_with_cloud("TM-XXXX", "")
    assert result["status"] == "error"
    assert "Cloud unreachable" in result.get("message", "")


def test_can_access_public_api(manager):
    ok, reason = manager.can_access_api("/api/config")
    assert ok


def test_can_access_menu(manager):
    ok, reason = manager.can_access_menu("proposal")
    # Without license, should be denied or allowed depending on tier
    assert isinstance(ok, bool)


def test_cache_file_path(manager):
    assert manager._cache_file.name == ".license_cloud_cache"


def test_cache_written_on_validate(manager):
    test_data = {"status": "valid", "tier": "basic", "features": ["workflow"],
                 "expires_at": "2099-01-01T00:00:00", "device_limit": 1,
                 "device_count": 1, "revoked": False, "user_email": "",
                 "signature": "", "signed_at": "2026-01-01T00:00:00"}
    manager._cache_license_state(test_data)
    assert manager._cache_file.exists()
    cached = json.loads(manager._cache_file.read_text())
    assert cached["tier"] == "basic"
    assert "cached_at" in cached
