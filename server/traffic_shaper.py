"""
Traffic Shaper — real OS-level bandwidth control for app-aware traffic management.

Uses Windows QoS policies (New-NetQosPolicy) and firewall rules to throttle
or prioritize traffic per application. Integrates with IBN for natural
language control.

Supported apps: Zoom, YouTube, Teams, Netflix, Spotify, Discord, Slack,
Gaming, Twitch, Google Meet, Skype, WhatsApp, Telegram, etc.

Requires: Administrator privileges for PowerShell QoS commands.
"""

from __future__ import annotations
import asyncio
import os
import re
import socket
import subprocess
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from server import audit


# ── App Definitions ────────────────────────────────────────────
# Each app has: process names, domain patterns (for DNS-based IP resolution),
# known IP ranges, and a default priority class.

class PriorityClass(str, Enum):
    CRITICAL = "critical"       # VoIP, video calls — never throttle
    HIGH = "high"               # Business apps — minimal throttling
    NORMAL = "normal"           # Default
    LOW = "low"                 # Streaming, bulk — throttle first
    BLOCKED = "blocked"         # Fully blocked


@dataclass
class AppProfile:
    """Defines a network application for traffic shaping."""
    name: str
    display_name: str
    category: str  # voip, video_call, streaming, gaming, business, social, bulk
    process_names: list[str]  # Windows process names (e.g., ["Zoom.exe"])
    domains: list[str]        # Domain patterns for IP resolution
    ip_prefixes: list[str]    # Known IP CIDR ranges
    default_priority: PriorityClass = PriorityClass.NORMAL
    default_bandwidth_kbps: int = 0  # 0 = unlimited


