"""Turns a ScanResult into Telegram chat messages and a downloadable PDF.

Telegram text is sent as plain text (no Markdown/HTML parse mode): scan
evidence can contain arbitrary characters (backticks, asterisks, angle
brackets) pulled from the target, and letting any of that reach Telegram's
Markdown/HTML parser risks a "can't parse entities" send failure. Visual
structure comes from emoji/ASCII markers instead, which always render.
"""

from __future__ import annotations

import io
from datetime import datetime

from sdevpro.scanner.models import ScanResult

_SEVERITY_EMOJI = {
    "critical": "🟥",
    "high": "🟧",
    "medium": "🟨",
    "low": "🟦",
    "info": "⬜",
}

_SEVERITY_LABEL_UZ = {
    "critical": "KRITIK",
    "high": "YUQORI",
    "medium": "O'RTA",
    "low": "PAST",
    "info": "MA'LUMOT",
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


def format_summary_message(result: ScanResult) -> str:
    counts = result.severity_counts()
    lines: list[str] = []
    lines.append("SDeVPro — Xavfsizlik Skanerlash Hisoboti")
    lines.append(f"Nishon: {result.target}")
    lines.append(f"Rejim: {result.scan_mode} | {'Whitebox (kod)' if result.whitebox else 'Blackbox (tashqi)'}")
    lines.append(f"Boshlandi: {_fmt_time(result.started_at)}")
    if result.finished_at:
        lines.append(f"Tugadi: {_fmt_time(result.finished_at)}")
    lines.append("")
    lines.append("Topilmalar bo'yicha xulosa:")
    for sev in ("critical", "high", "medium", "low", "info"):
        if counts.get(sev):
            lines.append(f"  {_SEVERITY_EMOJI[sev]} {_SEVERITY_LABEL_UZ[sev]}: {counts[sev]}")
    if not any(counts.values()):
        lines.append("  Hech qanday topilma yo'q.")
    if result.error:
        lines.append("")
        lines.append(f"[!] Skanerlash davomida xatolik: {result.error}")
    if result.summary:
        lines.append("")
        lines.append("AI xulosasi:")
        lines.append(result.summary)
    return "\n".join(lines)


def format_findings_messages(result: ScanResult) -> list[str]:
    findings = result.sorted_findings()
    if not findings:
        return []
    blocks: list[str] = []
    for i, finding in enumerate(findings, start=1):
        emoji = _SEVERITY_EMOJI.get(finding.severity, "⬜")
        label = _SEVERITY_LABEL_UZ.get(finding.severity, finding.severity.upper())
        block = [
            f"{emoji} [{label}] #{i}: {finding.title}",
            f"Kategoriya: {finding.category}",
        ]
        if finding.location:
            block.append(f"Joylashuv: {finding.location}")
        if finding.description:
            block.append(f"Tavsif: {finding.description}")
        if finding.attack_vector:
            block.append(f"Hujum vektori: {finding.attack_vector}")
        if finding.remediation:
            block.append(f"Tuzatish: {finding.remediation}")
        if finding.cwe:
            block.append(f"CWE: {finding.cwe}")
        if finding.cvss_score is not None:
            block.append(f"CVSS: {finding.cvss_score}")
        blocks.append("\n".join(block))

    full_text = "\n\n".join(blocks)
    return chunk_text(full_text)


def format_defense_message(result: ScanResult) -> str | None:
    if not result.defense_recommendations:
        return None
    return "SDeVPro — Umumiy Himoya Tavsiyalari\n\n" + result.defense_recommendations


def _fmt_time(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        return iso_ts


# ---------------------------------------------------------------------------
# PDF report
# ---------------------------------------------------------------------------


def build_pdf_report(result: ScanResult, logo_path: str | None = None) -> bytes:
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
        title=f"SDeVPro xavfsizlik hisoboti — {result.target}",
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

    story.append(Paragraph("SDeVPro — Xavfsizlik Skanerlash Hisoboti", title_style))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(f"<b>Nishon:</b> {_escape(result.target)}", body))
    story.append(Paragraph(f"<b>Rejim:</b> {_escape(result.scan_mode)}", body))
    story.append(Paragraph(f"<b>Boshlandi:</b> {_fmt_time(result.started_at)}", body))
    if result.finished_at:
        story.append(Paragraph(f"<b>Tugadi:</b> {_fmt_time(result.finished_at)}", body))

    if result.summary:
        story.append(Paragraph("Xulosa", h2))
        story.append(Paragraph(_escape(result.summary), body))

    counts = result.severity_counts()
    story.append(Paragraph("Xavflilik darajasi bo'yicha taqsimot", h2))
    table_data = [["Daraja", "Soni"]] + [
        [_SEVERITY_LABEL_UZ[sev], str(counts[sev])] for sev in ("critical", "high", "medium", "low", "info")
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
        story.append(Paragraph("Batafsil topilmalar", h2))
        for i, finding in enumerate(findings, start=1):
            label = _SEVERITY_LABEL_UZ.get(finding.severity, finding.severity.upper())
            story.append(
                Paragraph(f"<b>#{i} [{label}] {_escape(finding.title)}</b>", body)
            )
            story.append(Paragraph(f"<i>Kategoriya:</i> {_escape(finding.category)}", body))
            if finding.location:
                story.append(Paragraph(f"<i>Joylashuv:</i> {_escape(finding.location)}", body))
            if finding.description:
                story.append(Paragraph(_escape(finding.description), body))
            if finding.attack_vector:
                story.append(Paragraph(f"<b>Hujum vektori:</b> {_escape(finding.attack_vector)}", body))
            if finding.remediation:
                story.append(Paragraph(f"<b>Tuzatish:</b> {_escape(finding.remediation)}", body))
            meta = []
            if finding.cwe:
                meta.append(f"CWE: {finding.cwe}")
            if finding.cvss_score is not None:
                meta.append(f"CVSS: {finding.cvss_score}")
            if meta:
                story.append(Paragraph(" | ".join(meta), body))
            story.append(Spacer(1, 0.3 * cm))
    else:
        story.append(Paragraph("Topilmalar aniqlanmadi.", body))

    if result.defense_recommendations:
        story.append(Paragraph("Umumiy himoya tavsiyalari", h2))
        story.append(Paragraph(_escape(result.defense_recommendations), body))

    story.append(Spacer(1, 0.6 * cm))
    story.append(
        Paragraph(
            "<i>Ushbu hisobot faqat vakolat berilgan (authorized) xavfsizlik tekshiruvi doirasida "
            "yaratilgan. SDeVPro / mijoz ruxsatisiz tizimlarni tekshirish uchun javobgar emas.</i>",
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
