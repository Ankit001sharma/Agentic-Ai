# SentinelGuard frontend

Production dashboard for the **14-stage** SentinelGuard pipeline (Next.js 15, React 19, Tailwind, shadcn-style UI, TanStack Query, NextAuth).

## Environment

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend base URL (browser calls), e.g. `http://localhost:8080` |
| `NEXT_PUBLIC_SENTINEL_KEY` | Must match backend `SENTINEL_API_KEY` |
| `AUTH_SECRET` | NextAuth secret (generate with `openssl rand -base64 32`) |
| `DASHBOARD_PASSWORD` | Shared password for credential login (default `sentinel`) |

## Development

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) — you will be redirected to `/login`.

## Production build

```bash
npm run build
npm start
```

Docker image uses `output: "standalone"` (see `Dockerfile`).

## E2E

```bash
npx playwright install
npm run test:e2e
```

## Architecture

- **Operate:** Dashboard, Live (SSE), Incidents, Review  
- **Investigate:** Conversations (`/api/v2/sessions`), Threat intel  
- **Configure:** Policies (Monaco), Tools (`/api/catalog/tools`), Models, Integrations  
- **Develop:** Sandbox (`/api/v2/chat`), API keys (stub), Quickstart  
- **Observe:** Analytics, Audit, Health (`/api/system/health`)  
- **Settings:** Org / Members (stub admin API)

Auth is enforced in `app/(dashboard)/layout.tsx` via `auth()` (Node runtime — no Edge middleware).
