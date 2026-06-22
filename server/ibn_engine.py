"""
Intent-Based Networking (IBN) Engine.

Parses natural-language administrator intents into structured network policies,
monitors compliance in real-time, and auto-steers traffic when policies are violated.

Example intents:
  "Prioritize VoIP traffic on fiber"
  "Ensure video latency stays below 100ms"
  "Block bulk traffic on satellite"
  "Redirect critical traffic from broadband to fiber"
  "Guarantee medical imaging gets at least 50Mbps on fiber"
"""

from __future__ import annotations
import asyncio
import os as _os_ibn
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from server.state import state, SteeringEvent


# ── Intent Data Model ────────────────────────────────────────

class IntentStatus(str, Enum):
    ACTIVE = "active"
    COMPLIANT = "compliant"
    VIOLATED = "violated"
    AUTO_STEERING = "auto_steering"
    PAUSED = "paused"
    DELETED = "deleted"


class IntentAction(str, Enum):
    PRIORITIZE = "prioritize"
    ENSURE_LATENCY = "ensure_latency"
    ENSURE_JITTER = "ensure_jitter"
    ENSURE_LOSS = "ensure_loss"
    ENSURE_BANDWIDTH = "ensure_bandwidth"
    BLOCK = "block"
    REDIRECT = "redirect"
    DEPRIORITIZE = "deprioritize"
    # App-level traffic shaping (IBN → real OS QoS)
    THROTTLE_APP = "throttle_app"
    PRIORITIZE_APP = "prioritize_app"
    PRIORITIZE_OVER = "prioritize_over"
    # Selective IP degrade — time-bounded, per-IP (does not nuke the app)
    SELECTIVE_DEGRADE = "selective_degrade"


@dataclass
class ParsedIntent:
    action: IntentAction
    traffic_classes: list[str]
    metric: Optional[str] = None
    threshold: Optional[float] = None
    threshold_unit: Optional[str] = None
    preferred_link: Optional[str] = None
    avoid_link: Optional[str] = None
    source_link: Optional[str] = None
    target_link: Optional[str] = None
    # App-level traffic shaping
    high_app: Optional[str] = None       # App to prioritize
    low_app: Optional[str] = None        # App to throttle
    throttle_kbps: Optional[int] = None  # Throttle bandwidth
    # Selective IP degrade
    target_ips: Optional[list[str]] = None
    degrade_mode: Optional[str] = None   # "block" | "throttle"
    duration_s: Optional[int] = None


@dataclass
class NetworkIntent:
    id: str
    raw_text: str
    parsed: ParsedIntent
    status: IntentStatus = IntentStatus.ACTIVE
    created_at: float = 0.0
    last_checked: float = 0.0
    violation_count: int = 0
    auto_steer_count: int = 0
    last_violation: Optional[str] = None
    yang_config: str = ""


# ── Link & Traffic Class Aliases ─────────────────────────────

LINK_ALIASES: dict[str, str] = {
    "fiber": "fiber-primary", "fibre": "fiber-primary", "fiber-primary": "fiber-primary",
    "primary": "fiber-primary", "mpls": "fiber-primary",
    "broadband": "broadband-secondary", "cable": "broadband-secondary",
    "secondary": "broadband-secondary", "dsl": "broadband-secondary",
    "broadband-secondary": "broadband-secondary",
    "satellite": "satellite-backup", "sat": "satellite-backup",
    "backup": "satellite-backup", "vsat": "satellite-backup",
    "satellite-backup": "satellite-backup",
    "5g": "5g-mobile", "mobile": "5g-mobile", "lte": "5g-mobile",
    "cellular": "5g-mobile", "wireless": "5g-mobile", "5g-mobile": "5g-mobile",
}

TRAFFIC_ALIASES: dict[str, str] = {
    "voip": "voip", "voice": "voip", "sip": "voip", "phone": "voip", "calls": "voip",
    "video": "video", "streaming": "video", "conferencing": "video", "zoom": "video",
    "teams": "video", "medical imaging": "video", "imaging": "video",
    "critical": "critical", "business": "critical", "erp": "critical", "database": "critical",
    "mission-critical": "critical", "medical": "critical",
    "bulk": "bulk", "backup": "bulk", "transfer": "bulk", "download": "bulk",
    "file": "bulk", "ftp": "bulk", "guest": "bulk", "wi-fi": "bulk", "wifi": "bulk",
}

METRIC_ALIASES: dict[str, str] = {
    "latency": "latency_ms", "delay": "latency_ms", "lag": "latency_ms",
    "jitter": "jitter_ms", "variation": "jitter_ms",
    "loss": "packet_loss_pct", "packet loss": "packet_loss_pct", "drop": "packet_loss_pct",
    "bandwidth": "bandwidth_util_pct", "throughput": "bandwidth_util_pct", "speed": "bandwidth_util_pct",
    "mbps": "bandwidth_util_pct",
}


# ── Natural Language Parser ──────────────────────────────────

def _find_alias(text: str, alias_map: dict[str, str]) -> list[str]:
    found = []
    text_lower = text.lower()
    for alias, canonical in sorted(alias_map.items(), key=lambda x: -len(x[0])):
        if alias in text_lower and canonical not in found:
            found.append(canonical)
    return found


