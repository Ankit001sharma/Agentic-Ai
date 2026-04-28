"""Embedding-similarity jailbreak scanner.

Embeds the input prompt and queries pgvector for the closest known-jailbreak vector.
If the cosine similarity exceeds a threshold, raises a JAILBREAK finding.

Uses sentence-transformers (`all-MiniLM-L6-v2`) when available; otherwise no-op.
"""

from __future__ import annotations

from app.schemas.sentinel import Finding

from .base import ScannerResult

_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            _MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        except Exception:  # noqa: BLE001
            _MODEL = False  # sentinel
    return _MODEL


def embed(text: str) -> list[float] | None:
    model = _get_model()
    if not model:
        return None
    try:
        vec = model.encode([text], normalize_embeddings=True)[0]
        return vec.tolist()
    except Exception:  # noqa: BLE001
        return None


class EmbeddingJailbreakScanner:
    name = "embedding_jailbreak"
    THRESHOLD = 0.78

    async def scan(self, text: str, **ctx) -> ScannerResult:
        if not text:
            return ScannerResult()
        vec = embed(text)
        if vec is None:
            return ScannerResult()

        session = ctx.get("db_session")
        if session is None:
            return ScannerResult()

        try:
            from sqlalchemy import text as sql_text

            # pgvector cosine distance: <=> operator. similarity = 1 - distance
            row = await session.execute(
                sql_text(
                    "SELECT id, text, source, category, 1 - (embedding <=> CAST(:v AS vector)) as sim "
                    "FROM jailbreak_embeddings ORDER BY embedding <=> CAST(:v AS vector) LIMIT 1"
                ),
                {"v": vec},
            )
            r = row.first()
            if r is None:
                return ScannerResult()
            sim = float(r.sim or 0.0)
            if sim < self.THRESHOLD:
                return ScannerResult(score=max(0.0, sim - 0.2))
            return ScannerResult(
                findings=[
                    Finding(
                        category=str(r.category or "JAILBREAK"),
                        scanner=self.name,
                        severity=min(1.0, sim),
                        evidence=str(r.text)[:120],
                        metadata={"similarity": sim, "source": r.source},
                    )
                ],
                score=sim,
            )
        except Exception:  # noqa: BLE001
            return ScannerResult()
