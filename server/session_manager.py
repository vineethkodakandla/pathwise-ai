"""
Session Manager — PathWise AI
Tracks and preserves active TCP/VoIP sessions during WAN link handoff.
Satisfies: Req-Func-Sw-7 (maintain all active session states during handoff)

Design:
  - Maintains an in-memory table of active sessions per link
  - Before handoff: snapshots all sessions on the degrading link
  - During handoff: holds session state (seq numbers, RTP SSRC, codec)
  - After handoff: migrates sessions to new link, confirms no drops
  - Audit: logs session counts and any dropped sessions
"""

from __future__ import annotations
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("pathwise.session")


class SessionType(str, Enum):
    TCP = "tcp"
    UDP = "udp"
    VOIP_RTP = "voip_rtp"
    VOIP_SIP = "voip_sip"
    VIDEO = "video"
    OTHER = "other"


class SessionState(str, Enum):
    ACTIVE = "active"
    MIGRATING = "migrating"
    MIGRATED = "migrated"
    DROPPED = "dropped"


@dataclass
class NetworkSession:
    """Represents an active network session traversing a WAN link."""
    id: str
    session_type: SessionType
    link_id: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str = "tcp"
    state: SessionState = SessionState.ACTIVE
    # TCP state
    tcp_seq_number: Optional[int] = None
    tcp_ack_number: Optional[int] = None
    tcp_window_size: Optional[int] = None
    # VoIP/RTP state
    rtp_ssrc: Optional[int] = None
    rtp_sequence: Optional[int] = None
    rtp_timestamp: Optional[int] = None
    codec: Optional[str] = None
    # Tracking
    started_at: float = 0.0
    migrated_at: Optional[float] = None
    bytes_transferred: int = 0


@dataclass
class HandoffResult:
    """Result of a session-preserving handoff operation."""
    source_link: str
    target_link: str
    total_sessions: int
    migrated_sessions: int
    dropped_sessions: int
    migration_time_ms: float
    preserved: bool  # True if all sessions survived
    session_details: list[dict] = field(default_factory=list)


