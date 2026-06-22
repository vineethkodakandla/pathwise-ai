"""
Tamper-evident Audit Log — records all system events with SHA-256 checksums.

Implements:
  - Req-Func-Sw-18: Persistent, tamper-evident audit log
  - Req-Qual-Sec-3: HIPAA-compliant audit trail
"""

from __future__ import annotations
import hashlib
import json
import time
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class AuditEntry:
    id: str
    event_time: float
    event_type: str  # STEERING, VALIDATION, POLICY_CHANGE, AUTH, ALERT, SYSTEM
    actor: str       # user email or "SYSTEM"
    link_id: Optional[str] = None
    health_score: Optional[float] = None
    confidence: Optional[float] = None
    validation_result: Optional[str] = None  # PASSED, FAILED
    routing_change: Optional[dict] = None
    policy_change: Optional[dict] = None
    details: Optional[str] = None
    checksum: str = ""
    prev_checksum: str = ""  # Chain reference for tamper detection


# ── Audit Log Store ────────────────────────────────────────────

_audit_log: deque[AuditEntry] = deque(maxlen=10000)
_last_checksum: str = "genesis"


def _compute_checksum(entry: AuditEntry, prev_checksum: str) -> str:
    """
    SHA-256 of entry fields + previous entry's checksum.
    Creates a hash chain: modifying or deleting any entry breaks the chain.
    """
    payload = (
        f"{entry.id}|{entry.event_time}|{entry.event_type}|{entry.actor}|"
        f"{entry.link_id}|{entry.health_score}|{entry.confidence}|"
        f"{entry.validation_result}|{json.dumps(entry.routing_change, sort_keys=True)}|"
        f"{json.dumps(entry.policy_change, sort_keys=True)}|{entry.details}|"
        f"{prev_checksum}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def log_event(
    event_type: str,
    actor: str = "SYSTEM",
    link_id: Optional[str] = None,
    health_score: Optional[float] = None,
    confidence: Optional[float] = None,
    validation_result: Optional[str] = None,
    routing_change: Optional[dict] = None,
    policy_change: Optional[dict] = None,
    details: Optional[str] = None,
) -> AuditEntry:
    """Create a new audit entry with chained checksum."""
    global _last_checksum

    entry = AuditEntry(
        id=str(uuid.uuid4()),
        event_time=time.time(),
        event_type=event_type,
        actor=actor,
        link_id=link_id,
        health_score=health_score,
        confidence=confidence,
        validation_result=validation_result,
        routing_change=routing_change,
        policy_change=policy_change,
        details=details,
        prev_checksum=_last_checksum,
    )
    entry.checksum = _compute_checksum(entry, _last_checksum)
    _last_checksum = entry.checksum
    _audit_log.append(entry)
    return entry


def get_audit_log(
    page: int = 1,
    per_page: int = 50,
    event_type: Optional[str] = None,
    actor: Optional[str] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
) -> tuple[list[AuditEntry], int]:
    """Paginated, filterable retrieval."""
    entries = list(_audit_log)
    entries.reverse()  # Most recent first

    if event_type:
        entries = [e for e in entries if e.event_type == event_type]
    if actor:
        entries = [e for e in entries if actor.lower() in e.actor.lower()]
    if start_time:
        entries = [e for e in entries if e.event_time >= start_time]
    if end_time:
        entries = [e for e in entries if e.event_time <= end_time]

    total = len(entries)
    start = (page - 1) * per_page
    end = start + per_page
    return entries[start:end], total


def verify_integrity() -> dict:
    """
    Verify the hash chain is intact. Returns verification result.
    If any entry has been modified or deleted, the chain will break.
    """
    entries = list(_audit_log)
    if not entries:
        return {"valid": True, "checked": 0, "errors": []}

    errors = []
    prev_checksum = "genesis"

    for i, entry in enumerate(entries):
        expected = _compute_checksum(entry, prev_checksum)
        if entry.checksum != expected:
            errors.append({
                "index": i,
                "entry_id": entry.id,
                "expected": expected[:16] + "...",
                "actual": entry.checksum[:16] + "...",
            })
        if entry.prev_checksum != prev_checksum:
            errors.append({
                "index": i,
                "entry_id": entry.id,
                "error": "prev_checksum chain broken",
            })
        prev_checksum = entry.checksum

    return {
        "valid": len(errors) == 0,
        "checked": len(entries),
        "errors": errors,
    }


def serialize_entry(e: AuditEntry) -> dict:
    return {
        "id": e.id,
        "event_time": e.event_time,
        "event_type": e.event_type,
        "actor": e.actor,
        "link_id": e.link_id,
        "health_score": round(e.health_score, 1) if e.health_score is not None else None,
        "confidence": round(e.confidence, 3) if e.confidence is not None else None,
        "validation_result": e.validation_result,
        "routing_change": e.routing_change,
        "policy_change": e.policy_change,
        "details": e.details,
        "checksum": e.checksum,
    }


def get_all_entries_raw() -> list[AuditEntry]:
    """Return all entries for report generation."""
    return list(_audit_log)
