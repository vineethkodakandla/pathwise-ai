"""
Selective IP Degrader -- time-bounded, per-IP network degradation.

Distinct from the full App Priority Switch (which blocks a whole app via
hosts file + NRPT + DoH + QUIC blocks). This module lets the operator pick
specific remote IPs or CIDRs, choose "block" or "throttle <kbps>", and set
a duration. After the timer expires, the artifacts are removed automatically
and the host's connectivity to those IPs is restored to normal.

Rule naming:
  PW_Sel_<rule_id>_*       -- firewall rules
  PW_SelQ_<rule_id>_*      -- NetQoS policies

Those prefixes are intentionally different from the App Priority Switch
prefixes (PW_Disrupt_*, PW_*, PathWise-*) so a cleanup on one feature
never stomps the other.

Uses:
  * Windows  -> New-NetFirewallRule / New-NetQosPolicy (needs Administrator)
  * Linux    -> iptables / tc (needs NET_ADMIN)
  * simulate -> logs only
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Literal, Optional

from server.app_qos.signatures import APP_SIGNATURES

logger = logging.getLogger("pathwise.selective")

ENFORCER_MODE = os.environ.get("ENFORCER_MODE", "simulate").lower()

# Defensive bounds so a demo script can't accidentally pin the host for hours.
MIN_DURATION_S = 5
MAX_DURATION_S = 60 * 60  # 1 hour
MIN_THROTTLE_KBPS = 32
MAX_IPS_PER_RULE = 32


Mode = Literal["block", "throttle"]


@dataclass
class SelectiveRule:
    id: str
    app_id: Optional[str]
    ips: List[str]
    mode: Mode
    throttle_kbps: Optional[int]
    started_at: float
    duration_s: int
    expires_at: float
    reason: str = ""
    active: bool = True
    commands_run: int = 0

    def remaining_s(self) -> int:
        if not self.active:
            return 0
        return max(0, int(round(self.expires_at - time.time())))

    def as_dict(self) -> dict:
        d = asdict(self)
        d["remaining_s"] = self.remaining_s()
        return d


_rules: Dict[str, SelectiveRule] = {}
_lock = asyncio.Lock()
_sweeper_started = False


# ── Public API ────────────────────────────────────────────────────

def list_rules(include_expired: bool = False) -> List[dict]:
    now = time.time()
    items = []
    for r in _rules.values():
        if not include_expired and not r.active:
            continue
        items.append(r.as_dict())
    items.sort(key=lambda x: x["started_at"], reverse=True)
    return items


def get_rule(rule_id: str) -> Optional[SelectiveRule]:
    return _rules.get(rule_id)


def candidate_ips_for(app_id: str) -> List[str]:
    """
    Return a list of remote IPs the user can target for this app:
      1. Static CIDRs from the signature
      2. Freshly resolved A records for the app's domains
    """
    sig = APP_SIGNATURES.get(app_id)
    if not sig:
        return []

    out: List[str] = list(sig.cidrs)

    for dom in (sig.domains or [])[:6]:
        clean = dom.lstrip("*.")
        try:
            import socket
            infos = socket.getaddrinfo(clean, 443, type=socket.SOCK_STREAM)
            for i in infos:
                ip = i[4][0]
                if ip and ip not in out:
                    out.append(ip)
        except Exception:
            continue
    return out


def start_rule(
    ips: List[str],
    mode: Mode,
    duration_s: int,
    throttle_kbps: Optional[int] = None,
    app_id: Optional[str] = None,
    reason: str = "",
) -> SelectiveRule:
    """Create and apply a selective degrade rule. Returns the active rule."""
    ips = [ip.strip() for ip in ips if ip and ip.strip()]
    ips = _validate_ips(ips)
    if not ips:
        raise ValueError("At least one valid IP or CIDR is required.")
    if len(ips) > MAX_IPS_PER_RULE:
        raise ValueError(f"Too many IPs (max {MAX_IPS_PER_RULE}).")

    if mode not in ("block", "throttle"):
        raise ValueError("mode must be 'block' or 'throttle'.")

    duration_s = int(duration_s)
    if duration_s < MIN_DURATION_S or duration_s > MAX_DURATION_S:
        raise ValueError(
            f"duration_s must be between {MIN_DURATION_S} and {MAX_DURATION_S}."
        )

    if mode == "throttle":
        if throttle_kbps is None or throttle_kbps < MIN_THROTTLE_KBPS:
            raise ValueError(f"throttle_kbps must be >= {MIN_THROTTLE_KBPS}.")

    rule_id = uuid.uuid4().hex[:10]
    now = time.time()
    rule = SelectiveRule(
        id=rule_id,
        app_id=app_id,
        ips=ips,
        mode=mode,
        throttle_kbps=throttle_kbps if mode == "throttle" else None,
        started_at=now,
        duration_s=duration_s,
        expires_at=now + duration_s,
        reason=reason,
        active=True,
    )

    _apply(rule)
    _rules[rule_id] = rule

    logger.info(
        "Selective rule %s started: mode=%s ips=%d duration=%ds throttle=%s app=%s",
        rule_id, mode, len(ips), duration_s, throttle_kbps, app_id,
    )
    return rule


def stop_rule(rule_id: str) -> bool:
    """Stop a rule early and remove its OS artifacts."""
    rule = _rules.get(rule_id)
    if not rule or not rule.active:
        return False
    _remove(rule)
    rule.active = False
    logger.info("Selective rule %s stopped early.", rule_id)
    return True


def stop_all() -> int:
    count = 0
    for rule in list(_rules.values()):
        if rule.active:
            _remove(rule)
            rule.active = False
            count += 1
    return count


# ── Sweeper ───────────────────────────────────────────────────────

async def sweeper_loop(interval_s: float = 1.0) -> None:
    """Background task -- expires rules whose TTL has elapsed."""
    global _sweeper_started
    _sweeper_started = True
    logger.info("Selective-degrader sweeper started.")
    while True:
        try:
            now = time.time()
            for rule in list(_rules.values()):
                if rule.active and now >= rule.expires_at:
                    _remove(rule)
                    rule.active = False
                    logger.info(
                        "Selective rule %s auto-expired after %ds.",
                        rule.id, rule.duration_s,
                    )
        except Exception as exc:
            logger.exception("sweeper error: %s", exc)
        await asyncio.sleep(interval_s)


# ── Internal: apply / remove ──────────────────────────────────────

def _apply(rule: SelectiveRule) -> None:
    if ENFORCER_MODE == "powershell":
        _apply_windows(rule)
    elif ENFORCER_MODE == "tc":
        _apply_linux(rule)
    else:
        logger.info("[SIMULATE] would %s %s for %ds", rule.mode,
                    rule.ips, rule.duration_s)


def _remove(rule: SelectiveRule) -> None:
    if ENFORCER_MODE == "powershell":
        _remove_windows(rule)
    elif ENFORCER_MODE == "tc":
        _remove_linux(rule)
    else:
        logger.info("[SIMULATE] would remove rule %s", rule.id)


# -- Windows --

def _apply_windows(rule: SelectiveRule) -> None:
    v4 = [ip for ip in rule.ips if ":" not in ip]
    v6 = [ip for ip in rule.ips if ":" in ip]

    if rule.mode == "block":
        # Block outbound TCP + UDP to the selected IPs on :443 only. That's
        # enough to stall any HTTPS stream to that exact IP -- but the rest
        # of the host's internet (DNS, DoH, other Google services, hosts
        # file, other apps) stays completely untouched.
        if v4:
            _run_ps(
                f"New-NetFirewallRule -DisplayName 'PW_Sel_{rule.id}_TCP4' "
                f"-Direction Outbound -Action Block -Protocol TCP "
                f"-RemoteAddress {','.join(v4)} -RemotePort 443 "
                f"-Enabled True -ErrorAction SilentlyContinue"
            )
            _run_ps(
                f"New-NetFirewallRule -DisplayName 'PW_Sel_{rule.id}_UDP4' "
                f"-Direction Outbound -Action Block -Protocol UDP "
                f"-RemoteAddress {','.join(v4)} -RemotePort 443 "
                f"-Enabled True -ErrorAction SilentlyContinue"
            )
        if v6:
            _run_ps(
                f"New-NetFirewallRule -DisplayName 'PW_Sel_{rule.id}_TCP6' "
                f"-Direction Outbound -Action Block -Protocol TCP "
                f"-RemoteAddress {','.join(v6)} -RemotePort 443 "
                f"-Enabled True -ErrorAction SilentlyContinue"
            )
        rule.commands_run += len(v4) * 2 + (1 if v6 else 0)
        return

    # Throttle: one NetQoS policy per target IP/CIDR with the requested rate.
    rate_bps = max(MIN_THROTTLE_KBPS, int(rule.throttle_kbps or 0)) * 1000
    for idx, ip in enumerate(rule.ips):
        prefix = ip if "/" in ip else (f"{ip}/32" if ":" not in ip else f"{ip}/128")
        _run_ps(
            f"New-NetQosPolicy -Name 'PW_SelQ_{rule.id}_{idx}' "
            f"-IPDstPrefixMatchCondition '{prefix}' "
            f"-ThrottleRateActionBitsPerSecond {rate_bps} "
            f"-PolicyStore ActiveStore -ErrorAction SilentlyContinue"
        )
        rule.commands_run += 1


def _remove_windows(rule: SelectiveRule) -> None:
    _run_ps(
        f"Get-NetFirewallRule -ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.DisplayName -like 'PW_Sel_{rule.id}_*' }} | "
        f"Remove-NetFirewallRule -ErrorAction SilentlyContinue"
    )
    _run_ps(
        f"Get-NetQosPolicy -PolicyStore ActiveStore -ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.Name -like 'PW_SelQ_{rule.id}_*' }} | "
        f"Remove-NetQosPolicy -Confirm:$false -ErrorAction SilentlyContinue"
    )


# -- Linux --

def _apply_linux(rule: SelectiveRule) -> None:
    if rule.mode == "block":
        for ip in rule.ips:
            _run(f"iptables -I OUTPUT -d {ip} -p tcp --dport 443 -m comment "
                 f"--comment 'PW_Sel_{rule.id}' -j DROP")
            _run(f"iptables -I OUTPUT -d {ip} -p udp --dport 443 -m comment "
                 f"--comment 'PW_Sel_{rule.id}' -j DROP")
        return
    # Throttle via tc is complex on shared qdiscs; for demo we iptables-mark
    # and rely on the full traffic_shaper htb tree. Fallback: DROP every Nth
    # packet with iptables statistic module for a crude degrade.
    drop_ratio = 0.85
    for ip in rule.ips:
        _run(
            f"iptables -I OUTPUT -d {ip} -p tcp --dport 443 -m statistic "
            f"--mode random --probability {drop_ratio} -m comment "
            f"--comment 'PW_Sel_{rule.id}' -j DROP"
        )


def _remove_linux(rule: SelectiveRule) -> None:
    comment = f"PW_Sel_{rule.id}"
    _run(
        f"iptables-save | grep -v 'comment \"{comment}\"' | iptables-restore"
    )


# -- Helpers --

def _validate_ips(raw: List[str]) -> List[str]:
    valid: List[str] = []
    for ip in raw:
        try:
            if "/" in ip:
                net = ipaddress.ip_network(ip, strict=False)
                if net.is_loopback or net.is_link_local or net.is_multicast:
                    continue
                valid.append(str(net))
            else:
                addr = ipaddress.ip_address(ip)
                if addr.is_loopback or addr.is_link_local or addr.is_multicast:
                    continue
                valid.append(str(addr))
        except ValueError:
            continue
    return valid


def _run_ps(script: str) -> None:
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as exc:
        logger.debug("PS command failed: %s", exc)


def _run(cmd: str) -> None:
    try:
        subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
    except Exception as exc:
        logger.debug("shell command failed: %s", exc)