# Registry of known applications
APP_REGISTRY: dict[str, AppProfile] = {
    "zoom": AppProfile(
        name="zoom", display_name="Zoom", category="video_call",
        process_names=["Zoom.exe", "ZoomWebHost.exe"],
        domains=["*.zoom.us", "*.zoomgov.com"],
        ip_prefixes=["3.7.35.0/25", "3.21.137.128/25", "3.22.11.0/24",
                      "3.23.93.0/24", "3.25.41.128/25", "3.25.42.0/25",
                      "3.25.49.0/24", "8.5.128.0/23", "13.52.6.128/25",
                      "52.61.100.128/25", "64.125.62.0/24", "64.211.144.0/24"],
        default_priority=PriorityClass.CRITICAL,
    ),
    "youtube": AppProfile(
        name="youtube", display_name="YouTube", category="streaming",
        process_names=["chrome.exe", "msedge.exe", "firefox.exe"],
        domains=["*.googlevideo.com", "*.youtube.com", "*.ytimg.com"],
        ip_prefixes=["216.58.0.0/16", "142.250.0.0/15", "172.217.0.0/16",
                      "208.65.152.0/22", "208.117.224.0/19"],
        default_priority=PriorityClass.LOW,
    ),
    "teams": AppProfile(
        name="teams", display_name="Microsoft Teams", category="video_call",
        process_names=["ms-teams.exe", "Teams.exe", "msteams.exe"],
        domains=["*.teams.microsoft.com", "*.skype.com", "*.lync.com"],
        ip_prefixes=["13.107.64.0/18", "52.112.0.0/14", "52.120.0.0/14"],
        default_priority=PriorityClass.CRITICAL,
    ),
    "netflix": AppProfile(
        name="netflix", display_name="Netflix", category="streaming",
        process_names=["chrome.exe", "msedge.exe", "Netflix.exe"],
        domains=["*.netflix.com", "*.nflxvideo.net", "*.nflximg.net"],
        ip_prefixes=["23.246.0.0/18", "37.77.184.0/21", "38.72.126.0/24",
                      "45.57.0.0/17", "64.120.128.0/17", "66.197.128.0/17",
                      "69.53.224.0/19", "108.175.32.0/20"],
        default_priority=PriorityClass.LOW,
    ),
    "spotify": AppProfile(
        name="spotify", display_name="Spotify", category="streaming",
        process_names=["Spotify.exe"],
        domains=["*.spotify.com", "*.spotifycdn.com", "*.scdn.co"],
        ip_prefixes=["35.186.224.0/20", "104.154.0.0/15"],
        default_priority=PriorityClass.LOW,
    ),
    "discord": AppProfile(
        name="discord", display_name="Discord", category="social",
        process_names=["Discord.exe", "Update.exe"],
        domains=["*.discord.com", "*.discord.gg", "*.discordapp.com", "*.discord.media"],
        ip_prefixes=["162.159.128.0/17", "66.22.196.0/22"],
        default_priority=PriorityClass.NORMAL,
    ),
    "slack": AppProfile(
        name="slack", display_name="Slack", category="business",
        process_names=["slack.exe"],
        domains=["*.slack.com", "*.slack-edge.com", "*.slack-msgs.com"],
        ip_prefixes=["54.192.0.0/16"],
        default_priority=PriorityClass.HIGH,
    ),
    "gaming": AppProfile(
        name="gaming", display_name="Online Gaming", category="gaming",
        process_names=["steam.exe", "EpicGamesLauncher.exe", "Battle.net.exe",
                        "valorant.exe", "FortniteClient-Win64-Shipping.exe"],
        domains=["*.steampowered.com", "*.epicgames.com", "*.battle.net"],
        ip_prefixes=["208.64.200.0/24", "205.185.192.0/18"],
        default_priority=PriorityClass.NORMAL,
    ),
    "twitch": AppProfile(
        name="twitch", display_name="Twitch", category="streaming",
        process_names=["chrome.exe", "msedge.exe"],
        domains=["*.twitch.tv", "*.ttvnw.net", "*.jtvnw.net"],
        ip_prefixes=["52.223.192.0/18", "99.181.64.0/18"],
        default_priority=PriorityClass.LOW,
    ),
    "google_meet": AppProfile(
        name="google_meet", display_name="Google Meet", category="video_call",
        process_names=["chrome.exe", "msedge.exe"],
        domains=["*.meet.google.com", "meet.google.com"],
        ip_prefixes=["74.125.250.0/24", "142.250.82.0/24"],
        default_priority=PriorityClass.CRITICAL,
    ),
    "skype": AppProfile(
        name="skype", display_name="Skype", category="video_call",
        process_names=["Skype.exe", "SkypeApp.exe"],
        domains=["*.skype.com", "*.lync.com"],
        ip_prefixes=["13.107.64.0/18", "52.112.0.0/14"],
        default_priority=PriorityClass.CRITICAL,
    ),
    "whatsapp": AppProfile(
        name="whatsapp", display_name="WhatsApp", category="social",
        process_names=["WhatsApp.exe"],
        domains=["*.whatsapp.net", "*.whatsapp.com"],
        ip_prefixes=["31.13.64.0/18", "157.240.0.0/16"],
        default_priority=PriorityClass.HIGH,
    ),
    "telegram": AppProfile(
        name="telegram", display_name="Telegram", category="social",
        process_names=["Telegram.exe"],
        domains=["*.telegram.org", "*.t.me"],
        ip_prefixes=["91.108.4.0/22", "91.108.8.0/22", "91.108.12.0/22",
                      "91.108.16.0/22", "91.108.20.0/22", "149.154.160.0/20"],
        default_priority=PriorityClass.NORMAL,
    ),
    "web_browsing": AppProfile(
        name="web_browsing", display_name="Web Browsing", category="bulk",
        process_names=["chrome.exe", "msedge.exe", "firefox.exe"],
        domains=[],
        ip_prefixes=[],
        default_priority=PriorityClass.NORMAL,
    ),
    "file_transfer": AppProfile(
        name="file_transfer", display_name="File Transfers", category="bulk",
        process_names=["OneDrive.exe", "Dropbox.exe", "googledrivesync.exe"],
        domains=["*.dropbox.com", "*.onedrive.com", "*.googleapis.com"],
        ip_prefixes=[],
        default_priority=PriorityClass.LOW,
    ),
}

# Aliases for natural language parsing
APP_ALIASES: dict[str, str] = {
    "zoom": "zoom", "zoom call": "zoom", "zoom meeting": "zoom",
    "youtube": "youtube", "yt": "youtube", "youtube video": "youtube",
    "teams": "teams", "microsoft teams": "teams", "ms teams": "teams",
    "netflix": "netflix",
    "spotify": "spotify", "music": "spotify",
    "discord": "discord",
    "slack": "slack",
    "gaming": "gaming", "games": "gaming", "steam": "gaming", "fortnite": "gaming", "valorant": "gaming",
    "twitch": "twitch", "twitch stream": "twitch",
    "google meet": "google_meet", "gmeet": "google_meet",
    "skype": "skype",
    "whatsapp": "whatsapp",
    "telegram": "telegram",
    "browsing": "web_browsing", "web": "web_browsing", "chrome": "web_browsing",
    "file transfer": "file_transfer", "onedrive": "file_transfer", "dropbox": "file_transfer",
}

