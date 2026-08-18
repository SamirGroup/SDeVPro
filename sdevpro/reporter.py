"""Turns a ScanResult into Telegram chat messages, a downloadable PDF, and a
downloadable plain-text (.txt) report — in the user's chosen language.

Telegram chat text is sent as plain text (no Markdown/HTML parse mode): scan
evidence can contain arbitrary characters (backticks, asterisks, angle
brackets) pulled from the target, and letting any of that reach Telegram's
Markdown/HTML parser risks a "can't parse entities" send failure. Visual
structure comes from emoji/ASCII markers instead, which always render.
"""

from __future__ import annotations

import io
from datetime import datetime

from sdevpro.i18n import DEFAULT_LANGUAGE, severity_label, t
from sdevpro.scanner.models import ScanResult

_SEVERITY_EMOJI = {
    "critical": "🟥",
    "high": "🟧",
    "medium": "🟨",
    "low": "🟦",
    "info": "⬜",
}

TELEGRAM_MESSAGE_LIMIT = 3800  # headroom under Telegram's 4096 hard cap


def chunk_text(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at <= 0:
            split_at = remaining.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _kind_label(lang: str, result: ScanResult) -> str:
    key = {
        "github": "report_kind_github",
        "whitebox": "report_kind_whitebox",
    }.get(result.target_kind, "report_kind_blackbox")
    return t(lang, key)


def format_summary_message(result: ScanResult, lang: str | None = None) -> str:
    lang = lang or result.language or DEFAULT_LANGUAGE
    counts = result.severity_counts()
    lines: list[str] = []
    lines.append(t(lang, "report_summary_title"))
    lines.append(t(lang, "report_target", target=result.target))
    lines.append(t(lang, "report_mode", mode=result.scan_mode, kind=_kind_label(lang, result)))
    lines.append(t(lang, "report_started", time=_fmt_time(result.started_at)))
    if result.finished_at:
        lines.append(t(lang, "report_finished", time=_fmt_time(result.finished_at)))
    lines.append("")
    lines.append(t(lang, "report_findings_summary"))
    for sev in ("critical", "high", "medium", "low", "info"):
        if counts.get(sev):
            lines.append(f"  {_SEVERITY_EMOJI[sev]} {severity_label(lang, sev)}: {counts[sev]}")
    if not any(counts.values()):
        lines.append(t(lang, "report_no_findings"))
    if result.error:
        lines.append("")
        lines.append(t(lang, "report_error", error=result.error))
    if result.summary:
        lines.append("")
        lines.append(t(lang, "report_ai_summary"))
        lines.append(result.summary)
    return "\n".join(lines)


def _finding_block(finding, lang: str, index: int) -> str:  # noqa: ANN001
    emoji = _SEVERITY_EMOJI.get(finding.severity, "⬜")
    label = severity_label(lang, finding.severity)
    block = [
        f"{emoji} [{label}] #{index}: {finding.title}",
        t(lang, "finding_category", value=finding.category),
    ]
    if finding.location:
        block.append(t(lang, "finding_location", value=finding.location))
    if finding.description:
        block.append(t(lang, "finding_description", value=finding.description))
    if finding.attack_vector:
        block.append(t(lang, "finding_attack_vector", value=finding.attack_vector))
    if finding.remediation:
        block.append(t(lang, "finding_remediation", value=finding.remediation))
    if finding.cwe:
        block.append(f"CWE: {finding.cwe}")
    if finding.cvss_score is not None:
        block.append(f"CVSS: {finding.cvss_score}")
    return "\n".join(block)


def format_findings_messages(result: ScanResult, lang: str | None = None) -> list[str]:
    lang = lang or result.language or DEFAULT_LANGUAGE
    findings = result.sorted_findings()
    if not findings:
        return []
    blocks = [_finding_block(f, lang, i) for i, f in enumerate(findings, start=1)]
    full_text = "\n\n".join(blocks)
    return chunk_text(full_text)


def format_defense_message(result: ScanResult, lang: str | None = None) -> str | None:
    lang = lang or result.language or DEFAULT_LANGUAGE
    if not result.defense_recommendations:
        return None
    return t(lang, "report_defense_title") + "\n\n" + result.defense_recommendations


def format_full_text_report(result: ScanResult, lang: str | None = None) -> str:
    """Single plain-text document combining summary + all findings + defense advice."""
    lang = lang or result.language or DEFAULT_LANGUAGE
    parts = [format_summary_message(result, lang)]
    findings = result.sorted_findings()
    if findings:
        parts.append("\n\n".join(_finding_block(f, lang, i) for i, f in enumerate(findings, start=1)))
    defense = format_defense_message(result, lang)
    if defense:
        parts.append(defense)
    return "\n\n" + ("\n\n" + "-" * 40 + "\n\n").join(parts)


def _fmt_time(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        return iso_ts


# ---------------------------------------------------------------------------
# PDF report
# ---------------------------------------------------------------------------


def build_pdf_report(result: ScanResult, logo_path: str | None = None, lang: str | None = None) -> bytes:
    lang = lang or result.language or DEFAULT_LANGUAGE
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"SDeVPro - {result.target}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SDeVProTitle", parent=styles["Title"], textColor=colors.HexColor("#7a1220")
    )
    h2 = ParagraphStyle("SDeVProH2", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6)
    body = styles["BodyText"]

    story: list[object] = []
    if logo_path:
        try:
            story.append(Image(logo_path, width=2.4 * cm, height=2.4 * cm))
            story.append(Spacer(1, 0.3 * cm))
        except Exception:  # noqa: BLE001
            pass

    story.append(Paragraph(_escape(t(lang, "report_summary_title")), title_style))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(f"<b>{_escape(t(lang, 'report_target', target=result.target))}</b>", body))
    story.append(
        Paragraph(
            _escape(t(lang, "report_mode", mode=result.scan_mode, kind=_kind_label(lang, result))), body
        )
    )
    story.append(Paragraph(_escape(t(lang, "report_started", time=_fmt_time(result.started_at))), body))
    if result.finished_at:
        story.append(
            Paragraph(_escape(t(lang, "report_finished", time=_fmt_time(result.finished_at))), body)
        )

    if result.summary:
        story.append(Paragraph(_escape(t(lang, "report_ai_summary")), h2))
        story.append(Paragraph(_escape(result.summary), body))

    counts = result.severity_counts()
    story.append(Paragraph(_escape(t(lang, "report_findings_summary")), h2))
    table_data = [["", ""]] + [
        [severity_label(lang, sev), str(counts[sev])] for sev in ("critical", "high", "medium", "low", "info")
    ]
    table = Table(table_data, colWidths=[6 * cm, 3 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7a1220")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ]
        )
    )
    story.append(table)

    findings = result.sorted_findings()
    if findings:
        story.append(Spacer(1, 0.4 * cm))
        for i, finding in enumerate(findings, start=1):
            label = severity_label(lang, finding.severity)
            story.append(Paragraph(f"<b>#{i} [{label}] {_escape(finding.title)}</b>", body))
            story.append(
                Paragraph(f"<i>{_escape(t(lang, 'finding_category', value=finding.category))}</i>", body)
            )
            if finding.location:
                story.append(Paragraph(_escape(t(lang, "finding_location", value=finding.location)), body))
            if finding.description:
                story.append(
                    Paragraph(_escape(t(lang, "finding_description", value=finding.description)), body)
                )
            if finding.attack_vector:
                story.append(
                    Paragraph(
                        f"<b>{_escape(t(lang, 'finding_attack_vector', value=finding.attack_vector))}</b>",
                        body,
                    )
                )
            if finding.remediation:
                story.append(
                    Paragraph(
                        f"<b>{_escape(t(lang, 'finding_remediation', value=finding.remediation))}</b>", body
                    )
                )
            meta = []
            if finding.cwe:
                meta.append(f"CWE: {finding.cwe}")
            if finding.cvss_score is not None:
                meta.append(f"CVSS: {finding.cvss_score}")
            if meta:
                story.append(Paragraph(" | ".join(meta), body))
            story.append(Spacer(1, 0.3 * cm))
    else:
        story.append(Paragraph(_escape(t(lang, "report_no_findings")), body))

    if result.defense_recommendations:
        story.append(Paragraph(_escape(t(lang, "report_defense_title")), h2))
        story.append(Paragraph(_escape(result.defense_recommendations), body))

    story.append(Spacer(1, 0.6 * cm))
    story.append(
        Paragraph(
            "<i>SDeVPro — authorized security assessment report.</i>",
            styles["Italic"],
        )
    )

    doc.build(story)
    return buffer.getvalue()


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