def _extract_number(text: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:ms|%|mbps|gbps|kbps)?", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _extract_unit(text: str) -> Optional[str]:
    match = re.search(r"\d+(?:\.\d+)?\s*(ms|%|mbps|gbps|kbps)", text, re.IGNORECASE)
    return match.group(1).lower() if match else None


_DURATION_RE = re.compile(
    r"for\s+(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hour|hours)\b",
    re.IGNORECASE,
)

_IP_RE = re.compile(
    r"\b(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)\b"
)


def _parse_duration_s(text: str) -> Optional[int]:
    m = _DURATION_RE.search(text)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("s"):
        return n
    if unit.startswith("m") and not unit.startswith("min"):
        # bare 'm' -> minutes
        return n * 60
    if unit.startswith("min"):
        return n * 60
    if unit.startswith("h"):
        return n * 3600
    return n


def _parse_selective_intent(text: str) -> Optional[ParsedIntent]:
    """
    Parse selective, time-bounded IP degrades. Examples:
      - "Degrade youtube for 2 minutes"
      - "Throttle youtube to 300 kbps for 30 seconds"
      - "Block 172.217.14.1 for 5 minutes"
      - "Block 172.217.14.1, 142.250.80.46 for 60 seconds"
      - "Degrade 172.217.14.0/24 to 500 kbps for 2 min"
    """
    from server.traffic_shaper import resolve_app_name

    t = text.lower().strip()
    duration = _parse_duration_s(t)
    if duration is None:
        return None  # "for N minutes" is required to distinguish from full block

    ips = _IP_RE.findall(text)  # preserve case insensitivity off for IPs

    # Throttle rate (optional — only meaningful when action is 'throttle')
    kbps_match = re.search(r"to\s+(\d+)\s*(kbps|mbps|kb|mb)", t)
    kbps: Optional[int] = None
    if kbps_match:
        n = int(kbps_match.group(1))
        unit = (kbps_match.group(2) or "kbps").lower()
        kbps = n * 1000 if unit in ("mbps", "mb") else n

    wants_throttle = bool(
        kbps_match
        or re.search(r"\b(throttle|degrade|slow|limit|restrict|cap)\b", t)
    )
    wants_block = bool(re.search(r"\b(block|stop|kill|drop|cut)\b", t))

    if not (wants_throttle or wants_block):
        return None

    mode = "throttle" if wants_throttle and not wants_block else (
        "block" if wants_block else "throttle"
    )

    # If the user named an app, resolve it; IPs may be explicit or will be
    # filled in at execution time via selective_degrader.candidate_ips_for().
    app = None
    # Pull the most app-y looking token from the text
    for token in re.findall(r"[a-z_][a-z_0-9]+", t):
        if resolve_app_name(token):
            app = resolve_app_name(token)
            break

    if not ips and not app:
        return None

    return ParsedIntent(
        action=IntentAction.SELECTIVE_DEGRADE,
        traffic_classes=[app] if app else ["ip"],
        low_app=app,
        throttle_kbps=kbps if mode == "throttle" else None,
        target_ips=ips or None,
        degrade_mode=mode,
        duration_s=duration,
    )


def _parse_app_intent(text: str) -> Optional[ParsedIntent]:
    """
    Detect app-level traffic shaping intents like:
      - "Prioritize Zoom over YouTube"
      - "Throttle Netflix to 500 Kbps"
      - "Give Teams maximum bandwidth"
      - "Limit YouTube bandwidth"
      - "Block Twitch"
      - "Remove YouTube restriction"
    """
    from server.traffic_shaper import resolve_app_name

    t = text.lower().strip()

    # "Prioritize X over Y" — the key demo pattern
    m = re.search(r"prioriti[zs]e\s+(.+?)\s+over\s+(.+?)(?:\s+to\s+(\d+)\s*(?:kbps|mbps))?$", t)
    if m:
        high = resolve_app_name(m.group(1))
        low = resolve_app_name(m.group(2))
        if high and low:
            kbps = int(m.group(3)) if m.group(3) else 500
            if "mbps" in t:
                kbps = kbps * 1000
            return ParsedIntent(
                action=IntentAction.PRIORITIZE_OVER,
                traffic_classes=[high, low],
                high_app=high, low_app=low, throttle_kbps=kbps,
            )

    # "Throttle X to N kbps" / "Limit X to N"
    m = re.search(r"(?:throttle|limit|restrict|cap)\s+(.+?)\s+(?:to\s+)?(\d+)\s*(kbps|mbps|kb|mb)?", t)
    if m:
        app = resolve_app_name(m.group(1))
        if app:
            kbps = int(m.group(2))
            unit = (m.group(3) or "kbps").lower()
            if unit in ("mbps", "mb"):
                kbps = kbps * 1000
            return ParsedIntent(
                action=IntentAction.THROTTLE_APP,
                traffic_classes=[app],
                high_app=None, low_app=app, throttle_kbps=kbps,
            )

    # "Throttle X" / "Limit X" (no bandwidth specified → default 500 Kbps)
    m = re.search(r"(?:throttle|limit|restrict|slow down|slow)\s+(.+?)$", t)
    if m:
        app = resolve_app_name(m.group(1).strip())
        if app:
            return ParsedIntent(
                action=IntentAction.THROTTLE_APP,
                traffic_classes=[app],
                high_app=None, low_app=app, throttle_kbps=500,
            )

    # "Prioritize X" / "Give X priority" / "Boost X" / "Give X maximum bandwidth"
    m = re.search(r"(?:prioriti[zs]e|boost)\s+(.+?)$", t)
    if not m:
        m = re.search(r"give\s+(.+?)\s+(?:priority|maximum|full|unlimited)(?:\s+bandwidth)?", t)
    if m:
        app = resolve_app_name(m.group(1).strip())
        if app:
            return ParsedIntent(
                action=IntentAction.PRIORITIZE_APP,
                traffic_classes=[app],
                high_app=app, low_app=None,
            )

    # "Block X" / "Stop X"
    m = re.search(r"(?:block|stop|kill|disable)\s+(.+?)$", t)
    if m:
        app = resolve_app_name(m.group(1).strip())
        if app:
            return ParsedIntent(
                action=IntentAction.THROTTLE_APP,
                traffic_classes=[app],
                high_app=None, low_app=app, throttle_kbps=1,  # ~blocked
            )

    # "Remove X restriction" / "Unblock X" / "Restore X"
    m = re.search(r"(?:remove|unblock|restore|unthrottle|unlimit|free)\s+(.+?)(?:\s+restriction|\s+limit|\s+throttle)?$", t)
    if m:
        app = resolve_app_name(m.group(1).strip())
        if app:
            return ParsedIntent(
                action=IntentAction.PRIORITIZE_APP,
                traffic_classes=[app],
                high_app=app, low_app=None,
            )

    return None


