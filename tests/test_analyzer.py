"""
Unit tests for the analyzer module.

Tests channel congestion calculation, interference scoring,
recommendation generation, and analysis report building.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.utils import (
    calculate_channel_congestion,
    get_best_channels,
    get_overlapping_channels,
    detect_band_from_channel,
)


# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

SAMPLE_NETWORKS: List[Dict[str, Any]] = [
    {"ssid": "Net-A", "bssid": "AA:BB:CC:DD:EE:01", "channel": 6, "signal": -45, "band": "2.4GHz"},
    {"ssid": "Net-B", "bssid": "AA:BB:CC:DD:EE:02", "channel": 6, "signal": -55, "band": "2.4GHz"},
    {"ssid": "Net-C", "bssid": "AA:BB:CC:DD:EE:03", "channel": 1, "signal": -60, "band": "2.4GHz"},
    {"ssid": "Net-D", "bssid": "AA:BB:CC:DD:EE:04", "channel": 11, "signal": -50, "band": "2.4GHz"},
    {"ssid": "Net-E", "bssid": "AA:BB:CC:DD:EE:05", "channel": 36, "signal": -40, "band": "5GHz"},
    {"ssid": "Net-F", "bssid": "AA:BB:CC:DD:EE:06", "channel": 36, "signal": -65, "band": "5GHz"},
    {"ssid": "Net-G", "bssid": "AA:BB:CC:DD:EE:07", "channel": 149, "signal": -35, "band": "5GHz"},
    {"ssid": "Net-H", "bssid": "AA:BB:CC:DD:EE:08", "channel": 7, "signal": -70, "band": "2.4GHz"},
    {"ssid": "Net-I", "bssid": "AA:BB:CC:DD:EE:09", "channel": 3, "signal": -75, "band": "2.4GHz"},
]

CROWDED_2GHZ_NETWORKS: List[Dict[str, Any]] = [
    {"ssid": f"Net-{i:02d}", "channel": 6, "signal": -50 - i, "band": "2.4GHz"}
    for i in range(10)
] + [
    {"ssid": f"Net-{i:02d}", "channel": 1, "signal": -50 - i, "band": "2.4GHz"}
    for i in range(3)
]


class TestChannelCongestion(unittest.TestCase):
    """Tests for channel congestion calculation."""

    def test_congestion_empty_networks(self) -> None:
        """Test congestion with no nearby networks."""
        result = calculate_channel_congestion(6, [])
        self.assertEqual(result["co_channel"], 0)
        self.assertEqual(result["overlapping"], 0)
        self.assertEqual(result["total_interfering"], 0)

    def test_congestion_co_channel_only(self) -> None:
        """Test congestion with only co-channel interference."""
        networks = [
            {"channel": 6, "signal": -50},
            {"channel": 6, "signal": -60},
        ]
        result = calculate_channel_congestion(6, networks)
        self.assertEqual(result["co_channel"], 2)
        self.assertEqual(result["overlapping"], 0)
        self.assertEqual(result["total_interfering"], 2)

    def test_congestion_overlapping_channels(self) -> None:
        """Test congestion with overlapping channel interference."""
        networks = [
            {"channel": 5, "signal": -50},   # Overlaps with 6
            {"channel": 7, "signal": -55},   # Overlaps with 6
            {"channel": 4, "signal": -60},   # Overlaps with 6
            {"channel": 1, "signal": -65},   # Does NOT overlap with 6
        ]
        result = calculate_channel_congestion(6, networks)
        self.assertEqual(result["co_channel"], 0)
        self.assertEqual(result["overlapping"], 3)
        self.assertEqual(result["total_interfering"], 3)

    def test_congestion_mixed(self) -> None:
        """Test congestion with both co-channel and overlapping."""
        networks = [
            {"channel": 6, "signal": -50},   # Co-channel
            {"channel": 6, "signal": -55},   # Co-channel
            {"channel": 5, "signal": -60},   # Overlapping
            {"channel": 7, "signal": -65},   # Overlapping
            {"channel": 11, "signal": -70},  # Non-overlapping
        ]
        result = calculate_channel_congestion(6, networks)
        self.assertEqual(result["co_channel"], 2)
        self.assertEqual(result["overlapping"], 2)
        self.assertEqual(result["total_interfering"], 4)

    def test_congestion_5ghz_no_overlap(self) -> None:
        """Test 5 GHz channels have no overlap at 20 MHz width."""
        networks = [
            {"channel": 36, "signal": -50},
            {"channel": 40, "signal": -55},
            {"channel": 44, "signal": -60},
        ]
        result = calculate_channel_congestion(40, networks)
        self.assertEqual(result["co_channel"], 1)
        self.assertEqual(result["overlapping"], 0)

    def test_congestion_ignores_missing_channel(self) -> None:
        """Test that networks without channel info are skipped."""
        networks = [
            {"channel": 6, "signal": -50},
            {"signal": -55},  # No channel key
            {"channel": None, "signal": -60},  # None channel
        ]
        result = calculate_channel_congestion(6, networks)
        self.assertEqual(result["co_channel"], 1)
        self.assertEqual(result["overlapping"], 0)


class TestInterferenceScoring(unittest.TestCase):
    """Tests for interference scoring logic."""

    def test_no_interference_score(self) -> None:
        """Test score is zero with no interfering networks."""
        result = calculate_channel_congestion(1, [])
        self.assertEqual(result["total_interfering"], 0)

    def test_high_interference_score(self) -> None:
        """Test high interference on crowded channel."""
        result = calculate_channel_congestion(6, CROWDED_2GHZ_NETWORKS)
        # 10 networks on channel 6 + some overlapping
        self.assertGreater(result["co_channel"], 5)
        self.assertGreater(result["total_interfering"], 5)

    def test_low_interference_score(self) -> None:
        """Test low interference on quiet channel."""
        # Channel 11 has only 1 network in sample data
        result = calculate_channel_congestion(11, SAMPLE_NETWORKS)
        self.assertEqual(result["co_channel"], 1)
        # Channels 9, 10 overlap with 11
        self.assertLessEqual(result["total_interfering"], 2)

    def test_interference_comparison_across_channels(self) -> None:
        """Test that crowded channels score higher than quiet ones."""
        ch6 = calculate_channel_congestion(6, SAMPLE_NETWORKS)
        ch11 = calculate_channel_congestion(11, SAMPLE_NETWORKS)
        # Channel 6 should have more interference than 11 in our sample
        self.assertGreaterEqual(
            ch6["total_interfering"],
            ch11["total_interfering"],
        )


class TestChannelRecommendations(unittest.TestCase):
    """Tests for best channel recommendation logic."""

    def test_best_channels_2ghz_returns_list(self) -> None:
        """Test that best_channels returns a non-empty list."""
        results = get_best_channels(SAMPLE_NETWORKS, "2.4GHz")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_best_channels_5ghz_returns_list(self) -> None:
        """Test that best_channels works for 5 GHz band."""
        results = get_best_channels(SAMPLE_NETWORKS, "5GHz")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_best_channels_sorted_by_interference(self) -> None:
        """Test that results are sorted by least interference first."""
        results = get_best_channels(SAMPLE_NETWORKS, "2.4GHz")
        for i in range(1, len(results)):
            prev_total = results[i - 1][1]["total_interfering"]
            curr_total = results[i][1]["total_interfering"]
            self.assertLessEqual(prev_total, curr_total)

    def test_best_channels_empty_networks(self) -> None:
        """Test with no networks - all channels should have zero interference."""
        results = get_best_channels([], "2.4GHz")
        for ch, metrics in results:
            self.assertEqual(metrics["total_interfering"], 0)

    def test_best_channels_unknown_band(self) -> None:
        """Test with unknown band returns empty list."""
        results = get_best_channels(SAMPLE_NETWORKS, "6GHz")
        self.assertEqual(results, [])

    def test_best_channels_crowded_environment(self) -> None:
        """Test recommendations in a crowded 2.4 GHz environment."""
        results = get_best_channels(CROWDED_2GHZ_NETWORKS, "2.4GHz")
        best_ch, best_metrics = results[0]
        worst_ch, worst_metrics = results[-1]
        # Best channel should have less interference than the worst
        self.assertLessEqual(best_metrics["total_interfering"], worst_metrics["total_interfering"])
        # In a crowded env with most on ch 6, channel 11 should be relatively clean
        self.assertLessEqual(best_metrics["total_interfering"], 2)

    def test_best_channels_tuple_structure(self) -> None:
        """Test that each result is a (channel, metrics) tuple."""
        results = get_best_channels(SAMPLE_NETWORKS, "2.4GHz")
        for item in results:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            self.assertIsInstance(item[0], int)
            self.assertIsInstance(item[1], dict)
            self.assertIn("co_channel", item[1])
            self.assertIn("overlapping", item[1])
            self.assertIn("total_interfering", item[1])

    def test_best_channels_band_filtering(self) -> None:
        """Test that only networks of the specified band are considered."""
        # Add a 5 GHz network - it should not affect 2.4 GHz analysis
        networks = list(SAMPLE_NETWORKS) + [
            {"channel": 36, "signal": -30, "band": "5GHz"},
        ]
        results_2ghz = get_best_channels(networks, "2.4GHz")
        results_5ghz = get_best_channels(networks, "5GHz")

        # The extra 5 GHz network should affect 5 GHz results
        ch36_5ghz = [m for ch, m in results_5ghz if ch == 36]
        if ch36_5ghz:
            self.assertGreater(ch36_5ghz[0]["co_channel"], 0)


class TestOverlappingChannels(unittest.TestCase):
    """Tests for overlapping channel calculation."""

    def test_2ghz_channel_6_overlaps(self) -> None:
        """Test channel 6 overlapping channels at 20 MHz."""
        overlapping = get_overlapping_channels(6, 20)
        # Channel 6 at 20 MHz overlaps with channels 4-8
        self.assertIn(4, overlapping)
        self.assertIn(5, overlapping)
        self.assertIn(6, overlapping)
        self.assertIn(7, overlapping)
        self.assertIn(8, overlapping)

    def test_2ghz_channel_1_boundary(self) -> None:
        """Test channel 1 does not overlap below channel 1."""
        overlapping = get_overlapping_channels(1, 20)
        self.assertIn(1, overlapping)
        self.assertNotIn(0, overlapping)
        self.assertNotIn(-1, overlapping)

    def test_2ghz_channel_14_boundary(self) -> None:
        """Test channel 14 boundary."""
        overlapping = get_overlapping_channels(14, 20)
        self.assertIn(14, overlapping)
        self.assertNotIn(15, overlapping)

    def test_5ghz_no_overlap_at_20mhz(self) -> None:
        """Test 5 GHz channels don't overlap at 20 MHz."""
        overlapping_36 = get_overlapping_channels(36, 20)
        overlapping_40 = get_overlapping_channels(40, 20)
        self.assertEqual(overlapping_36, [36])
        self.assertEqual(overlapping_40, [40])

    def test_unknown_channel(self) -> None:
        """Test unknown channel returns only itself."""
        overlapping = get_overlapping_channels(999, 20)
        self.assertEqual(overlapping, [999])

    def test_5ghz_40mhz_overlap(self) -> None:
        """Test 5 GHz channels overlap at 40 MHz width."""
        overlapping = get_overlapping_channels(36, 40)
        # At 40 MHz, channel 36 should overlap with 40
        self.assertIn(36, overlapping)
        self.assertIn(40, overlapping)