BANDWIDTH_PRESETS = {
    PriorityClass.CRITICAL: 0,           # Unlimited
    PriorityClass.HIGH: 0,               # Unlimited
    PriorityClass.NORMAL: 10_000_000,    # 10 Mbps
    PriorityClass.LOW: 500_000,          # 500 Kbps (forces low quality video)
    PriorityClass.BLOCKED: 1,            # Effectively blocked
}


# ── Active Traffic Policy ──────────────────────────────────────

@dataclass
class TrafficPolicy:
    id: str
    app_name: str
    display_name: str
    action: str          # throttle, prioritize, block, unblock
    bandwidth_kbps: int  # 0 = unlimited
    priority: PriorityClass
    created_at: float
    created_by: str      # IBN intent ID or "manual"
    qos_policy_name: str  # Windows QoS policy name
    active: bool = True
    reason: str = ""


_active_policies: deque[TrafficPolicy] = deque(maxlen=100)
_policy_counter = 0


# ── Resolve App IPs via DNS ────────────────────────────────────

def _resolve_domains(domains: list[str]) -> list[str]:
    """Resolve domain patterns to IP addresses for QoS targeting."""
    ips = []
    for domain in domains:
        clean = domain.lstrip("*.")
        try:
            results = socket.getaddrinfo(clean, None, socket.AF_INET)
            for _, _, _, _, (ip, _) in results:
                if ip not in ips:
                    ips.append(ip)
        except (socket.gaierror, OSError):
            pass
    return ips


# ── PowerShell Execution (elevated) ───────────────────────────
#
# Traffic shaping requires admin. We use two strategies:
#   1. QoS policies (New-NetQosPolicy) — real bandwidth throttling
#   2. Firewall rules (New-NetFirewallRule) — block/allow as fallback
#
# Both are written to a .ps1 script file and executed via
# Start-Process -Verb RunAs for elevation. A UAC prompt appears
# once when the first policy is created.

_SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "..", "infra", "qos_scripts")
os.makedirs(_SCRIPT_DIR, exist_ok=True)


def _run_powershell(command: str, need_admin: bool = True) -> tuple[bool, str]:
    """
    Execute a PowerShell command. If need_admin=True, writes to a script
    and executes with elevation via Start-Process -Verb RunAs.
    When ENFORCER_MODE=simulate the call is a no-op so unattended runs /
    dev mode never trigger a UAC prompt that blocks the request thread.
    """
    if os.environ.get("ENFORCER_MODE", "").lower() == "simulate":
        return True, "[SIMULATE] " + command.splitlines()[0][:80]
    if need_admin:
        return _run_elevated_powershell(command)

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout.strip() + result.stderr.strip()
        return result.returncode == 0, output
    except Exception as e:
        return False, str(e)


def _run_elevated_powershell(command: str) -> tuple[bool, str]:
    """
    Execute PowerShell with admin elevation.
    Writes commands to a .ps1 script, launches it elevated, waits for completion.
    """
    script_path = os.path.join(_SCRIPT_DIR, f"qos_cmd_{int(time.time()*1000)}.ps1")
    result_path = script_path + ".result"

    # Write script that executes the command and captures full output
    result_path_escaped = result_path.replace("\\", "\\\\")
    script_content = f"""
$ErrorActionPreference = "Continue"
$allOutput = @()
try {{
{command}
    $allOutput += "OK"
}} catch {{
    $allOutput += "FAIL"
    $allOutput += $_.Exception.Message
}}
$allOutput -join "`n" | Out-File -FilePath "{result_path}" -Encoding UTF8
"""
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        # Launch elevated — this triggers UAC prompt on first run
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f'Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File {script_path}" '
             f'-Verb RunAs -Wait -WindowStyle Hidden'],
            capture_output=True, text=True, timeout=15,
        )

        # Read result
        if os.path.exists(result_path):
            with open(result_path, "r", encoding="utf-8-sig") as f:
                result = f.read().strip()
            os.remove(result_path)
            ok = "OK" in result
            if not ok:
                print(f"[traffic_shaper] Elevated PS error: {result}")
            return ok, result
        else:
            # Script ran but no result file — likely UAC was denied
            return False, "UAC denied or script failed"

    except subprocess.TimeoutExpired:
        return False, "Elevated command timed out"
    except Exception as e:
        return False, str(e)
    finally:
        # Cleanup script file
        try:
            os.remove(script_path)
        except OSError:
            pass


