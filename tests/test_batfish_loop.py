"""
TC-9: Batfish correctly rejects a loop-introducing routing change.
Run: pytest tests/test_batfish_loop.py -v
"""

import os

import pytest

os.environ.setdefault("BATFISH_HOST", "localhost")
os.environ.setdefault("BATFISH_PORT", "9997")

# Sandbox mode is scoped to this module via an autouse fixture below, so
# changing it doesn't leak into other test files (notably test_critical_tcs.py
# whose Req-Qual-Perf-3 < 5 s SLA assertion would otherwise blow up waiting
# on a 30 s Mininet socket timeout).

from server.sandbox import _run_batfish_analysis  # noqa: E402


@pytest.fixture(autouse=True)
def _batfish_sandbox_mode(monkeypatch):
    monkeypatch.setenv("SANDBOX_MODE", "mininet")
    yield


def test_batfish_rejects_loop():
    """A topology with a circular route must be rejected."""
    # Topology: 1 -> 2 -> 3 -> 1 (loop)
    loop_topology = {
        "nodes": [{"id": 1}, {"id": 2}, {"id": 3}],
        "links": [
            {"src": 1, "dst": 2},
            {"src": 2, "dst": 3},
            {"src": 3, "dst": 1},
        ],
    }
    flow_body = {"priority": 1000, "traffic_class": "bulk", "target_ip": "10.0.0.3"}
    result = _run_batfish_analysis(loop_topology, flow_body)

    if result.get("fallback"):
        pytest.skip("Batfish container not running — skipped (fallback mode)")

    assert result["loops_found"] is True, "Batfish must detect the loop"
    assert result["passed"] is False, "Loop-introducing change must be rejected"


def test_batfish_approves_clean_path():
    """A clean two-node path must be approved."""
    clean_topology = {
        "nodes": [{"id": 1}, {"id": 2}],
        "links": [{"src": 1, "dst": 2}],
    }
    flow_body = {"priority": 50000, "traffic_class": "voip", "target_ip": "10.0.0.2"}
    result = _run_batfish_analysis(clean_topology, flow_body)

    if result.get("fallback"):
        pytest.skip("Batfish container not running — skipped (fallback mode)")

    assert result["passed"] is True, "Clean path must be approved by Batfish"
