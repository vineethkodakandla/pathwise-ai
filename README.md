# PathWise AI

A prototype SD-WAN management dashboard built by a four-person team (Team Pathfinders) as the course project for COSC 6370-001 Advanced Software Engineering, Spring 2026.

> **Status: course prototype.** The hosted demo runs on simulated telemetry. Several subsystems in this repository (LSTM training, SDN controller clients, Mininet/Batfish validation, NETCONF delivery, hardware collectors) were designed and partly implemented, but the demo does not exercise them and no test verifies them end to end. The table below says which parts are which.

## Live demo

| | |
|---|---|
| Dashboard (Vercel) | https://pathwise-ai-swart.vercel.app |
| API docs (Render) | https://pathwise-ai-api.onrender.com/docs |

Use the **Admin demo** or **Business owner demo** button on the sign-in page. No passwords are needed or published.

- **Demo sessions are read-only.** The backend runs with `DEMO_MODE=true` ([server/demo.py](server/demo.py)) and rejects every change (user management, billing, tickets, policies, routing rules) except sandbox validation and intent previews.
- **Tokens and passwords.** Demo tokens expire after 30 minutes. Every seeded account gets a new random password on each boot.
- **Cold starts.** The backend is on Render's free tier, so the first request after it sleeps can take 30 to 50 seconds.

## What runs in the demo, and what does not

| Area | In the hosted demo | In the repository but not exercised |
|---|---|---|
| Telemetry | A synthetic simulator generates 1 Hz samples for four links (fiber, broadband, satellite, 5G) with noise, a daily cycle and random brownouts (`server/simulator.py`). | SNMP and gNMI collectors for a live mode (`server/collectors/`). A NetFlow parser in the earlier `services/` design. |
| Forecasting | A trend-plus-noise heuristic over the last 20 samples produces a 30-step (30 s) forecast and a link health score (`server/lstm_engine.py`). The API health endpoint reports `lstm_enabled: false`. | An LSTM with temporal attention (60 s input window, 30 s output horizon) and its training scripts (`services/prediction-engine/`, `ml/scripts/`). No trained weights or training data are published, so the accuracy figures shown in the dashboard and `ml/checkpoints/training_log.json` cannot be reproduced from this repository. |
| "LSTM on vs off" panel | Illustrative only. The simulator sets the "on" latency and jitter averages to 80% of the "off" averages. | None. |
| Traffic steering | The simulator generates steering events and the dashboard shows them. Manual routing rules are blocked in the read-only demo. Locally they are stored in memory. | OpenDaylight and ONOS REST clients (`server/sdn_adapter.py`) and a make-before-break handoff routine (`server/routing.py`) that only the test suite calls. No controller is contacted and packet loss is never measured. |
| Digital-twin sandbox | An in-memory simulation of the validation steps (`server/sandbox.py`). The loop and reachability checks are randomized, and "under 5 s" is a threshold the code checks, not a measured result. | Mininet and Batfish integration paths. Neither is verified, and a Batfish error counts as a pass. |
| Intent-based management | A rule-based (regular expression) parser turns common English commands into structured policies and renders an illustrative YANG-style XML payload. | NETCONF delivery through `ncclient`, off by default. The generated XML uses non-standard elements and has not been validated against a device. |
| Dashboard | React 18, TypeScript and Vite, with Recharts charts and 1 Hz WebSocket updates. | None. |
| App-Priority QoS | You can view apps and priorities, but changes are blocked in the demo. Locally, the default simulate mode only logs rules. | Windows `New-NetQosPolicy` and Linux `tc` enforcement for the machine the server runs on. |
| Auth and audit | JWT sign-in with bcrypt-hashed passwords. A SHA-256 hash-chained audit log with an integrity check (`GET /api/v1/audit/verify`), kept in memory. | Role-based access checks, which are only partly consistent. See the limitations below. |
| Storage | In-memory state, plus SQLite for accounts, billing, sites and tickets. | TimescaleDB and Redis configuration for the Docker Compose stack. |

## Known limitations

