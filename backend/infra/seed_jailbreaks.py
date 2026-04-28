"""Seed pgvector jailbreak corpus.

Reads `datasets/jailbreaks.jsonl` (one JSON per line: {text, source, category}),
embeds with `all-MiniLM-L6-v2`, and inserts into `jailbreak_embeddings`.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from sqlalchemy import delete, select

from app.core.logging import configure_logging, get_logger
from app.db.models import JailbreakEmbedding
from app.db.session import SessionLocal, init_db

DATASET_PATHS = [
    Path("/datasets/jailbreaks.jsonl"),
    Path(__file__).resolve().parents[2] / "datasets" / "jailbreaks.jsonl",
]


async def main() -> None:
    configure_logging()
    log = get_logger("seed")
    await init_db()

    # Lazy import — only needed when embedding
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception as e:  # noqa: BLE001
        log.error("embedding_model_unavailable", error=str(e))
        return

    path = next((p for p in DATASET_PATHS if p.exists()), None)
    if path is None:
        log.error("dataset_not_found", paths=[str(p) for p in DATASET_PATHS])
        return

    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    log.info("seed_starting", count=len(rows))

    async with SessionLocal() as db:
        await db.execute(delete(JailbreakEmbedding))
        await db.commit()

        texts = [r["text"] for r in rows]
        vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        for r, v in zip(rows, vecs, strict=False):
            db.add(
                JailbreakEmbedding(
                    text=r["text"][:2000],
                    source=r.get("source", "custom"),
                    category=r.get("category", "JAILBREAK"),
                    embedding=v.tolist(),
                )
            )
        await db.commit()
        log.info("seed_done", count=len(rows))


if __name__ == "__main__":
    asyncio.run(main())
