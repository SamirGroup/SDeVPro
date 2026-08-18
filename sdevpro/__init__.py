"""SDeVPro — native (Docker-free) AI security scanning engine and Telegram bot.

Independent from the bundled ``strix`` package (kept for reference as the
original multi-agent/Docker-sandboxed engine). This package implements a
lighter engine that runs directly on the host: recon + web/code probes,
LLM-based triage and remediation guidance, PDF/Telegram reporting, scheduled
recurring scans, and server-log attack-source analysis.
"""

from __future__ import annotations


__version__ = "1.0.0"
