"""
Alert system — email notifications on health threshold breaches.

Implements:
  - Req-Func-Sw-17: Real-time alerts via dashboard + email
  - UC-2: Alert suppression/deduplication within configurable window
"""

from __future__ import annotations
import asyncio
import os
import smtplib
import time
from collections import deque
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


@dataclass
class AlertRecord:
    id: str
    timestamp: float
    link_id: str
    health_score: float
    confidence: float
    alert_type: str  # threshold_breach, brownout, recovery
    details: str
    email_sent: bool = False


# ── Configuration ──────────────────────────────────────────────

SMTP_HOST = os.environ.get("ALERT_EMAIL_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("ALERT_EMAIL_SMTP_PORT", "587"))
EMAIL_FROM = os.environ.get("ALERT_EMAIL_FROM", "")
EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "").split(",")
HEALTH_THRESHOLD = float(os.environ.get("HEALTH_SCORE_THRESHOLD", "70"))
SUPPRESSION_WINDOW = float(os.environ.get("ALERT_SUPPRESSION_WINDOW_S", "5"))

# ── State ──────────────────────────────────────────────────────

_alert_history: deque[AlertRecord] = deque(maxlen=500)
_last_alert_time: dict[str, float] = {}
_alert_id_counter = 0


def check_and_alert(
    link_id: str,
    health_score: float,
    confidence: float,
) -> Optional[AlertRecord]:
    """
    Check if an alert should be fired for this link.
    Handles deduplication via suppression window.
    """
    global _alert_id_counter

    if health_score >= HEALTH_THRESHOLD:
        return None

    # Suppression: don't alert for same link within window
    last = _last_alert_time.get(link_id, 0)
    if time.time() - last < SUPPRESSION_WINDOW:
        return None

    _alert_id_counter += 1
    alert = AlertRecord(
        id=f"alert-{_alert_id_counter}",
        timestamp=time.time(),
        link_id=link_id,
        health_score=health_score,
        confidence=confidence,
        alert_type="threshold_breach",
        details=f"Link {link_id} health score {health_score:.0f} below threshold {HEALTH_THRESHOLD:.0f}",
    )

    _last_alert_time[link_id] = time.time()
    _alert_history.append(alert)

    # Try sending email (non-blocking, fire-and-forget)
    if SMTP_HOST and EMAIL_FROM and any(EMAIL_TO):
        try:
            _send_email_sync(alert)
            alert.email_sent = True
        except Exception as e:
            print(f"[alerts] Email send failed: {e}")

    # Log to audit
    try:
        from server.audit import log_event
        log_event(
            event_type="ALERT",
            actor="SYSTEM",
            link_id=link_id,
            health_score=health_score,
            confidence=confidence,
            details=alert.details,
        )
    except Exception:
        pass

    return alert


def _send_email_sync(alert: AlertRecord):
    """Send alert email via SMTP."""
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)
    msg["Subject"] = f"[PathWise AI] Alert: {alert.link_id} health {alert.health_score:.0f}/100"

    body = f"""PathWise AI Network Health Alert

Link:         {alert.link_id}
Health Score: {alert.health_score:.0f}/100
Confidence:   {alert.confidence:.1%}
Time:         {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert.timestamp))}

{alert.details}

This is an automated alert from PathWise AI SD-WAN Management Platform.
"""
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        smtp_user = os.environ.get("ALERT_EMAIL_USER", "")
        smtp_pass = os.environ.get("ALERT_EMAIL_PASS", "")
        if smtp_user and smtp_pass:
            server.starttls()
            server.login(smtp_user, smtp_pass)
        server.send_message(msg)


# ── Query ──────────────────────────────────────────────────────

def get_alert_history(limit: int = 50) -> list[dict]:
    entries = list(_alert_history)
    entries.reverse()
    return [
        {
            "id": a.id,
            "timestamp": a.timestamp,
            "link_id": a.link_id,
            "health_score": round(a.health_score, 1),
            "confidence": round(a.confidence, 3),
            "alert_type": a.alert_type,
            "details": a.details,
            "email_sent": a.email_sent,
        }
        for a in entries[:limit]
    ]


def update_config(threshold: Optional[float] = None, suppression: Optional[float] = None):
    global HEALTH_THRESHOLD, SUPPRESSION_WINDOW
    if threshold is not None:
        HEALTH_THRESHOLD = threshold
    if suppression is not None:
        SUPPRESSION_WINDOW = suppression
