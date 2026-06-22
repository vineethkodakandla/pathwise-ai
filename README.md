# PathWise AI

**AI-Powered SD-WAN Management Platform**
Team Pathfinders | COSC6370-001 Advanced Software Engineering | Spring 2026

![React](https://img.shields.io/badge/React-18-61dafb?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.3-3178c6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-8-646cff?logo=vite&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.1x-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776ab?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-Academic-lightgrey)

> A full-stack, real-time SD-WAN management dashboard: an LSTM forecasts WAN link
> degradation seconds ahead, traffic is autonomously re-steered, every change is
> validated in an in-memory digital-twin sandbox, and natural-language intents
> compile to network policy — all behind a JWT/RBAC multi-tenant portal.

### 🔗 Live Demo

| | URL |
|---|---|
| **Dashboard (Vercel)** | _add your Vercel URL after deploy_ |
| **API + docs (Render)** | _add your Render URL after deploy_ → `…/docs` |

The frontend is resilient: if the backend is asleep (free-tier cold start) the UI
still loads and reconnects automatically.

### ▶️ Run locally in 3 minutes (no Docker, no GPU, no heavy deps)

```bash
# 1) Backend — torch-free "sim" mode, ~11 light deps
python -m venv .venv && .venv\Scripts\activate        # Windows
pip install -r requirements-cloud.txt
python run.py                                          # → http://localhost:8000/docs

# 2) Frontend (new terminal)
cd frontend
npm install
npm run dev                                            # → http://localhost:3000
```

The backend runs the synthetic simulator by default (`DATA_SOURCE=sim`), auto-seeds
a demo database (SQLite), and the LSTM falls back to a NumPy heuristic when PyTorch
isn't installed — so the whole platform runs on a laptop with the minimal deps above.
The Vite dev server proxies `/api` and `/ws` to the backend automatically.

### 🔑 Demo credentials

| Role | Email | Password |
|---|---|---|
| Super Admin | `admin@pathwise.ai` | `Admin@PathWise2026` |
| Business Owner | `marcus@riveralogistics.com` | `Rivera@2026` |

(Full persona list is seeded by `scripts/seed_ui_data.py`. The demo DB is gitignored
and regenerated on first run.)

### ☁️ Deploy to the cloud

Frontend → **Vercel** (static SPA), backend → **Render** (FastAPI + WebSockets, sim
mode). One-click via the included `frontend/vercel.json` and `render.yaml`. Full
walkthrough: **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

---

## 1. Overview

PathWise AI is an intelligent, vendor-agnostic SD-WAN management platform that
turns enterprise network management from reactive to predictive. An LSTM neural
network forecasts WAN link degradation 30–60 seconds ahead; the platform
autonomously reroutes mission-critical traffic (VoIP, video, financial) through
an SDN controller, achieving **hitless handoff with zero packet loss**. Every
proposed routing change is first validated in a Mininet/Batfish **digital-twin
sandbox** (< 5 s) before it is allowed to touch production.

A complementary **App-Priority Switch** module lets end users assign
`HIGH / NORMAL / LOW` priority to detected applications (Zoom, Teams, YouTube,
Netflix, …). The bandwidth enforcer then applies real QoS rules on the host
(`tc` on Linux, `New-NetQosPolicy` on Windows).

### Core Features

| # | Feature | Description |
|---|---|---|
| 1 | Predictive Telemetry Engine | LSTM + attention forecasts latency/jitter/loss at t+30s, t+60s |
| 2 | Autonomous Traffic Steering | Pre-emptive, hitless flow-table update via OpenDaylight / ONOS |
| 3 | Digital Twin Sandbox | Mininet topology + Batfish policy check in < 5 s |
| 4 | Intent-Based Management | Natural-language policies → YANG/NETCONF payloads |
| 5 | Multi-Link Health Scoreboard | Real-time D3.js dashboard over WebSocket |
| 6 | App-Priority Switch | Per-app QoS enforcement (Windows PowerShell / Linux `tc`) |
| 7 | RBAC + Audit | JWT auth, 5-role RBAC, tamper-evident audit log |

---

## 2. Repository Layout

```
PATHWISEAI/
├── run.py                     # offline launcher (uvicorn)
├── start_enforcer.bat         # Windows admin launcher for real QoS
├── setup_pathwise.py          # one-shot dependency installer/checker
├── requirements.txt           # all Python dependencies
├── docker-compose.yml         # full-stack container deployment
├── server/                    # FastAPI backend
│   ├── main.py                # app entry point
│   ├── routers/               # REST/WS routers (telemetry, steering, apps, ibn…)
│   ├── app_qos/               # App-Priority Switch (enforcer, signatures)
│   ├── lstm_engine.py         # trained LSTM inference
│   ├── auth.py, rbac.py       # JWT + role checks
│   ├── audit.py, reports.py   # audit log + PDF/CSV reports
│   └── sandbox.py             # digital-twin validator
├── frontend/                  # React 18 + TypeScript + Vite dashboard
│   └── src/pages, components  # scoreboard, IBN, policies, audit, reports
├── ml/                        # LSTM training pipeline
│   ├── scripts/train_lstm.py
│   └── checkpoints/
├── infra/                     # TimescaleDB init, Redis, nginx configs
├── tests/                     # pytest unit + integration suites
└── docs/                      # API spec + design documents
```

---

## 3. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, TailwindCSS, Zustand, D3.js, Recharts |
| API | FastAPI, Uvicorn (Python 3.11+) |
| ML | PyTorch 2.x, NumPy, Pandas, scikit-learn |
| Auth | JWT (PyJWT), bcrypt |
| Persistence | TimescaleDB (prod) / SQLite (local) via SQLAlchemy |
| Messaging | Redis 7 (prod) / in-proc pub/sub (local) |
| SDN | OpenDaylight, ONOS (REST northbound) |
| Validation | Mininet (WSL2 on Windows), Batfish (pybatfish) |
| Telemetry | SNMP (pysnmp), gNMI (pygnmi), NetFlow |
| QoS enforcement | Linux `tc`, Windows `New-NetQosPolicy` |
| Container | Docker, Docker Compose |

---

## 4. Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11 or newer |
| Node.js | 18 LTS or newer (npm 9+) |
| OS | Windows 10/11, macOS 12+, or Linux |
| Docker (optional, for full stack) | 24+ |
| WSL2 (optional, for Mininet data generation) | Ubuntu 22.04 |
| RAM | ≥ 8 GB local, ≥ 32 GB for full production deployment |

---

## 5. Installation

### Option A — automatic (recommended)

```bash
python setup_pathwise.py              # installs everything + verifies imports
python setup_pathwise.py --check      # dry-run: report only, no installs
```

The script:
- verifies Python ≥ 3.11 and Node ≥ 18
- runs `pip install -r requirements.txt`
- runs `npm install` in `frontend/`
- import-checks FastAPI, Uvicorn, PyTorch, JWT, bcrypt, psutil, etc.
- warns on missing optional components (Docker, WSL, Mininet)

### Option B — manual

```bash
# 1. Python backend
python -m pip install --upgrade pip
pip install -r requirements.txt

# 2. Frontend
cd frontend
npm install
cd ..
```

---

## 6. Running the Platform

### Local development (no Docker)

Terminal 1 — backend:

```bash
python run.py
# → http://localhost:8000/docs  (OpenAPI UI)
```

Terminal 2 — frontend:

```bash
cd frontend
npm start
# → http://localhost:3000       (dashboard; proxies /api and /ws to :8000)
```

### Real Windows QoS enforcement (App-Priority Switch)

Right-click **`start_enforcer.bat` → Run as administrator**. This sets
`ENFORCER_MODE=powershell` and dispatches real `New-NetQosPolicy` rules.
Without admin rights the enforcer silently falls back to simulate mode.

### Docker Compose (full stack)

```bash
docker compose up --build
# dashboard  → http://localhost:3000
# api        → http://localhost:8000
# timescale  → localhost:5432
# redis      → localhost:6379
```

### Environment variables (`.env`)

Copy `.env.example` to `.env` and adjust. Key variables:

```
JWT_SECRET=change-me
ENFORCER_MODE=simulate        # simulate | tc | powershell
WAN_INTERFACE=Ethernet
TOTAL_LINK_MBPS=100
DATA_SOURCE=sim               # sim | live
ODL_HOST=localhost
ONOS_HOST=localhost
```

---

## 7. Running Tests

```bash
pytest tests/ -v                  # full suite
pytest tests/test_app_qos -v      # App-Priority module
pytest tests/ -k steering         # keyword filter
```

---

## 8. Key API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/auth/login` | JWT authentication |
| POST | `/api/v1/auth/register` | Create user (requires admin token, even when AUTH_ENABLED=false) |
| GET  | `/api/v1/telemetry/{link_id}` | Per-link telemetry |
| GET  | `/api/v1/predictions/all` | Current LSTM forecasts |
| POST | `/api/v1/sandbox/validate` | Run digital-twin check |
| POST | `/api/v1/ibn/parse` | Preview a natural-language intent (400 on unparseable) |
| POST | `/api/v1/ibn/intents` | Submit an intent-based policy |
| POST | `/api/v1/ibn/deploy` | Validate + deploy an intent |
| GET  | `/api/v1/apps/active` | Detected running applications |
| POST | `/api/v1/apps/priorities` | Apply per-app QoS rules |
| GET  | `/api/v1/apps/enforcement-status` | QoS enforcer state |
| WS   | `/ws/scoreboard` | Real-time health-score stream |
| WS   | `/api/v1/apps/ws/{user_id}/quality` | Per-user quality updates |

Full schema: http://localhost:8000/docs

---

## 9. Default Roles (RBAC)

| Role | Capability |
|---|---|
| `SUPER_ADMIN` | All admin endpoints + cross-user visibility |
| `NETWORK_ADMIN` | Telemetry, steering, policies |
| `IT_MANAGER` | Read-only dashboards + reports |
| `MSP_TECHNICIAN` | Multi-tenant ops |
| `BUSINESS_OWNER` / `END_USER` | App-Priority self-service |

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `winerror 10013` binding port 8000 | Another process holds the port — kill it or run on `--port 8001` |
| App-Priority shows `mode: simulate` | Set `ENFORCER_MODE=powershell` *and* run as Administrator |
| `pybatfish` import fails | Start the Batfish container: `docker run -d -p 9997:9997 batfish/allinone` |
| `torch` download is slow | Pre-install with `pip install torch --index-url https://download.pytorch.org/whl/cpu` |
| Frontend cannot reach API | Ensure backend is on `:8000`; Vite proxy is configured in `frontend/vite.config.ts` |

---

## 11. Team

| Member | Role |
|---|---|
| Vineeth Reddy Kodakandla | Project manager — API, integration, DevOps |
| Meghana Nalluri | Requirements lead — ML pipeline, LSTM training |
| Bharadwaj Jakkula | Design/Test lead — React dashboard, IBN, test automation |
| Sricharitha Katta | Config/Tech lead — Mininet/Batfish, SDN clients |

---

## 12. License

Academic project — COSC6370-001 Advanced Software Engineering, Spring 2026.
Not for production use without authorization.