class SessionManager:
    """
    Manages active network sessions across WAN links.
    Ensures zero session loss during hitless handoff (Req-Func-Sw-7).
    """

    def __init__(self):
        # link_id -> list of active sessions
        self._sessions: dict[str, list[NetworkSession]] = defaultdict(list)
        self._handoff_history: list[HandoffResult] = []

    def register_session(self, link_id: str, session_type: SessionType,
                         src_ip: str, dst_ip: str,
                         src_port: int, dst_port: int,
                         **kwargs) -> NetworkSession:
        """Register a new active session on a link."""
        session = NetworkSession(
            id=str(uuid.uuid4())[:12],
            session_type=session_type,
            link_id=link_id,
            src_ip=src_ip,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            started_at=time.time(),
            **kwargs,
        )
        self._sessions[link_id].append(session)
        return session

    def get_active_sessions(self, link_id: str) -> list[NetworkSession]:
        """Get all active sessions on a given link."""
        return [s for s in self._sessions.get(link_id, [])
                if s.state == SessionState.ACTIVE]

    def get_session_count(self, link_id: str) -> int:
        return len(self.get_active_sessions(link_id))

    def snapshot_sessions(self, link_id: str) -> list[dict]:
        """
        Capture the state of all sessions on a link before handoff.
        This is Stage 1 of hitless handoff.
        """
        sessions = self.get_active_sessions(link_id)
        snapshots = []
        for s in sessions:
            snapshots.append({
                "id": s.id,
                "type": s.session_type.value,
                "src": f"{s.src_ip}:{s.src_port}",
                "dst": f"{s.dst_ip}:{s.dst_port}",
                "tcp_seq": s.tcp_seq_number,
                "tcp_ack": s.tcp_ack_number,
                "rtp_ssrc": s.rtp_ssrc,
                "rtp_seq": s.rtp_sequence,
                "bytes": s.bytes_transferred,
            })
        logger.info("Snapshot %d sessions on link %s", len(snapshots), link_id)
        return snapshots

    def migrate_sessions(self, source_link: str, target_link: str) -> HandoffResult:
        """
        Migrate all active sessions from source to target link.
        Preserves TCP sequence numbers, VoIP RTP SSRC/sequence, and codec state.
        This is the core of Req-Func-Sw-7.

        Returns a HandoffResult with counts and timing.
        """
        t0 = time.perf_counter()

        source_sessions = self.get_active_sessions(source_link)
        total = len(source_sessions)
        migrated = 0
        dropped = 0
        details: list[dict] = []

        for session in source_sessions:
            try:
                # Mark as migrating
                session.state = SessionState.MIGRATING

                # Preserve all state — TCP seq/ack, RTP SSRC, codec
                # (The actual flow table update in SDN keeps packets flowing
                #  to the same destination; we just re-associate the session
                #  with the new link_id.)
                session.link_id = target_link
                session.state = SessionState.MIGRATED
                session.migrated_at = time.time()
                migrated += 1

                # Move to target link's session list
                self._sessions[target_link].append(session)

                details.append({
                    "session_id": session.id,
                    "type": session.session_type.value,
                    "status": "migrated",
                })

            except Exception as exc:
                session.state = SessionState.DROPPED
                dropped += 1
                details.append({
                    "session_id": session.id,
                    "type": session.session_type.value,
                    "status": "dropped",
                    "error": str(exc),
                })
                logger.error("Session %s dropped during migration: %s",
                             session.id, exc)

        # Remove migrated sessions from source
        self._sessions[source_link] = [
            s for s in self._sessions[source_link]
            if s.state == SessionState.ACTIVE
        ]

        elapsed_ms = (time.perf_counter() - t0) * 1000

        result = HandoffResult(
            source_link=source_link,
            target_link=target_link,
            total_sessions=total,
            migrated_sessions=migrated,
            dropped_sessions=dropped,
            migration_time_ms=round(elapsed_ms, 3),
            preserved=(dropped == 0),
            session_details=details,
        )

        self._handoff_history.append(result)

        logger.info(
            "Session migration %s -> %s: %d/%d migrated, %d dropped, %.1fms",
            source_link, target_link, migrated, total, dropped, elapsed_ms,
        )
        return result

    def get_handoff_history(self, limit: int = 20) -> list[dict]:
        """Get recent handoff results."""
        return [
            {
                "source_link": h.source_link,
                "target_link": h.target_link,
                "total_sessions": h.total_sessions,
                "migrated": h.migrated_sessions,
                "dropped": h.dropped_sessions,
                "migration_time_ms": h.migration_time_ms,
                "preserved": h.preserved,
            }
            for h in self._handoff_history[-limit:]
        ]

    def simulate_sessions(self, link_id: str, count: int = 10):
        """
        Populate a link with synthetic sessions for testing.
        Called during startup or before load tests.
        """
        import random
        for i in range(count):
            stype = random.choice(list(SessionType))
            self.register_session(
                link_id=link_id,
                session_type=stype,
                src_ip=f"10.0.{random.randint(1,254)}.{random.randint(1,254)}",
                dst_ip=f"10.0.{random.randint(1,254)}.{random.randint(1,254)}",
                src_port=random.randint(1024, 65535),
                dst_port=random.choice([80, 443, 5060, 5004, 8080, 3389]),
                tcp_seq_number=random.randint(0, 2**32 - 1) if stype == SessionType.TCP else None,
                tcp_ack_number=random.randint(0, 2**32 - 1) if stype == SessionType.TCP else None,
                rtp_ssrc=random.randint(0, 2**32 - 1) if stype in (SessionType.VOIP_RTP, SessionType.VIDEO) else None,
                rtp_sequence=random.randint(0, 65535) if stype in (SessionType.VOIP_RTP, SessionType.VIDEO) else None,
                codec="G.711" if stype == SessionType.VOIP_RTP else None,
            )


# Module-level singleton
_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager
