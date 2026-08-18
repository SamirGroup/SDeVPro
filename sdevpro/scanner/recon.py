"""Passive/active reconnaissance probes: DNS, HTTP fingerprint, TLS, ports.

Every probe here is read-only (GET requests, TCP connect checks, DNS
lookups) — nothing here sends exploit payloads. That lives in
``web_probes.py``, gated behind the same authorized-target consent as
everything else the bot runs.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
import ssl
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import requests


logger = logging.getLogger("sdevpro.recon")

DEFAULT_TIMEOUT = 8
USER_AGENT = "SDeVPro-Scanner/1.0 (+authorized-security-assessment)"

# A curated, small, fast port list rather than a full 1-65535 sweep — this is
# the "lightweight" scanner tier; a full sweep is left to nmap/nuclei-class
# tools if the operator installs and wires them in separately.
COMMON_PORTS: tuple[int, ...] = (
    21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445, 465, 587,
    993, 995, 1433, 1521, 2049, 27017, 3000, 3306, 3389, 5000, 5432, 5900,
    6379, 6443, 8000, 8008, 8080, 8081, 8443, 8888, 9000, 9090, 9200, 11211,
)  # fmt: skip

_TECH_SIGNATURES: dict[str, tuple[str, ...]] = {
    "WordPress": ("wp-content", "wp-includes", "/wp-json/"),
    "Joomla": ("joomla", "/media/jui/"),
    "Drupal": ("drupal.js", "sites/default/files"),
    "Laravel": ("laravel_session", "x-powered-by: php"),
    "Django": ("csrftoken", "django"),
    "Express/Node.js": ("x-powered-by: express",),
    "Nginx": ("server: nginx",),
    "Apache": ("server: apache",),
    "IIS": ("server: microsoft-iis",),
    "Cloudflare": ("server: cloudflare", "cf-ray"),
    "React": ("__next_data__", "react"),
    "Next.js": ("__next_data__", "/_next/"),
    "PHP": ("x-powered-by: php", "phpsessid"),
}


@dataclass
class ReconResult:
    target: str
    resolved_ips: list[str] = field(default_factory=list)
    dns_records: dict[str, list[str]] = field(default_factory=dict)
    open_ports: list[int] = field(default_factory=list)
    http_status: int | None = None
    http_headers: dict[str, str] = field(default_factory=dict)
    http_redirects: list[str] = field(default_factory=list)
    tls_info: dict[str, Any] = field(default_factory=dict)
    detected_tech: list[str] = field(default_factory=list)
    robots_txt: str | None = None
    body_sample: str = ""
    errors: list[str] = field(default_factory=list)


def normalize_url(target: str) -> str:
    target = target.strip()
    if not target:
        return target
    if "://" not in target:
        target = f"https://{target}"
    return target


def _hostname_of(target_url: str) -> str:
    return urlparse(target_url).hostname or target_url


async def resolve_dns(hostname: str) -> dict[str, list[str]]:
    records: dict[str, list[str]] = {}
    try:
        import dns.resolver  # type: ignore[import-untyped]

        resolver = dns.resolver.Resolver()
        resolver.timeout = 4
        resolver.lifetime = 4
        for rtype in ("A", "AAAA", "MX", "NS", "TXT", "CNAME"):
            try:
                answer = await asyncio.to_thread(resolver.resolve, hostname, rtype)
                records[rtype] = [str(r).strip('"') for r in answer]
            except Exception:  # noqa: BLE001
                continue
    except ImportError:
        with contextlib.suppress(Exception):
            ip = await asyncio.to_thread(socket.gethostbyname, hostname)
            records["A"] = [ip]
    return records


async def resolve_ips(hostname: str) -> list[str]:
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
        return sorted({info[4][0] for info in infos})
    except OSError as exc:
        logger.debug("resolve_ips failed for %s: %s", hostname, exc)
        return []


async def _check_port(host: str, port: int, timeout: float) -> int | None:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
    except Exception:  # noqa: BLE001
        return None
    return port


async def scan_ports(
    host: str, ports: tuple[int, ...] = COMMON_PORTS, *, timeout: float = 0.8, concurrency: int = 40
) -> list[int]:
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded(port: int) -> int | None:
        async with semaphore:
            return await _check_port(host, port, timeout)

    results = await asyncio.gather(*(bounded(p) for p in ports))
    return sorted(p for p in results if p is not None)


def _fetch_http_sync(url: str) -> requests.Response:
    return requests.get(
        url,
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        allow_redirects=True,
        verify=True,
    )


async def fetch_http(url: str) -> tuple[requests.Response | None, list[str], str | None]:
    """Return (response, redirect chain urls, error)."""
    try:
        response = await asyncio.to_thread(_fetch_http_sync, url)
    except requests.exceptions.SSLError:
        try:
            response = await asyncio.to_thread(
                lambda: requests.get(
                    url,
                    timeout=DEFAULT_TIMEOUT,
                    headers={"User-Agent": USER_AGENT},
                    allow_redirects=True,
                    verify=False,  # noqa: S501 — explicit fallback probe, result is flagged as a finding
                )
            )
        except Exception as exc:  # noqa: BLE001
            return None, [], f"TLS/connection error: {exc}"
    except requests.exceptions.RequestException as exc:
        return None, [], str(exc)

    chain = [r.url for r in response.history] + [response.url]
    return response, chain, None


def _get_tls_info(hostname: str, port: int = 443) -> dict[str, Any]:
    info: dict[str, Any] = {}
    try:
        ctx = ssl.create_default_context()
        with (
            socket.create_connection((hostname, port), timeout=DEFAULT_TIMEOUT) as sock,
            ctx.wrap_socket(sock, server_hostname=hostname) as ssock,
        ):
            cert = ssock.getpeercert()
            info["protocol"] = ssock.version()
            info["cipher"] = ssock.cipher()
            if cert:
                info["subject"] = dict(x[0] for x in cert.get("subject", ()))
                info["issuer"] = dict(x[0] for x in cert.get("issuer", ()))
                info["not_after"] = cert.get("notAfter")
                info["not_before"] = cert.get("notBefore")
                info["san"] = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
                not_after = cert.get("notAfter")
                if not_after:
                    with contextlib.suppress(Exception):
                        expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
                            tzinfo=UTC
                        )
                        info["days_until_expiry"] = (expiry - datetime.now(UTC)).days
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)
    return info


async def get_tls_info(hostname: str, port: int = 443) -> dict[str, Any]:
    return await asyncio.to_thread(_get_tls_info, hostname, port)


def detect_technologies(headers: dict[str, str], body: str) -> list[str]:
    lower_headers = "\n".join(f"{k.lower()}: {v.lower()}" for k, v in headers.items())
    lower_body = body[:20000].lower()
    haystack = f"{lower_headers}\n{lower_body}"
    return sorted(
        tech
        for tech, signatures in _TECH_SIGNATURES.items()
        if any(sig in haystack for sig in signatures)
    )


async def fetch_robots(base_url: str) -> str | None:
    try:
        response = await asyncio.to_thread(
            requests.get,
            f"{base_url.rstrip('/')}/robots.txt",
            timeout=5,
            headers={"User-Agent": USER_AGENT},
        )
        if response.status_code == 200 and response.text.strip():
            return response.text[:4000]
    except requests.exceptions.RequestException:
        pass
    return None


async def run_recon(target: str) -> ReconResult:
    url = normalize_url(target)
    hostname = _hostname_of(url)
    result = ReconResult(target=url)

    dns_task = asyncio.create_task(resolve_dns(hostname))
    ips_task = asyncio.create_task(resolve_ips(hostname))
    http_task = asyncio.create_task(fetch_http(url))
    robots_task = asyncio.create_task(fetch_robots(url))

    result.dns_records = await dns_task
    result.resolved_ips = await ips_task

    if result.resolved_ips:
        result.open_ports = await scan_ports(result.resolved_ips[0])
    elif hostname:
        result.open_ports = await scan_ports(hostname)

    response, chain, err = await http_task
    if err:
        result.errors.append(err)
    if response is not None:
        result.http_status = response.status_code
        result.http_headers = dict(response.headers)
        result.http_redirects = chain
        result.body_sample = response.text[:20000] if response.text else ""
        result.detected_tech = detect_technologies(result.http_headers, result.body_sample)

    result.robots_txt = await robots_task

    if url.startswith("https://"):
        result.tls_info = await get_tls_info(hostname)

    return result
