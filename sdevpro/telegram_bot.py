"""SDeVPro Telegram bot: submit targets, get live findings, schedule recurring
scans, and upload server logs for attack-source analysis.

Every scan requires the requester to explicitly confirm they are authorized
to test the target (same rule the underlying Strix engine states in its own
README) before anything runs.
"""

from __future__ import annotations

import contextlib
import logging
import re
from pathlib import Path

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from sdevpro import reporter, storage
from sdevpro.config import Settings, get_settings
from sdevpro.log_analyzer import analyze_log_text, format_report_uz
from sdevpro.scanner import run_scan


logger = logging.getLogger("sdevpro.bot")

_LOGO_PATH = str(Path(__file__).parent / "assets" / "logo.png")

_WELCOME = (
    "SDeVPro Xavfsizlik Botiga xush kelibsiz!\n\n"
    "Men sizning tizimingizni (veb-sayt, API yoki server) AI yordamida "
    "xavfsizlik bo'yicha tekshiruvdan o'tkazaman: zaifliklarni topaman, "
    "ularni qanday tuzatish kerakligini tushuntiraman va xohlasangiz "
    "belgilangan vaqt oralig'ida avtomatik hisobot yuboraman.\n\n"
    "Buyruqlar:\n"
    "/scan <manzil> — bir martalik to'liq tekshiruv\n"
    "  masalan: /scan https://example.com\n"
    "/schedule <manzil> <interval> — davriy tekshiruv o'rnatish\n"
    "  masalan: /schedule https://example.com 1h\n"
    "/unschedule <manzil> — davriy tekshiruvni bekor qilish\n"
    "/myschedules — faol davriy tekshiruvlar ro'yxati\n"
    "/report — oxirgi hisobotni PDF ko'rinishida qayta olish\n\n"
    "Server log faylini (.log/.txt) yuborsangiz — undan shubhali "
    "hujum urinishlari va IP manzillarni tahlil qilib beraman.\n\n"
    "MUHIM: faqat o'zingizga tegishli yoki tekshirishga yozma ruxsatingiz "
    "bo'lgan tizimlarni tekshiring. Ruxsatsiz tekshiruv qonunga zid."
)

_CONSENT_TEXT = (
    "Tekshiruvni boshlashdan oldin tasdiqlang:\n\n"
    "Men ushbu manzilning (yoki tizimning) egasiman, yoki uni xavfsizlik "
    "tekshiruvidan o'tkazish uchun yozma ruxsatga egaman, va bu tekshiruv "
    "natijalari uchun to'liq javobgarlikni o'z zimmamga olaman."
)

_pending_scan_target: dict[int, str] = {}


def _is_allowed(settings: Settings, update: Update) -> bool:
    user = update.effective_user
    if user is None:
        return False
    return settings.is_user_allowed(user.id, user.username)


async def _deny(update: Update) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "Kechirasiz, sizda bu botdan foydalanish uchun ruxsat yo'q."
        )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    try:
        with open(_LOGO_PATH, "rb") as logo_file:
            await update.effective_message.reply_photo(photo=logo_file)
    except OSError:
        pass
    await update.effective_message.reply_text(_WELCOME)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(_WELCOME)


def _extract_target(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    if not context.args:
        return None
    return " ".join(context.args).strip()


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return

    target = _extract_target(context)
    if not target:
        await update.effective_message.reply_text(
            "Foydalanish: /scan <manzil>\nMasalan: /scan https://example.com"
        )
        return

    chat_id = update.effective_chat.id
    if settings.require_consent and not storage.has_consented(chat_id):
        _pending_scan_target[chat_id] = target
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Ha, vakolatim bor — boshlash", callback_data="consent_ok")]]
        )
        await update.effective_message.reply_text(_CONSENT_TEXT, reply_markup=keyboard)
        return

    await _run_and_send_scan(update, context, target)


async def on_consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    storage.record_consent(chat_id)
    target = _pending_scan_target.pop(chat_id, None)
    if not target:
        await query.edit_message_text("Tasdiqlandi. Endi /scan <manzil> orqali tekshiruvni boshlang.")
        return
    await query.edit_message_text("Tasdiqlandi. Tekshiruv boshlanmoqda...")
    await _run_and_send_scan(update, context, target)


