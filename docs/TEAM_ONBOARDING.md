# Team Onboarding — getting every member onto the GitHub history

This file is the operational guide for the three teammates who haven't
committed yet. Each section is a copy-paste recipe. Roles below mirror
README.md §11 and CONTRIBUTORS.md.

> **Why this matters:** the audit trail is `git log` + GitHub's contributors
> page. Each commit must be made under the **author's own git identity**
> (matching their GitHub email), pushed from their own clone. No one else
> commits on anyone's behalf.

---

## Step 0 — One-time GitHub setup (Vineeth does this once)

On <https://github.com/vineethkodakandla/PATHWISEAI> →
**Settings → Collaborators → Add people** → invite each of the three teammates
by their GitHub username. They each accept via email.

Verify with:

```bash
gh api repos/vineethkodakandla/PATHWISEAI/collaborators --jq '.[].login'
```

You should see four logins listed.

---

## Step 1 — Each teammate clones and configures their identity

The three other members each run **on their own machine**:

```bash
git clone https://github.com/vineethkodakandla/PATHWISEAI.git
cd PATHWISEAI

# CRITICAL: use your own name and your GitHub-verified email.
# To find your verified email: GitHub → Settings → Emails.
git config user.name  "Your Full Name"
git config user.email "yourname@example.com"

# Sanity check:
git config user.name
git config user.email
```

If `user.email` does not match a verified GitHub email, GitHub will
**not** credit your contributions on the contributor graph.

---

## Step 2 — Each member's first-commit task

Pick the row matching your role. Each task is real engineering work
(not symbolic). Commit it, push it, then move to step 3.

### Vineeth (PM) — commit the work-in-progress already on disk

```bash
# You already have ~30 modified files + the CONTRIBUTORS/TEAM_ONBOARDING
# additions. Commit them in 4-5 logical batches:

# Batch 1: Selective IP Degrade backend
git add server/app_qos/selective_degrader.py server/routers/app_priority.py \
        server/ibn_engine.py
git commit -m "Add Selective IP Degrade backend + IBN NL integration"

# Batch 2: Selective IP Degrade UI
git add frontend/src/components/SelectiveIPDegrade.tsx \
        frontend/src/pages/user/AppPriorityManager.tsx
git commit -m "Add Selective IP Degrade UI panel"

# Batch 3: Test infrastructure
git add tests/smoke_all_features.py
git commit -m "Add full-feature smoke test suite covering all SRS Req-Func-Sw"

# Batch 4: traffic_shaper simulate-mode fix
git add server/traffic_shaper.py
git commit -m "traffic_shaper: short-circuit elevated PowerShell in simulate mode"

# Batch 5: contributor docs
git add CONTRIBUTORS.md TEAM_ONBOARDING.md
git commit -m "Add CONTRIBUTORS.md and TEAM_ONBOARDING.md"

git push origin main
```

### Meghana (Requirements / ML lead)

Real first-commit work:

1. Document the LSTM architecture you built. Create `ml/README.md`
   describing input shape, sequence length, hidden size, attention,
   training hyperparameters, and the held-out test MSE achieved.
2. Add 3 new unit tests for `server/lstm_engine.py` covering edge cases
   you actually thought about during development:
   - empty telemetry buffer (cold start)
   - NaN values in incoming samples
   - prediction window when recent samples are missing

```bash
# create your work
$EDITOR ml/README.md
$EDITOR tests/unit/test_lstm_edge_cases.py    # new file

# stage and commit
git add ml/README.md
git commit -m "Document LSTM architecture and training pipeline"

git add tests/unit/test_lstm_edge_cases.py
git commit -m "Add LSTM edge-case tests: cold start, NaN, missing samples"

# pull then push (in case Vineeth pushed in the meantime)
git pull --rebase origin main
git push origin main
```

### Bharadwaj (Design/Test lead)

Real first-commit work:

1. Document the IBN grammar — every NL pattern the parser supports.
   Create `frontend/IBN_GRAMMAR.md` listing each phrasing with examples
   and the resulting `IntentAction`. This is a teaching artifact you
   can show during the demo.
2. Add a frontend smoke test that exercises the IBN console end-to-end
   (mount → submit "Throttle YouTube to 500 kbps" → assert intent appears
   in the list). Place under `tests/ui/`.

