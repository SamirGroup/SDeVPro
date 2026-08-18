"""Follow-up pass: STRIX_<NAME> env-var tokens -> SDEVPRO_<NAME>.

Throwaway script. The main migration only handled lowercase "strix" /
capitalized "Strix"; every all-caps "STRIX_*" env var name (STRIX_LLM,
STRIX_DEBUG, STRIX_RUNTIME_BACKEND, ...) was untouched and needs its own
case-preserving pass.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent

ALLCAPS_RE = re.compile(r"\bSTRIX_")
ALLCAPS_BARE_RE = re.compile(r"\bSTRIX\b(?!_)")

TARGET_DIRS = [
    ROOT / "sdevpro" / "engine",
    ROOT / "tests",
    ROOT / "scripts",
    ROOT / "containers",
    ROOT / ".github",
]
TARGET_FILES = [
    ROOT / "Makefile",
    ROOT / "sdevpro.spec",
    ROOT / ".pre-commit-config.yaml",
]

EXTS = {".py", ".sh", ".ps1", ".yml", ".yaml", ".spec", ".dockerfile", ""}


def should_process(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() not in EXTS and path.name not in {"Dockerfile", "Makefile", "docker-entrypoint.sh"}:
        return False
    return True


def main() -> None:
    files: list[Path] = []
    for d in TARGET_DIRS:
        if d.is_dir():
            files.extend(f for f in d.rglob("*") if should_process(f))
    files.extend(f for f in TARGET_FILES if f.is_file())

    changed = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new_text = ALLCAPS_RE.sub("SDEVPRO_", text)
        new_text = ALLCAPS_BARE_RE.sub("SDEVPRO", new_text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed += 1
            print(f"  updated: {path.relative_to(ROOT)}")
    print(f"Updated {changed} files (STRIX_* -> SDEVPRO_*)")


if __name__ == "__main__":
    main()
