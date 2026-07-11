"""Application configuration.

Reads settings from environment variables with safe local-dev defaults.
No `.env` file is required to run the service. This intentionally does not
use `pydantic-settings` to avoid adding an extra dependency for a handful
of simple values (AGENT_RULES.md rule 11 — ask before adding heavy deps).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _str_to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    log_path: str
    enable_audit_log: bool


def load_settings() -> Settings:
    """Read settings fresh from the current environment.

    Exposed separately from the module-level `settings` singleton so tests
    can construct alternate configurations without monkeypatching env vars.
    """
    return Settings(
        app_env=os.getenv("APP_ENV", "dev"),
        log_path=os.getenv("LOG_PATH", "logs/audit.jsonl"),
        enable_audit_log=_str_to_bool(os.getenv("ENABLE_AUDIT_LOG", "true")),
    )


settings = load_settings()
