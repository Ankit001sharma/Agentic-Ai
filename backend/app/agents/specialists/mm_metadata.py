"""MetadataThreatAgent — EXIF/authorship hints from attachment metadata dict."""

from __future__ import annotations

from app.schemas.explanation import AgentFindingRecord
from app.agents.specialists.base import append_finding
from app.schemas.sentinel import ScanState


async def analyze_attachment(state: ScanState, att: dict) -> None:
    meta = att.get("metadata") or att.get("exif") or {}
    if not isinstance(meta, dict) or not meta:
        return
    keys = [str(k).lower() for k in meta.keys()]
    hits = [k for k in keys if k in ("gps", "location", "author", "creator", "software", "camera")]
    if not hits:
        return
    append_finding(
        state,
        AgentFindingRecord(
            agent="metadata_threat",
            claim="sensitive_metadata_keys_present",
            evidence=hits[:12],
            confidence=0.5,
            metadata={"keys": hits},
        ),
    )
