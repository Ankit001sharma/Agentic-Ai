# Deployment Guide

## Local (Docker Compose)

```bash
cp .env.example .env
# (optional) set OPENAI_API_KEY for real LLM calls; otherwise the offline stub kicks in.
docker compose up --build
make seed
```

Services:

| Service | Port |
|---|---|
| Backend (FastAPI) | 8000 |
| Frontend (Next.js) | 3000 |
| Postgres + pgvector | 5432 |
| Redis | 6379 |
| OPA | 8181 |

## Production deploy

### Backend / OPA / DB / Redis → Railway (or Render / Fly.io)

1. Create a new Railway project, link the repo.
2. Add three services:
   - **Postgres** (Railway plugin, version 16 + run `CREATE EXTENSION vector;`).
   - **Redis** (Railway plugin).
   - **OPA**: deploy the official image `openpolicyagent/opa:0.68.0` (or `openpolicyagent/opa:latest-rootless` if you need the rootless variant) and mount `infra/opa/policies/*` via a persistent volume or build a small image that copies them in.
   - **Backend**: build from `./backend/Dockerfile`. Set:
     - `DATABASE_URL=postgresql+asyncpg://…`
     - `REDIS_URL=redis://…`
     - `OPA_URL=http://opa.railway.internal:8181`
     - `OPENAI_API_KEY=…`
     - `SENTINEL_API_KEY=<random>`
3. After first boot, run `python -m infra.seed_jailbreaks` once (Railway "Run command").

### Frontend → Vercel

1. Import the repo, point root at `frontend/`.
2. Set:
   - `NEXT_PUBLIC_API_URL=https://<your-backend>.railway.app`
   - `NEXT_PUBLIC_SENTINEL_KEY=<same as backend SENTINEL_API_KEY>`
3. Vercel auto-builds on every push.

### CORS

Set `CORS_ORIGINS=https://<your-frontend>.vercel.app` on the backend.

### SIEM / Slack

Set `SIEM_WEBHOOK_URL` to any HTTPS endpoint that accepts JSON; ReportingAgent
will POST every `request` event in the shape:

```json
{
  "severity": "high|medium|low",
  "source": "sentinelguard",
  "event": { "request_id": "...", "verdict": "BLOCK", ... }
}
```
