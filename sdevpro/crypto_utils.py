"""At-rest encryption for per-user secrets (LLM API keys, GitHub tokens).

Key resolution order:
1. ``SDEVPRO_SECRET_KEY`` env var, if set (required for serverless/Vercel
   deployments, where the filesystem is not persistent between invocations).
2. A key auto-generated on first run and saved to
   ``<data_dir>/secret.key`` (0600-ish via plain file permissions on the
   host). Fine for a single-operator local/VPS deployment; losing this file
   means previously-stored user tokens can no longer be decrypted (users
   just re-run /setkey).

This protects secrets against casual disk/backup exposure. It is not a
substitute for a real secrets manager in a multi-operator production
deployment.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import os
from functools import lru_cache
from pathlib import Path


def _derive_key_from_passphrase(passphrase: str) -> bytes:
    digest = hashlib.sha256(passphrase.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _load_or_create_local_key(data_dir: Path) -> bytes:
    key_path = data_dir / "secret.key"
    if key_path.is_file():
        return key_path.read_bytes().strip()

    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    data_dir.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key)
    with contextlib.suppress(Exception):
        os.chmod(key_path, 0o600)
    return key


@lru_cache(maxsize=1)
def _fernet():  # noqa: ANN202
    from cryptography.fernet import Fernet

    from sdevpro.config import get_settings

    env_key = os.environ.get("SDEVPRO_SECRET_KEY", "").strip()
    if env_key:
        try:
            key = env_key.encode("utf-8")
            Fernet(key)  # validate it's a proper 32-byte urlsafe-b64 key
        except Exception:  # noqa: BLE001
            key = _derive_key_from_passphrase(env_key)
    else:
        key = _load_or_create_local_key(get_settings().data_dir)
    return Fernet(key)


def encrypt_text(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_text(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:  # noqa: BLE001
        return ""


def mask_secret(secret: str, keep: int = 4) -> str:
    if not secret:
        return ""
    if len(secret) <= keep:
        return "*" * len(secret)
    return f"{'*' * (len(secret) - keep)}{secret[-keep:]}"
