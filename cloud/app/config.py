"""Cloud service configuration — all values from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ──
    database_url: str = "postgresql+asyncpg://thesismind:thesismind@localhost:5432/thesismind"

    # ── License signing keypair ──
    license_private_key: str = ""  # PEM or base64url 32-byte Ed25519
    license_public_key: str = ""   # PEM or base64url 32-byte Ed25519

    # ── CDN ──
    cdn_base_url: str = "https://cdn.thesismind.com"

    # ── Rate limiting ──
    rate_limit_per_ip: int = 100  # requests per hour

    # ── Trial ──
    trial_days: int = 3
    max_devices_per_license_basic: int = 1
    max_devices_per_license_pro: int = 2
    max_devices_per_license_vip: int = 3

    # ── License ticket TTL ──
    ticket_ttl_minutes: int = 5

    # ── Logging ──
    log_level: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
