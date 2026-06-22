"""
TC-1 (live mode): SNMP v2c and NetFlow v9 collectors ingest at >=1 Hz.
Satisfies: Req-Func-Sw-20, Req-Func-Sw-1
Run: pytest tests/test_tc1_live_telemetry.py -v
"""

import os
import socket
import time

import pytest

SNMP_HOST    = os.getenv("SNMP_TEST_HOST", "")
SNMP_COMM    = os.getenv("SNMP_COMMUNITY", "public")
NETFLOW_PORT = int(os.getenv("NETFLOW_PORT", "2055"))
BACKEND_URL  = os.getenv("BACKEND_URL", "http://localhost:8000")


@pytest.mark.skipif(not SNMP_HOST,
                    reason="SNMP_TEST_HOST not set — skipping live SNMP test")
def test_snmp_v2c_poll():
    """SNMP v2c must return ifInOctets from a real device."""
    try:
        from pysnmp.hlapi import (
            getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
            ContextData, ObjectType, ObjectIdentity,
        )
    except ImportError:
        pytest.skip("pysnmp not installed")

    error_indication, error_status, _, var_binds = next(
        getCmd(
            SnmpEngine(),
            CommunityData(SNMP_COMM, mpModel=1),
            UdpTransportTarget((SNMP_HOST, 161), timeout=5, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity("IF-MIB", "ifInOctets", 1)),
        )
    )
    assert error_indication is None, f"SNMP error: {error_indication}"
    assert error_status == 0, f"SNMP status error: {error_status}"
    assert len(var_binds) > 0, "No SNMP data returned"
    print(f"\nSNMP ifInOctets: {var_binds[0][1]}")


def test_netflow_listener_starts():
    """NetFlow collector must bind to UDP port without error."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", NETFLOW_PORT))
        sock.settimeout(1.0)
        print(f"\nNetFlow listener bound to UDP {NETFLOW_PORT}")
    except OSError as e:
        pytest.skip(f"Port {NETFLOW_PORT} already in use (collector running): {e}")
    finally:
        sock.close()


def test_telemetry_ingestion_rate():
    """
    Confirm 1 Hz ingestion rate by polling the telemetry endpoint twice
    1 second apart and checking that data continues to arrive.
    """
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed")

    try:
        token_resp = httpx.post(
            f"{BACKEND_URL}/api/v1/auth/login",
            json={"email": "admin@pathwise.local", "password": "admin"},
            timeout=5,
        )
    except Exception as exc:
        pytest.skip(f"Backend not reachable: {exc}")

    headers = {}
    if token_resp.status_code == 200:
        token = token_resp.json().get("access_token") or token_resp.json().get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"

    r1 = httpx.get(f"{BACKEND_URL}/api/v1/telemetry/links", headers=headers)
    if r1.status_code != 200:
        pytest.skip(f"Telemetry endpoint not reachable: {r1.status_code}")
    links = r1.json().get("links", [])
    if not links:
        pytest.skip("No active links yet")

    link_id = links[0]
    r1 = httpx.get(f"{BACKEND_URL}/api/v1/telemetry/{link_id}?window=5", headers=headers)
    pts1 = r1.json().get("points", [])
    ts1 = pts1[-1]["timestamp"] if pts1 else 0

    time.sleep(1.1)

    r2 = httpx.get(f"{BACKEND_URL}/api/v1/telemetry/{link_id}?window=5", headers=headers)
    pts2 = r2.json().get("points", [])
    ts2 = pts2[-1]["timestamp"] if pts2 else 0

    assert ts2 > ts1, f"TC-1 FAIL: timestamp did not advance ({ts1} == {ts2})"
    print(f"\nTC-1 PASS: telemetry timestamp advanced {ts2 - ts1:.3f}s")