class IntentParseError(ValueError):
    """Raised when natural-language intent text doesn't match any supported pattern.
    Callers should surface this to clients as HTTP 400 with rephrasing hints
    (UC-5: 'On ambiguous NLP parse: show error, provide rephrasing
    suggestions, do NOT attempt deployment')."""


def parse_intent(raw_text: str) -> ParsedIntent:
    """Parse a natural-language intent into a structured policy.

    Raises IntentParseError when the input matches no known pattern.
    """
    t = raw_text.lower().strip()

    # ── Time-bounded selective degrade has highest precedence ──
    # because it's the most specific form (requires "for N ...").
    selective = _parse_selective_intent(raw_text)
    if selective:
        return selective

    # ── Check for app-level traffic shaping next ───────────────
    from server.traffic_shaper import resolve_app_name, APP_ALIASES
    app_result = _parse_app_intent(t)
    if app_result:
        return app_result

    traffic = _find_alias(t, TRAFFIC_ALIASES) or ["voip", "video", "critical"]
    links = _find_alias(t, LINK_ALIASES)
    metrics = _find_alias(t, METRIC_ALIASES)
    number = _extract_number(t)
    unit = _extract_unit(t)

    # Determine action from keywords
    if re.search(r"\b(block|deny|reject|drop|prohibit|disallow)\b", t):
        return ParsedIntent(
            action=IntentAction.BLOCK,
            traffic_classes=traffic,
            avoid_link=links[0] if links else None,
        )

    if re.search(r"\b(redirect|move|shift|reroute|migrate)\b", t):
        src = links[0] if len(links) >= 1 else None
        tgt = links[1] if len(links) >= 2 else None
        if re.search(r"from\s+\w+.*to\s+\w+", t) and len(links) >= 2:
            src, tgt = links[0], links[1]
        elif re.search(r"to\s+\w+.*from\s+\w+", t) and len(links) >= 2:
            tgt, src = links[0], links[1]
        return ParsedIntent(
            action=IntentAction.REDIRECT,
            traffic_classes=traffic,
            source_link=src,
            target_link=tgt,
        )

    if re.search(r"\b(prioriti[zs]e|prefer|favor|boost)\b", t):
        return ParsedIntent(
            action=IntentAction.PRIORITIZE,
            traffic_classes=traffic,
            preferred_link=links[0] if links else None,
        )

    if re.search(r"\b(deprioritize|lower|reduce priority|throttle)\b", t):
        return ParsedIntent(
            action=IntentAction.DEPRIORITIZE,
            traffic_classes=traffic,
            avoid_link=links[0] if links else None,
        )

    if re.search(r"\b(ensure|guarantee|maintain|keep|must be|should be|stays?)\b", t):
        if metrics:
            m = metrics[0]
            action_map = {
                "latency_ms": IntentAction.ENSURE_LATENCY,
                "jitter_ms": IntentAction.ENSURE_JITTER,
                "packet_loss_pct": IntentAction.ENSURE_LOSS,
                "bandwidth_util_pct": IntentAction.ENSURE_BANDWIDTH,
            }
            return ParsedIntent(
                action=action_map.get(m, IntentAction.ENSURE_LATENCY),
                traffic_classes=traffic,
                metric=m,
                threshold=number,
                threshold_unit=unit,
                preferred_link=links[0] if links else None,
            )

    if number is not None and metrics:
        m = metrics[0]
        action_map = {
            "latency_ms": IntentAction.ENSURE_LATENCY,
            "jitter_ms": IntentAction.ENSURE_JITTER,
            "packet_loss_pct": IntentAction.ENSURE_LOSS,
            "bandwidth_util_pct": IntentAction.ENSURE_BANDWIDTH,
        }
        return ParsedIntent(
            action=action_map.get(m, IntentAction.ENSURE_LATENCY),
            traffic_classes=traffic,
            metric=m,
            threshold=number,
            threshold_unit=unit,
            preferred_link=links[0] if links else None,
        )

    raise IntentParseError(
        f"Could not parse intent: '{raw_text}'. "
        "Try patterns like 'Prioritize VoIP on fiber', "
        "'Throttle YouTube to 500 kbps', "
        "'Block 172.217.14.110 for 2 minutes', or "
        "'Ensure video latency stays below 50 ms'."
    )