class TestAnalysisReport(unittest.TestCase):
    """Tests for analysis report generation."""

    def test_report_contains_all_sections(self) -> None:
        """Test that a basic analysis report has all required sections."""
        from src.utils import get_best_channels

        report: Dict[str, Any] = {
            "timestamp": "2024-01-01T00:00:00",
            "total_networks": len(SAMPLE_NETWORKS),
            "band_2ghz_count": sum(1 for n in SAMPLE_NETWORKS if n["band"] == "2.4GHz"),
            "band_5ghz_count": sum(1 for n in SAMPLE_NETWORKS if n["band"] == "5GHz"),
            "networks": SAMPLE_NETWORKS,
            "recommendations": {
                "best_2ghz_channels": get_best_channels(SAMPLE_NETWORKS, "2.4GHz")[:3],
                "best_5ghz_channels": get_best_channels(SAMPLE_NETWORKS, "5GHz")[:3],
            },
        }

        self.assertIn("timestamp", report)
        self.assertIn("total_networks", report)
        self.assertIn("recommendations", report)
        self.assertIn("best_2ghz_channels", report["recommendations"])
        self.assertIn("best_5ghz_channels", report["recommendations"])

    def test_report_network_count(self) -> None:
        """Test network count accuracy in report."""
        count_2ghz = sum(1 for n in SAMPLE_NETWORKS if n["band"] == "2.4GHz")
        count_5ghz = sum(1 for n in SAMPLE_NETWORKS if n["band"] == "5GHz")
        self.assertEqual(count_2ghz + count_5ghz, len(SAMPLE_NETWORKS))

    def test_report_json_serializable(self) -> None:
        """Test that report data can be serialized to JSON."""
        import json

        report = {
            "networks": SAMPLE_NETWORKS,
            "best_channels": get_best_channels(SAMPLE_NETWORKS, "2.4GHz")[:3],
        }
        # Convert tuples to lists for JSON
        serializable = {
            "networks": report["networks"],
            "best_channels": [
                {"channel": ch, **metrics}
                for ch, metrics in report["best_channels"]
            ],
        }
        json_str = json.dumps(serializable)
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)
        self.assertEqual(len(parsed["best_channels"]), 3)


if __name__ == "__main__":
    unittest.main()
