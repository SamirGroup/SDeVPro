"""Pluggable key -> JSON-value store.

Default backend is local JSON files (``FileKVStore``) — perfect for a
long-running process on a local machine or VPS, which is what this project
targets first. Serverless deployments (Vercel etc.) have no persistent
filesystem between invocations, so an optional Upstash Redis REST backend
(``UpstashKVStore``) is available for that case: set ``UPSTASH_REDIS_REST_URL``
and ``UPSTASH_REDIS_REST_TOKEN`` (both come free from https://upstash.com)
and ``SDEVPRO_STORAGE_BACKEND=redis``.

Both backends store an entire JSON-serializable value per string key —
callers (``storage.py``) decide what goes in each key.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Protocol


class KVStore(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any) -> None: ...


class FileKVStore:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._lock = threading.Lock()

    def _path_for(self, key: str) -> Path:
        safe = key.replace("/", "__").replace("\\", "__").replace(":", "_")
        return self._base_dir / "kv" / f"{safe}.json"

    def get(self, key: str) -> Any | None:
        path = self._path_for(key)
        with self._lock:
            if not path.is_file():
                return None
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None

    def set(self, key: str, value: Any) -> None:
        path = self._path_for(key)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8")
            os.replace(tmp, path)


class UpstashKVStore:
    """Best-effort Upstash Redis REST backend for serverless deployments.

    Uses Upstash's generic command endpoint (``POST {url}`` with a JSON
    command array), which avoids URL-encoding pitfalls that per-path command
    endpoints have for values containing slashes.
    """

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    def _command(self, *parts: str) -> Any | None:
        import requests

        try:
            response = requests.post(
                self._base_url,
                json=list(parts),
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=8,
            )
            response.raise_for_status()
            return response.json().get("result")
        except Exception:  # noqa: BLE001
            return None

    def get(self, key: str) -> Any | None:
        raw = self._command("GET", key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def set(self, key: str, value: Any) -> None:
        self._command("SET", key, json.dumps(value, ensure_ascii=False, default=str))


_store: KVStore | None = None
_store_lock = threading.Lock()


def get_store() -> KVStore:
    global _store  # noqa: PLW0603
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        backend = os.environ.get("SDEVPRO_STORAGE_BACKEND", "file").strip().lower()
        if backend == "redis":
            url = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip()
            token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip()
            if url and token:
                _store = UpstashKVStore(url, token)
                return _store
        from sdevpro.config import get_settings

        _store = FileKVStore(get_settings().data_dir)
        return _store


def reset_store_for_tests() -> None:
    global _store  # noqa: PLW0603
    _store = None
