# Contributors — Team Pathfinders

PathWise AI was built collaboratively by four students for **COSC 6370-001 —
Advanced Software Engineering** (Spring 2026). This file records what each
team member is responsible for; the git commit history under each member's
GitHub account is the timestamped audit trail.

The role assignments below mirror the Implementation Guide (§11) and
README.md (§11). Each member is the **DRI (Directly Responsible Individual)**
for the modules in their column — they make commits, run tests, and answer
Q&A for that domain.

---

## Team

### Vineeth Reddy Kodakandla — `@vineethkodakandla`
**Role:** Project Manager — API gateway, integration, DevOps
**SRS Reqs owned:** Req-Func-Sw-15, -16, -17, -18, -21
**Backend code (~3.7K LOC):**
- `server/main.py` — FastAPI app, all top-level routes, lifespan & shutdown handlers
- `server/auth.py`, `server/rbac.py` — JWT + bcrypt + 5-role RBAC enforcement (UC-6)
- `server/audit.py` — tamper-evident audit log with SHA-256 chain (Req-Func-Sw-18)
- `server/alerts.py` — threshold alerts + dashboard panel + email (Req-Func-Sw-17)
- `server/reports.py` — PDF + CSV exports (Req-Func-Sw-21)
- `server/db.py`, `server/encryption.py` — persistence + AES-256
- `server/state.py`, `server/redis_broker.py` — in-memory + pub/sub state
- `server/ibn_engine.py` — NL parser, intent store, YANG/NETCONF generator,
  `deploy_intent` integration entrypoint
- `server/app_qos/signatures.py`, `priority_manager.py`, `selective_degrader.py`
  — application-layer QoS logic (App Priority Switch + Selective IP Degrade)
- `server/routers/admin_portal.py`, `billing.py`, `tickets.py`, `profile.py`,
  `app_priority.py` — multi-tenant admin/business APIs

**DevOps / infra:**
- `docker-compose.yml`, `Dockerfile.api`, `requirements*.txt`
- `infra/db/init.sql`, `infra/nginx/`, `infra/redis/`
- `run.py`, `start_demo.bat`, `stop_demo.bat`

**Document owned:** Project Plan (PP) v1.0
**Demo focus:** end-to-end smoke run, audit log integrity, PDF/CSV export, admin portal.

---

### Meghana Nalluri — `@<github-handle>`
**Role:** Requirements lead — ML pipeline, LSTM training, telemetry collectors
**SRS Reqs owned:** Req-Func-Sw-1, -2, -3, -14, -20
**Backend code (~3.3K LOC):**
- `server/lstm_engine.py` — PyTorch LSTM with attention, 1 Hz prediction loop,
  health-score generation, confidence emission (Req-Func-Sw-2, -3, -14)
- `server/collector.py`, `server/simulator.py` — live + synthetic telemetry feeds
- `server/collectors/` entire directory (~2.2K LOC):
  - `base.py`, `snmp.py`, `netflow.py` — SNMP v2c+ / NetFlow v9+ ingest (Req-Func-Sw-20)
  - `fiber.py`, `fiveg.py`, `satellite.py`, `broadband.py`, `ethernet.py`,
    `wifi.py`, `replay.py`, `starlink_stub.py` — per-link adapters
- `server/routers/lstm_control.py` — model management API (train/activate/hyperparams)

**ML pipeline:**
- `ml/data_generation/` — Mininet-based synthetic telemetry generator
- `ml/scripts/train.py`, `ml/scripts/evaluate.py` — training + evaluation
- `ml/notebooks/` — exploratory / hyperparameter analysis
- `ml/checkpoints/` — saved model artifacts

**Document owned:** Project Vision Document (PVD) v1.2 + LSTM training/evaluation report
**Demo focus:** model architecture walkthrough, prediction accuracy on test set,
collector live feed.

---

### Bharadwaj Jakkula — `@<github-handle>`
**Role:** Design/Test lead — React dashboard, IBN console UI, test automation
**SRS Reqs owned:** Req-Func-Sw-11 (UI), -13, -19
**Frontend code (~6.2K LOC) — entire React SPA:**
- `frontend/src/App.tsx`, routing, layout shell
- `frontend/src/pages/LoginPage.tsx` (122)
- `frontend/src/pages/Dashboard.tsx` (496) — main multi-link dashboard
- `frontend/src/pages/IBNConsole.tsx` (434) — natural-language policy console
- `frontend/src/pages/HealthScoreboardPage.tsx` + `components/HealthScoreboard/`
- `frontend/src/pages/SandboxViewer.tsx` (596), `NetworkSimulation.tsx` (975)
- `frontend/src/pages/AuditLog.tsx`, `Reports.tsx`, `AdminPanel.tsx`
- `frontend/src/pages/admin/*` — admin dashboards (LSTMControlCenter,
  UserManagement, AppQoSOverview, RevenueDashboard, SiteAnalytics, TicketDashboard)