- **Unmet design goals.** Hitless handoff with zero packet loss, forecasts 30 to 60 seconds ahead, and a Mininet/Batfish check in under 5 seconds were targets from the project requirements. None of them is demonstrated or measured here. The model's horizon is 30 seconds.
- **No vendor comparison.** There is no benchmark or comparison against commercial SD-WAN products.
- **Most core routes skip authentication by default.** `AUTH_ENABLED` defaults to `false`. In that mode the core routes in `server/main.py` treat every caller as a network admin, and only the multi-tenant routers under `server/routers/` require a token. The public demo is protected by the read-only guard in `server/demo.py`, not by these role checks. Do not expose a non-demo instance to the internet.
- **Role names disagree across files.** `server/rbac.py` defines five roles, `server/auth.py` accepts seven (adding `SUPER_ADMIN` and `BUSINESS_OWNER`), and the multi-tenant routers check `SUPER_ADMIN` and `BUSINESS_OWNER` directly.
- **The audit log resets and can report false breaks.** It is lost on restart and keeps the most recent 10,000 entries. Once older entries are dropped, the integrity check reports a break that did not happen.
- **Two backends are in the repo.** `services/` is an earlier microservice design (API gateway, prediction engine, traffic steering, digital twin, telemetry ingestion). The unit tests and the Docker Compose file still use it, but the deployed app is the consolidated FastAPI server in `server/`.
- **Older documents state targets as results.** The design documents, `build_pptx.py` and the slide deck repeat some of the goals above as if they were achieved. Treat them as the project plan.

## Run locally

```bash
# Backend: torch-free sim mode
python -m venv .venv && .venv\Scripts\activate        # Windows
pip install -r requirements-cloud.txt
python run.py                                          # http://localhost:8000/docs

# Frontend (new terminal)
cd frontend
npm install
npm run dev                                            # http://localhost:3000
```

**Seeded accounts**

- The backend seeds a SQLite database on first start: one super admin (`admin@pathwise.ai`) and eight business-owner accounts.
- Set `SEED_DEMO_PASSWORD` before the first start to choose their password. Otherwise each account gets a random password, printed in the server log.
- Delete `pathwise_local.db` to re-seed.
- `server/auth.py` also creates five local-only accounts used by `tests/smoke_all_features.py`.
- To try the public read-only mode locally, start the backend with `DEMO_MODE=true`.

The Vite dev server proxies `/api` and `/ws` to the backend.

## Tests and CI

```bash
pytest tests/unit                  # no external services needed
pytest tests/integration           # steering and telemetry tests need Redis; the digital-twin test skips without Mininet
```

- `tests/smoke_all_features.py` walks the software requirements against a running server. In simulate mode it reports the hardware-bound requirements as SKIP: ODL/ONOS, hitless handoff, TCP session preservation, Mininet, Batfish, 100-site scale and SNMP/NetFlow.
- `.github/workflows/ci.yml` checks Python code for syntax errors and undefined names, runs the unit and integration tests, and type-checks and builds the frontend.
- Earlier CI runs never passed: the first failed to start and the next two stopped at lint. Check the Actions tab for the current status.

## Deploy

- **Backend:** Render, via the Blueprint in `render.yaml`. It sets `DEMO_MODE=true` and `ENFORCER_MODE=simulate`.
- **Frontend:** Vercel, with Root Directory `frontend` and `VITE_API_URL` set to the Render URL.

Full walkthrough: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Repository layout

```
server/      FastAPI app the demo runs: auth, audit log, simulator, forecaster, sandbox, IBN parser, QoS logic, multi-tenant routers
frontend/    React 18 + TypeScript + Vite dashboard
services/    earlier microservice design (not deployed); used by the unit tests
ml/          LSTM training and evaluation scripts and notebooks (no weights or data committed)
infra/       TimescaleDB, Redis, nginx and Mininet configuration for Docker Compose
scripts/     demo data seeding, simulators, deployment checks
tests/       unit, integration, UI, load and requirement smoke tests
docs/        implementation guide, deployment guide, OpenAPI spec
```

## Team

This public repository is a squashed snapshot of the team's working repository, so its git history does not show who wrote what. The table gives each member's planned responsibilities from the project plan. [CONTRIBUTORS.md](CONTRIBUTORS.md) has per-module detail.

| Member | Planned responsibilities |
|---|---|
| Vineeth Reddy Kodakandla | Project manager. Backend API, JWT authentication, SHA-256 hash-chained audit log, application-layer QoS logic, DevOps |
| Meghana Nalluri | Requirements lead. ML pipeline, LSTM training |
| Bharadwaj Jakkula | Design and test lead. React dashboard, IBN, test automation |
| Sricharitha Katta | Configuration and technical lead. Mininet/Batfish, SDN clients |

## License

Academic project for COSC 6370-001 Advanced Software Engineering, Spring 2026. Not for production use.
