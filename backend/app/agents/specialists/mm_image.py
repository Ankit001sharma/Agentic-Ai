"""ImageThreatAgent — vision describe when image bytes or URLs present."""

from __future__ import annotations

import base64
import re

from app.core.config import get_settings
from app.llm.litellm_client import adescribe_image
from app.schemas.explanation import AgentFindingRecord
from app.agents.specialists.base import append_finding
from app.schemas.sentinel import ScanState


_DATA_URI = re.compile(r"^data:(image/[^;]+);base64,(.+)$", re.IGNORECASE | re.DOTALL)


async def analyze_attachment(state: ScanState, att: dict) -> None:
    """Append findings for one image-like attachment."""
    mtype = (att.get("mime") or att.get("content_type") or "").lower()
    name = (att.get("name") or "").lower()
    if "image" not in mtype and not name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return
    raw: bytes | None = None
    b64 = att.get("base64") or att.get("data")
    if isinstance(b64, str) and b64.strip():
        try:
            raw = base64.b64decode(b64.split(",", 1)[-1])
        except Exception:  # noqa: BLE001
            raw = None
    elif isinstance(att.get("url"), str):
        u = att["url"].strip()
        m = _DATA_URI.match(u)
        if m:
            try:
                raw = base64.b64decode(m.group(2))
            except Exception:  # noqa: BLE001
                raw = None
    if not raw:
        append_finding(
            state,
            AgentFindingRecord(
                agent="image_threat",
                claim="image_reference_without_decodable_bytes",
                evidence=[name or mtype or "unknown"],
                confidence=0.4,
                metadata={"surface": "metadata_only"},
            ),
        )
        return
    s = get_settings()
    desc = await adescribe_image(raw=raw, mime=mtype or "image/png")
    evidence = [desc[:1200]] if desc else ["vision_unavailable"]
    append_finding(
        state,
        AgentFindingRecord(
            agent="image_threat",
            claim="vision_surface_review",
            evidence=evidence,
            confidence=0.65 if desc else 0.35,
            metadata={"mime": mtype, "name": name},
        ),
    )
