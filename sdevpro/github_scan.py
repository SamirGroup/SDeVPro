"""GitHub repository scanning: clone (public or token-authenticated private
repos) into a temp directory and run the same whitebox code scan used for
local paths.

Requires the ``git`` binary on PATH. No GitHub SDK/API dependency — a plain
shallow ``git clone`` is enough and works identically for any git host, not
just GitHub.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


_GITHUB_URL_RE = re.compile(
    r"^https?://(www\.)?(github|gitlab)\.com/[^/\s]+/[^/\s]+/?", re.IGNORECASE
)


class GitNotAvailableError(RuntimeError):
    pass


class CloneFailedError(RuntimeError):
    pass


def is_git_repo_url(target: str) -> bool:
    return bool(_GITHUB_URL_RE.match(target.strip()))


def git_available() -> bool:
    return shutil.which("git") is not None


def _with_token(url: str, token: str) -> str:
    parts = urlsplit(url)
    netloc = f"{token}@{parts.netloc}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def clone_repo(url: str, token: str = "", *, timeout: int = 120) -> Path:
    """Shallow-clone ``url`` into a fresh temp directory and return its path.

    Caller is responsible for removing the returned directory (see
    ``cleanup``). Raises ``GitNotAvailableError`` / ``CloneFailedError``.
    """
    if not git_available():
        raise GitNotAvailableError("git is not installed on this host")

    clone_url = _with_token(url, token) if token else url
    dest = Path(tempfile.mkdtemp(prefix="sdevpro_repo_"))
    try:
        subprocess.run(  # noqa: S603
            ["git", "clone", "--depth", "1", "--quiet", clone_url, str(dest)],  # noqa: S607
            check=True,
            timeout=timeout,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        shutil.rmtree(dest, ignore_errors=True)
        # Never let the token-embedded clone URL (present in exc.cmd /
        # str(exc)) reach logs or a chat message.
        raise CloneFailedError(f"git clone failed for {url}") from None
    return dest


def cleanup(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
