"""LLM-based triage: turns raw probe findings into a prioritized, explained report.

Uses ``litellm`` so any provider Strix itself supports also works here
(``STRIX_LLM``/``SDEVPRO_LLM`` model strings like ``anthropic/claude-sonnet-4-6``,
``openai/gpt-5.4``, ``gemini/gemini-3-pro``, ``ollama/llama3``, ...).

Design principle: the AI never invents new findings. It only re-ranks,
explains, and writes remediation/defense guidance for what the probes in
``sdevpro/scanner/`` actually observed — so a report never claims a
vulnerability exists that no probe evidence supports.
"""

from __future__ import annotations

import json
import logging
import re

from sdevpro.config import get_settings
from sdevpro.scanner.models import ScanResult


logger = logging.getLogger("sdevpro.ai_analyst")

_SYSTEM_PROMPT = """Siz SDeVPro platformasining AI xavfsizlik tahlilchisisiz.
Sizga avtomatik skanerlash vositasi tomonidan aniqlangan xom (raw) xavfsizlik
topilmalari va texnik ma'lumotlar (recon) beriladi. Vazifangiz:

1. Har bir topilma uchun aniqroq va tushunarli tavsif, real hujum stsenariysi
   (attack_vector) va amaliy tuzatish yo'riqnomasi (remediation) yozish.
2. Agar CVSS ball berilmagan bo'lsa, taxminiy CVSS 3.1 ballni baholash.
3. Umumiy holat bo'yicha qisqa, tushunarli xulosa (summary) yozish — 3-6 gap,
   o'zbek tilida, texnik bo'lmagan mijoz ham tushunadigan darajada.
4. Umumiy himoya tavsiyalari (defense_recommendations) — tizimni qanday
   mustahkamlash kerakligi haqida amaliy qadamlar ro'yxati.

MUHIM QOIDA: Yangi, dalilsiz "topilma" o'ylab topmang. Faqat sizga berilgan
topilmalar ro'yxatidagi elementlarni yaxshilang/izohlang. Agar biror topilma
haqiqatan xato yoki ahamiyatsiz (false positive) deb hisoblasangiz, uni olib
tashlamang — shunchaki tavsifda buni qayd eting.

Javobni FAQAT quyidagi JSON formatda qaytaring, boshqa hech qanday matn
qo'shmang:
{
  "summary": "...",
  "defense_recommendations": "...",
  "findings": [
    {
      "title": "...",
      "severity": "critical|high|medium|low|info",
      "category": "...",
      "description": "...",
      "attack_vector": "...",
      "remediation": "...",
      "cwe": "CWE-XXX yoki null",
      "cvss_score": 0.0
    }
  ]
}
"findings" ro'yxati sizga berilgan topilmalar bilan bir xil sonda va bir xil
tartibda bo'lishi kerak (faqat matnlarni yaxshilaysiz).
"""


def _extract_json(text: str) -> dict[str, object] | None:
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            text = text[brace_start : brace_end + 1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("AI response was not valid JSON")
        return None
    return parsed if isinstance(parsed, dict) else None


def _build_user_prompt(result: ScanResult) -> str:
    findings_payload = [
        {
            "index": i,
            "title": f.title,
            "severity": f.severity,
            "category": f.category,
            "description": f.description,
            "evidence": f.evidence,
            "location": f.location,
        }
        for i, f in enumerate(result.findings)
    ]
    payload = {
        "target": result.target,
        "scan_mode": result.scan_mode,
        "whitebox": result.whitebox,
        "raw_evidence": result.raw_evidence,
        "findings": findings_payload,
    }
    return (
        "Quyidagi skanerlash natijalarini tahlil qiling va yuqoridagi JSON "
        "formatda javob bering:\n\n" + json.dumps(payload, ensure_ascii=False, default=str)
    )


async def triage_scan(result: ScanResult) -> None:
    """Mutate ``result`` in place: enrich findings, set summary + defense advice."""
    settings = get_settings()
    if not settings.llm_model:
        raise RuntimeError(
            "LLM sozlanmagan (SDEVPRO_LLM / STRIX_LLM bo'sh). .env faylida "
            "SDEVPRO_LLM va SDEVPRO_LLM_API_KEY qiymatlarini belgilang."
        )
    if not result.findings and not result.raw_evidence:
        result.summary = "Skanerlashda hech qanday ma'lumot yig'ilmadi."
        return

    import litellm

    litellm.drop_params = True
    litellm.suppress_debug_info = True

    kwargs: dict[str, object] = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(result)},
        ],
        "timeout": 120,
    }
    if settings.llm_api_key:
        kwargs["api_key"] = settings.llm_api_key
    if settings.llm_api_base:
        kwargs["api_base"] = settings.llm_api_base

    response = await litellm.acompletion(**kwargs)
    content = response.choices[0].message.content or ""
    parsed = _extract_json(content)
    if parsed is None:
        result.summary = content[:2000] if content else "AI javobini tahlil qilib bo'lmadi."
        return

    result.summary = str(parsed.get("summary") or result.summary)
    result.defense_recommendations = str(
        parsed.get("defense_recommendations") or result.defense_recommendations
    )

    ai_findings = parsed.get("findings")
    if isinstance(ai_findings, list) and len(ai_findings) == len(result.findings):
        for original, enriched in zip(result.findings, ai_findings, strict=False):
            if not isinstance(enriched, dict):
                continue
            original.description = str(enriched.get("description") or original.description)
            original.attack_vector = str(enriched.get("attack_vector") or original.attack_vector)
            original.remediation = str(enriched.get("remediation") or original.remediation)
            cwe = enriched.get("cwe")
            if isinstance(cwe, str) and cwe.lower() != "null":
                original.cwe = cwe
            cvss = enriched.get("cvss_score")
            if isinstance(cvss, (int, float)):
                original.cvss_score = float(cvss)
            severity = enriched.get("severity")
            if isinstance(severity, str) and severity.lower() in {
                "critical", "high", "medium", "low", "info",
            }:  # fmt: skip
                original.severity = severity.lower()
    elif isinstance(ai_findings, list):
        logger.warning(
            "AI returned %d findings but %d were sent; skipping per-finding merge",
            len(ai_findings),
            len(result.findings),
        )
