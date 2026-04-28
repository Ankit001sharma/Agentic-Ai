"""Episodic recall: similar past incidents (pgvector on requests)."""

from __future__ import annotations

from sqlalchemy import text as sql_text

from app.db.session import SessionLocal
from app.scanners.embedding_jailbreak import embed


async def recall_similar_incidents_text(text: str, k: int = 5) -> list[dict]:
    """Legacy: recent BLOCK/ESCALATE rows (no vector sort). Prefer recall_similar_incidents_vector."""
    rows = await recall_similar_incidents_vector(text, k=k)
    return rows


async def recall_similar_incidents_vector(text: str, k: int = 5) -> list[dict]:
    """Top-k past requests by embedding cosine similarity among BLOCK/ESCALATE with embeddings."""
    if not text or not text.strip():
        return []
    try:
        vec = embed(text[:2000])
    except Exception:  # noqa: BLE001
        return []
    if vec is None:
        return []
    out: list[dict] = []
    try:
        async with SessionLocal() as db:
            r = await db.execute(
                sql_text(
                    "SELECT id, user_id, verdict, risk, prompt, "
                    "1 - (embedding <=> CAST(:v AS vector)) AS sim "
                    "FROM requests WHERE embedding IS NOT NULL "
                    "AND verdict IN ('BLOCK','ESCALATE') "
                    "ORDER BY embedding <=> CAST(:v AS vector) ASC "
                    "LIMIT :lim"
                ),
                {"v": vec, "lim": max(1, min(k * 3, 50))},
            )
            fetched = r.fetchall()
        for row in fetched[:k]:
            sim = float(row.sim or 0.0)
            out.append(
                {
                    "id": str(row.id),
                    "user_id": row.user_id,
                    "verdict": row.verdict,
                    "risk": row.risk,
                    "preview": (row.prompt or "")[:200],
                    "similarity": round(sim, 4),
                }
            )
    except Exception:  # noqa: BLE001
        return []
    return out
