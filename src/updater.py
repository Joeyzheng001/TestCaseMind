"""Auto-updater: check, download, verify, install new client releases.

Flow:
  1. GET /v1/release/latest → compare versions
  2. If newer: download zip → verify SHA256 → verify Ed25519 sig
  3. Backup current web/ → extract → update version.txt
  4. On failure: rollback from web.backup/
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import httpx

from src.license_manager import LicenseManager

VERSION_FILE = "web/version.txt"
BACKUP_DIR = "web.backup"


def get_local_version(project_root: Path) -> str:
    version_path = project_root / VERSION_FILE
    if version_path.exists():
        return version_path.read_text().strip()
    return "1.0.0"


def check_update(project_root: Path) -> Optional[dict]:
    """Check cloud for newer version. Returns release dict or None."""
    manager = LicenseManager()
    cloud_url = manager.cloud_url

    try:
        resp = httpx.get(f"{cloud_url}/v1/release/latest", timeout=10)
        if resp.status_code != 200:
            return None
        release = resp.json()
    except Exception:
        return None

    if not release.get("version"):
        return None

    local = get_local_version(project_root)
    if release["version"] <= local:
        return None

    return release


def verify_sha256(file_path: Path, expected: str) -> bool:
    sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return sha == expected


def verify_release_signature(release: dict) -> bool:
    sig = release.get("signature", "")
    if not sig:
        return False
    manager = LicenseManager()
    if manager.public_key is None:
        return False
    payload = f"{release['version']}|{release['url']}|{release['sha256']}"
    ok, _ = manager._verify_signature(payload, sig)
    return ok


def install_release(project_root: Path, release: dict) -> bool:
    """Download, verify, backup, and install a release. Returns True on success."""
    url = release["url"]
    expected_sha = release["sha256"]

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        # Download
        with httpx.stream("GET", url, timeout=300, follow_redirects=True) as resp:
            if resp.status_code != 200:
                return False
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=8192):
                    f.write(chunk)

        # Verify SHA256
        if not verify_sha256(tmp_path, expected_sha):
            return False

        # Verify Ed25519 signature
        if not verify_release_signature(release):
            return False

        # Backup current web/
        web_dir = project_root / "web"
        backup_dir = project_root / BACKUP_DIR
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        if web_dir.exists():
            shutil.copytree(web_dir, backup_dir)

        # Extract and overwrite
        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(project_root)

        # Update version file
        (project_root / VERSION_FILE).write_text(release["version"])

        return True

    except Exception:
        # Rollback
        backup_dir = project_root / BACKUP_DIR
        web_dir = project_root / "web"
        if backup_dir.exists():
            if web_dir.exists():
                shutil.rmtree(web_dir)
            shutil.move(str(backup_dir), str(web_dir))
        return False

    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


def try_auto_update(project_root: Path) -> bool:
    """Perform auto-update if newer version available. Non-blocking, safe.

    Returns True if update succeeded or no update needed.
    Returns False if update failed (old version still running).
    """
    release = check_update(project_root)
    if release is None:
        return True  # No update needed

    print(f"[updater] New version {release['version']} available, updating...")
    ok = install_release(project_root, release)
    if ok:
        print(f"[updater] Updated to {release['version']}")
    else:
        print("[updater] Update failed, continuing with current version")
    return ok
