from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from sdevpro.engine.report.state import ReportState


logger = logging.getLogger(__name__)

# SDeVPro fork: Scarf install-ping telemetry permanently disabled and its
# upstream endpoint (sdevpro.engine.gateway.scarf.sh) removed. Every public function
# below is a hard no-op — no scan or usage data is ever collected or sent
# anywhere. See NOTICE for the full list of changes made to the original
# SDeVPro codebase.


def _is_enabled() -> bool:
    return False


def _send(event: str, properties: dict[str, Any]) -> bool:
    logger.debug("telemetry disabled (sdevpro); skipping event %s", event)
    return False


def start(
    model: str | None,
    scan_mode: str | None,
    is_whitebox: bool,
    interactive: bool,
    has_instructions: bool,
    auth_mode: str | None = None,
) -> None:
    return


def finding(severity: str, cwe: str | None = None, is_cve: bool = False) -> None:
    return


def skill_loaded(skill_name: str) -> None:
    return


def end(report_state: "ReportState", exit_reason: str = "completed") -> None:
    return


def error(error_type: str) -> None:
    return
