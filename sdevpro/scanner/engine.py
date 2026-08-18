"""Scan orchestration: recon + web/code probes -> AI triage -> ScanResult."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

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


async def run_scan(
    target: str,
    *,
    scan_mode: str = "quick",
    on_progress: ProgressCallback | None = None,
    use_ai: bool = True,
) -> ScanResult:
    def report(message: str) -> None:
        logger.info(message)
        if on_progress:
            on_progress(message)

    whitebox = _looks_like_local_path(target)
    result = ScanResult(target=target, scan_mode=scan_mode, whitebox=whitebox)

    try:
        if whitebox:
            report("Manba kod tekshirilmoqda (secrets, xavfli naqshlar)...")
            findings, stats = scan_directory(target)
            result.findings.extend(findings)
            result.raw_evidence["code_scan_stats"] = {
                "files_scanned": stats.files_scanned,
                "files_skipped_binary": stats.files_skipped_binary,
            }
            report(f"Kod skanerlash tugadi: {stats.files_scanned} fayl tekshirildi.")
        else:
            url = normalize_url(target)
            report(f"Recon boshlandi: {url}")
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
                f"Recon tugadi: {len(recon_result.open_ports)} ochiq port, "
                f"{len(recon_result.detected_tech)} texnologiya aniqlandi."
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
            if isinstance(tls_expiry, int) and tls_expiry < 30:
                result.findings.append(
                    Finding(
                        title=f"SSL sertifikat muddati tez orada tugaydi ({tls_expiry} kun qoldi)",
                        severity="high" if tls_expiry < 7 else "medium",
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

            report("Web zaifliklar tekshirilmoqda (XSS, SQLi, CORS, maxfiy fayllar)...")
            response, _chain, _err = await fetch_http(url)
            probe_findings = await web_probes.run_web_probes(url, recon_result.http_headers, response)
            result.findings.extend(probe_findings)
            report(f"Web probe tugadi: {len(probe_findings)} topilma.")

    except Exception as exc:  # noqa: BLE001
        logger.exception("scan failed for %s", target)
        result.error = str(exc)

    if use_ai and (result.findings or result.raw_evidence):
        report("AI tahlilchisi topilmalarni baholamoqda...")
        try:
            from sdevpro.ai_analyst import triage_scan

            await triage_scan(result)
            report("AI tahlili tugadi.")
        except Exception as exc:  # noqa: BLE001
            logger.exception("AI triage failed")
            result.summary = result.summary or (
                "AI tahlili muvaffaqiyatsiz tugadi; quyida xom (AI ishlov bermagan) topilmalar keltirilgan. "
                f"Xato: {exc}"
            )

    result.finished_at = datetime.now(UTC).isoformat()
    return result