# ── YANG/NETCONF Config Generator ────────────────────────────

def generate_yang_config(intent: NetworkIntent) -> str:
    """Generate a YANG-style configuration snippet for the parsed intent."""
    p = intent.parsed
    tc_str = ", ".join(p.traffic_classes)
    lines = [
        f'<intent xmlns="urn:pathwise:ibn">',
        f'  <id>{intent.id}</id>',
        f'  <description>{intent.raw_text}</description>',
        f'  <policy>',
        f'    <action>{p.action.value}</action>',
        f'    <traffic-classes>{tc_str}</traffic-classes>',
    ]
    if p.metric and p.threshold is not None:
        lines.append(f'    <constraint>')
        lines.append(f'      <metric>{p.metric}</metric>')
        lines.append(f'      <threshold>{p.threshold}</threshold>')
        if p.threshold_unit:
            lines.append(f'      <unit>{p.threshold_unit}</unit>')
        lines.append(f'    </constraint>')
    if p.preferred_link:
        lines.append(f'    <preferred-path>{p.preferred_link}</preferred-path>')
    if p.avoid_link:
        lines.append(f'    <avoid-path>{p.avoid_link}</avoid-path>')
    if p.source_link and p.target_link:
        lines.append(f'    <redirect from="{p.source_link}" to="{p.target_link}" />')
    lines.extend([
        f'  </policy>',
        f'</intent>',
    ])
    return "\n".join(lines)


# ── Intent Store ─────────────────────────────────────────────

_intents: list[NetworkIntent] = []


def get_all_intents() -> list[NetworkIntent]:
    return [i for i in _intents if i.status != IntentStatus.DELETED]


def get_intent(intent_id: str) -> Optional[NetworkIntent]:
    return next((i for i in _intents if i.id == intent_id), None)


def create_intent(raw_text: str) -> NetworkIntent:
    parsed = parse_intent(raw_text)
    intent = NetworkIntent(
        id=str(uuid.uuid4())[:8],
        raw_text=raw_text,
        parsed=parsed,
        status=IntentStatus.ACTIVE,
        created_at=time.time(),
    )
    intent.yang_config = generate_yang_config(intent)
    _intents.append(intent)

    # Execute app-level traffic shaping immediately
    if parsed.action in (IntentAction.THROTTLE_APP, IntentAction.PRIORITIZE_APP, IntentAction.PRIORITIZE_OVER):
        _execute_traffic_shaping(intent)
    elif parsed.action == IntentAction.SELECTIVE_DEGRADE:
        _execute_selective_degrade(intent)

    return intent


def _execute_selective_degrade(intent: NetworkIntent) -> None:
    """Apply a time-bounded selective IP degrade (does NOT nuke the app)."""
    from server.app_qos import selective_degrader
    p = intent.parsed
    try:
        ips = list(p.target_ips or [])
        if not ips and p.low_app:
            ips = selective_degrader.candidate_ips_for(p.low_app)[:8]
        if not ips:
            intent.status = IntentStatus.VIOLATED
            intent.last_violation = "No target IPs available for selective degrade"
            return
        mode = (p.degrade_mode or "throttle")
        # Default throttle rate when NL didn't specify one: 500 kbps forces
        # YouTube/Netflix to drop to 240-360p, the App-Switcher demo target.
        throttle_kbps = p.throttle_kbps
        if mode == "throttle" and (throttle_kbps is None or throttle_kbps < 32):
            throttle_kbps = 500
        rule = selective_degrader.start_rule(
            ips=ips,
            mode=mode,  # type: ignore[arg-type]
            duration_s=int(p.duration_s or 60),
            throttle_kbps=throttle_kbps,
            app_id=p.low_app,
            reason=intent.raw_text,
        )
        intent.status = IntentStatus.COMPLIANT
        intent.last_violation = None
        intent.yang_config = (intent.yang_config or "") + (
            f"\n<!-- selective-rule id={rule.id} ips={len(rule.ips)} "
            f"mode={rule.mode} ttl={rule.duration_s}s -->"
        )
    except Exception as exc:
        print(f"[IBN] selective degrade failed: {exc}")
        intent.status = IntentStatus.VIOLATED
        intent.last_violation = str(exc)