def _create_qos_throttle(policy_name: str, app: AppProfile, bandwidth_bps: int) -> bool:
    """
    Create Windows QoS + Firewall rules to throttle an app.

    Uses a multi-strategy approach:
      1. QoS by process name (best for native apps like Zoom.exe, Spotify.exe)
      2. QoS by destination IP prefix (for browser-based apps like YouTube)
      3. QoS by resolved domain IPs (dynamic, catches CDN IPs)
      4. Firewall rate-limit as fallback (block if bandwidth_bps <= 1000)
    """
    commands = []

    # Collect all target IPs (static ranges + DNS-resolved)
    all_prefixes = list(app.ip_prefixes[:5])
    resolved_ips = _resolve_domains(app.domains[:5])
    for ip in resolved_ips[:8]:
        all_prefixes.append(f"{ip}/32")

    # Strategy 1: Throttle by process name (unique process apps like Zoom.exe, Spotify.exe)
    if app.process_names and app.process_names[0] not in ("chrome.exe", "msedge.exe", "firefox.exe"):
        commands.append(
            f'New-NetQosPolicy -Name "{policy_name}" '
            f'-AppPathNameMatchCondition "{app.process_names[0]}" '
            f'-ThrottleRateActionBitsPerSecond {bandwidth_bps} '
            f'-PolicyStore ActiveStore'
        )

    # Strategy 2: Throttle by destination IP (works for browser-based apps)
    for i, prefix in enumerate(all_prefixes):
        sub_name = f"{policy_name}-r{i}"
        commands.append(
            f'New-NetQosPolicy -Name "{sub_name}" '
            f'-IPDstPrefixMatchCondition "{prefix}" '
            f'-ThrottleRateActionBitsPerSecond {bandwidth_bps} '
            f'-PolicyStore ActiveStore'
        )

    # Strategy 4: Block QUIC/UDP to force TCP (YouTube/Netflix use QUIC
    # which bypasses QoS). Blocking UDP on port 443 forces fallback to TCP
    # which IS subject to QoS throttling.
    all_ips = list(app.ip_prefixes[:5])
    resolved = _resolve_domains(app.domains[:3])
    all_ips.extend(f"{ip}/32" for ip in resolved[:5])
    if all_ips:
        fw_ips = ",".join(f'"{p}"' for p in all_ips)
        # Block QUIC (UDP 443) to force TCP — TCP is QoS-throttleable
        commands.append(
            f'New-NetFirewallRule -DisplayName "{policy_name}-quic" '
            f'-Direction Outbound -Action Block '
            f'-Protocol UDP -RemotePort 443 '
            f'-RemoteAddress {fw_ips} '
            f'-Enabled True'
        )

    # Strategy 5: If effectively blocking (<=1 Kbps), fully block with firewall
    if bandwidth_bps <= 1000:
        if all_ips:
            fw_ips2 = ",".join(f'"{p}"' for p in all_ips)
            commands.append(
                f'New-NetFirewallRule -DisplayName "{policy_name}-block" '
                f'-Direction Outbound -Action Block '
                f'-RemoteAddress {fw_ips2} '
                f'-Enabled True'
            )

    if not commands:
        print(f"[traffic_shaper] No throttle rules generated for {app.name}")
        return False

    # Execute all commands in a single elevated script
    combined = "\n".join(commands)
    ok, msg = _run_powershell(combined)
    if ok:
        print(f"[traffic_shaper] QoS applied: {len(commands)} rules for {app.display_name} @ {bandwidth_bps/1000:.0f} Kbps")
    else:
        print(f"[traffic_shaper] QoS apply failed for {app.display_name}: {msg}")
    return ok


