"""Whitebox probes: local source tree secret/pattern scanning.

Used when the scan target is a local directory path rather than a URL.
Lightweight regex-based equivalents of gitleaks/trufflehog/bandit — not a
replacement for those tools, but requires no extra binaries and runs
natively on Windows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sdevpro.scanner.models import Finding


_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", "vendor", ".next", "target",
}  # fmt: skip

_MAX_FILE_BYTES = 2_000_000
_MAX_FILES = 5000

_SECRET_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("AWS Access Key ID", "critical", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Access Key (heuristic)", "high", re.compile(r"aws_secret_access_key\s*=\s*['\"]?[A-Za-z0-9/+=]{40}")),
    ("Private key block", "critical", re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----")),
    ("Generic API key assignment", "medium", re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]")),
    ("Hardcoded password assignment", "medium", re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"][^'\"\s]{4,}['\"]")),
    ("Slack token", "high", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("Google API key", "high", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("Generic connection string with credentials", "high", re.compile(r"(?i)(mongodb|postgres|mysql|redis)://[^:\s]+:[^@\s]+@")),
    ("GitHub token", "critical", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("JWT-looking secret in source", "low", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
)  # fmt: skip

_DANGEROUS_PATTERNS: tuple[tuple[str, str, str, re.Pattern[str]], ...] = (
    (
        "eval()/exec() ishlatilishi",
        "high",
        "python",
        re.compile(r"\b(eval|exec)\s*\("),
    ),
    (
        "os.system() / shell=True bilan subprocess",
        "high",
        "python",
        re.compile(r"os\.system\(|subprocess\.[A-Za-z_]+\([^)]*shell\s*=\s*True"),
    ),
    (
        "pickle.loads() ishonchsiz ma'lumot bilan",
        "medium",
        "python",
        re.compile(r"pickle\.loads?\("),
    ),
    (
        "yaml.load() SafeLoader'siz",
        "medium",
        "python",
        re.compile(r"yaml\.load\(([^)]*(?!Loader=yaml\.SafeLoader))\)"),
    ),
    (
        "innerHTML ga to'g'ridan-to'g'ri yozish (potensial DOM XSS)",
        "medium",
        "javascript",
        re.compile(r"\.innerHTML\s*="),
    ),
    (
        "SQL so'rovi string-concatenation orqali qurilmoqda",
        "high",
        "generic",
        re.compile(
            r"(SELECT|INSERT|UPDATE|DELETE)\b.{0,80}\"\s*\+|(SELECT|INSERT|UPDATE|DELETE)\b.{0,80}'\s*\+",
            re.IGNORECASE,
        ),
    ),
    (
        "PHP eval()/system()/exec() ishlatilishi",
        "high",
        "php",
        re.compile(r"\b(eval|system|exec|shell_exec|passthru)\s*\("),
    ),
)  # fmt: skip

_TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".php", ".rb", ".go", ".java", ".cs",
    ".env", ".yml", ".yaml", ".json", ".txt", ".cfg", ".ini", ".conf", ".sh",
    ".ps1", ".sql", ".xml", ".toml", ".properties", ".pem", ".key",
}  # fmt: skip


@dataclass
class CodeScanStats:
    files_scanned: int = 0
    files_skipped_binary: int = 0


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if len(files) >= _MAX_FILES:
            break
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def _read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def scan_directory(root_dir: str | Path) -> tuple[list[Finding], CodeScanStats]:
    root = Path(root_dir).expanduser().resolve()
    findings: list[Finding] = []
    stats = CodeScanStats()
    seen_secret_titles: set[tuple[str, str]] = set()

    for path in _iter_files(root):
        if path.suffix.lower() not in _TEXT_EXTENSIONS and path.suffix != "":
            continue
        text = _read_text(path)
        if text is None:
            stats.files_skipped_binary += 1
            continue
        stats.files_scanned += 1
        rel = str(path.relative_to(root))

        for title, severity, pattern in _SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                key = (title, rel)
                if key in seen_secret_titles:
                    continue
                seen_secret_titles.add(key)
                line_no = text.count("\n", 0, match.start()) + 1
                findings.append(
                    Finding(
                        title=f"Manba kodda maxfiy ma'lumot topildi: {title}",
                        severity=severity,
                        category="Secrets Exposure",
                        description=f"'{rel}' faylining {line_no}-qatorida {title.lower()} ko'rinishidagi qiymat aniqlandi.",
                        location=f"{rel}:{line_no}",
                        evidence="[qiymat hisobotda maxfiylik uchun yashiringan]",
                        attack_vector="Manba kod/repo orqali maxfiy kalitlarni olish va ulardan tashqi xizmatlarga kirish uchun foydalanish",
                        remediation="Kalitni darhol bekor qiling (rotate), kodni tozalab, muhit o'zgaruvchilari/secret manager orqali saqlang.",
                        source_probe="code_scan.secrets",
                    )
                )

        for title, severity, lang, pattern in _DANGEROUS_PATTERNS:
            match = pattern.search(text)
            if match:
                line_no = text.count("\n", 0, match.start()) + 1
                findings.append(
                    Finding(
                        title=f"Xavfli kod naqshi: {title}",
                        severity=severity,
                        category="Insecure Code Pattern",
                        description=f"'{rel}' faylining {line_no}-qatorida xavfli konstruksiya topildi ({lang}).",
                        location=f"{rel}:{line_no}",
                        evidence=match.group(0)[:200],
                        remediation="Ushbu konstruksiyani xavfsizroq alternativaga almashtiring va foydalanuvchi kiritmalarini tekshiring.",
                        source_probe="code_scan.dangerous_pattern",
                    )
                )

    return findings, stats
