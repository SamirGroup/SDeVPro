"""Scan orchestration: recon + web/code probes -> AI triage -> ScanResult."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sdevpro import github_scan
from sdevpro.i18n import DEFAULT_LANGUAGE, t
from sdevpro.scanner import recon, web_probes
from sdevpro.scanner.code_scan import scan_directory
from sdevpro.scanner.models import Finding, ScanResult
from sdevpro.scanner.recon import fetch_http, normalize_url


logger = logging.getLogger("sdevpro.engine")

ProgressCallback = Callable[[str], None]


def _looks_like_local_path(target: str) -> bool:
    if target.startswith(("http://", "https://")):
        return False
    candidate = Path(target).expanduser()
    return candidate.exists() and candidate.is_dir()


async def _run_whitebox(target_dir: str, result: ScanResult, report: Callable[[str], None], lang: str) -> None:
    report(t(lang, "progress_codescan_started"))
    findings, stats = scan_directory(target_dir)
    result.findings.extend(findings)
    result.raw_evidence["code_scan_stats"] = {
        "files_scanned": stats.files_scanned,
        "files_skipped_binary": stats.files_skipped_binary,
    }
    report(t(lang, "progress_codescan_done", files=stats.files_scanned))


async def _run_github(target: str, github_token: str, result: ScanResult, report: Callable[[str], None], lang: str) -> None:
    if not github_scan.git_available():
        result.error = t(lang, "no_git")
        return
    report(t(lang, "progress_github_cloning", target=target))
    cloned_dir = None
    try:
        cloned_dir = github_scan.clone_repo(target, github_token)
        report(t(lang, "progress_github_cloned"))
        await _run_whitebox(str(cloned_dir), result, report, lang)
    except github_scan.CloneFailedError:
        result.error = t(lang, "github_clone_failed")
    finally:
        if cloned_dir is not None:
            github_scan.cleanup(cloned_dir)


async def _run_web(url: str, result: ScanResult, report: Callable[[str], None], lang: str) -> None:
    report(t(lang, "progress_recon_started", target=url))
    recon_result = await recon.run_recon(url)
    result.raw_evidence["recon"] = {
        "resolved_ips": recon_result.resolved_ips,
        "dns_records": recon_result.dns_records,
        "open_ports": recon_result.open_ports,
        "http_status": recon_result.http_status,
        "detected_tech": recon_result.detected_tech,
        "tls_info": {k: v for k, v in recon_result.tls_info.items() if k != "cipher"},
    }
    report(
        t(
            lang,
            "progress_recon_done",
            ports=len(recon_result.open_ports),
            tech=len(recon_result.detected_tech),
        )
    )

    if recon_result.open_ports:
        result.findings.append(
            Finding(
                title=f"Ochiq portlar aniqlandi: {', '.join(map(str, recon_result.open_ports))}",
                severity="info",
                category="Reconnaissance",
                description="Quyidagi TCP portlar tashqi tarmoqdan ulanish uchun ochiq.",
                location=url,
                source_probe="recon.port_scan",
            )
        )

    tls_expiry = recon_result.tls_info.get("days_until_expiry")
    if isinstance(tls_expiry, int) and tls_expiry < 30:  # noqa: PLR2004
        result.findings.append(
            Finding(
                title=f"SSL sertifikat muddati tez orada tugaydi ({tls_expiry} kun qoldi)",
                severity="high" if tls_expiry < 7 else "medium",  # noqa: PLR2004
                category="Security Misconfiguration",
                description="Sertifikat muddati tugasa, sayt brauzerlarda ishonchsiz deb belgilanadi.",
                location=url,
                remediation="Sertifikatni muddati tugashidan oldin yangilang (avtomatik yangilanishni sozlang, masalan Let's Encrypt/certbot).",
                source_probe="recon.tls",
            )
        )
    if "error" in recon_result.tls_info:
        result.findings.append(
            Finding(
                title="TLS/SSL bilan bog'lanishda muammo",
                severity="medium",
                category="Security Misconfiguration",
                description=str(recon_result.tls_info.get("error")),
                location=url,
                source_probe="recon.tls",
            )
        )

    report(t(lang, "progress_webprobe_started"))
    response, _chain, _err = await fetch_http(url)
    probe_findings = await web_probes.run_web_probes(url, recon_result.http_headers, response)
    result.findings.extend(probe_findings)
    report(t(lang, "progress_webprobe_done", count=len(probe_findings)))


async def run_scan(
    target: str,
    *,
    scan_mode: str = "quick",
    on_progress: ProgressCallback | None = None,
    use_ai: bool = True,
    llm_model: str = "",
    llm_api_key: str = "",
    llm_api_base: str = "",
    github_token: str = "",
    language: str = DEFAULT_LANGUAGE,
) -> ScanResult:
    def report(message: str) -> None:
        logger.info(message)
        if on_progress:
            on_progress(message)

    is_github = github_scan.is_git_repo_url(target)
    whitebox = is_github or _looks_like_local_path(target)
    target_kind = "github" if is_github else ("whitebox" if whitebox else "web")
    result = ScanResult(
        target=target, scan_mode=scan_mode, whitebox=whitebox, target_kind=target_kind, language=language
    )

    try:
        if is_github:
            await _run_github(target, github_token, result, report, language)
        elif whitebox:
            await _run_whitebox(target, result, report, language)
        else:
            await _run_web(normalize_url(target), result, report, language)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scan failed for %s", target)
        result.error = str(exc)

    if use_ai and (result.findings or result.raw_evidence):
        report(t(language, "progress_ai_analyzing"))
        try:
            from sdevpro.ai_analyst import triage_scan

            await triage_scan(
                result,
                model=llm_model,
                api_key=llm_api_key,
                api_base=llm_api_base,
                language=language,
            )
            report(t(language, "progress_ai_done"))
        except Exception:
            logger.exception("AI triage failed")
            result.summary = result.summary or t(language, "ai_failed_fallback")

    result.finished_at = datetime.now(UTC).isoformat()
    return result
