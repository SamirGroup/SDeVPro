"""Schedules, consent, scan history, and per-user settings — backed by
``kvstore.get_store()`` (local JSON files by default, optional Upstash
Redis for serverless deployments).
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field

from sdevpro import crypto_utils
from sdevpro.i18n import DEFAULT_LANGUAGE
from sdevpro.kvstore import get_store
from sdevpro.scanner.models import ScanResult


_lock = threading.Lock()

_SCHEDULES_KEY = "schedules"


@dataclass
class ScheduleEntry:
    chat_id: int
    target: str
    interval_minutes: int
    created_by: int | None = None
    scan_mode: str = "quick"

    def key(self) -> str:
        return f"{self.chat_id}::{self.target}"


def load_schedules() -> list[ScheduleEntry]:
    with _lock:
        data = get_store().get(_SCHEDULES_KEY) or {}
    return [ScheduleEntry(**item) for item in data.get("schedules", [])]


def save_schedule(entry: ScheduleEntry) -> None:
    with _lock:
        store = get_store()
        data = store.get(_SCHEDULES_KEY) or {}
        schedules = [ScheduleEntry(**item) for item in data.get("schedules", [])]
        schedules = [s for s in schedules if s.key() != entry.key()]
        schedules.append(entry)
        store.set(_SCHEDULES_KEY, {"schedules": [asdict(s) for s in schedules]})


def remove_schedule(chat_id: int, target: str) -> bool:
    with _lock:
        store = get_store()
        data = store.get(_SCHEDULES_KEY) or {}
        schedules = [ScheduleEntry(**item) for item in data.get("schedules", [])]
        remaining = [s for s in schedules if s.key() != f"{chat_id}::{target}"]
        removed = len(remaining) != len(schedules)
        store.set(_SCHEDULES_KEY, {"schedules": [asdict(s) for s in remaining]})
        return removed


def list_schedules_for_chat(chat_id: int) -> list[ScheduleEntry]:
    return [s for s in load_schedules() if s.chat_id == chat_id]


def _history_key(chat_id: int) -> str:
    return f"history::{chat_id}"


def save_last_result(chat_id: int, result: ScanResult) -> None:
    with _lock:
        get_store().set(_history_key(chat_id), {"last_result": result.to_dict()})


def load_last_result(chat_id: int) -> ScanResult | None:
    with _lock:
        data = get_store().get(_history_key(chat_id)) or {}
    raw = data.get("last_result")
    return ScanResult.from_dict(raw) if raw else None


def _consent_key(chat_id: int) -> str:
    return f"consent::{chat_id}"


def has_consented(chat_id: int) -> bool:
    with _lock:
        data = get_store().get(_consent_key(chat_id))
    return bool(data)


def record_consent(chat_id: int) -> None:
    with _lock:
        get_store().set(_consent_key(chat_id), True)


# ---------------------------------------------------------------------------
# Per-user settings: language + LLM model/API key (bring-your-own-token) +
# optional GitHub token for private repo scans.
# ---------------------------------------------------------------------------


@dataclass
class UserSettings:
    user_id: int
    language: str = DEFAULT_LANGUAGE
    llm_model: str = ""
    llm_api_key_encrypted: str = ""
    llm_api_base: str = ""
    github_token_encrypted: str = ""

    def has_llm_key(self) -> bool:
        return bool(self.llm_model and self.llm_api_key_encrypted)

    def decrypted_llm_api_key(self) -> str:
        return crypto_utils.decrypt_text(self.llm_api_key_encrypted)

    def decrypted_github_token(self) -> str:
        return crypto_utils.decrypt_text(self.github_token_encrypted)


def _user_key(user_id: int) -> str:
    return f"user::{user_id}"


def get_user_settings(user_id: int) -> UserSettings:
    with _lock:
        data = get_store().get(_user_key(user_id))
    if not data:
        return UserSettings(user_id=user_id)
    known = {f.name for f in UserSettings.__dataclass_fields__.values()}
    return UserSettings(**{k: v for k, v in data.items() if k in known})


def save_user_settings(settings: UserSettings) -> None:
    with _lock:
        get_store().set(_user_key(settings.user_id), asdict(settings))


def set_user_language(user_id: int, language: str) -> UserSettings:
    settings = get_user_settings(user_id)
    settings.language = language
    save_user_settings(settings)
    return settings


def set_user_llm_key(user_id: int, model: str, api_key: str, api_base: str = "") -> UserSettings:
    settings = get_user_settings(user_id)
    settings.llm_model = model
    settings.llm_api_key_encrypted = crypto_utils.encrypt_text(api_key)
    settings.llm_api_base = api_base
    save_user_settings(settings)
    return settings


def delete_user_llm_key(user_id: int) -> bool:
    settings = get_user_settings(user_id)
    had_key = settings.has_llm_key()
    settings.llm_model = ""
    settings.llm_api_key_encrypted = ""
    settings.llm_api_base = ""
    save_user_settings(settings)
    return had_key


def set_user_github_token(user_id: int, token: str) -> UserSettings:
    settings = get_user_settings(user_id)
    settings.github_token_encrypted = crypto_utils.encrypt_text(token)
    save_user_settings(settings)
    return settings