def _remove_qos_policies(policy_name: str) -> bool:
    """Remove all QoS policies and firewall rules matching a name pattern."""
    cmd = (
        f'Get-NetQosPolicy -PolicyStore ActiveStore -ErrorAction SilentlyContinue | '
        f'Where-Object {{ $_.Name -like "{policy_name}*" }} | '
        f'Remove-NetQosPolicy -Confirm:$false -ErrorAction SilentlyContinue\n'
        f'Get-NetFirewallRule -ErrorAction SilentlyContinue | '
        f'Where-Object {{ $_.DisplayName -like "{policy_name}*" }} | '
        f'Remove-NetFirewallRule -ErrorAction SilentlyContinue'
    )
    ok, _ = _run_powershell(cmd)
    return ok


# ── Public API ─────────────────────────────────────────────────

def _apply_app_qos_enforcement(app_name: str, priority: str) -> None:
    """
    Delegate OS-level enforcement to the BandwidthEnforcer used by the
    App Priority Switch. This is the working 5-step stack:
    hosts file + NRPT wildcard DNS + DNS flush + Chrome net-service kill
    + live-IP firewall + global QUIC block. Without this delegation,
    IBN's "Block YouTube" only installs a NetQoS throttle, which
    Chrome bypasses via DoH/Alt-Svc cache.
    """
    try:
        from server.app_qos.priority_manager import set_priorities
        set_priorities("ibn", {app_name: priority})
    except Exception as exc:
        print(f"[traffic_shaper] enforcer delegation failed: {exc}")


def throttle_app(app_name: str, bandwidth_kbps: int = 500, reason: str = "", created_by: str = "manual") -> Optional[TrafficPolicy]:
    """
    Throttle an application to a specified bandwidth.
    bandwidth_kbps=500 forces YouTube/Netflix to drop to 144p/240p.
    bandwidth_kbps=1   is treated as BLOCK (runs the full OS stack).
    """
    global _policy_counter
    app = APP_REGISTRY.get(app_name)
    if not app:
        return None

    _policy_counter += 1
    policy_name = f"PathWise-{app_name}-{_policy_counter}"
    bandwidth_bps = bandwidth_kbps * 1000

    _create_qos_throttle(policy_name, app, bandwidth_bps)

    # Full OS-level block: NRPT wildcard DNS + hosts file + Chrome
    # network-service kill + firewall IPs + global QUIC block.
    # Without this, Chrome uses DoH + Alt-Svc cache and the video keeps playing.
    _apply_app_qos_enforcement(app_name, "BLOCKED" if bandwidth_kbps <= 10 else "LOW")

    policy = TrafficPolicy(
        id=str(uuid.uuid4())[:8],
        app_name=app_name,
        display_name=app.display_name,
        action="throttle",
        bandwidth_kbps=bandwidth_kbps,
        priority=PriorityClass.LOW,
        created_at=time.time(),
        created_by=created_by,
        qos_policy_name=policy_name,
        reason=reason or f"Throttled {app.display_name} to {bandwidth_kbps} Kbps",
    )
    _active_policies.append(policy)

    audit.log_event(
        "POLICY_CHANGE", actor="SYSTEM",
        policy_change={"action": "throttle", "app": app_name, "bandwidth_kbps": bandwidth_kbps},
        details=policy.reason,
    )

    print(f"[traffic_shaper] Throttled {app.display_name} to {bandwidth_kbps} Kbps")
    return policy


def prioritize_app(app_name: str, reason: str = "", created_by: str = "manual") -> Optional[TrafficPolicy]:
    """Remove any throttle on an app and mark it as prioritized."""
    global _policy_counter
    app = APP_REGISTRY.get(app_name)
    if not app:
        return None

    # Remove any existing throttle for this app
    for p in _active_policies:
        if p.app_name == app_name and p.active:
            _remove_qos_policies(p.qos_policy_name)
            p.active = False

    _policy_counter += 1
    policy = TrafficPolicy(
        id=str(uuid.uuid4())[:8],
        app_name=app_name,
        display_name=app.display_name,
        action="prioritize",
        bandwidth_kbps=0,
        priority=PriorityClass.CRITICAL,
        created_at=time.time(),
        created_by=created_by,
        qos_policy_name=f"PathWise-pri-{app_name}-{_policy_counter}",
        reason=reason or f"Prioritized {app.display_name} — unlimited bandwidth",
    )
    _active_policies.append(policy)

    audit.log_event(
        "POLICY_CHANGE", actor="SYSTEM",
        policy_change={"action": "prioritize", "app": app_name},
        details=policy.reason,
    )

    print(f"[traffic_shaper] Prioritized {app.display_name}")
    return policy


