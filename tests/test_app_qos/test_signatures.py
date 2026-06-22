"""Tests for server.app_qos.signatures — app catalog and quality prediction."""

import pytest
from server.app_qos.signatures import (
    APP_SIGNATURES,
    PRIORITY_CLASSES,
    get_app,
    get_all_app_ids,
    predict_quality,
)

EXPECTED_APP_IDS = [
    "zoom", "teams", "google_meet", "youtube", "netflix", "twitch",
    "disney_plus", "discord", "spotify", "google_chrome", "onedrive", "steam",
]


class TestAppCatalog:
    def test_all_12_apps_present(self):
        for app_id in EXPECTED_APP_IDS:
            assert app_id in APP_SIGNATURES, f"Missing app: {app_id}"

    def test_total_count(self):
        assert len(APP_SIGNATURES) == 12

    def test_get_app_returns_signature(self):
        sig = get_app("zoom")
        assert sig is not None
        assert sig.display_name == "Zoom"

    def test_get_app_unknown_returns_none(self):
        assert get_app("nonexistent_app") is None

    def test_get_all_app_ids_sorted(self):
        ids = get_all_app_ids()
        assert ids == sorted(ids)
        assert len(ids) == 12


class TestYouTubeTiers:
    def test_youtube_has_8_quality_tiers(self):
        sig = get_app("youtube")
        assert sig is not None
        assert len(sig.quality_tiers) == 8

    def test_youtube_tier_labels(self):
        sig = get_app("youtube")
        labels = [t.label for t in sig.quality_tiers]
        assert "144p" in labels
        assert "1080p" in labels
        assert "4K" in labels


class TestZoomTiers:
    def test_zoom_has_tiers(self):
        sig = get_app("zoom")
        assert sig is not None
        assert len(sig.quality_tiers) >= 3

    def test_zoom_excellent_tier_exists(self):
        sig = get_app("zoom")
        labels = [t.label for t in sig.quality_tiers]
        assert "Excellent" in labels


class TestPriorityClasses:
    def test_all_classes_defined(self):
        for cls in ["CRITICAL", "HIGH", "NORMAL", "LOW", "BLOCKED"]:
            assert cls in PRIORITY_CLASSES

    def test_critical_has_highest_bandwidth(self):
        assert PRIORITY_CLASSES["CRITICAL"]["bandwidth_pct"] > PRIORITY_CLASSES["HIGH"]["bandwidth_pct"]

    def test_blocked_has_zero_bandwidth(self):
        assert PRIORITY_CLASSES["BLOCKED"]["bandwidth_pct"] == 0.0


class TestQualityPrediction:
    def test_youtube_144p_low_bandwidth(self):
        result = predict_quality("youtube", 0.2)
        assert result is not None
        assert result["label"] == "144p"
        assert result["score"] == 5

    def test_youtube_1080p(self):
        result = predict_quality("youtube", 7.0)
        assert result is not None
        assert result["label"] == "1080p"
        assert result["score"] == 80

    def test_youtube_4k(self):
        result = predict_quality("youtube", 25.0)
        assert result is not None
        assert result["label"] == "4K"
        assert result["score"] == 100

    def test_unknown_app_returns_none(self):
        result = predict_quality("nonexistent", 10.0)
        assert result is None

    def test_zero_bandwidth(self):
        result = predict_quality("zoom", 0.0)
        assert result is not None
        assert result["score"] == 0 or "Below" in result["label"]