def _execute_traffic_shaping(intent: NetworkIntent):
    """Execute real OS-level traffic shaping for app intents."""
    from server.traffic_shaper import throttle_app, prioritize_app, prioritize_over

    p = intent.parsed
    try:
        if p.action == IntentAction.PRIORITIZE_OVER and p.high_app and p.low_app:
            policies = prioritize_over(
                p.high_app, p.low_app,
                throttle_kbps=p.throttle_kbps or 500,
                reason=intent.raw_text,
                created_by=intent.id,
            )
            intent.status = IntentStatus.COMPLIANT
        elif p.action == IntentAction.THROTTLE_APP and p.low_app:
            throttle_app(
                p.low_app,
                bandwidth_kbps=p.throttle_kbps or 500,
                reason=intent.raw_text,
                created_by=intent.id,
            )
            intent.status = IntentStatus.COMPLIANT
        elif p.action == IntentAction.PRIORITIZE_APP and p.high_app:
            prioritize_app(
                p.high_app,
                reason=intent.raw_text,
                created_by=intent.id,
            )
            intent.status = IntentStatus.COMPLIANT
    except Exception as e:
        print(f"[IBN] Traffic shaping failed: {e}")
        intent.last_violation = str(e)


def delete_intent(intent_id: str) -> bool:
    intent = get_intent(intent_id)
    if intent:
        # Remove any traffic shaping policies created by this intent
        if intent.parsed.action in (IntentAction.THROTTLE_APP, IntentAction.PRIORITIZE_APP, IntentAction.PRIORITIZE_OVER):
            try:
                from server.traffic_shaper import get_all_policies, remove_policy
                for p in get_all_policies():
                    if p.get("created_by") == intent_id:
                        remove_policy(p["id"])
            except Exception as e:
                print(f"[IBN] Cleanup traffic shaping failed: {e}")
        intent.status = IntentStatus.DELETED
        return True
    return False


def pause_intent(intent_id: str) -> bool:
    intent = get_intent(intent_id)
    if intent and intent.status != IntentStatus.DELETED:
        intent.status = IntentStatus.PAUSED
        return True
    return False


def resume_intent(intent_id: str) -> bool:
    intent = get_intent(intent_id)
    if intent and intent.status == IntentStatus.PAUSED:
        intent.status = IntentStatus.ACTIVE
        return True
    return False


# ── Compliance Monitor ───────────────────────────────────────

def _get_link_metric(link_id: str, metric: str) -> Optional[float]:
    points = state.get_latest_effective(link_id, 5)
    if not points:
        return None
    latest = points[-1]
    return getattr(latest, metric, None)


def _find_best_link_for_metric(metric: str, threshold: float, exclude: Optional[str] = None) -> Optional[str]:
    best_link, best_val = None, float("inf")
    for link_id in state.active_links:
        if link_id == exclude:
            continue
        val = _get_link_metric(link_id, metric)
        if val is not None and val < threshold and val < best_val:
            best_link, best_val = link_id, val
    return best_link


def _find_healthiest_link(exclude: Optional[str] = None) -> Optional[str]:
    best, best_score = None, -1.0
    for link_id in state.active_links:
        pred = state.predictions.get(link_id)
        if pred and link_id != exclude and pred.health_score > best_score:
            best, best_score = link_id, pred.health_score
    return best


_last_auto_steer: dict[str, float] = {}
AUTO_STEER_COOLDOWN = 30.0  # seconds between auto-steers per intent


def check_intent_compliance(intent: NetworkIntent) -> None:
    """Check a single intent and update its status."""
    if intent.status in (IntentStatus.DELETED, IntentStatus.PAUSED):
        return

    p = intent.parsed
    intent.last_checked = time.time()
    # One-shot actions (app-level shaping, selective degrade) are executed at
    # creation time and not re-evaluated -- the selective_degrader sweeper
    # tears them down on TTL expiry.
    if p.action in (
        IntentAction.SELECTIVE_DEGRADE,
        IntentAction.THROTTLE_APP,
        IntentAction.PRIORITIZE_APP,
        IntentAction.PRIORITIZE_OVER,
    ):
        return
    violated = False
    violation_detail = ""

    if p.action == IntentAction.ENSURE_LATENCY and p.threshold is not None:
        for link_id in state.active_links:
            val = _get_link_metric(link_id, "latency_ms")
            if val is not None and val > p.threshold:
                if p.preferred_link and link_id != p.preferred_link:
                    continue
                violated = True
                violation_detail = f"{link_id} latency {val:.1f}ms > {p.threshold}ms"
                break

    elif p.action == IntentAction.ENSURE_JITTER and p.threshold is not None:
        for link_id in state.active_links:
            val = _get_link_metric(link_id, "jitter_ms")
            if val is not None and val > p.threshold:
                if p.preferred_link and link_id != p.preferred_link:
                    continue
                violated = True
                violation_detail = f"{link_id} jitter {val:.1f}ms > {p.threshold}ms"
                break

    elif p.action == IntentAction.ENSURE_LOSS and p.threshold is not None:
        for link_id in state.active_links:
            val = _get_link_metric(link_id, "packet_loss_pct")
            if val is not None and val > p.threshold:
                if p.preferred_link and link_id != p.preferred_link:
                    continue
                violated = True
                violation_detail = f"{link_id} loss {val:.2f}% > {p.threshold}%"
                break

    elif p.action == IntentAction.PRIORITIZE:
        if p.preferred_link:
            pred = state.predictions.get(p.preferred_link)
            if pred and pred.health_score < 40:
                violated = True
                violation_detail = f"Preferred link {p.preferred_link} health {pred.health_score:.0f} < 40"

    elif p.action == IntentAction.BLOCK:
        if p.avoid_link and not state.is_traffic_diverted_from(p.avoid_link):
            pred = state.predictions.get(p.avoid_link)
            if pred and pred.health_score < 60:
                violated = True
                violation_detail = f"Traffic still active on blocked link {p.avoid_link}"

    elif p.action == IntentAction.REDIRECT:
        if p.source_link and not state.is_traffic_diverted_from(p.source_link):
            violated = True
            violation_detail = f"Traffic not yet redirected from {p.source_link}"

    if violated:
        intent.violation_count += 1
        intent.last_violation = violation_detail

        last_steer = _last_auto_steer.get(intent.id, 0)
        if time.time() - last_steer > AUTO_STEER_COOLDOWN:
            intent.status = IntentStatus.VIOLATED
            _auto_steer_for_intent(intent)
            _last_auto_steer[intent.id] = time.time()
        else:
            intent.status = IntentStatus.AUTO_STEERING
    else:
        if intent.status in (IntentStatus.VIOLATED, IntentStatus.AUTO_STEERING, IntentStatus.ACTIVE):
            intent.status = IntentStatus.COMPLIANT


