"""Flask webhook adapter — lets the same bot logic run on serverless hosts
(Vercel and similar) instead of long-running polling.

IMPORTANT — read before relying on this for production:

1. **Storage.** Serverless functions have no persistent local disk between
   invocations. Set ``SDEVPRO_STORAGE_BACKEND=redis`` plus
   ``UPSTASH_REDIS_REST_URL`` / ``UPSTASH_REDIS_REST_TOKEN`` (free tier at
   https://upstash.com) so schedules/consent/user settings survive across
   requests. Without it, every cold start starts from an empty store.

2. **Execution time.** A full scan (recon + web probes + AI triage) can
   easily take 30-120+ seconds. Vercel's default Python function timeout is
   too short for that on the Hobby plan; the Pro plan allows a much higher
   ``maxDuration`` (see ``vercel.json``). For Hobby-plan deployments, steer
   users toward ``--scan-mode quick`` targets, or run the always-on bot
   (``sdevpro-bot`` / ``python -m sdevpro.main``) on a normal server/VPS
   instead, which has no such limit — that path is what this project
   recommends as the primary deployment and is what has been tested live.

3. **Scheduling.** Recurring ``/schedule`` scans need something to actually
   trigger them on a timer. Vercel Cron (configured in ``vercel.json``) can
   hit ``/api/cron`` periodically, but the Hobby plan only allows daily cron
   triggers — true hourly automation needs Vercel Pro (per-minute cron) or,
   again, the always-on bot process.

This module intentionally reuses every handler from ``telegram_bot.py`` — it
is the exact same bot logic, just invoked per-HTTP-request instead of via
long-polling, so behavior is identical either way.
"""

from __future__ import annotations

import asyncio
import logging
import os

from flask import Flask, jsonify, request
from telegram import Update

from sdevpro import storage
from sdevpro.config import get_settings
from sdevpro.telegram_bot import build_application


logger = logging.getLogger("sdevpro.webhook")

app = Flask(__name__)

_application = None
_application_lock = asyncio.Lock()


async def _get_application():  # noqa: ANN202
    global _application  # noqa: PLW0603
    if _application is None:
        _application = build_application()
        await _application.initialize()
    return _application


def _run_async(coro):  # noqa: ANN001, ANN202
    return asyncio.run(coro)


@app.route("/api/webhook", methods=["POST"])
def webhook() -> object:
    secret = os.environ.get("SDEVPRO_WEBHOOK_SECRET", "")
    if secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    payload = request.get_json(force=True, silent=True)
    if not payload:
        return jsonify({"ok": False, "error": "empty payload"}), 400

    async def _process() -> None:
        application = await _get_application()
        update = Update.de_json(payload, application.bot)
        await application.process_update(update)

    try:
        _run_async(_process())
    except Exception:  # noqa: BLE001
        logger.exception("webhook processing failed")
        return jsonify({"ok": False}), 200  # ack anyway so Telegram doesn't retry forever
    return jsonify({"ok": True})


@app.route("/api/cron", methods=["GET", "POST"])
def cron() -> object:
    """Best-effort trigger for due recurring scans (see module docstring).

    Requires ``SDEVPRO_STORAGE_BACKEND=redis`` to see schedules created via
    the bot. Wire this to Vercel Cron in ``vercel.json``.
    """
    secret = os.environ.get("SDEVPRO_CRON_SECRET", "")
    if secret and request.headers.get("Authorization") != f"Bearer {secret}":
        return jsonify({"ok": False, "error": "forbidden"}), 403

    async def _run_due() -> int:
        from datetime import UTC, datetime

        from sdevpro.telegram_bot import _scheduled_scan_job

        application = await _get_application()
        now = datetime.now(UTC)
        due = [entry for entry in storage.load_schedules() if entry.is_due(now)]

        count = 0
        for entry in due:
            job_data = type(
                "J", (), {"chat_id": entry.chat_id, "data": {"target": entry.target, "created_by": entry.created_by}}
            )()
            fake_context = type("C", (), {"bot": application.bot, "job": job_data, "application": application})()
            await _scheduled_scan_job(fake_context)
            count += 1
        return count

    try:
        ran = _run_async(_run_due())
    except Exception:  # noqa: BLE001
        logger.exception("cron run failed")
        return jsonify({"ok": False}), 500
    return jsonify({"ok": True, "scans_run": ran})


@app.route("/api/health", methods=["GET"])
def health() -> object:
    settings = get_settings()
    return jsonify({"ok": True, "telegram_configured": bool(settings.telegram_bot_token)})
