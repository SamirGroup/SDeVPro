"""Server-log attack-source analysis.

Parses common web-server access-log formats (nginx/Apache combined log, and
a generic fallback) and flags IPs whose requests match known attack
signatures, scanner user-agents, or unusually high request-volume bursts.

This is heuristic, offline, best-effort analysis of logs the client uploads
themselves — SDeVPro has no direct access to their infrastructure. It is not
a replacement for a real SIEM, but gives a fast, actionable first read.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from sdevpro.i18n import DEFAULT_LANGUAGE, t

_COMBINED_LOG_RE = re.compile(
    r'(?P<ip>[\da-fA-F:.]+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<method>[A-Z]+)\s+(?P<path>\S+)\s+[^"]*"\s+'
    r'(?P<status>\d{3})\s+(?P<size>\S+)'
    r'(?:\s+"(?P<referer>[^"]*)"\s+"(?P<ua>[^"]*)")?'
)

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

# (signature_id, severity, pattern) — signature_id maps to an i18n key
# "sig_<id>" resolved at report-format time, so this module has no
# language-specific text of its own.
_ATTACK_SIGNATURES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("sqli", "critical", re.compile(r"(?i)(union\s+select|or\s+1=1|sleep\(\d+\)|'\s*or\s*'1'\s*=\s*'1|information_schema|--\s|;drop\s+table)")),
    ("traversal", "high", re.compile(r"(\.\./){2,}|%2e%2e%2f|/etc/passwd|boot\.ini")),
    ("xss", "high", re.compile(r"(?i)(<script|onerror=|onload=|javascript:|%3Cscript)")),
    ("cmdi", "critical", re.compile(r"(?i)(;|\||`)\s*(cat|whoami|wget|curl|nc|bash|sh)\s")),
    ("wp_bruteforce", "medium", re.compile(r"(?i)(wp-login\.php|wp-admin|xmlrpc\.php)")),
    ("sensitive_path", "medium", re.compile(r"(?i)(\.env|\.git/config|id_rsa|\.aws/credentials|phpinfo\.php|config\.php\.bak)")),
    ("scanner_ua", "medium", re.compile(r"(?i)(sqlmap|nikto|nmap|nuclei|acunetix|masscan|dirbuster|gobuster|wpscan)")),
    ("admin_probe", "low", re.compile(r"(?i)(/admin|/administrator|/phpmyadmin|/manager/html)")),
)  # fmt: skip

_RATE_BURST_THRESHOLD = 50  # requests from a single IP in the uploaded log to flag as a burst


@dataclass
class IpFinding:
    ip: str
    score: int = 0
    total_requests: int = 0
    signature_hits: Counter[str] = field(default_factory=Counter)  # keyed by signature_id
    status_counts: Counter[str] = field(default_factory=Counter)
    sample_lines: list[str] = field(default_factory=list)
    user_agents: set[str] = field(default_factory=set)


@dataclass
class LogAnalysisResult:
    total_lines: int = 0
    parsed_lines: int = 0
    suspicious_ips: list[IpFinding] = field(default_factory=list)
    top_paths_hit: Counter[str] = field(default_factory=Counter)


_SEVERITY_WEIGHT = {"critical": 10, "high": 6, "medium": 3, "low": 1}


def analyze_log_text(text: str, *, max_sample_lines_per_ip: int = 3) -> LogAnalysisResult:
    result = LogAnalysisResult()
    per_ip: dict[str, IpFinding] = defaultdict(lambda: IpFinding(ip=""))

    lines = text.splitlines()
    result.total_lines = len(lines)

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        match = _COMBINED_LOG_RE.search(line)
        if match:
            ip = match.group("ip")
            path = match.group("path") or ""
            status = match.group("status") or ""
            ua = match.group("ua") or ""
            result.parsed_lines += 1
        else:
            ip_match = _IP_RE.search(line)
            if not ip_match:
                continue
            ip = ip_match.group(0)
            path = line
            status = ""
            ua = ""

        finding = per_ip[ip]
        finding.ip = ip
        finding.total_requests += 1
        if status:
            finding.status_counts[status] += 1
        if ua:
            finding.user_agents.add(ua[:120])
        if path:
            result.top_paths_hit[path[:200]] += 1

        for sig_id, severity, pattern in _ATTACK_SIGNATURES:
            haystack = f"{path} {ua}"
            if pattern.search(haystack):
                finding.signature_hits[sig_id] += 1
                finding.score += _SEVERITY_WEIGHT.get(severity, 1)
                if len(finding.sample_lines) < max_sample_lines_per_ip:
                    finding.sample_lines.append(line[:300])

    for finding in per_ip.values():
        if finding.total_requests >= _RATE_BURST_THRESHOLD:
            finding.signature_hits["rate_burst"] += 1
            finding.score += min(finding.total_requests // _RATE_BURST_THRESHOLD, 10) * 2
        error_ratio_hits = finding.status_counts.get("404", 0) + finding.status_counts.get("403", 0)
        if finding.total_requests > 20 and error_ratio_hits / max(finding.total_requests, 1) > 0.6:  # noqa: PLR2004
            finding.signature_hits["error_bruteforce"] += 1
            finding.score += 4
        if finding.score > 0:
            result.suspicious_ips.append(finding)

    result.suspicious_ips.sort(key=lambda f: f.score, reverse=True)
    return result


def format_report(result: LogAnalysisResult, lang: str = DEFAULT_LANGUAGE, *, top_n: int = 15) -> str:
    lines: list[str] = []
    lines.append(t(lang, "log_report_title"))
    lines.append("")
    lines.append(t(lang, "log_report_totals", total=result.total_lines, parsed=result.parsed_lines))
    lines.append(t(lang, "log_report_suspicious_count", count=len(result.suspicious_ips)))
    lines.append("")

    if not result.suspicious_ips:
        lines.append(t(lang, "log_report_none"))
        return "\n".join(lines)

    lines.append(t(lang, "log_report_top_header"))
    for finding in result.suspicious_ips[:top_n]:
        lines.append("")
        lines.append(
            t(lang, "log_report_ip_line", ip=finding.ip, score=finding.score, total=finding.total_requests)
        )
        for sig_id, count in finding.signature_hits.most_common(5):
            lines.append(f"   - {t(lang, f'sig_{sig_id}')} ({count}x)")
        if finding.user_agents:
            ua_sample = next(iter(finding.user_agents))
            lines.append(f"   UA: {ua_sample[:100]}")

    lines.append("")
    lines.append(t(lang, "log_report_tip"))
    return "\n".join(lines)