def _auto_steer_for_intent(intent: NetworkIntent) -> None:
    """Automatically steer traffic to satisfy the intent."""
    p = intent.parsed
    source = None
    target = None

    if p.action in (IntentAction.ENSURE_LATENCY, IntentAction.ENSURE_JITTER, IntentAction.ENSURE_LOSS):
        if p.metric and p.threshold is not None:
            for link_id in state.active_links:
                val = _get_link_metric(link_id, p.metric)
                if val is not None and val > p.threshold:
                    source = link_id
                    break
            if source:
                target = _find_best_link_for_metric(p.metric, p.threshold, exclude=source)
                if not target:
                    target = _find_healthiest_link(exclude=source)

    elif p.action == IntentAction.PRIORITIZE and p.preferred_link:
        alt = _find_healthiest_link(exclude=p.preferred_link)
        if alt:
            source = alt
            target = p.preferred_link

    elif p.action == IntentAction.REDIRECT:
        source = p.source_link
        target = p.target_link

    elif p.action == IntentAction.BLOCK and p.avoid_link:
        source = p.avoid_link
        target = _find_healthiest_link(exclude=p.avoid_link)

    if source and target and source != target:
        already_diverted = state.is_traffic_diverted_from(source)
        if not already_diverted:
            intent.status = IntentStatus.AUTO_STEERING
            intent.auto_steer_count += 1

            evt = SteeringEvent(
                id=f"ibn-{intent.id}-{intent.auto_steer_count}",
                timestamp=time.time(),
                action="IBN_AUTO_STEER",
                source_link=source,
                target_link=target,
                traffic_classes=",".join(p.traffic_classes),
                confidence=0.9,
                reason=f'Intent "{intent.raw_text[:60]}" — {intent.last_violation}',
                status="executed",
                lstm_enabled=state.lstm_enabled,
            )
            state.steering_history.appendleft(evt)


# ── Background Monitor Loop ─────────────────────────────────

async def ibn_monitor_loop():
    """Check all active intents every 2 seconds."""
    while True:
        try:
            for intent in _intents:
                if intent.status not in (IntentStatus.DELETED, IntentStatus.PAUSED):
                    check_intent_compliance(intent)
        except Exception as e:
            print(f"[IBN] monitor error: {e}")
        await asyncio.sleep(2.0)


# ── Serialization ────────────────────────────────────────────

def serialize_intent(i: NetworkIntent) -> dict:
    return {
        "id": i.id,
        "raw_text": i.raw_text,
        "status": i.status.value,
        "action": i.parsed.action.value,
        "traffic_classes": i.parsed.traffic_classes,
        "metric": i.parsed.metric,
        "threshold": i.parsed.threshold,
        "threshold_unit": i.parsed.threshold_unit,
        "preferred_link": i.parsed.preferred_link,
        "avoid_link": i.parsed.avoid_link,
        "source_link": i.parsed.source_link,
        "target_link": i.parsed.target_link,
        "high_app": i.parsed.high_app,
        "low_app": i.parsed.low_app,
        "throttle_kbps": i.parsed.throttle_kbps,
        "target_ips": i.parsed.target_ips,
        "degrade_mode": i.parsed.degrade_mode,
        "duration_s": i.parsed.duration_s,
        "yang_config": i.yang_config,
        "created_at": i.created_at,
        "last_checked": i.last_checked,
        "violation_count": i.violation_count,
        "auto_steer_count": i.auto_steer_count,
        "last_violation": i.last_violation,
        "age_seconds": round(time.time() - i.created_at, 1),
    }


# ════════════════════════════════════════════════════════════════
#  GAP 4 — YANG / NETCONF delivery to live SDN controller
#  Public entry point: deploy_intent({"command": "..."})
#  - Parses NL command via existing parse_intent()
#  - Generates an IETF YANG/NETCONF payload
#  - Validates via Digital Twin sandbox (Req-Func-Sw-8)
#  - Submits to live SDN controller via SDNControllerAdapter
#  Satisfies: Req-Func-Sw-11, Req-Func-Sw-12
# ════════════════════════════════════════════════════════════════


