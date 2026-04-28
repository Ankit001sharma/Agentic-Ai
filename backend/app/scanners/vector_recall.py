"""Vector Recall scanner — looks for similarity to past BLOCKED requests in DB.

Catches repeat attackers who slightly modify their attack prompt."""

from __future__ import annotations

from app.schemas.sentinel import Finding

from .base import ScannerResult
from .embedding_jailbreak import embed


class VectorRecallScanner:
    name = "vector_recall"
    THRESHOLD = 0.83

    async def scan(self, text: str, **ctx) -> ScannerResult:
        if not text:
            return ScannerResult()
        vec = embed(text)
        if vec is None:
            return ScannerResult()
        session = ctx.get("db_session")
        if session is None:
            return ScannerResult()
        user_id = ctx.get("user_id", "anonymous")

        try:
            from sqlalchemy import text as sql_text

            row = await session.execute(
                sql_text(
                    "SELECT id, user_id, verdict, 1 - (embedding <=> CAST(:v AS vector)) as sim "
                    "FROM requests WHERE embedding IS NOT NULL AND verdict IN ('BLOCK','ESCALATE') "
                    "ORDER BY embedding <=> CAST(:v AS vector) LIMIT 1"
                ),
                {"v": vec},
            )
            r = row.first()
            if r is None:
                return ScannerResult()
            sim = float(r.sim or 0.0)
            if sim < self.THRESHOLD:
                return ScannerResult(score=max(0.0, sim - 0.3))

            same_user = (r.user_id == user_id)
            sev = min(1.0, sim + (0.1 if same_user else 0.0))
            return ScannerResult(
                findings=[
                    Finding(
                        category="REPEAT_ATTACK",
                        scanner=self.name,
                        severity=sev,
                        evidence=f"sim={sim:.3f} prior_verdict={r.verdict}",
                        metadata={
                            "similarity": sim,
                            "matched_request_id": str(r.id),
                            "matched_user": r.user_id,
                            "same_user": same_user,
                        },
                    )
                ],
                score=sev,
            )
        except Exception:  # noqa: BLE001
            return ScannerResult()
