"""Small JSON-file-backed persistence for schedules, consent, and scan history.

Scale target is one operator's bot serving a handful of clients — a real
database would be overkill. Every write is atomic (write to a temp file,
then replace) so a crash mid-write cannot corrupt the store.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sdevpro.config import get_settings
from sdevpro.scanner.models import ScanResult


_lock = threading.Lock()


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


@dataclass
class ScheduleEntry:
    chat_id: int
    target: str
    interval_minutes: int
    created_by: int | None = None
    scan_mode: str = "quick"

    def key(self) -> str:
        return f"{self.chat_id}::{self.target}"


def _schedules_path() -> Path:
    return get_settings().data_dir / "schedules" / "schedules.json"


def load_schedules() -> list[ScheduleEntry]:
    with _lock:
        data = _read_json(_schedules_path())
    return [ScheduleEntry(**item) for item in data.get("schedules", [])]


def save_schedule(entry: ScheduleEntry) -> None:
    with _lock:
        path = _schedules_path()
        data = _read_json(path)
        schedules = [ScheduleEntry(**item) for item in data.get("schedules", [])]
        schedules = [s for s in schedules if s.key() != entry.key()]
        schedules.append(entry)
        _atomic_write(path, {"schedules": [asdict(s) for s in schedules]})


def remove_schedule(chat_id: int, target: str) -> bool:
    with _lock:
        path = _schedules_path()
        data = _read_json(path)
        schedules = [ScheduleEntry(**item) for item in data.get("schedules", [])]
        remaining = [s for s in schedules if s.key() != f"{chat_id}::{target}"]
        removed = len(remaining) != len(schedules)
        _atomic_write(path, {"schedules": [asdict(s) for s in remaining]})
        return removed


def list_schedules_for_chat(chat_id: int) -> list[ScheduleEntry]:
    return [s for s in load_schedules() if s.chat_id == chat_id]


def _history_path(chat_id: int) -> Path:
    return get_settings().data_dir / "history" / f"{chat_id}.json"


def save_last_result(chat_id: int, result: ScanResult) -> None:
    with _lock:
        _atomic_write(_history_path(chat_id), {"last_result": result.to_dict()})


def load_last_result(chat_id: int) -> ScanResult | None:
    with _lock:
        data = _read_json(_history_path(chat_id))
    raw = data.get("last_result")
    return ScanResult.from_dict(raw) if raw else None


_consent_lock = threading.Lock()


def _consent_path() -> Path:
    return get_settings().data_dir / "consent.json"


def has_consented(chat_id: int) -> bool:
    with _consent_lock:
        data = _read_json(_consent_path())
    return bool(data.get(str(chat_id)))


def record_consent(chat_id: int) -> None:
    with _consent_lock:
        path = _consent_path()
        data = _read_json(path)
        data[str(chat_id)] = True
        _atomic_write(path, data)