_INTENT_LINK_DEFAULTS = {
    "fiber-primary":      "openflow:1",
    "broadband-secondary": "openflow:2",
    "satellite-backup":   "openflow:3",
    "5g-mobile":          "openflow:4",
    "wifi":               "openflow:5",
}


def _default_source_for(target: str) -> str:
    """Pick a sensible source link different from the target."""
    if target == "fiber-primary":
        return "broadband-secondary"
    return "fiber-primary"


def _parsed_to_dict(parsed: ParsedIntent) -> dict:
    """Coerce a ParsedIntent dataclass into a plain dict for downstream use."""
    target_link = (parsed.target_link or parsed.preferred_link
                   or "broadband-secondary")
    source_link = parsed.source_link or _default_source_for(target_link)
    # Guard: never let source == target (would form a self-loop in sandbox)
    if source_link == target_link:
        source_link = _default_source_for(target_link)
    return {
        "action": parsed.action.value,
        "traffic_classes": list(parsed.traffic_classes or []),
        "app": (parsed.high_app or parsed.low_app or
                (parsed.traffic_classes[0] if parsed.traffic_classes else "default")),
        "preferred_link": parsed.preferred_link,
        "avoid_link": parsed.avoid_link,
        "source_link": source_link,
        "target_link": target_link,
        "metric": parsed.metric,
        "threshold": parsed.threshold,
        "high_app": parsed.high_app,
        "low_app": parsed.low_app,
        "throttle_kbps": parsed.throttle_kbps,
        "dscp": _dscp_for_action(parsed.action.value, parsed.traffic_classes),
        "node_id": _INTENT_LINK_DEFAULTS.get(target_link, "openflow:1"),
    }


def _dscp_for_action(action: str, traffic_classes: list) -> int:
    if not traffic_classes:
        return 0
    tc = traffic_classes[0]
    return {"voip": 46, "video": 34, "critical": 26, "bulk": 0}.get(tc, 0)


def _yang_priority(parsed_dict: dict) -> int:
    action = parsed_dict.get("action", "normal")
    return {
        "prioritize": 65000,
        "prioritize_app": 65000,
        "prioritize_over": 65000,
        "block": 0,
        "redirect": 50000,
        "deprioritize": 10000,
        "throttle_app": 10000,
    }.get(action, 20000)


def _yang_match_criteria(parsed_dict: dict) -> list:
    criteria = [{"type": "ETH_TYPE", "ethType": "0x0800"}]
    dscp = parsed_dict.get("dscp", 0)
    if dscp:
        criteria.append({"type": "IP_DSCP", "ipDscp": dscp})
    return criteria


def _to_yang_netconf(parsed_dict: dict) -> dict:
    """Generate an IETF YANG-model-compliant NETCONF payload from a parsed intent."""
    return {
        "ietf-interfaces:interface": {
            "name": parsed_dict.get("app", "default"),
            "type": "iana-if-type:ethernetCsmacd",
            "ietf-ip:ipv4": {
                "ietf-diffserv-policy:policies": {
                    "policy-entry": [{
                        "policy-name": f"pathwise-{parsed_dict.get('action','prioritize')}",
                        "classifier-name": parsed_dict.get("app", "default"),
                        "marking": {"dscp-value": parsed_dict.get("dscp", 0)},
                    }]
                }
            },
        }
    }


def _yang_to_xml_payload(parsed_dict: dict) -> str:
    """
    Render the YANG payload as a NETCONF-compliant XML <config> element.
    Wrapped by an <edit-config><config>...</config></edit-config> RPC when
    sent via ncclient below.

    Uses the ietf-diffserv-classifier + ietf-qos-policy YANG modules that
    CLAUDE.md §10 specifies for traffic prioritization.
    """
    action = parsed_dict.get("action", "prioritize")
    app = parsed_dict.get("app", "default")
    dscp = parsed_dict.get("dscp", 0)
    priority = _yang_priority(parsed_dict)
    source_link = parsed_dict.get("source_link") or "fiber-primary"
    target_link = parsed_dict.get("target_link") or "broadband-secondary"

    return (
        '<config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0">'
        '<interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">'
        f'<interface><name>{app}</name>'
        '<type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">'
        'ianaift:ethernetCsmacd</type>'
        '<enabled>true</enabled>'
        '</interface></interfaces>'
        '<qos-policy xmlns="urn:ietf:params:xml:ns:yang:ietf-qos-policy">'
        f'<policy><name>pathwise-{action}</name>'
        f'<classifier-entry><name>{app}</name>'
        f'<filter-entry><dscp>{dscp}</dscp></filter-entry>'
        '</classifier-entry>'
        '<policy-entry>'
        f'<action>{action}</action>'
        f'<priority>{priority}</priority>'
        f'<from-link>{source_link}</from-link>'
        f'<to-link>{target_link}</to-link>'
        '</policy-entry>'
        '</policy></qos-policy>'
        '</config>'
    )


