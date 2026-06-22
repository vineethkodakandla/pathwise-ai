#!/usr/bin/env python3
"""
PathWise AI — Build Orchestrator

Validates that the entire project structure is in place and all
required files exist. This is the first thing to run after cloning
or generating the project.

Usage:
    python build_orchestrator.py
"""

import os
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent

# Colors for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def check_file(path: str) -> bool:
    """Check if a file exists relative to project root."""
    return (ROOT / path).exists()


def check_dir(path: str) -> bool:
    """Check if a directory exists relative to project root."""
    return (ROOT / path).is_dir()


def main():
    print(f"\n{Colors.BOLD}{Colors.CYAN}PathWise AI — Build Orchestrator{Colors.END}")
    print(f"{Colors.CYAN}{'=' * 60}{Colors.END}\n")

    errors = []
    warnings = []
    passed = 0
    total = 0

    # ── Root / Config files ─────────────────────────────
    root_files = [
        "docker-compose.yml",
        "docker-compose.dev.yml",
        "build_orchestrator.py",
        ".gitignore",
        ".env.example",
        "pyproject.toml",
        "Makefile",
        "README.md",
    ]

    # ── GitHub Workflows ────────────────────────────────
    github_files = [
        ".github/workflows/ci.yml",
        ".github/workflows/ml-tests.yml",
    ]

    # ── API Gateway ─────────────────────────────────────
    api_gateway_files = [
        "services/api-gateway/Dockerfile",
        "services/api-gateway/requirements.txt",
        "services/api-gateway/app/__init__.py",
        "services/api-gateway/app/main.py",
        "services/api-gateway/app/config.py",
        "services/api-gateway/app/routers/__init__.py",
        "services/api-gateway/app/routers/telemetry.py",
        "services/api-gateway/app/routers/predictions.py",
        "services/api-gateway/app/routers/steering.py",
        "services/api-gateway/app/routers/sandbox.py",
        "services/api-gateway/app/routers/policies.py",
        "services/api-gateway/app/models/__init__.py",
        "services/api-gateway/app/models/schemas.py",
        "services/api-gateway/app/middleware/__init__.py",
        "services/api-gateway/app/middleware/auth.py",
        "services/api-gateway/app/websocket/__init__.py",
        "services/api-gateway/app/websocket/scoreboard.py",
    ]

    # ── Telemetry Ingestion ────────────────────────────
    telemetry_files = [
        "services/telemetry-ingestion/__init__.py",
        "services/telemetry-ingestion/collector.py",
        "services/telemetry-ingestion/main.py",
        "services/telemetry-ingestion/requirements.txt",
        "services/telemetry-ingestion/Dockerfile",
        "services/telemetry-ingestion/parsers/__init__.py",
        "services/telemetry-ingestion/parsers/snmp_parser.py",
        "services/telemetry-ingestion/parsers/netflow_parser.py",
        "services/telemetry-ingestion/parsers/streaming_telemetry.py",
    ]

    # ── Prediction Engine ──────────────────────────────
    prediction_files = [
        "services/prediction-engine/__init__.py",
        "services/prediction-engine/serve.py",
        "services/prediction-engine/Dockerfile",
        "services/prediction-engine/requirements.txt",
        "services/prediction-engine/model/__init__.py",
        "services/prediction-engine/model/lstm_network.py",
        "services/prediction-engine/model/trainer.py",
        "services/prediction-engine/model/inference.py",
        "services/prediction-engine/model/feature_engineering.py",
    ]

    # ── Traffic Steering ───────────────────────────────
    steering_files = [
        "services/traffic-steering/__init__.py",
        "services/traffic-steering/steering_engine.py",
        "services/traffic-steering/flow_manager.py",
        "services/traffic-steering/requirements.txt",
        "services/traffic-steering/Dockerfile",
        "services/traffic-steering/sdn_clients/__init__.py",
        "services/traffic-steering/sdn_clients/base.py",
        "services/traffic-steering/sdn_clients/opendaylight.py",
        "services/traffic-steering/sdn_clients/onos.py",
    ]

    # ── Digital Twin ───────────────────────────────────
    digital_twin_files = [
        "services/digital-twin/__init__.py",
        "services/digital-twin/twin_manager.py",
        "services/digital-twin/mininet_topology.py",
        "services/digital-twin/batfish_validator.py",
        "services/digital-twin/main.py",
        "services/digital-twin/requirements.txt",
        "services/digital-twin/Dockerfile",
    ]

    # ── Frontend ───────────────────────────────────────
    frontend_files = [
        "frontend/package.json",
        "frontend/Dockerfile",
        "frontend/tsconfig.json",
        "frontend/tailwind.config.js",
        "frontend/postcss.config.js",
        "frontend/nginx.conf",
        "frontend/public/index.html",
        "frontend/src/index.tsx",
        "frontend/src/index.css",
        "frontend/src/react-app-env.d.ts",
        "frontend/src/App.tsx",
        "frontend/src/types/index.ts",
        "frontend/src/pages/Dashboard.tsx",
        "frontend/src/pages/PolicyManager.tsx",
        "frontend/src/pages/SandboxViewer.tsx",
        "frontend/src/components/HealthScoreboard/HealthScoreboard.tsx",
        "frontend/src/components/HealthScoreboard/index.ts",
        "frontend/src/components/TopologyMap/TopologyMap.tsx",
        "frontend/src/components/TopologyMap/index.ts",
        "frontend/src/components/IBNConsole/IBNConsole.tsx",
        "frontend/src/components/IBNConsole/index.ts",
        "frontend/src/components/PredictionChart/PredictionChart.tsx",
        "frontend/src/components/PredictionChart/index.ts",
        "frontend/src/components/SteeringLog/SteeringLog.tsx",
        "frontend/src/components/SteeringLog/index.ts",
        "frontend/src/components/Layout/Header.tsx",
        "frontend/src/components/Layout/Sidebar.tsx",
        "frontend/src/components/Layout/index.ts",
        "frontend/src/hooks/useWebSocket.ts",
        "frontend/src/hooks/useTelemetry.ts",
        "frontend/src/services/api.ts",
        "frontend/src/services/websocket.ts",
        "frontend/src/store/networkStore.ts",
    ]

    # ── ML Pipeline ────────────────────────────────────
    ml_files = [
        "ml/__init__.py",
        "ml/scripts/__init__.py",
        "ml/scripts/generate_synthetic_data.py",
        "ml/scripts/train.py",
        "ml/scripts/evaluate.py",
        "ml/notebooks/01_data_exploration.ipynb",
        "ml/notebooks/02_feature_engineering.ipynb",
        "ml/notebooks/03_model_training.ipynb",
        "ml/notebooks/04_evaluation.ipynb",
    ]

    # ── Infrastructure ─────────────────────────────────
    infra_files = [
        "infra/db/init.sql",
        "infra/mininet/Dockerfile",
        "infra/mininet/topologies/sdwan_topology.py",
        "infra/mininet/scripts/start_topology.sh",
    ]

    # ── Tests ──────────────────────────────────────────
    test_files = [
        "tests/__init__.py",
        "tests/conftest.py",
        "tests/unit/__init__.py",
        "tests/unit/test_intent_parser.py",
        "tests/unit/test_health_score.py",
        "tests/unit/test_lstm_network.py",
        "tests/unit/test_feature_engineering.py",
        "tests/unit/test_steering_engine.py",
        "tests/unit/test_flow_manager.py",
        "tests/unit/test_collector.py",
        "tests/unit/test_snmp_parser.py",
        "tests/integration/__init__.py",
        "tests/integration/test_steering_pipeline.py",
        "tests/integration/test_telemetry_pipeline.py",
        "tests/integration/test_prediction_pipeline.py",
        "tests/integration/test_sandbox_pipeline.py",
        "tests/e2e/__init__.py",
        "tests/e2e/test_api_gateway.py",
        "tests/e2e/test_full_flow.py",
    ]

    # ── Required Directories ───────────────────────────
    required_dirs = [
        "ml/data/raw",
        "ml/data/processed",
        "ml/data/synthetic",
        "ml/checkpoints",
        "infra/batfish/configs",
    ]

    # ── Run all checks ─────────────────────────────────
    all_file_groups = {
        "Root / Config Files": root_files,
        "GitHub Workflows": github_files,
        "API Gateway Service": api_gateway_files,
        "Telemetry Ingestion Service": telemetry_files,
        "Prediction Engine Service": prediction_files,
        "Traffic Steering Service": steering_files,
        "Digital Twin Service": digital_twin_files,
        "Frontend": frontend_files,
        "ML Pipeline": ml_files,
        "Infrastructure": infra_files,
        "Tests": test_files,
    }

    for group_name, files in all_file_groups.items():
        group_ok = 0
        group_total = len(files)

        for f in files:
            total += 1
            if check_file(f):
                passed += 1
                group_ok += 1
            else:
                errors.append(f)

        status = f"{Colors.GREEN}PASS" if group_ok == group_total else f"{Colors.RED}FAIL"
        print(f"  {status}{Colors.END}  {group_name}: {group_ok}/{group_total} files")

    # Check directories
    print()
    dir_passed = 0
    for d in required_dirs:
        total += 1
        if check_dir(d):
            passed += 1
            dir_passed += 1
        else:
            warnings.append(f"Directory missing: {d}")

    status = f"{Colors.GREEN}PASS" if dir_passed == len(required_dirs) else f"{Colors.YELLOW}WARN"
    print(f"  {status}{Colors.END}  Required Directories: {dir_passed}/{len(required_dirs)}")

    # ── Summary ────────────────────────────────────────
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}SUMMARY{Colors.END}")
    print(f"{'=' * 60}")
    print(f"  Total checks:  {total}")
    print(f"  {Colors.GREEN}Passed:  {passed}{Colors.END}")

    if errors:
        print(f"  {Colors.RED}Missing: {len(errors)}{Colors.END}")
        print(f"\n{Colors.RED}Missing files:{Colors.END}")
        for e in errors:
            print(f"    {Colors.RED}x{Colors.END} {e}")

    if warnings:
        print(f"\n{Colors.YELLOW}Warnings:{Colors.END}")
        for w in warnings:
            print(f"    {Colors.YELLOW}!{Colors.END} {w}")

    if not errors and not warnings:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All {total} checks passed! Project is complete.{Colors.END}")
        print(f"\n{Colors.CYAN}Next steps:{Colors.END}")
        print(f"  1. Generate synthetic data:  python ml/scripts/generate_synthetic_data.py --duration-hours 1")
        print(f"  2. Start infrastructure:     docker compose up -d timescaledb redis")
        print(f"  3. Start all services:       docker compose up --build")
        print(f"  4. Run tests:                pytest tests/ -v")
        print(f"  5. Open dashboard:           http://localhost:3000")
        print(f"  6. Open API docs:            http://localhost:8000/docs")
        return 0
    else:
        print(f"\n{Colors.RED}Build verification failed. Fix missing items above.{Colors.END}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
