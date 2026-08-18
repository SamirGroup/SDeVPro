"""SDeVPro Telegram bot: submit targets, get live findings, schedule recurring
scans, and upload server logs for attack-source analysis — in Uzbek, Russian
or English, with each user bringing their own AI (LLM) API key.

Every scan requires the requester to explicitly confirm they are authorized
to test the target before anything runs.
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
from sdevpro.ai_analyst import MissingLlmKeyError
from sdevpro.config import Settings, get_settings
from sdevpro.i18n import LANGUAGE_LABELS, SUPPORTED_LANGUAGES, t
from sdevpro.log_analyzer import analyze_log_text, format_report as format_log_report
from sdevpro.scanner import run_scan


logger = logging.getLogger("sdevpro.bot")

_LOGO_PATH = str(Path(__file__).parent / "assets" / "logo.png")

_pending_scan_target: dict[int, str] = {}


def _lang(user_id: int | None) -> str:
    if user_id is None:
        return "uz"
    return storage.get_user_settings(user_id).language


def _is_allowed(settings: Settings, update: Update) -> bool:
    user = update.effective_user
    if user is None:
        return False
    return settings.is_user_allowed(user.id, user.username)


async def _deny(update: Update) -> None:
    if update.effective_message and update.effective_user:
        await update.effective_message.reply_text(t(_lang(update.effective_user.id), "denied"))


def _language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(LANGUAGE_LABELS[code], callback_data=f"lang_{code}") for code in SUPPORTED_LANGUAGES]]
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    user = update.effective_user
    user_settings = storage.get_user_settings(user.id) if user else None
    if user_settings is None or not user_settings.language_set:
        await update.effective_message.reply_text(t("uz", "choose_language"), reply_markup=_language_keyboard())
        return
    lang = user_settings.language
    with contextlib.suppress(OSError):
        with open(_LOGO_PATH, "rb") as logo_file:
            await update.effective_message.reply_photo(photo=logo_file)
    await update.effective_message.reply_text(t(lang, "welcome"))


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(t("uz", "choose_language"), reply_markup=_language_keyboard())


async def on_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = (query.data or "lang_uz").removeprefix("lang_")
    if lang not in SUPPORTED_LANGUAGES:
        lang = "uz"
    user = update.effective_user
    if user:
        storage.set_user_language(user.id, lang)
    await query.edit_message_text(t(lang, "language_set"))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.effective_message.reply_text(t(_lang(user.id if user else None), "help"))


async def cmd_aitoken(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.effective_message.reply_text(t(_lang(user.id if user else None), "aitoken_help"))


async def cmd_githubtoken(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.effective_message.reply_text(t(_lang(user.id if user else None), "githubtoken_help"))


_MODEL_RE = re.compile(r"^[a-zA-Z0-9_.\-]+/[a-zA-Z0-9_.:\-]+$")


async def cmd_setkey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    user = update.effective_user
    lang = _lang(user.id if user else None)
    args = context.args or []
    if len(args) < 2 or not _MODEL_RE.match(args[0]):  # noqa: PLR2004
        await update.effective_message.reply_text(t(lang, "setkey_usage"))
        return
    model, api_key = args[0], args[1]

    with contextlib.suppress(Exception):
        await update.effective_message.delete()

    storage.set_user_llm_key(user.id, model, api_key)
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=t(lang, "setkey_saved", model=model)
    )


async def cmd_deletekey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    user = update.effective_user
    lang = _lang(user.id)
    had_key = storage.delete_user_llm_key(user.id)
    await update.effective_message.reply_text(t(lang, "deletekey_done" if had_key else "deletekey_none"))


async def cmd_setgithubtoken(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    user = update.effective_user
    lang = _lang(user.id)
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(t(lang, "setgithubtoken_usage"))
        return
    with contextlib.suppress(Exception):
        await update.effective_message.delete()
    storage.set_user_github_token(user.id, args[0])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=t(lang, "setgithubtoken_saved"))


async def cmd_mysettings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    user = update.effective_user
    us = storage.get_user_settings(user.id)
    lang = us.language
    await update.effective_message.reply_text(
        t(
            lang,
            "mysettings",
            language=LANGUAGE_LABELS.get(lang, lang),
            model=us.llm_model or "-",
            github_token_status=t(
                lang, "github_token_set" if us.github_token_encrypted else "github_token_unset"
            ),
        )
    )


def _extract_target(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    if not context.args:
        return None
    return " ".join(context.args).strip()


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return

    user = update.effective_user
    lang = _lang(user.id)
    target = _extract_target(context)
    if not target:
        await update.effective_message.reply_text(t(lang, "scan_usage"))
        return

    us = storage.get_user_settings(user.id)
    if not us.has_llm_key():
        await update.effective_message.reply_text(t(lang, "no_api_key"))
        return

    chat_id = update.effective_chat.id
    if settings.require_consent and not storage.has_consented(chat_id):
        _pending_scan_target[chat_id] = target
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(t(lang, "consent_button"), callback_data="consent_ok")]]
        )
        await update.effective_message.reply_text(t(lang, "consent_prompt"), reply_markup=keyboard)
        return

    await _run_and_send_scan(update, context, target, user.id)


async def on_consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    user = update.effective_user
    lang = _lang(user.id if user else None)
    storage.record_consent(chat_id)
    target = _pending_scan_target.pop(chat_id, None)
    if not target:
        await query.edit_message_text(t(lang, "consent_confirmed"))
        return
    await query.edit_message_text(t(lang, "consent_confirmed"))
    await _run_and_send_scan(update, context, target, user.id if user else chat_id)


async def _run_and_send_scan(
    update: Update, context: ContextTypes.DEFAULT_TYPE, target: str, user_id: int
) -> None:
    chat_id = update.effective_chat.id
    us = storage.get_user_settings(user_id)
    lang = us.language

    status_message = await context.bot.send_message(
        chat_id=chat_id, text=t(lang, "scan_started", target=target)
    )

    async def on_progress(message: str) -> None:
        with contextlib.suppress(Exception):
            await status_message.edit_text(t(lang, "scan_progress", target=target, message=message))

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    def sync_progress_bridge(message: str) -> None:
        context.application.create_task(on_progress(message))

    try:
        result = await run_scan(
            target,
            on_progress=sync_progress_bridge,
            llm_model=us.llm_model,
            llm_api_key=us.decrypted_llm_api_key(),
            llm_api_base=us.llm_api_base,
            github_token=us.decrypted_github_token(),
            language=lang,
        )
    except MissingLlmKeyError:
        await status_message.edit_text(t(lang, "no_api_key"))
        return

    storage.save_last_result(chat_id, result)

    await status_message.edit_text(t(lang, "scan_done_preparing"))
    await _send_full_report(context, chat_id, result, lang)


async def _send_full_report(context: ContextTypes.DEFAULT_TYPE, chat_id: int, result, lang: str) -> None:  # noqa: ANN001
    await context.bot.send_message(chat_id=chat_id, text=reporter.format_summary_message(result, lang))
    for chunk in reporter.format_findings_messages(result, lang):
        await context.bot.send_message(chat_id=chat_id, text=chunk)
    defense = reporter.format_defense_message(result, lang)
    if defense:
        for chunk in reporter.chunk_text(defense):
            await context.bot.send_message(chat_id=chat_id, text=chunk)

    base_name = _safe_filename(result.target)
    try:
        pdf_bytes = reporter.build_pdf_report(result, logo_path=_LOGO_PATH, lang=lang)
        await context.bot.send_document(
            chat_id=chat_id,
            document=pdf_bytes,
            filename=f"sdevpro_report_{base_name}.pdf",
            caption=t(lang, "pdf_caption"),
        )
    except Exception:  # noqa: BLE001
        logger.exception("PDF report generation failed")

    try:
        txt_bytes = reporter.format_full_text_report(result, lang).encode("utf-8")
        await context.bot.send_document(
            chat_id=chat_id,
            document=txt_bytes,
            filename=f"sdevpro_report_{base_name}.txt",
            caption=t(lang, "txt_caption"),
        )
    except Exception:  # noqa: BLE001
        logger.exception("TXT report generation failed")


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

    user = update.effective_user
    lang = _lang(user.id)
    args = context.args or []
    if len(args) < 2:  # noqa: PLR2004
        await update.effective_message.reply_text(t(lang, "schedule_usage"))
        return

    *target_parts, interval_raw = args
    target = " ".join(target_parts)
    minutes = parse_interval_minutes(interval_raw)
    if not minutes or minutes < 5:  # noqa: PLR2004
        await update.effective_message.reply_text(t(lang, "schedule_bad_interval"))
        return

    us = storage.get_user_settings(user.id)
    if not us.has_llm_key():
        await update.effective_message.reply_text(t(lang, "no_api_key"))
        return

    chat_id = update.effective_chat.id
    if settings.require_consent and not storage.has_consented(chat_id):
        await update.effective_message.reply_text(t(lang, "schedule_needs_consent"))
        return

    entry = storage.ScheduleEntry(
        chat_id=chat_id,
        target=target,
        interval_minutes=minutes,
        created_by=user.id,
    )
    storage.save_schedule(entry)
    _register_job(context.application, entry)
    await update.effective_message.reply_text(t(lang, "schedule_set", target=target, minutes=minutes))


async def cmd_unschedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    user = update.effective_user
    lang = _lang(user.id)
    target = _extract_target(context)
    if not target:
        await update.effective_message.reply_text(t(lang, "unschedule_usage"))
        return
    chat_id = update.effective_chat.id
    removed = storage.remove_schedule(chat_id, target)
    _unregister_job(context.application, chat_id, target)
    await update.effective_message.reply_text(t(lang, "unschedule_done" if removed else "unschedule_none"))


async def cmd_myschedules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    user = update.effective_user
    lang = _lang(user.id)
    chat_id = update.effective_chat.id
    schedules = storage.list_schedules_for_chat(chat_id)
    if not schedules:
        await update.effective_message.reply_text(t(lang, "myschedules_none"))
        return
    lines = [t(lang, "myschedules_header")]
    lines.extend(t(lang, "myschedules_item", target=s.target, minutes=s.interval_minutes) for s in schedules)
    await update.effective_message.reply_text("\n".join(lines))


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    user = update.effective_user
    lang = _lang(user.id)
    chat_id = update.effective_chat.id
    result = storage.load_last_result(chat_id)
    if result is None:
        await update.effective_message.reply_text(t(lang, "report_none"))
        return
    await _send_full_report(context, chat_id, result, lang)


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    if not _is_allowed(settings, update):
        await _deny(update)
        return
    user = update.effective_user
    lang = _lang(user.id)
    document = update.effective_message.document
    if document is None:
        return
    name = (document.file_name or "").lower()
    if not (name.endswith(".log") or name.endswith(".txt")):
        await update.effective_message.reply_text(t(lang, "doc_only_log"))
        return
    if document.file_size and document.file_size > 20 * 1024 * 1024:  # noqa: PLR2004
        await update.effective_message.reply_text(t(lang, "doc_too_big"))
        return

    await update.effective_message.reply_text(t(lang, "doc_analyzing"))
    telegram_file = await document.get_file()
    raw_bytes = await telegram_file.download_as_bytearray()
    text = bytes(raw_bytes).decode("utf-8", errors="ignore")

    analysis = analyze_log_text(text)
    report_text = format_log_report(analysis, lang)
    for chunk in reporter.chunk_text(report_text):
        await update.effective_message.reply_text(chunk)

    with contextlib.suppress(Exception):
        await update.effective_message.reply_document(
            document=report_text.encode("utf-8"),
            filename="sdevpro_log_analysis.txt",
            caption=t(lang, "txt_caption"),
        )


# ---------------------------------------------------------------------------
# Scheduled recurring scans
# ---------------------------------------------------------------------------


def _job_name(chat_id: int, target: str) -> str:
    return f"sdevpro-schedule::{chat_id}::{target}"


async def _scheduled_scan_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    chat_id = job.chat_id
    target = job.data["target"]
    creator_id = job.data.get("created_by")
    us = storage.get_user_settings(creator_id) if creator_id else None
    lang = us.language if us else "uz"

    if us is None or not us.has_llm_key():
        with contextlib.suppress(Exception):
            await context.bot.send_message(chat_id=chat_id, text=t(lang, "no_api_key"))
        return

    try:
        result = await run_scan(
            target,
            llm_model=us.llm_model,
            llm_api_key=us.decrypted_llm_api_key(),
            llm_api_base=us.llm_api_base,
            github_token=us.decrypted_github_token(),
            language=lang,
        )
        storage.save_last_result(chat_id, result)
        await _send_full_report(context, chat_id, result, lang)
    except Exception:  # noqa: BLE001
        logger.exception("scheduled scan failed for %s / %s", chat_id, target)
        with contextlib.suppress(Exception):
            await context.bot.send_message(chat_id=chat_id, text=t(lang, "scheduled_scan_failed", target=target))
    finally:
        from datetime import UTC, datetime

        storage.mark_schedule_run(chat_id, target, datetime.now(UTC).isoformat())


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
        data={"target": entry.target, "created_by": entry.created_by},
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
    if isinstance(update, Update) and update.effective_message and update.effective_user:
        with contextlib.suppress(Exception):
            await update.effective_message.reply_text(t(_lang(update.effective_user.id), "unexpected_error"))


def build_application(settings: Settings | None = None) -> Application:
    settings = settings or get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN sozlanmagan. .env fayliga @BotFather bergan tokenni qo'shing."
        )

    application = Application.builder().token(settings.telegram_bot_token).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("language", cmd_language))
    application.add_handler(CommandHandler("aitoken", cmd_aitoken))
    application.add_handler(CommandHandler("githubtoken", cmd_githubtoken))
    application.add_handler(CommandHandler("setkey", cmd_setkey))
    application.add_handler(CommandHandler("deletekey", cmd_deletekey))
    application.add_handler(CommandHandler("setgithubtoken", cmd_setgithubtoken))
    application.add_handler(CommandHandler("mysettings", cmd_mysettings))
    application.add_handler(CommandHandler("scan", cmd_scan))
    application.add_handler(CommandHandler("schedule", cmd_schedule))
    application.add_handler(CommandHandler("unschedule", cmd_unschedule))
    application.add_handler(CommandHandler("myschedules", cmd_myschedules))
    application.add_handler(CommandHandler("report", cmd_report))
    application.add_handler(CallbackQueryHandler(on_language_callback, pattern="^lang_"))
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