async def _run_and_send_scan(
    update: Update, context: ContextTypes.DEFAULT_TYPE, target: str
) -> None:
    chat_id = update.effective_chat.id
    status_message = await context.bot.send_message(
        chat_id=chat_id, text=f"Tekshiruv boshlandi: {target}\n\nRecon boshlanmoqda..."
    )

    async def on_progress(message: str) -> None:
        with contextlib.suppress(Exception):
            await status_message.edit_text(f"Tekshiruv davom etmoqda: {target}\n\n{message}")

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    def sync_progress_bridge(message: str) -> None:
        context.application.create_task(on_progress(message))

    result = await run_scan(target, on_progress=sync_progress_bridge)
    storage.save_last_result(chat_id, result)

    await status_message.edit_text("Tekshiruv tugadi. Hisobot tayyorlanmoqda...")
    await _send_full_report(context, chat_id, result)


async def _send_full_report(context: ContextTypes.DEFAULT_TYPE, chat_id: int, result) -> None:  # noqa: ANN001
    await context.bot.send_message(chat_id=chat_id, text=reporter.format_summary_message(result))
    for chunk in reporter.format_findings_messages(result):
        await context.bot.send_message(chat_id=chat_id, text=chunk)
    defense = reporter.format_defense_message(result)
    if defense:
        for chunk in reporter.chunk_text(defense):
            await context.bot.send_message(chat_id=chat_id, text=chunk)

    try:
        pdf_bytes = reporter.build_pdf_report(result, logo_path=_LOGO_PATH)
        await context.bot.send_document(
            chat_id=chat_id,
            document=pdf_bytes,
            filename=f"sdevpro_report_{_safe_filename(result.target)}.pdf",
            caption="To'liq PDF hisobot",
        )
    except Exception:  # noqa: BLE001
        logger.exception("PDF report generation failed")


def _safe_filename(target: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", target)[:60] or "scan"


_INTERVAL_RE = re.compile(r"(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?", re.IGNORECASE)


def parse_interval_minutes(raw: str) -> int | None:
    raw = raw.strip().lower()
    if raw.isdigit():
        return int(raw)
    match = _INTERVAL_RE.fullmatch(raw)
    if not match or not any(match.groups()):
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    total = hours * 60 + minutes
    return total or None


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return

    args = context.args or []
    if len(args) < 2:  # noqa: PLR2004
        await update.effective_message.reply_text(
            "Foydalanish: /schedule <manzil> <interval>\n"
            "Masalan: /schedule https://example.com 1h\n"
            "Interval: '30m', '1h', '2h30m' yoki daqiqada butun son."
        )
        return

    *target_parts, interval_raw = args
    target = " ".join(target_parts)
    minutes = parse_interval_minutes(interval_raw)
    if not minutes or minutes < 5:  # noqa: PLR2004
        await update.effective_message.reply_text(
            "Interval noto'g'ri yoki juda qisqa (kamida 5 daqiqa bo'lishi kerak)."
        )
        return

    chat_id = update.effective_chat.id
    if settings.require_consent and not storage.has_consented(chat_id):
        await update.effective_message.reply_text(
            "Avval /scan orqali kamida bitta tekshiruv qilib, vakolatni tasdiqlang, "
            "so'ng /schedule buyrug'ini qayta yuboring."
        )
        return

    entry = storage.ScheduleEntry(
        chat_id=chat_id,
        target=target,
        interval_minutes=minutes,
        created_by=update.effective_user.id if update.effective_user else None,
    )
    storage.save_schedule(entry)
    _register_job(context.application, entry)
    await update.effective_message.reply_text(
        f"Davriy tekshiruv o'rnatildi: {target}\nHar {minutes} daqiqada avtomatik hisobot yuboriladi."
    )


async def cmd_unschedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    target = _extract_target(context)
    if not target:
        await update.effective_message.reply_text("Foydalanish: /unschedule <manzil>")
        return
    chat_id = update.effective_chat.id
    removed = storage.remove_schedule(chat_id, target)
    _unregister_job(context.application, chat_id, target)
    await update.effective_message.reply_text(
        "Davriy tekshiruv bekor qilindi." if removed else "Bunday davriy tekshiruv topilmadi."
    )


async def cmd_myschedules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    chat_id = update.effective_chat.id
    schedules = storage.list_schedules_for_chat(chat_id)
    if not schedules:
        await update.effective_message.reply_text("Faol davriy tekshiruvlar yo'q.")
        return
    lines = ["Faol davriy tekshiruvlar:"]
    lines.extend(f"- {s.target} (har {s.interval_minutes} daqiqada)" for s in schedules)
    await update.effective_message.reply_text("\n".join(lines))


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    chat_id = update.effective_chat.id
    result = storage.load_last_result(chat_id)
    if result is None:
        await update.effective_message.reply_text(
            "Hozircha saqlangan hisobot yo'q. Avval /scan orqali tekshiruv qiling."
        )
        return
    await _send_full_report(context, chat_id, result)


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    document = update.effective_message.document
    if document is None:
        return
    name = (document.file_name or "").lower()
    if not (name.endswith(".log") or name.endswith(".txt")):
        await update.effective_message.reply_text(
            "Faqat .log yoki .txt formatidagi server log fayllarini qabul qilaman."
        )
        return
    if document.file_size and document.file_size > 20 * 1024 * 1024:  # noqa: PLR2004
        await update.effective_message.reply_text("Fayl juda katta (20MB dan oshmasin).")
        return

    await update.effective_message.reply_text("Log fayli tahlil qilinmoqda...")
    telegram_file = await document.get_file()
    raw_bytes = await telegram_file.download_as_bytearray()
    text = bytes(raw_bytes).decode("utf-8", errors="ignore")

    analysis = analyze_log_text(text)
    report_text = format_report_uz(analysis)
    for chunk in reporter.chunk_text(report_text):
        await update.effective_message.reply_text(chunk)


# ---------------------------------------------------------------------------
# Scheduled recurring scans
# ---------------------------------------------------------------------------


def _job_name(chat_id: int, target: str) -> str:
    return f"sdevpro-schedule::{chat_id}::{target}"


async def _scheduled_scan_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    chat_id = job.chat_id
    target = job.data["target"]
    try:
        result = await run_scan(target)
        storage.save_last_result(chat_id, result)
        await _send_full_report(context, chat_id, result)
    except Exception:  # noqa: BLE001
        logger.exception("scheduled scan failed for %s / %s", chat_id, target)
        with contextlib.suppress(Exception):
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Davriy tekshiruvda xatolik yuz berdi ({target}). Keyinroq qayta urinib ko'riladi.",
            )


