"""One-shot migration: strix/ -> sdevpro/engine/, with all references updated.

Throwaway script — deleted after running. Ordered, context-aware text
substitutions so path-style ("strix/bin/...") and Python dotted-import
("strix.core...") references get the right replacement instead of a single
blind regex mangling one or the other.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent

# Ordered (most-specific-first) literal/regex substitutions.
SPECIAL_LITERALS = [
    ("strix/bin/strix-tui", "sdevpro/engine/bin/sdevpro-tui"),
    ("strix-tui.exe", "sdevpro-tui.exe"),
    ("strix-tui", "sdevpro-tui"),
    ("strix.spec", "sdevpro.spec"),
    ("strix-agent", "sdevpro-agent"),
    ("strix-sandbox", "sdevpro-sandbox"),
    ("strix-codex", "sdevpro-codex"),
    ("strix-viewer", "sdevpro-viewer"),
    ("strix-triage", "sdevpro-triage"),
    ("strix-finding", "sdevpro-finding"),
    ("strix-report", "sdevpro-report"),
    ("strix-run", "sdevpro-run"),
    ("strix-ai", "sdevpro-ai"),
    ("Strix-owned", "SDeVPro-owned"),
    ("Strix-specific", "SDeVPro-specific"),
]

PATH_STYLE_RE = re.compile(r"\bstrix/")
WORD_RE = re.compile(r"\bstrix\b")
WORD_CAP_RE = re.compile(r"\bStrix\b")

PY_EXTS = {".py"}
BUILD_FILES = {
    "Makefile",
    ".pre-commit-config.yaml",
}
BUILD_GLOB_DIRS = ["scripts", "containers"]


def transform_python(text: str) -> str:
    for old, new in SPECIAL_LITERALS:
        text = text.replace(old, new)
    text = PATH_STYLE_RE.sub("sdevpro/engine/", text)
    text = WORD_RE.sub("sdevpro.engine", text)
    text = WORD_CAP_RE.sub("SDeVPro", text)
    return text


def transform_build_file(text: str) -> str:
    for old, new in SPECIAL_LITERALS:
        text = text.replace(old, new)
    text = PATH_STYLE_RE.sub("sdevpro/engine/", text)
    # Non-python build/shell/toml files: bare "strix" is always a path/name
    # token here (never a dotted import), so map it to "sdevpro" (not
    # "sdevpro.engine" — dots don't belong in shell/toml identifiers).
    text = WORD_RE.sub("sdevpro", text)
    text = WORD_CAP_RE.sub("SDeVPro", text)
    return text


def main() -> None:
    src = ROOT / "strix"
    dst = ROOT / "sdevpro" / "engine"
    assert src.is_dir(), "strix/ not found"
    assert not dst.exists(), "sdevpro/engine already exists"
    shutil.move(str(src), str(dst))
    print(f"Moved {src} -> {dst}")

    py_files = list(dst.rglob("*.py")) + list((ROOT / "tests").rglob("*.py"))
    changed = 0
    for path in py_files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new_text = transform_python(text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed += 1
    print(f"Updated {changed} Python files")

    build_targets = []
    for name in BUILD_FILES:
        p = ROOT / name
        if p.is_file():
            build_targets.append(p)
    for dirname in BUILD_GLOB_DIRS:
        d = ROOT / dirname
        if d.is_dir():
            build_targets.extend(f for f in d.rglob("*") if f.is_file())
    spec_file = ROOT / "strix.spec"
    if spec_file.is_file():
        build_targets.append(spec_file)

    changed_build = 0
    for path in build_targets:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new_text = transform_build_file(text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed_build += 1
            print(f"  updated: {path.relative_to(ROOT)}")
    print(f"Updated {changed_build} build/tooling files")

    if spec_file.is_file():
        new_spec = ROOT / "sdevpro.spec"
        spec_file.rename(new_spec)
        print(f"Renamed {spec_file.name} -> {new_spec.name}")


if __name__ == "__main__":
    main()
