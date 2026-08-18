"""Active (but non-destructive) web vulnerability probes.

Every payload here is a safe, read-only detection probe — reflection markers,
single-quote error triggers, header/cookie inspection, HEAD/GET requests
against well-known paths. Nothing here writes data, deletes data, or attempts
denial of service. This still constitutes active security testing and must
only ever run against targets the operator is authorized to test — the
Telegram bot enforces an explicit consent step before any scan starts.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlparse

import requests

from sdevpro.scanner.models import Finding
from sdevpro.scanner.recon import DEFAULT_TIMEOUT, USER_AGENT


logger = logging.getLogger("sdevpro.web_probes")

_XSS_MARKER = "sdevpro_xss_9f2c"
_SQLI_ERROR_SIGNATURES = (
    "you have an error in your sql syntax",
    "warning: mysql",
    "unclosed quotation mark",
    "quoted string not properly terminated",
    "sqlstate",
    "pg_query()",
    "sqlite3.operationalerror",
    "ora-01756",
    "microsoft odbc",
    "syntax error at or near",
)

_SENSITIVE_PATHS: tuple[str, ...] = (
    ".git/config", ".git/HEAD", ".env", ".env.local", ".env.production",
    "wp-config.php.bak", "config.php.bak", "backup.zip", "backup.sql",
    "database.sql", ".DS_Store", "web.config", "phpinfo.php",
    ".well-known/security.txt", "server-status", "actuator/env",
    "actuator/health", "debug", "console", ".htaccess", "id_rsa",
    "credentials.json", "docker-compose.yml", ".aws/credentials",
    "swagger.json", "swagger-ui.html", "api/swagger.json",
)  # fmt: skip


def _get(url: str, **kwargs: object) -> requests.Response:
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    kwargs.setdefault("headers", {"User-Agent": USER_AGENT})
    return requests.get(url, **kwargs)  # type: ignore[arg-type]


def security_headers_audit(headers: dict[str, str], base_url: str) -> list[Finding]:
    lower = {k.lower(): v for k, v in headers.items()}
    findings: list[Finding] = []

    checks = [
        (
            "content-security-policy",
            "Content-Security-Policy sarlavhasi yo'q",
            "medium",
            "CSP sarlavhasi XSS va data-injection hujumlarining ta'sirini cheklaydi.",
            "Web-server yoki ilova darajasida mos CSP siyosatini joriy qiling "
            "(masalan: default-src 'self').",
        ),
        (
            "x-content-type-options",
            "X-Content-Type-Options: nosniff yo'q",
            "low",
            "Brauzer MIME-turini 'sniff' qilib, kutilmagan kontentni bajarishi mumkin.",
            "Barcha javoblarga 'X-Content-Type-Options: nosniff' sarlavhasini qo'shing.",
        ),
        (
            "strict-transport-security",
            "HSTS (Strict-Transport-Security) sarlavhasi yo'q",
            "medium",
            "HTTPS-ga majburlovchi HSTS bo'lmasa, foydalanuvchi SSL-strip hujumiga ochiq bo'lishi mumkin.",
            "'Strict-Transport-Security: max-age=31536000; includeSubDomains' sarlavhasini qo'shing.",
        ),
        (
            "referrer-policy",
            "Referrer-Policy sarlavhasi yo'q",
            "low",
            "URL manzillaridagi maxfiy tokenlar/parametrlar tashqi saytlarga referrer orqali oqib ketishi mumkin.",
            "'Referrer-Policy: strict-origin-when-cross-origin' kabi sarlavha qo'shing.",
        ),
        (
            "permissions-policy",
            "Permissions-Policy sarlavhasi yo'q",
            "info",
            "Brauzer imkoniyatlari (camera, geolocation va h.k.) cheklanmagan.",
            "Kerak bo'lmagan brauzer imkoniyatlarini Permissions-Policy orqali o'chiring.",
        ),
    ]  # fmt: skip

    for header_key, title, severity, description, remediation in checks:
        if header_key not in lower:
            findings.append(
                Finding(
                    title=title,
                    severity=severity,
                    category="Security Misconfiguration",
                    description=description,
                    location=base_url,
                    remediation=remediation,
                    source_probe="security_headers_audit",
                )
            )

    xfo = lower.get("x-frame-options", "").lower()
    csp = lower.get("content-security-policy", "").lower()
    if "deny" not in xfo and "sameorigin" not in xfo and "frame-ancestors" not in csp:
        findings.append(
            Finding(
                title="Clickjacking himoyasi yo'q (X-Frame-Options / frame-ancestors)",
                severity="medium",
                category="Security Misconfiguration",
                description=(
                    "Sahifa boshqa domenlar tomonidan <iframe> ichiga joylashtirilishi mumkin, "
                    "bu clickjacking hujumlariga yo'l ochadi."
                ),
                location=base_url,
                attack_vector="Clickjacking / UI redressing",
                remediation=(
                    "X-Frame-Options: DENY yoki CSP frame-ancestors 'none' sarlavhasini qo'shing."
                ),
                source_probe="security_headers_audit",
            )
        )

    server = lower.get("server", "")
    powered_by = lower.get("x-powered-by", "")
    if server or powered_by:
        findings.append(
            Finding(
                title="Server/texnologiya versiyasi HTTP sarlavhada oshkor qilinmoqda",
                severity="info",
                category="Information Disclosure",
                description=f"Server: {server!r}, X-Powered-By: {powered_by!r}",
                location=base_url,
                remediation="Ishlab chiqarish muhitida Server/X-Powered-By sarlavhalarini o'chiring yoki umumiylashtiring.",
                source_probe="security_headers_audit",
            )
        )

    return findings


def cookie_audit(response: requests.Response, base_url: str) -> list[Finding]:
    findings: list[Finding] = []
    for cookie in response.cookies:
        issues = []
        if not cookie.secure:
            issues.append("Secure flag yo'q")
        has_httponly = bool(cookie._rest.get("HttpOnly") or cookie._rest.get("httponly"))  # noqa: SLF001
        if not has_httponly:
            issues.append("HttpOnly flag yo'q")
        samesite = cookie._rest.get("SameSite") or cookie._rest.get("samesite")  # noqa: SLF001
        if not samesite:
            issues.append("SameSite flag yo'q")
        if issues:
            findings.append(
                Finding(
                    title=f"Cookie '{cookie.name}' xavfsiz emas: {', '.join(issues)}",
                    severity="medium" if "Secure flag yo'q" in issues else "low",
                    category="Broken Authentication / Session Management",
                    description=(
                        f"'{cookie.name}' cookie'sida quyidagi flaglar yetishmaydi: "
                        f"{', '.join(issues)}."
                    ),
                    location=base_url,
                    attack_vector="Session hijacking / XSS orqali cookie o'g'irlash",
                    remediation="Cookie'larni Secure; HttpOnly; SameSite=Lax (yoki Strict) bilan o'rnating.",
                    source_probe="cookie_audit",
                )
            )
    return findings


async def cors_probe(url: str) -> list[Finding]:
    findings: list[Finding] = []
    probe_origin = "https://sdevpro-cors-probe.example"
    try:
        response = await asyncio.to_thread(
            _get,
            url,
            headers={"User-Agent": USER_AGENT, "Origin": probe_origin},
        )
    except requests.exceptions.RequestException:
        return findings

    acao = response.headers.get("Access-Control-Allow-Origin", "")
    acac = response.headers.get("Access-Control-Allow-Credentials", "").lower()
    if acao == "*" and acac == "true":
        findings.append(
            Finding(
                title="Xavfli CORS konfiguratsiyasi: '*' + credentials=true",
                severity="high",
                category="Security Misconfiguration",
                description=(
                    "Server 'Access-Control-Allow-Origin: *' bilan birga "
                    "'Access-Control-Allow-Credentials: true' qaytarmoqda — bu holat "
                    "brauzer siyosati bo'yicha odatda taqiqlangan, lekin ba'zi eski/moslashtirilgan "
                    "sozlamalarda uchraydi va juda xavflidir."
                ),
                location=url,
                attack_vector="Cross-origin so'rovlar orqali autentifikatsiyalangan ma'lumotlarni o'g'irlash",
                remediation="Access-Control-Allow-Origin uchun aniq domenlar oq ro'yxatini ishlating, '*' ishlatmang.",
                source_probe="cors_probe",
            )
        )
    elif acao == probe_origin:
        findings.append(
            Finding(
                title="CORS: har qanday Origin qaytarib yuborilmoqda (reflected origin)",
                severity="medium",
                category="Security Misconfiguration",
                description=(
                    "Server so'rovda yuborilgan istalgan Origin qiymatini "
                    "Access-Control-Allow-Origin sifatida qaytarmoqda."
                ),
                location=url,
                attack_vector="Cross-origin ma'lumot sizib chiqishi",
                remediation="Faqat ishonchli domenlar ro'yxatini CORS orqali ruxsat bering.",
                source_probe="cors_probe",
            )
        )
    return findings


async def reflected_xss_probe(url: str) -> list[Finding]:
    findings: list[Finding] = []
    parsed = urlparse(url)
    if not parsed.query:
        return findings
    params = dict(pair.split("=", 1) if "=" in pair else (pair, "") for pair in parsed.query.split("&"))
    for param in list(params)[:8]:
        test_params = dict(params)
        test_params[param] = f"<{_XSS_MARKER}>"
        test_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(test_params)}"
        try:
            response = await asyncio.to_thread(_get, test_url)
        except requests.exceptions.RequestException:
            continue
        if f"<{_XSS_MARKER}>" in response.text:
            findings.append(
                Finding(
                    title=f"Ehtimoliy reflected XSS: '{param}' parametri",
                    severity="high",
                    category="Cross-Site Scripting (XSS)",
                    description=(
                        f"'{param}' GET-parametriga yuborilgan HTML belgi (<...>) hech qanday "
                        "encode qilinmasdan javobda aynan qaytdi — bu reflected XSS ehtimolini bildiradi."
                    ),
                    location=test_url,
                    evidence=f"Test payload '<{_XSS_MARKER}>' javobda o'zgarishsiz topildi.",
                    attack_vector="Zararli <script> havolasini qurbonga yuborish orqali sessiya/cookie o'g'irlash",
                    remediation=(
                        "Foydalanuvchi kiritgan barcha ma'lumotlarni chiqishda (output) kontekstga mos "
                        "encode qiling (HTML-escape) va Content-Security-Policy qo'llang."
                    ),
                    cwe="CWE-79",
                    source_probe="reflected_xss_probe",
                )
            )
    return findings


async def sqli_error_probe(url: str) -> list[Finding]:
    findings: list[Finding] = []
    parsed = urlparse(url)
    if not parsed.query:
        return findings
    params = dict(pair.split("=", 1) if "=" in pair else (pair, "") for pair in parsed.query.split("&"))
    for param in list(params)[:8]:
        test_params = dict(params)
        test_params[param] = params[param] + "'"
        test_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(test_params)}"
        try:
            response = await asyncio.to_thread(_get, test_url)
        except requests.exceptions.RequestException:
            continue
        lowered = response.text.lower()
        if any(sig in lowered for sig in _SQLI_ERROR_SIGNATURES):
            findings.append(
                Finding(
                    title=f"Ehtimoliy SQL Injection: '{param}' parametri",
                    severity="critical",
                    category="Injection",
                    description=(
                        f"'{param}' parametriga yolg'iz qo'shtirnoq (') qo'shilganda javobda "
                        "ma'lumotlar bazasi xatolik xabari aniqlandi — bu SQL so'rovga xom kiritilgan "
                        "ma'lumot to'g'ridan-to'g'ri qo'shilayotganidan dalolat beradi."
                    ),
                    location=test_url,
                    evidence="Javobda SQL xato signaturasi topildi (aniq xabar hisobotda yashiringan).",
                    attack_vector="SQL Injection orqali ma'lumotlar bazasini o'qish/o'zgartirish, autentifikatsiyani chetlab o'tish",
                    remediation=(
                        "Barcha SQL so'rovlarda parametrlashtirilgan so'rovlar (prepared statements) "
                        "yoki ORM ishlatilishi shart. Xom string-concatenation orqali SQL qurishdan qoching."
                    ),
                    cwe="CWE-89",
                    cvss_score=9.1,
                    source_probe="sqli_error_probe",
                )
            )
    return findings


async def open_redirect_probe(url: str) -> list[Finding]:
    findings: list[Finding] = []
    parsed = urlparse(url)
    redirect_param_names = ("redirect", "url", "next", "return", "returnurl", "dest", "continue")
    params = (
        dict(pair.split("=", 1) if "=" in pair else (pair, "") for pair in parsed.query.split("&"))
        if parsed.query
        else {}
    )
    candidate_params = [p for p in params if p.lower() in redirect_param_names]
    if not candidate_params:
        return findings
    evil = "https://sdevpro-redirect-probe.example"
    for param in candidate_params:
        test_params = dict(params)
        test_params[param] = evil
        test_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(test_params)}"
        try:
            response = await asyncio.to_thread(
                _get, test_url, allow_redirects=False
            )
        except requests.exceptions.RequestException:
            continue
        location = response.headers.get("Location", "")
        if location.startswith(evil):
            findings.append(
                Finding(
                    title=f"Ehtimoliy Open Redirect: '{param}' parametri",
                    severity="medium",
                    category="Broken Access Control",
                    description=(
                        f"'{param}' parametriga tashqi URL berilganda server foydalanuvchini "
                        "o'sha tashqi manzilga tekshirmasdan yo'naltirmoqda."
                    ),
                    location=test_url,
                    attack_vector="Fishing hujumlarida ishonchli domendan foydalanib qurbonlarni yo'ldan urish",
                    remediation="Redirect maqsadlarini ruxsat etilgan (whitelist) ichki manzillar bilan cheklang.",
                    cwe="CWE-601",
                    source_probe="open_redirect_probe",
                )
            )
    return findings


async def sensitive_path_scan(
    base_url: str, paths: tuple[str, ...] = _SENSITIVE_PATHS, *, concurrency: int = 15
) -> list[Finding]:
    findings: list[Finding] = []
    semaphore = asyncio.Semaphore(concurrency)
    base = base_url.rstrip("/")

    async def check(path: str) -> None:
        async with semaphore:
            test_url = f"{base}/{path}"
            try:
                response = await asyncio.to_thread(_get, test_url, allow_redirects=False)
            except requests.exceptions.RequestException:
                return
            if response.status_code == 200 and len(response.content) > 0:
                findings.append(
                    Finding(
                        title=f"Ochiq/himoyalanmagan maxfiy yo'l topildi: /{path}",
                        severity="high" if any(k in path for k in (".git", ".env", "credentials", "id_rsa")) else "medium",
                        category="Security Misconfiguration",
                        description=(
                            f"'/{path}' manzili autentifikatsiyasiz 200 OK javob qaytardi "
                            f"({len(response.content)} bayt)."
                        ),
                        location=test_url,
                        evidence=f"HTTP {response.status_code}, Content-Length={len(response.content)}",
                        attack_vector="Maxfiy fayllar/konfiguratsiya orqali kalitlar, parollar yoki manba kodni oshkor qilish",
                        remediation="Bu faylni web-root'dan olib tashlang yoki web-server darajasida kirishni to'liq bloklang.",
                        source_probe="sensitive_path_scan",
                    )
                )

    await asyncio.gather(*(check(p) for p in paths))
    return findings


def jwt_weakness_check(token: str, location: str = "") -> list[Finding]:
    findings: list[Finding] = []
    parts = token.strip().split(".")
    if len(parts) != 3:  # noqa: PLR2004
        return findings
    import base64

    def _b64decode(segment: str) -> dict[str, object]:
        padded = segment + "=" * (-len(segment) % 4)
        try:
            return json.loads(base64.urlsafe_b64decode(padded))
        except Exception:  # noqa: BLE001
            return {}

    header = _b64decode(parts[0])
    payload = _b64decode(parts[1])
    alg = str(header.get("alg", "")).lower()

    if alg in {"none", ""}:
        findings.append(
            Finding(
                title="JWT 'alg: none' zaifligi",
                severity="critical",
                category="Broken Authentication",
                description="JWT sarlavhasida algoritm 'none' yoki bo'sh — imzo tekshiruvini chetlab o'tish mumkin.",
                location=location,
                evidence=json.dumps(header),
                attack_vector="Token qalbakilashtirish orqali autentifikatsiyani to'liq chetlab o'tish",
                remediation="Serverda faqat kutilgan aniq algoritm (masalan RS256/HS256) qabul qilinishini majburlang.",
                cwe="CWE-347",
                cvss_score=9.8,
                source_probe="jwt_weakness_check",
            )
        )
    if alg.startswith("hs") and not header.get("kid"):
        findings.append(
            Finding(
                title="JWT HMAC (HS*) algoritmi ishlatilmoqda — kalit boshqaruvini tekshiring",
                severity="info",
                category="Broken Authentication",
                description=(
                    "Token HMAC-asoslangan algoritm bilan imzolangan. Agar server RS256 tokenlarni ham "
                    "qabul qilsa, 'algorithm confusion' hujumi ehtimoli bor."
                ),
                location=location,
                remediation="Serverda faqat bitta kutilgan algoritm qat'iy tekshirilishini ta'minlang.",
                source_probe="jwt_weakness_check",
            )
        )
    exp = payload.get("exp")
    if not exp:
        findings.append(
            Finding(
                title="JWT muddati (exp) belgilanmagan",
                severity="low",
                category="Broken Authentication",
                description="Tokenda 'exp' claim yo'q — token muddatsiz amal qilishi mumkin.",
                location=location,
                remediation="Har bir tokenga qisqa amal qilish muddati (exp) belgilang.",
                source_probe="jwt_weakness_check",
            )
        )
    return findings


async def run_web_probes(url: str, headers: dict[str, str], response: requests.Response | None) -> list[Finding]:
    findings: list[Finding] = []
    if response is not None:
        findings.extend(security_headers_audit(headers, url))
        with contextlib.suppress(Exception):
            findings.extend(cookie_audit(response, url))

    probe_results = await asyncio.gather(
        cors_probe(url),
        reflected_xss_probe(url),
        sqli_error_probe(url),
        open_redirect_probe(url),
        sensitive_path_scan(url),
        return_exceptions=True,
    )
    for result in probe_results:
        if isinstance(result, list):
            findings.extend(result)
        elif isinstance(result, Exception):
            logger.debug("web probe failed: %s", result)
    return findings