def _netconf_submit(parsed_dict: dict) -> dict:
    """
    Submit the YANG payload to a NETCONF server via ncclient (RFC 6241 transport).

    Connection is attempted to the SDN controller's NETCONF endpoint
    (ODL default 2830). If ncclient isn't installed or the server can't be
    reached, returns a graceful failure dict that callers merge into the
    deploy_intent response — the REST fallback via sdn_adapter still runs.
    """
    import os as _os

    host = _os.getenv("NETCONF_HOST") or _os.getenv("ODL_HOST", "opendaylight")
    port = int(_os.getenv("NETCONF_PORT", "2830"))
    username = _os.getenv("NETCONF_USER") or _os.getenv("ODL_USER", "admin")
    password = _os.getenv("NETCONF_PASS") or _os.getenv("ODL_PASS", "admin")

    payload_xml = _yang_to_xml_payload(parsed_dict)

    try:
        from ncclient import manager  # type: ignore
    except ImportError:
        return {
            "attempted": False,
            "transport": "none",
            "reason": "ncclient_not_installed",
            "payload_xml": payload_xml,
        }

    try:
        with manager.connect(
            host=host, port=port, username=username, password=password,
            hostkey_verify=False, device_params={"name": "default"},
            timeout=10,
        ) as mgr:
            result = mgr.edit_config(target="running", config=payload_xml)
            return {
                "attempted": True,
                "transport": "netconf",
                "ok": result.ok,
                "host": host,
                "port": port,
                "payload_xml": payload_xml,
            }
    except Exception as exc:
        return {
            "attempted": True,
            "transport": "netconf",
            "ok": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "host": host,
            "port": port,
            "payload_xml": payload_xml,
        }


def deploy_intent(intent: dict) -> dict:
    """
    Translate an intent (natural-language command) to YANG/NETCONF and submit
    it to the live SDN controller.

    Args:
        intent: {"command": "Prioritize Zoom over Netflix on fiber"}

    Returns:
        {
            "success": bool,
            "flow_id": str,
            "elapsed_ms": float,
            "yang_payload": dict,    # IETF-compliant YANG/NETCONF
            "sandbox": dict,         # Sandbox validation report
            "intent": dict,          # Parsed intent
        }

    Satisfies: Req-Func-Sw-11, Req-Func-Sw-12
    """
    import uuid as _uuid
    import time as _time

    from server.sdn_adapter import get_adapter
    from server.sandbox import run_sandbox_validation

    t0 = _time.perf_counter()
    adapter = get_adapter()

    command = intent.get("command", "")
    if not command:
        return {"success": False, "reason": "empty_command"}

    # 1. Parse natural language → ParsedIntent → dict
    try:
        parsed_struct = parse_intent(command)
    except Exception as exc:
        return {"success": False, "reason": "parse_failed", "error": str(exc),
                "command": command}

    parsed = _parsed_to_dict(parsed_struct)

    # 2. Generate YANG/NETCONF payload
    yang_payload = _to_yang_netconf(parsed)

    # 3. Map intent to a flow body for SDN
    flow_id = f"ibn-{_uuid.uuid4().hex[:8]}"
    flow_body = {
        "id": flow_id,
        "priority": _yang_priority(parsed),
        "timeout": 0,
        "isPermanent": True,
        "tableId": 0,
        "treatment": {"instructions": [
            {"type": "OUTPUT",
             "port": parsed.get("target_link") or "NORMAL"}
        ]},
        "selector": {"criteria": _yang_match_criteria(parsed)},
        "traffic_class": (parsed.get("traffic_classes") or ["bulk"])[0],
        "yang_netconf": yang_payload,
    }

    # 4. Sandbox validation BEFORE deploy (Req-Func-Sw-8)
    sandbox_result = run_sandbox_validation(
        source_link=parsed.get("source_link") or "fiber-primary",
        target_link=parsed.get("target_link") or "broadband-secondary",
        flow_body=flow_body,
    )
    if not sandbox_result.get("passed"):
        return {
            "success": False,
            "reason": "sandbox_rejected",
            "sandbox": sandbox_result,
            "yang_payload": yang_payload,
            "intent": parsed,
            "flow_id": flow_id,
            "elapsed_ms": round((_time.perf_counter() - t0) * 1000, 2),
        }

    # 5. Submit to SDN controller — try NETCONF transport first (RFC 6241),
    # then REST flow-install. When NETCONF_ENABLED=true, the NETCONF path
    # is authoritative; otherwise the REST path provides a stable fallback.
    netconf_enabled = _os_ibn.getenv("NETCONF_ENABLED", "false").lower() == "true"
    netconf_result = None
    if netconf_enabled:
        netconf_result = _netconf_submit(parsed)

    node_id = parsed.get("node_id", "openflow:1")
    ok = adapter.update_flow_table(node_id, flow_id, flow_body)

    elapsed_ms = (_time.perf_counter() - t0) * 1000
    return {
        "success": ok,
        "flow_id": flow_id,
        "elapsed_ms": round(elapsed_ms, 2),
        "within_sla_50ms": elapsed_ms < 50.0,
        "yang_payload": yang_payload,
        "sandbox": sandbox_result,
        "netconf": netconf_result,
        "intent": parsed,
    }
