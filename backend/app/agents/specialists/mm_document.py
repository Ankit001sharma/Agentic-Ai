"""DocumentThreatAgent — PDF/office heuristic checks (no full parsing)."""

from __future__ import annotations

from app.schemas.explanation import AgentFindingRecord
from app.agents.specialists.base import append_finding
from app.schemas.sentinel import ScanState

_SUSPICIOUS = (".exe", ".scr", ".bat", ".cmd", ".ps1", ".vbs", ".js", "macro", "embedded")


async def analyze_attachment(state: ScanState, att: dict) -> None:
    mtype = (att.get("mime") or att.get("content_type") or "").lower()
    name = (att.get("name") or "").lower()
    if "pdf" not in mtype and not name.endswith(".pdf"):
        if "officedocument" not in mtype and "word" not in mtype and "spreadsheet" not in mtype:
            return
    flags: list[str] = []
    if name.endswith(".pdf"):
        flags.append("pdf_surface")
    for s in _SUSPICIOUS:
        if s in name:
            flags.append(f"suspicious_token:{s}")
    if flags:
        append_finding(
            state,
            AgentFindingRecord(
                agent="document_threat",
                claim="document_surface_heuristic",
                evidence=flags,
                confidence=0.45,
                metadata={"mime": mtype, "name": name},
            ),
        )