def remove_policy(policy_id: str) -> bool:
    """Remove a traffic policy and restore normal bandwidth."""
    for p in _active_policies:
        if p.id == policy_id and p.active:
            _remove_qos_policies(p.qos_policy_name)
            p.active = False

            # Also strip the App-Priority-Switch enforcement (hosts file,
            # NRPT rules, firewall rules, QUIC block). reset_all wipes
            # every PathWise artifact for the 'ibn' pseudo-user.
            try:
                from server.app_qos.priority_manager import reset_all
                reset_all("ibn")
            except Exception as exc:
                print(f"[traffic_shaper] enforcer reset failed: {exc}")

            audit.log_event(
                "POLICY_CHANGE", actor="SYSTEM",
                policy_change={"action": "remove", "app": p.app_name, "policy_id": p.id},
                details=f"Removed {p.action} policy on {p.display_name}",
            )
            print(f"[traffic_shaper] Removed policy on {p.display_name}")
            return True
    return False


def remove_all_policies():
    """Remove all active traffic shaping policies — full cleanup."""
    for p in _active_policies:
        if p.active:
            p.active = False
    # Remove ALL PathWise QoS and firewall rules in one elevated call
    cmd = (
        'Get-NetQosPolicy -PolicyStore ActiveStore -ErrorAction SilentlyContinue | '
        'Where-Object { $_.Name -like "PathWise-*" } | '
        'Remove-NetQosPolicy -Confirm:$false -ErrorAction SilentlyContinue\n'
        'Get-NetFirewallRule -ErrorAction SilentlyContinue | '
        'Where-Object { $_.DisplayName -like "PathWise-*" } | '
        'Remove-NetFirewallRule -ErrorAction SilentlyContinue'
    )
    _run_powershell(cmd)
    print("[traffic_shaper] All QoS policies and firewall rules removed")


def prioritize_over(high_app: str, low_app: str, throttle_kbps: int = 500, reason: str = "", created_by: str = "manual") -> list[TrafficPolicy]:
    """
    Prioritize one app over another.
    High app gets unlimited bandwidth, low app gets throttled.
    This is what "Prioritize Zoom over YouTube" does.
    """
    policies = []
    p1 = prioritize_app(high_app, reason=reason or f"Prioritized over {low_app}", created_by=created_by)
    if p1:
        policies.append(p1)
    p2 = throttle_app(low_app, bandwidth_kbps=throttle_kbps,
                       reason=reason or f"Throttled in favor of {high_app}", created_by=created_by)
    if p2:
        policies.append(p2)
    return policies


# ── Query ──────────────────────────────────────────────────────

def get_active_policies() -> list[dict]:
    return [
        {
            "id": p.id,
            "app_name": p.app_name,
            "display_name": p.display_name,
            "action": p.action,
            "bandwidth_kbps": p.bandwidth_kbps,
            "priority": p.priority.value,
            "created_at": p.created_at,
            "created_by": p.created_by,
            "active": p.active,
            "reason": p.reason,
            "age_seconds": round(time.time() - p.created_at, 1),
        }
        for p in _active_policies if p.active
    ]


def get_all_policies() -> list[dict]:
    return [
        {
            "id": p.id,
            "app_name": p.app_name,
            "display_name": p.display_name,
            "action": p.action,
            "bandwidth_kbps": p.bandwidth_kbps,
            "priority": p.priority.value,
            "active": p.active,
            "reason": p.reason,
            "created_at": p.created_at,
            "age_seconds": round(time.time() - p.created_at, 1),
        }
        for p in _active_policies
    ]


def get_app_list() -> list[dict]:
    """Return all known apps for the UI dropdown."""
    return [
        {
            "name": app.name,
            "display_name": app.display_name,
            "category": app.category,
            "default_priority": app.default_priority.value,
        }
        for app in APP_REGISTRY.values()
    ]


def resolve_app_name(text: str) -> Optional[str]:
    """Resolve a natural language app reference to a registry key."""
    t = text.lower().strip()
    # Direct match
    if t in APP_REGISTRY:
        return t
    # Alias match
    for alias, name in sorted(APP_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in t:
            return name
    return None