```bash
$EDITOR frontend/IBN_GRAMMAR.md
$EDITOR tests/ui/test_ibn_console.tsx          # new file

git add frontend/IBN_GRAMMAR.md
git commit -m "Document complete IBN natural-language grammar"

git add tests/ui/test_ibn_console.tsx
git commit -m "Add IBN console end-to-end UI smoke test"

git pull --rebase origin main
git push origin main
```

### Sricharitha (Config/Tech lead)

Real first-commit work:

1. Add a Mermaid architecture diagram to `docs/architecture.md` showing
   the steering pipeline: telemetry → LSTM → health drop → sandbox
   validation → SDN flow-table update → audit. Diagrams render natively
   on GitHub.
2. Add an integration test for `server/session_manager.py` covering
   reconnect-on-handoff: simulate a TCP session, trigger a flow-table
   change, assert the session does not drop.

```bash
mkdir -p docs
$EDITOR docs/architecture.md
$EDITOR tests/integration/test_session_handoff.py    # new file

git add docs/architecture.md
git commit -m "Add steering pipeline architecture diagram"

git add tests/integration/test_session_handoff.py
git commit -m "Add session preservation integration test for hitless handoff"

git pull --rebase origin main
git push origin main
```

---

## Step 3 — Continue committing for the next 1–2 weeks

Each DRI works on real polish in their domain. Suggested cadence: **at
least one commit per teammate per day** for a week. That gives the
contributor graph a healthy spread.

Polish ideas per role:

- **Vineeth:** error-handling sweep across `server/main.py`, OpenAPI tag
  cleanup, `start_demo.bat` improvements, deployment notes in README.
- **Meghana:** hyperparameter tuning experiments (commit notebooks),
  expand collector unit tests, add a `data_generation/README.md`
  documenting the synthetic scenarios.
- **Bharadwaj:** add accessibility (ARIA) to dashboard components,
  expand `tests/test_app_qos/` coverage, add a frontend `README.md`.
- **Sricharitha:** add `infra/mininet/README.md` with topology
  instructions, integration tests for `sdn_adapter.py` (mock ODL
  responses), document the OS-level QoS sequence for both Windows
  and Linux.

---

## Step 4 — Co-authorship on genuinely shared commits

When two of you actually pair-program a change, append `Co-authored-by`
trailers — GitHub renders the commit as multi-author and credits both
contributor graphs:

```
git commit -m "$(cat <<'EOF'
Wire IBN console to selective_degrader live countdown

Co-authored-by: Bharadwaj Jakkula <bharadwaj@example.com>
EOF
)"
```

Use this only where collaboration was real — not as decoration on every
commit. The professor can spot fake co-authoring as easily as fake
committing.

---

## Step 5 — Verify the final state before submission

```bash
# Per-author commit counts and emails
git shortlog -sne origin/main

# Should show four lines, one per teammate, with non-trivial counts.

# GitHub contributor graph (open in browser):
# https://github.com/vineethkodakandla/PATHWISEAI/graphs/contributors

# Each member's per-file authorship:
git log --pretty=format:'%an %ai  %s' --follow server/lstm_engine.py | head -10
git log --pretty=format:'%an %ai  %s' --follow frontend/src/pages/IBNConsole.tsx | head -10
git log --pretty=format:'%an %ai  %s' --follow server/sandbox.py | head -10
```

The last three commands should show the respective DRIs as authors of
recent commits to their domain files.

---

## What NOT to do

- **Do not** change `git config user.name`/`user.email` to a teammate's
  identity to commit on their behalf. That's impersonation.
- **Do not** use `git commit --author="Name <email>"` to assign past
  commits to teammates. Detectable, dishonest.
- **Do not** use `git commit --date=...` to backdate commits. The
  CommitterDate still shows the real time, exposing the manipulation.
- **Do** be honest with the professor about the workflow. The CONTRIBUTORS
  preamble already discloses Claude Code use as a pair programmer; if
  asked, each DRI can demo and explain their domain — that's the real
  proof no one outsourced.

---

*Last updated: 2026-04-27. Author of this onboarding doc: Vineeth.*
