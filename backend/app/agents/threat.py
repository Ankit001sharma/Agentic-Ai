"""ThreatDetectionAgent — fans out 5 input scanners in parallel."""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.scanners.code_ip import CodeIPScanner
from app.scanners.embedding_jailbreak import EmbeddingJailbreakScanner
from app.scanners.internal_info import InternalInfoScanner
from app.scanners.llm_judge import LLMJudgeScanner
from app.scanners.malware_request import MalwareRequestScanner
from app.scanners.nhi_check import NHIScanner
from app.scanners.presidio_pii import PIIPresidioScanner
from app.scanners.rbac import RBACScanner
from app.scanners.regex_rules import RegexScanner
from app.scanners.secrets_scan import SecretsScanner
from app.scanners.toxicity import ToxicityScanner
from app.scanners.vector_recall import VectorRecallScanner
from app.schemas.sentinel import ScanState

log = get_logger("agent.threat")

_REGEX = RegexScanner()
_PII = PIIPresidioScanner()
_SECRETS = SecretsScanner()
_TOX = ToxicityScanner()
_CODE = CodeIPScanner()
_EMBED = EmbeddingJailbreakScanner()
_RECALL = VectorRecallScanner()
_JUDGE = LLMJudgeScanner()
_MALWARE = MalwareRequestScanner()
_RBAC = RBACScanner()
_INTERNAL = InternalInfoScanner()
_NHI = NHIScanner()


async def run(state: ScanState) -> ScanState:
    text = state.prompt
    ctx = {
        "user_id": state.user.user_id,
        "role": state.user.role,
        "resource": state.user.resource,
        "auth_type": state.user.auth_type,
    }

    async with SessionLocal() as db:
        ctx["db_session"] = db
        # Layer 1: regex + heuristics (cheap, parallel)
        # Layer 2: ML scanners (PII, toxicity, embeddings)
        # Layer 3: identity-aware scanners (RBAC, NHI)
        # Layer 4: intent scanners (malware-request, internal-info)
        # Layer 5: LLM judge (only on borderline scores; below)
        results = await asyncio.gather(
            _REGEX.scan(text, **ctx),
            _PII.scan(text, **ctx),
            _SECRETS.scan(text, **ctx),
            _TOX.scan(text, **ctx),
            _CODE.scan(text, **ctx),
            _EMBED.scan(text, **ctx),
            _RECALL.scan(text, **ctx),
            _MALWARE.scan(text, **ctx),
            _RBAC.scan(text, **ctx),
            _INTERNAL.scan(text, **ctx),
            _NHI.scan(text, **ctx),
            return_exceptions=True,
        )

    aggregate_score = 0.0
    for r in results:
        if isinstance(r, Exception):
            log.warning("scanner_error", error=str(r))
            continue
        state.findings.extend(r.findings)
        aggregate_score = max(aggregate_score, r.score)

    # Borderline → invoke LLM judge (only if regex/embed didn't already overwhelm)
    if 0.3 <= aggregate_score < 0.7:
        try:
            j = await _JUDGE.scan(text)
            state.findings.extend(j.findings)
        except Exception as e:  # noqa: BLE001
            log.warning("llm_judge_error", error=str(e))

    state.audit_events.append({"agent": "threat", "findings": len(state.findings)})
    return state
