"""
Application signatures and quality-tier definitions for App Priority Switch.

Each application has:
  - network fingerprint (ports, CIDRs, process names)
  - quality tiers mapping bandwidth to perceived quality
  - default priority class
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class QualityTier:
    """Maps a bandwidth range to a human-readable quality label."""
    label: str                # e.g. "1080p", "Excellent"
    min_mbps: float           # minimum bandwidth for this tier
    max_mbps: float           # upper boundary (inclusive)
    score: int                # 0-100 quality score at this tier


@dataclass
class AppSignature:
    """Full signature for a recognised application."""
    app_id: str
    display_name: str
    category: str             # "video_conferencing", "streaming", "gaming", etc.
    icon: str                 # emoji shorthand
    ports: List[int] = field(default_factory=list)
    udp_ports: List[int] = field(default_factory=list)
    cidrs: List[str] = field(default_factory=list)
    process_names: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    quality_tiers: List[QualityTier] = field(default_factory=list)
    default_priority: str = "NORMAL"   # HIGH / NORMAL / LOW / BLOCKED
    base_bandwidth_mbps: float = 5.0   # typical bandwidth need


# ── Quality tier presets ──────────────────────────────────────────

_VIDEO_CONF_TIERS = [
    QualityTier("Audio Only",   0.1,  0.5,  20),
    QualityTier("Low (360p)",   0.5,  1.5,  40),
    QualityTier("Medium (720p)",1.5,  3.0,  60),
    QualityTier("HD (1080p)",   3.0,  5.0,  80),
    QualityTier("Excellent",    5.0, 50.0, 100),
]

_STREAMING_TIERS = [
    QualityTier("144p",   0.1,  0.3,   5),
    QualityTier("240p",   0.3,  0.7,  15),
    QualityTier("360p",   0.7,  1.5,  30),
    QualityTier("480p",   1.5,  3.0,  45),
    QualityTier("720p",   3.0,  5.0,  60),
    QualityTier("1080p",  5.0, 10.0,  80),
    QualityTier("1440p", 10.0, 20.0,  90),
    QualityTier("4K",    20.0, 50.0, 100),
]

_AUDIO_TIERS = [
    QualityTier("Low (96kbps)",    0.05, 0.15, 30),
    QualityTier("Normal (160kbps)",0.15, 0.35, 60),
    QualityTier("High (320kbps)",  0.35, 1.0,  85),
    QualityTier("Excellent",       1.0,  5.0, 100),
]

_BROWSER_TIERS = [
    QualityTier("Slow",     0.5,  2.0,  30),
    QualityTier("Normal",   2.0,  5.0,  60),
    QualityTier("Fast",     5.0, 20.0,  85),
    QualityTier("Blazing", 20.0, 100.0,100),
]

_CLOUD_STORAGE_TIERS = [
    QualityTier("Trickle",  0.1,  1.0,  20),
    QualityTier("Normal",   1.0,  5.0,  50),
    QualityTier("Fast",     5.0, 20.0,  80),
    QualityTier("Unlimited",20.0,100.0,100),
]

_GAMING_TIERS = [
    QualityTier("Unplayable", 0.1,  1.0,  10),
    QualityTier("Low",        1.0,  3.0,  30),
    QualityTier("Medium",     3.0, 10.0,  60),
    QualityTier("High",      10.0, 25.0,  80),
    QualityTier("Ultra",     25.0, 75.0, 100),
]


# ── App Signatures ────────────────────────────────────────────────

APP_SIGNATURES: Dict[str, AppSignature] = {
    "zoom": AppSignature(
        app_id="zoom",
        display_name="Zoom",
        category="video_conferencing",
        icon="V",
        ports=[8801, 8802, 8443],
        udp_ports=[8801, 8802, 3478, 3479],
        cidrs=["3.7.35.0/24", "3.21.137.0/24", "3.22.11.0/24",
               "3.23.93.0/24", "3.25.41.0/24", "3.25.42.0/24",
               "3.25.49.0/24", "8.5.128.0/18", "13.52.6.0/24"],
        process_names=["zoom", "zoom.exe", "Zoom.exe", "CptHost.exe"],
        domains=["*.zoom.us", "*.zoomgov.com"],
        quality_tiers=_VIDEO_CONF_TIERS,
        default_priority="HIGH",
        base_bandwidth_mbps=5.0,
    ),
    "teams": AppSignature(
        app_id="teams",
        display_name="Microsoft Teams",
        category="video_conferencing",
        icon="T",
        ports=[443, 3478, 3479, 3480, 3481],
        udp_ports=[3478, 3479, 3480, 3481, 50000, 50001, 50002,
                   50003, 50004, 50005, 50006, 50007, 50008, 50009,
                   50010, 50011, 50012, 50013, 50014, 50015, 50016,
                   50017, 50018, 50019, 50020, 50021, 50022, 50023,
                   50024, 50025, 50026, 50027, 50028, 50029, 50030,
                   50031, 50032, 50033, 50034, 50035, 50036, 50037,
                   50038, 50039, 50040, 50041, 50042, 50043, 50044,
                   50045, 50046, 50047, 50048, 50049, 50050, 50051,
                   50052, 50053, 50054, 50055, 50056, 50057, 50058,
                   50059],
        cidrs=["13.107.64.0/18", "52.112.0.0/14", "52.120.0.0/14"],
        process_names=["Teams", "Teams.exe", "ms-teams.exe"],
        domains=["*.teams.microsoft.com", "*.skype.com"],
        quality_tiers=_VIDEO_CONF_TIERS,
        default_priority="HIGH",
        base_bandwidth_mbps=5.0,
    ),
    "google_meet": AppSignature(
        app_id="google_meet",
        display_name="Google Meet",
        category="video_conferencing",
        icon="W",
        ports=[443, 19302, 19303, 19304, 19305, 19306, 19307, 19308, 19309],
        udp_ports=[19302, 19303, 19304, 19305, 19306, 19307, 19308, 19309,
                   3478],
        cidrs=["74.125.250.0/24", "142.250.0.0/15"],
        process_names=["chrome", "chrome.exe", "firefox", "firefox.exe"],
        domains=["meet.google.com", "*.meet.google.com"],
        quality_tiers=_VIDEO_CONF_TIERS,
        default_priority="HIGH",
        base_bandwidth_mbps=5.0,
    ),
    "youtube": AppSignature(
        app_id="youtube",
        display_name="YouTube",
        category="streaming",
        icon="P",
        ports=[443, 80],
        udp_ports=[443],
        cidrs=["208.65.152.0/22", "208.117.224.0/19", "209.85.128.0/17",
               "216.58.192.0/19", "216.239.32.0/19", "172.217.0.0/16"],
        process_names=["chrome", "chrome.exe", "firefox", "firefox.exe",
                       "msedge", "msedge.exe"],
        domains=["*.youtube.com", "*.googlevideo.com", "*.ytimg.com"],
        quality_tiers=_STREAMING_TIERS,
        default_priority="NORMAL",
        base_bandwidth_mbps=8.0,
    ),
    "netflix": AppSignature(
        app_id="netflix",
        display_name="Netflix",
        category="streaming",
        icon="F",
        ports=[443, 80],
        udp_ports=[],
        cidrs=["23.246.0.0/18", "37.77.184.0/21", "45.57.0.0/17",
               "64.120.128.0/17", "66.197.128.0/17", "69.53.224.0/19",
               "108.175.32.0/20", "185.2.220.0/22", "185.9.188.0/22",
               "192.173.64.0/18", "198.38.96.0/19", "198.45.48.0/20"],
        process_names=["netflix", "Netflix.exe"],
        domains=["*.netflix.com", "*.nflxvideo.net"],
        quality_tiers=_STREAMING_TIERS,
        default_priority="NORMAL",
        base_bandwidth_mbps=8.0,
    ),
    "twitch": AppSignature(
        app_id="twitch",
        display_name="Twitch",
        category="streaming",
        icon="Tw",
        ports=[443, 80, 1935],
        udp_ports=[],
        cidrs=["52.223.192.0/18", "99.181.64.0/18", "185.42.204.0/22"],
        process_names=["chrome", "chrome.exe", "firefox", "firefox.exe"],
        domains=["*.twitch.tv", "*.jtvnw.net", "*.ttvnw.net"],
        quality_tiers=_STREAMING_TIERS,
        default_priority="NORMAL",
        base_bandwidth_mbps=6.0,
    ),
    "disney_plus": AppSignature(
        app_id="disney_plus",
        display_name="Disney+",
        category="streaming",
        icon="D",
        ports=[443, 80],
        udp_ports=[],
        cidrs=["34.195.0.0/16", "54.0.0.0/8"],
        process_names=["DisneyPlus", "DisneyPlus.exe"],
        domains=["*.disneyplus.com", "*.disney-plus.net", "*.bamgrid.com",
                 "*.dssott.com"],
        quality_tiers=_STREAMING_TIERS,
        default_priority="NORMAL",
        base_bandwidth_mbps=8.0,
    ),
    "discord": AppSignature(
        app_id="discord",
        display_name="Discord",
        category="communication",
        icon="G",
        ports=[443, 80],
        udp_ports=[50000, 50001, 50002, 50003, 50004, 50005, 50006, 50007,
                   50008, 50009, 50010, 50011, 50012, 50013, 50014, 50015,
                   50016, 50017, 50018, 50019, 50020],
        cidrs=["162.159.128.0/17", "66.22.196.0/22"],
        process_names=["Discord", "Discord.exe", "discord"],
        domains=["*.discord.com", "*.discord.gg", "*.discordapp.com"],
        quality_tiers=_VIDEO_CONF_TIERS,
        default_priority="NORMAL",
        base_bandwidth_mbps=3.0,
    ),
    "spotify": AppSignature(
        app_id="spotify",
        display_name="Spotify",
        category="audio_streaming",
        icon="S",
        ports=[443, 80, 4070],
        udp_ports=[57621],
        cidrs=["35.186.224.0/20", "104.154.0.0/15"],
        process_names=["Spotify", "Spotify.exe", "spotify"],
        domains=["*.spotify.com", "*.spotifycdn.com", "*.scdn.co"],
        quality_tiers=_AUDIO_TIERS,
        default_priority="NORMAL",
        base_bandwidth_mbps=0.5,
    ),
    "google_chrome": AppSignature(
        app_id="google_chrome",
        display_name="Google Chrome (General)",
        category="browser",
        icon="W",
        ports=[443, 80, 8080],
        udp_ports=[443],
        cidrs=[],
        process_names=["chrome", "chrome.exe", "Google Chrome"],
        domains=["*"],
        quality_tiers=_BROWSER_TIERS,
        default_priority="NORMAL",
        base_bandwidth_mbps=10.0,
    ),
    "onedrive": AppSignature(
        app_id="onedrive",
        display_name="OneDrive",
        category="cloud_storage",
        icon="C",
        ports=[443, 80],
        udp_ports=[],
        cidrs=["13.107.136.0/22", "13.107.140.0/22", "52.109.0.0/16"],
        process_names=["OneDrive", "OneDrive.exe", "onedrive"],
        domains=["*.onedrive.live.com", "*.sharepoint.com",
                 "*.storage.live.com"],
        quality_tiers=_CLOUD_STORAGE_TIERS,
        default_priority="NORMAL",
        base_bandwidth_mbps=5.0,
    ),
    "steam": AppSignature(
        app_id="steam",
        display_name="Steam",
        category="gaming",
        icon="G",
        ports=[443, 80, 27015, 27016, 27017, 27018, 27019, 27020, 27036,
               27037],
        udp_ports=[27015, 27016, 27017, 27018, 27019, 27020, 4380, 27000,
                   27001, 27002, 27003, 27004, 27005, 27006, 27007, 27008,
                   27009, 27010, 27011, 27012, 27013, 27014, 27015],
        cidrs=["103.10.124.0/23", "146.66.152.0/22", "155.133.224.0/20",
               "162.254.192.0/21", "185.25.182.0/23", "190.217.32.0/22",
               "205.196.6.0/24"],
        process_names=["steam", "steam.exe", "Steam.exe", "steamwebhelper",
                       "steamwebhelper.exe"],
        domains=["*.steampowered.com", "*.steamcommunity.com",
                 "*.steamstatic.com", "*.steamcontent.com"],
        quality_tiers=_GAMING_TIERS,
        default_priority="LOW",
        base_bandwidth_mbps=15.0,
    ),
}


# ── Priority classes ──────────────────────────────────────────────

PRIORITY_CLASSES: Dict[str, dict] = {
    "CRITICAL": {
        "label": "Critical / Real-time",
        "bandwidth_pct": 0.90,
        "description": "Near-full bandwidth, minimal latency. For surgery, trading, etc.",
    },
    "HIGH": {
        "label": "High Priority",
        "bandwidth_pct": 0.60,
        "description": "Majority bandwidth share. Video calls, live collaboration.",
    },
    "NORMAL": {
        "label": "Normal",
        "bandwidth_pct": 0.30,
        "description": "Fair share. General browsing, email.",
    },
    "LOW": {
        "label": "Low Priority",
        "bandwidth_pct": 0.003,  # 0.3% = 300 Kbps on 100 Mbps → forces YouTube to 144p
        "description": "Minimal bandwidth. Background downloads, updates.",
    },
    "BLOCKED": {
        "label": "Blocked",
        "bandwidth_pct": 0.0,
        "description": "Zero bandwidth allocated. Traffic dropped.",
    },
}


# ── Helpers ───────────────────────────────────────────────────────

def get_app(app_id: str) -> Optional[AppSignature]:
    """Return the signature for *app_id*, or None."""
    return APP_SIGNATURES.get(app_id)


def get_all_app_ids() -> List[str]:
    """Return a sorted list of every known app_id."""
    return sorted(APP_SIGNATURES.keys())


def predict_quality(app_id: str, allocated_mbps: float) -> Optional[dict]:
    """
    Given an app and an allocated bandwidth, return the predicted quality tier.

    Returns dict with keys: label, score, min_mbps, max_mbps, allocated_mbps
    or None if the app is unknown.
    """
    sig = APP_SIGNATURES.get(app_id)
    if sig is None:
        return None

    tiers = sig.quality_tiers
    if not tiers:
        return {"label": "Unknown", "score": 50, "min_mbps": 0,
                "max_mbps": 0, "allocated_mbps": allocated_mbps}

    # Find the highest tier whose min_mbps is satisfied
    best: Optional[QualityTier] = None
    for tier in tiers:
        if allocated_mbps >= tier.min_mbps:
            if best is None or tier.min_mbps > best.min_mbps:
                best = tier

    if best is None:
        # Below the lowest tier
        worst = min(tiers, key=lambda t: t.min_mbps)
        ratio = max(0.0, allocated_mbps / worst.min_mbps) if worst.min_mbps else 0
        return {
            "label": f"Below {worst.label}",
            "score": max(0, int(worst.score * ratio)),
            "min_mbps": 0,
            "max_mbps": worst.min_mbps,
            "allocated_mbps": round(allocated_mbps, 2),
        }

    return {
        "label": best.label,
        "score": best.score,
        "min_mbps": best.min_mbps,
        "max_mbps": best.max_mbps,
        "allocated_mbps": round(allocated_mbps, 2),
    }
