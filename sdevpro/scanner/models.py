"""Data model shared by every scanner probe and the AI triage/report layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}[self.value]


SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


@dataclass
class Finding:
    """A single security observation, before or after AI triage."""

    title: str
    severity: str  # one of Severity values; kept as str for easy JSON round-trip
    category: str  # e.g. "Broken Access Control", "Injection", "Security Misconfiguration"
    description: str
    evidence: str = ""
    location: str = ""
    remediation: str = ""
    attack_vector: str = ""
    cwe: str | None = None
    cvss_score: float | None = None
    source_probe: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "evidence": self.evidence,
            "location": self.location,
            "remediation": self.remediation,
            "attack_vector": self.attack_vector,
            "cwe": self.cwe,
            "cvss_score": self.cvss_score,
            "source_probe": self.source_probe,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Finding:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class ScanResult:
    """Full outcome of one SDeVPro scan run against one target."""

    target: str
    scan_mode: str = "quick"
    whitebox: bool = False
    target_kind: str = "web"  # "web" | "whitebox" | "github"
    language: str = "uz"
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str | None = None
    findings: list[Finding] = field(default_factory=list)
    raw_evidence: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    defense_recommendations: str = ""
    error: str | None = None

    def sorted_findings(self) -> list[Finding]:
        return sorted(
            self.findings,
            key=lambda f: SEVERITY_ORDER.index(f.severity) if f.severity in SEVERITY_ORDER else 9,
        )

    def severity_counts(self) -> dict[str, int]:
        counts = dict.fromkeys(SEVERITY_ORDER, 0)
        for finding in self.findings:
            if finding.severity in counts:
                counts[finding.severity] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "scan_mode": self.scan_mode,
            "whitebox": self.whitebox,
            "target_kind": self.target_kind,
            "language": self.language,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "defense_recommendations": self.defense_recommendations,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScanResult:
        findings = [Finding.from_dict(f) for f in data.get("findings", [])]
        return cls(
            target=data.get("target", ""),
            scan_mode=data.get("scan_mode", "quick"),
            whitebox=bool(data.get("whitebox", False)),
            target_kind=data.get("target_kind", "web"),
            language=data.get("language", "uz"),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at"),
            findings=findings,
            summary=data.get("summary", ""),
            defense_recommendations=data.get("defense_recommendations", ""),
            error=data.get("error"),
        )
