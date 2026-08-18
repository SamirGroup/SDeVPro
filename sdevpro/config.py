"""Configuration loading for the SDeVPro engine and Telegram bot.

Everything is read from environment variables (optionally via a local
``.env`` file loaded with python-dotenv). See ``.env.example`` at the repo
root for the full list with explanations.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path.cwd() / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(override=False)


_load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """SDeVPro runtime configuration, resolved once at process start."""

    telegram_bot_token: str = field(
        default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    )
    allowed_user_ids: frozenset[int] = field(
        default_factory=lambda: frozenset(
            int(v) for v in _env_list("SDEVPRO_ALLOWED_USERS") if v.lstrip("-").isdigit()
        )
    )
    allowed_usernames: frozenset[str] = field(
        default_factory=lambda: frozenset(
            v.lstrip("@").lower() for v in _env_list("SDEVPRO_ALLOWED_USERNAMES")
        )
    )

    llm_model: str = field(
        default_factory=lambda: (
            os.environ.get("SDEVPRO_LLM") or os.environ.get("STRIX_LLM") or ""
        ).strip()
    )
    llm_api_key: str = field(
        default_factory=lambda: (
            os.environ.get("SDEVPRO_LLM_API_KEY") or os.environ.get("LLM_API_KEY") or ""
        ).strip()
    )
    llm_api_base: str = field(
        default_factory=lambda: (
            os.environ.get("SDEVPRO_LLM_API_BASE") or os.environ.get("LLM_API_BASE") or ""
        ).strip()
    )

    default_schedule_minutes: int = field(
        default_factory=lambda: _env_int("SDEVPRO_DEFAULT_SCHEDULE_MINUTES", 60)
    )
    scan_timeout_seconds: int = field(
        default_factory=lambda: _env_int("SDEVPRO_SCAN_TIMEOUT_SECONDS", 600)
    )
    max_dir_bruteforce_workers: int = field(
        default_factory=lambda: _env_int("SDEVPRO_DIRSCAN_CONCURRENCY", 20)
    )
    require_consent: bool = field(
        default_factory=lambda: _env_bool("SDEVPRO_REQUIRE_CONSENT", default=True)
    )

    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("SDEVPRO_DATA_DIR", "sdevpro_data")).resolve()
    )
    log_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("SDEVPRO_LOG_DIR", "sdevpro_data/logs")
        ).resolve()
    )

    report_language: str = field(
        default_factory=lambda: os.environ.get("SDEVPRO_REPORT_LANGUAGE", "uz").strip() or "uz"
    )

    def is_user_allowed(self, user_id: int, username: str | None) -> bool:
        """Access-control check. Empty allow-lists mean 'open to anyone in this chat'."""
        if not self.allowed_user_ids and not self.allowed_usernames:
            return True
        if user_id in self.allowed_user_ids:
            return True
        if username and username.lstrip("@").lower() in self.allowed_usernames:
            return True
        return False

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "schedules").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "history").mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings  # noqa: PLW0603
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings


def reload_settings() -> Settings:
    """Force re-reading environment variables (mainly useful for tests)."""
    global _settings  # noqa: PLW0603
    _settings = Settings()
    _settings.ensure_dirs()
    return _settings