def _register_job(application: Application, entry: storage.ScheduleEntry) -> None:
    if application.job_queue is None:
        logger.warning("job_queue not available; cannot register schedule")
        return
    name = _job_name(entry.chat_id, entry.target)
    for existing in application.job_queue.get_jobs_by_name(name):
        existing.schedule_removal()
    application.job_queue.run_repeating(
        _scheduled_scan_job,
        interval=entry.interval_minutes * 60,
        first=entry.interval_minutes * 60,
        chat_id=entry.chat_id,
        name=name,
        data={"target": entry.target},
    )


def _unregister_job(application: Application, chat_id: int, target: str) -> None:
    if application.job_queue is None:
        return
    name = _job_name(chat_id, target)
    for job in application.job_queue.get_jobs_by_name(name):
        job.schedule_removal()


def _restore_all_jobs(application: Application) -> None:
    for entry in storage.load_schedules():
        _register_job(application, entry)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled bot error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        with contextlib.suppress(Exception):
            await update.effective_message.reply_text(
                "Kutilmagan xatolik yuz berdi. Iltimos qaytadan urinib ko'ring."
            )


def build_application(settings: Settings | None = None) -> Application:
    settings = settings or get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN sozlanmagan. .env fayliga @BotFather bergan tokenni qo'shing."
        )

    application = Application.builder().token(settings.telegram_bot_token).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("scan", cmd_scan))
    application.add_handler(CommandHandler("schedule", cmd_schedule))
    application.add_handler(CommandHandler("unschedule", cmd_unschedule))
    application.add_handler(CommandHandler("myschedules", cmd_myschedules))
    application.add_handler(CommandHandler("report", cmd_report))
    application.add_handler(CallbackQueryHandler(on_consent_callback, pattern="^consent_ok$"))
    application.add_handler(MessageHandler(filters.Document.ALL, on_document))
    application.add_error_handler(on_error)

    _restore_all_jobs(application)
    return application


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    application = build_application()
    logger.info("SDeVPro Telegram bot ishga tushdi (polling rejimida).")
    application.run_polling(close_loop=False)
