"""LLM-based triage: turns raw probe findings into a prioritized, explained report.

Uses ``litellm`` so any provider Strix itself supports also works here
(model strings like ``anthropic/claude-sonnet-4-6``, ``openai/gpt-5.4``,
``gemini/gemini-3-pro``, ``ollama/llama3``, ...).

Every caller supplies its own ``model``/``api_key`` (normally the requesting
Telegram user's own key, set via ``/setkey``) — this module has no concept
of a single shared key, so one user's request always uses their own
credentials and never another user's.

Design principle: the AI never invents new findings. It only re-ranks,
explains, and writes remediation/defense guidance for what the probes in
``sdevpro/scanner/`` actually observed — so a report never claims a
vulnerability exists that no probe evidence supports.
"""

from __future__ import annotations

import json
import logging
import re

from sdevpro.i18n import DEFAULT_LANGUAGE
from sdevpro.scanner.models import ScanResult


logger = logging.getLogger("sdevpro.ai_analyst")


class MissingLlmKeyError(RuntimeError):
    """Raised when no LLM model/API key is available for this request."""


_LANGUAGE_NAMES = {
    "uz": "Uzbek (o'zbek tili)",
    "ru": "Russian (русский язык)",
    "en": "English",
}

_SYSTEM_PROMPT_TEMPLATE = """You are SDeVPro's AI security analyst.
You receive raw security findings and technical recon data produced by an
automated scanner. Your job:

1. For every finding, write a clearer description, a realistic attack
   scenario (attack_vector), and practical remediation guidance.
2. If no CVSS score is given, estimate one (CVSS 3.1).
3. Write a short, clear overall summary (3-6 sentences) that a non-technical
   client can understand.
4. Write general defense_recommendations — practical steps to harden the
   system as a whole.

IMPORTANT RULE: never invent a new finding without evidence. Only improve or
explain the items in the findings list you are given. If you believe a
finding is a false positive, do not remove it — just note that in its
description.

Write ALL text (title, category, summary, defense_recommendations,
description, attack_vector, remediation) in {language_name}, even though the
findings you receive are written in Uzbek.

Reply with ONLY the following JSON, no other text:
{{
  "summary": "...",
  "defense_recommendations": "...",
  "findings": [
    {{
      "title": "...",
      "severity": "critical|high|medium|low|info",
      "category": "...",
      "description": "...",
      "attack_vector": "...",
      "remediation": "...",
      "cwe": "CWE-XXX or null",
      "cvss_score": 0.0
    }}
  ]
}}
The "findings" list must have the same length and order as the findings you
were given (only improve the text/fields).
"""


def _system_prompt(language: str) -> str:
    language_name = _LANGUAGE_NAMES.get(language, _LANGUAGE_NAMES[DEFAULT_LANGUAGE])
    return _SYSTEM_PROMPT_TEMPLATE.format(language_name=language_name)


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
        "Analyze the following scan results and reply in the JSON format "
        "described above:\n\n" + json.dumps(payload, ensure_ascii=False, default=str)
    )


async def triage_scan(
    result: ScanResult,
    *,
    model: str,
    api_key: str,
    api_base: str = "",
    language: str = DEFAULT_LANGUAGE,
) -> None:
    """Mutate ``result`` in place: enrich findings, set summary + defense advice."""
    if not model or not api_key:
        raise MissingLlmKeyError("No LLM model/API key provided for this request.")
    if not result.findings and not result.raw_evidence:
        result.summary = "-"
        return

    import litellm

    litellm.drop_params = True
    litellm.suppress_debug_info = True

    kwargs: dict[str, object] = {
        "model": model,
        "api_key": api_key,
        "messages": [
            {"role": "system", "content": _system_prompt(language)},
            {"role": "user", "content": _build_user_prompt(result)},
        ],
        "timeout": 120,
    }
    if api_base:
        kwargs["api_base"] = api_base

    response = await litellm.acompletion(**kwargs)
    content = response.choices[0].message.content or ""
    parsed = _extract_json(content)
    if parsed is None:
        result.summary = content[:2000] if content else "-"
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
            original.title = str(enriched.get("title") or original.title)
            original.category = str(enriched.get("category") or original.category)
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
