# PathWise AI — Cloud Deployment Guide

This deploys the platform with **no local dependency**:

```
┌──────────────────────────┐     HTTPS / WSS      ┌───────────────────────────┐
│  Vercel  (static SPA)    │  ───────────────▶   │  Render  (FastAPI + WS)   │
│  React + Vite, root=      │                     │  sim mode, torch-free      │
│  frontend/, build/ output │  ◀───────────────   │  uvicorn server.main:app  │
└──────────────────────────┘   VITE_API_URL      └───────────────────────────┘
```

The frontend reads **`VITE_API_URL`** at build time; every API call and the
WebSocket derive their origin from it (`services/api.ts`, `utils/apiClient.ts`,
`context/AuthContext.tsx`). Backend CORS is open (`allow_origins=["*"]`), so the
cross-origin browser calls work; auth uses Bearer tokens (no cookies).

---

## 1. Backend → Render (do this first, to get the URL)

The repo ships a **`render.yaml`** blueprint.

1. Push the repo to GitHub (see below) — Render deploys from a Git repo.
2. On [render.com](https://render.com) → **New +** → **Blueprint** → pick the
   `pathwise-ai` repo. Render reads `render.yaml` and provisions a free web service:
   - Build: `pip install -r requirements-cloud.txt`
   - Start: `uvicorn server.main:app --host 0.0.0.0 --port $PORT`
   - Env: `DATA_SOURCE=sim`, `SEED_DEMO_DATA=true`, `JWT_SECRET`/`ENCRYPTION_KEY`
     auto-generated, Python `3.12.7`.
   - Health check: `/api/v1/health`
3. Wait for the first deploy, then copy the service URL, e.g.
   `https://pathwise-ai-api.onrender.com`. Open `…/docs` to confirm.

> Free tier sleeps after ~15 min idle and cold-starts (~30–50 s) on the next
> request. The frontend handles this — the dashboard loads and the WebSocket
> auto-reconnects once the API wakes.

**CLI alternative:** `render` CLI or just connect the repo in the dashboard.

---

## 2. Frontend → Vercel

The repo ships **`frontend/vercel.json`** (SPA rewrites + `build` output dir).

### Option A — Dashboard
1. [vercel.com](https://vercel.com) → **Add New… → Project** → import `pathwise-ai`.
2. Set **Root Directory** = `frontend`.
3. Add an **Environment Variable**: `VITE_API_URL` = your Render URL from step 1
   (e.g. `https://pathwise-ai-api.onrender.com`).
4. Deploy. Vercel auto-detects Vite; `vercel.json` sets output dir `build` and the
   SPA catch-all rewrite so deep links (`/login`, `/admin/dashboard`) don't 404.

### Option B — CLI
```bash
cd frontend
vercel link               # select/create the project
vercel env add VITE_API_URL production    # paste the Render URL
vercel --prod
```

---

## 3. GitHub

```bash
git init
git add -A
git status                 # confirm no *.db, *.key, .venv*, real_world/*.parquet
git commit -m "PathWise AI — initial public release"
gh repo create vineethkodakandla/pathwise-ai --public --source=. --push
```

---

## 4. Local full stack (verification)

```bash
pip install -r requirements-cloud.txt
python run.py                          # backend :8000  (DATA_SOURCE=sim)
cd frontend && npm install && npm run dev   # frontend :3000
```
The Vite dev server proxies `/api` and `/ws` to `:8000`, so `VITE_API_URL` is left
unset locally. Log in with the demo credentials in the README.

---

## 5. Notes & limits

- **Why not the backend on Vercel?** It's stateful (in-memory singleton mutated by
  always-on asyncio loops) and serves a 1 Hz WebSocket — neither fits ephemeral
  serverless functions. A long-running container (Render/Railway/Fly) is the right host.
- **Heavy/optional deps** (`torch`, `pysnmp`, `pygnmi`, `pybatfish`, `grpcio`) are
  **not** in `requirements-cloud.txt`; they're only needed for live-hardware mode
  (`DATA_SOURCE=live`) or LSTM training, and the app degrades gracefully without them.
- **Secrets:** set `JWT_SECRET` and `ENCRYPTION_KEY` in any real deployment (Render's
  blueprint generates them). Without them the app boots with ephemeral random values
  (tokens won't survive a restart) and prints a warning.
- **Railway/other PaaS:** a `Procfile` and `.python-version` are included.
