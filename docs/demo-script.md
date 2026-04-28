# 90-Second Demo Script

> Goal: showcase the full agentic pipeline end-to-end with one-click attack
> scenarios and live dashboard reactions.

## Setup (one-time)

```bash
cp .env.example .env
docker compose up --build -d
make seed       # loads jailbreak corpus into pgvector
open http://localhost:3000
```

## Walkthrough (90s)

1. **0:00–0:15 — Intro on the home dashboard**
   - "SentinelGuard is an OpenAI-compatible gateway that runs every request through 11 collaborating agents."
   - Point at the empty live-feed and risk-meter at 0.

2. **0:15–0:35 — Sandbox: classic injection**
   - Click **"Classic Injection"**.
   - Watch:
     - Risk meter spikes to 90+
     - Verdict chips: `BLOCK`
     - ThreatChips: `PROMPT_INJECTION`, `SYSTEM_PROMPT_EXTRACTION`
     - Live-feed gets a red entry; AlertToast pops in bottom-right.

3. **0:35–0:50 — PII MASK demo**
   - Click **"PII in Prompt (MASK)"**.
   - Result panel shows:
     - Verdict `MASK`, response `CLEAN`
     - DiffViewer: original SSN/email vs `[REDACTED:US_SSN:1]` / `[REDACTED:EMAIL_ADDRESS:1]` in the redacted prompt
     - Model returns the (safe) summary

4. **0:50–1:05 — HITL Escalate**
   - Click **"Borderline → ESCALATE"**.
   - Switch to **/review** — pending item appears.
   - Click **Approve** — request unblocks; pipeline continues.

5. **1:05–1:20 — Output controls**
   - Click **"Output PII Leak"**: model hallucinates fake contact card; output is REDACTED before delivery (DiffViewer shows the masking).
   - Click **"Dangerous Code in Output"**: model returns `rm -rf` snippet; output is BLOCKED with safe refusal.

6. **1:20–1:30 — Sensitive routing + Analytics**
   - Click **"Sensitive → Local Model"**: ModelBadge shows `ollama/llama3.1:8b` (data stayed local).
   - Switch to **/analytics**: bar chart of verdicts last 24h, top threats, model usage pie, top risky users from the Risk Graph.

7. **Bonus — Adaptive learning**
   - Repeatedly click any attack scenario 3x.
   - Switch to **/policies**: AI-suggested rule appears (`auto_block_user_<id>`) — Approve to enable.

## What to highlight

- **No code changes** to the client app — it just points at SentinelGuard instead of api.openai.com.
- **Cheap-first detection** (regex/embeddings) keeps p95 latency low; LLM-Judge only invoked for ambiguous cases.
- **Drop-in**: same OpenAI Chat Completions schema in/out, plus a `sentinel: {...}` extra field with full provenance.
- **Open & extensible**: add a new scanner = new file under `backend/app/scanners/` + register in `agents/threat.py`.
