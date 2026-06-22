"""
Availability SLA Monitor — PathWise AI
Polls /api/v1/health every 30s and reports uptime %.
Satisfies: Req-Qual-Rel-1 (>=99.9% availability target)

Run: python scripts/uptime_monitor.py --duration 3600
"""

from __future__ import annotations
import argparse
import json
import os
import time
from datetime import datetime

try:
    import httpx
except ImportError:  # pragma: no cover
    raise SystemExit("httpx is required: pip install httpx")

BASE_URL      = os.getenv("BACKEND_URL", "http://localhost:8000")
POLL_INTERVAL = int(os.getenv("UPTIME_POLL_INTERVAL", "30"))


def monitor(duration_s: int) -> dict:
    checks_total = 0
    checks_up    = 0
    failures: list[dict] = []

    end_time = time.time() + duration_s
    print(f"[{datetime.now()}] Starting availability monitor for {duration_s}s "
          f"(poll every {POLL_INTERVAL}s)")

    while time.time() < end_time:
        try:
            r = httpx.get(f"{BASE_URL}/api/v1/health", timeout=5)
            is_up = r.status_code == 200
        except Exception as e:
            is_up = False
            failures.append({"time": datetime.now().isoformat(), "error": str(e)})

        checks_total += 1
        if is_up:
            checks_up += 1

        uptime_pct = (checks_up / checks_total) * 100
        symbol = "OK" if is_up else "DOWN"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {symbol} "
              f"Uptime: {uptime_pct:.2f}% ({checks_up}/{checks_total})")

        time.sleep(POLL_INTERVAL)

    uptime_pct = (checks_up / checks_total) * 100 if checks_total else 0.0
    result = {
        "duration_s":   duration_s,
        "checks_total": checks_total,
        "checks_up":    checks_up,
        "uptime_pct":   round(uptime_pct, 4),
        "sla_target":   99.9,
        "sla_passed":   uptime_pct >= 99.9,
        "failures":     failures,
    }

    print("\n" + "=" * 50)
    print("AVAILABILITY REPORT")
    print(f"Uptime: {uptime_pct:.4f}%  (target >= 99.9%)")
    print(f"SLA:    {'PASSED' if result['sla_passed'] else 'FAILED'}")
    print("=" * 50)

    out = "availability_report.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Report saved to {out}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=3600,
                        help="Monitoring duration in seconds (default 3600)")
    args = parser.parse_args()
    monitor(args.duration)