- `frontend/src/pages/user/*` — user dashboards (UserDashboard, UserIBN,
  UserAudit, UserReports, UserTelemetry, UserSandbox, UserProfile,
  AppPriorityManager, BillingDashboard, SupportTickets, MySitesAnalytics, TrafficOverview)
- `frontend/src/components/SelectiveIPDegrade.tsx`
- `frontend/src/hooks/`, `frontend/src/services/api.ts`, `frontend/src/utils/`

**Test suite (~entire `tests/` tree):**
- `tests/unit/` — `test_intent_parser.py`, `test_lstm_network.py` (shared with Meghana),
  `test_collector.py`, `test_health_score.py`, `test_feature_engineering.py`,
  `test_steering_engine.py`, `test_flow_manager.py`, `test_snmp_parser.py`
- `tests/integration/` — telemetry / prediction / sandbox / steering pipelines,
  TC5 SLA, TC6 hitless, TC16 email alerts
- `tests/test_app_qos/` — App Priority Switch test pack
- `tests/smoke_all_features.py` — end-to-end SRS coverage
- `tests/test_critical_tcs.py`, `tests/test_live_server.py`, `tests/test_sdd_architecture.py`
- `tests/ui/`, `tests/e2e/`, `tests/load/`

**Document owned:** Software Test Description (STD) + presentation slides
**Demo focus:** dashboard walkthrough, IBN console live, test suite results.

---

### Sricharitha Katta — `@<github-handle>`
**Role:** Config/Tech lead — Mininet/Batfish, SDN integration, Digital Twin, OS-level QoS
**SRS Reqs owned:** Req-Func-Sw-4, -5, -6, -7, -8, -9, -10
**Backend code (~2.9K LOC):**
- `server/sdn_adapter.py` — OpenDaylight + ONOS REST clients (Req-Func-Sw-5)
- `server/routing.py` — flow-table apply / rollback orchestration
- `server/sandbox.py` — Mininet topology mirroring + Batfish loop & ACL
  validation (Req-Func-Sw-8, -9, -10, UC-4)
- `server/session_manager.py` — TCP/VoIP session state preservation
  during hitless handoff (Req-Func-Sw-6, -7)
- `server/traffic_shaper.py` — OS-level QoS scaffold (Linux `tc` HTB +
  Windows `New-NetQosPolicy` + simulate mode)
- `server/app_qos/bandwidth_enforcer.py` — Windows hosts/NRPT/firewall/QUIC
  enforcement engine (the OS-level half of App Priority Switch)
- `server/app_qos/flow_detector.py` — live socket inspection for app
  identification

**Infra:**
- `infra/mininet/` — Dockerfile + `scripts/validation_server.py` (sandbox runner)
- `infra/batfish/` — Batfish container config
- `infra/qos_scripts/` — generated PowerShell QoS scripts

**Document owned:** Software Design Document (SDD) + architecture diagrams
**Demo focus:** sandbox validation pipeline, ODL flow-table read-back,
hitless handoff session preservation, OS-level QoS commands.

---

## Tools and collaboration practices

- **AI-assisted development.** Team members used **Claude Code (Anthropic)** as a
  pair-programming assistant during implementation. All code was reviewed,
  tested, and committed by team members; the team is fully able to explain
  every component on demand. This is documented per project guidelines.
- **Code review.** Pull requests for any change touching another DRI's domain
  are reviewed by that DRI before merge.
- **Document collaboration.** Word / Google Docs revision history is preserved
  alongside the annotated PDFs in this repo for the PVD, SRS, SDD, STD, and
  Project Plan — those revision histories show multi-author edits over the
  project timeline.

## How to verify contributions

1. **Per-author commit count:** `git shortlog -sne`
2. **Per-file authorship:** `git log --follow --pretty=format:'%an %ai  %s' <file>`
3. **GitHub contributors page:** <https://github.com/vineethkodakandla/PATHWISEAI/graphs/contributors>
4. **Per-domain test runs:** each DRI's section above lists their test files; running them is reproducible end-to-end evidence the modules work.

---

*Sources for the role assignments: README.md §11, PathWise_AI_Implementation_Guide.md §11.*
