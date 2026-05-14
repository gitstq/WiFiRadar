"""
Unit tests for utility functions.

Tests signal conversion, channel/frequency mapping, overlap calculation,
string formatting, file path helpers, and platform detection.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.utils import (
    PlatformInfo,
    calculate_channel_congestion,
    channel_to_frequency,
    dbm_to_bars,
    dbm_to_percentage,
    dbm_to_quality,
    detect_band,
    detect_band_from_channel,
    frequency_to_channel,
    get_best_channels,
    get_overlapping_channels,
    pad_string,
    safe_filename,
    truncate_string,
    format_table,
    ensure_dir,
    get_data_dir,
    get_history_dir,
    _display_width,
    _is_cjk_char,
)
from src.config import (
    CHANNEL_FREQ_2GHZ,
    CHANNEL_FREQ_5GHZ,
    FREQ_CHANNEL_MAP,
    Config,
    SignalThresholds,
    reset_config,
    get_config,
)


# ===========================================================================
# Signal Conversion Tests
# ===========================================================================

class TestDbmToPercentage(unittest.TestCase):
    """Tests for dbm_to_percentage conversion."""

    def test_excellent_signal(self) -> None:
        """Test -30 dBm maps to 100%."""
        self.assertEqual(dbm_to_percentage(-30), 100)

    def test_good_signal(self) -> None:
        """Test -50 dBm maps to approximately 71%."""
        result = dbm_to_percentage(-50)
        self.assertEqual(result, 71)

    def test_fair_signal(self) -> None:
        """Test -65 dBm maps to approximately 50%."""
        result = dbm_to_percentage(-65)
        self.assertEqual(result, 50)

    def test_poor_signal(self) -> None:
        """Test -80 dBm maps to approximately 29%."""
        result = dbm_to_percentage(-80)
        self.assertEqual(result, 29)

    def test_no_signal(self) -> None:
        """Test -100 dBm maps to 0%."""
        self.assertEqual(dbm_to_percentage(-100), 0)

    def test_above_range_clamped(self) -> None:
        """Test values above -30 dBm are clamped to 100%."""
        self.assertEqual(dbm_to_percentage(-20), 100)
        self.assertEqual(dbm_to_percentage(0), 100)

    def test_below_range_clamped(self) -> None:
        """Test values below -100 dBm are clamped to 0%."""
        self.assertEqual(dbm_to_percentage(-110), 0)

    def test_boundary_values(self) -> None:
        """Test exact boundary values."""
        self.assertEqual(dbm_to_percentage(-30), 100)
        self.assertEqual(dbm_to_percentage(-100), 0)

    def test_returns_int(self) -> None:
        """Test that return type is always int."""
        self.assertIsInstance(dbm_to_percentage(-55), int)
        self.assertIsInstance(dbm_to_percentage(-30), int)
        self.assertIsInstance(dbm_to_percentage(-100), int)


class TestDbmToQuality(unittest.TestCase):
    """Tests for dbm_to_quality grade assignment."""

    def test_excellent(self) -> None:
        """Test -50 dBm is Excellent."""
        self.assertEqual(dbm_to_quality(-50), "Excellent")
        self.assertEqual(dbm_to_quality(-30), "Excellent")

    def test_good(self) -> None:
        """Test -55 dBm is Good."""
        self.assertEqual(dbm_to_quality(-55), "Good")
        self.assertEqual(dbm_to_quality(-60), "Good")

    def test_fair(self) -> None:
        """Test -65 dBm is Fair."""
        self.assertEqual(dbm_to_quality(-65), "Fair")
        self.assertEqual(dbm_to_quality(-70), "Fair")

    def test_poor(self) -> None:
        """Test -75 dBm is Poor."""
        self.assertEqual(dbm_to_quality(-75), "Poor")
        self.assertEqual(dbm_to_quality(-80), "Poor")

    def test_no_signal(self) -> None:
        """Test -85 dBm is No Signal."""
        self.assertEqual(dbm_to_quality(-85), "No Signal")
        self.assertEqual(dbm_to_quality(-100), "No Signal")

    def test_boundary_values(self) -> None:
        """Test exact threshold boundaries."""
        self.assertEqual(dbm_to_quality(-50), "Excellent")
        self.assertEqual(dbm_to_quality(-51), "Good")
        self.assertEqual(dbm_to_quality(-60), "Good")
        self.assertEqual(dbm_to_quality(-61), "Fair")
        self.assertEqual(dbm_to_quality(-70), "Fair")
        self.assertEqual(dbm_to_quality(-71), "Poor")
        self.assertEqual(dbm_to_quality(-80), "Poor")
        self.assertEqual(dbm_to_quality(-81), "No Signal")


class TestDbmToBars(unittest.TestCase):
    """Tests for dbm_to_bar visual representation."""

    def test_full_bars(self) -> None:
        """Test strong signal shows all bars."""
        bars = dbm_to_bars(-30, max_bars=5)
        self.assertEqual(bars.count("\u2588"), 5)
        self.assertEqual(bars.count("\u2591"), 0)

    def test_no_bars(self) -> None:
        """Test very weak signal shows no filled bars."""
        bars = dbm_to_bars(-100, max_bars=5)
        self.assertEqual(bars.count("\u2588"), 0)
        self.assertEqual(bars.count("\u2591"), 5)

    def test_partial_bars(self) -> None:
        """Test medium signal shows partial bars."""
        bars = dbm_to_bars(-65, max_bars=5)
        filled = bars.count("\u2588")
        empty = bars.count("\u2591")
        self.assertEqual(filled + empty, 5)
        self.assertGreater(filled, 0)
        self.assertGreater(empty, 0)

    def test_custom_max_bars(self) -> None:
        """Test custom max_bars parameter."""
        bars = dbm_to_bars(-30, max_bars=3)
        self.assertEqual(len(bars), 3)

    def test_bar_length(self) -> None:
        """Test total bar length equals max_bars."""
        for max_bars in [3, 5, 8, 10]:
            bars = dbm_to_bars(-50, max_bars=max_bars)
            self.assertEqual(len(bars), max_bars)


# ===========================================================================
# Channel / Frequency Mapping Tests
# ===========================================================================

class TestChannelToFrequency(unittest.TestCase):
    """Tests for channel_to_frequency conversion."""

    def test_2ghz_channel_1(self) -> None:
        self.assertEqual(channel_to_frequency(1), 2412)

    def test_2ghz_channel_6(self) -> None:
        self.assertEqual(channel_to_frequency(6), 2437)

    def test_2ghz_channel_11(self) -> None:
        self.assertEqual(channel_to_frequency(11), 2462)

    def test_2ghz_channel_14(self) -> None:
        self.assertEqual(channel_to_frequency(14), 2484)

    def test_5ghz_channel_36(self) -> None:
        self.assertEqual(channel_to_frequency(36), 5180)

    def test_5ghz_channel_149(self) -> None:
        self.assertEqual(channel_to_frequency(149), 5745)

    def test_5ghz_channel_165(self) -> None:
        self.assertEqual(channel_to_frequency(165), 5825)

    def test_unknown_channel(self) -> None:
        self.assertIsNone(channel_to_frequency(999))

    def test_all_2ghz_channels(self) -> None:
        """Test all defined 2.4 GHz channels return valid frequencies."""
        for ch in CHANNEL_FREQ_2GHZ:
            freq = channel_to_frequency(ch)
            self.assertIsNotNone(freq)
            self.assertGreaterEqual(freq, 2400)
            self.assertLessEqual(freq, 2500)

    def test_all_5ghz_channels(self) -> None:
        """Test all defined 5 GHz channels return valid frequencies."""
        for ch in CHANNEL_FREQ_5GHZ:
            freq = channel_to_frequency(ch)
            self.assertIsNotNone(freq)
            self.assertGreaterEqual(freq, 5000)
            self.assertLessEqual(freq, 6000)


class TestFrequencyToChannel(unittest.TestCase):
    """Tests for frequency_to_channel conversion."""

    def test_2ghz_freq_2412(self) -> None:
        self.assertEqual(frequency_to_channel(2412), 1)

    def test_2ghz_freq_2437(self) -> None:
        self.assertEqual(frequency_to_channel(2437), 6)

    def test_5ghz_freq_5180(self) -> None:
        self.assertEqual(frequency_to_channel(5180), 36)

    def test_unknown_freq(self) -> None:
        self.assertIsNone(frequency_to_channel(9999))

    def test_roundtrip(self) -> None:
        """Test channel -> freq -> channel roundtrip for all channels."""
        all_channels = {**CHANNEL_FREQ_2GHZ, **CHANNEL_FREQ_5GHZ}
        for ch, freq in all_channels.items():
            self.assertEqual(frequency_to_channel(freq), ch)


class TestDetectBand(unittest.TestCase):
    """Tests for band detection from frequency."""

    def test_2ghz_low(self) -> None:
        self.assertEqual(detect_band(2412), "2.4GHz")

    def test_2ghz_high(self) -> None:
        self.assertEqual(detect_band(2484), "2.4GHz")

    def test_5ghz_low(self) -> None:
        self.assertEqual(detect_band(5180), "5GHz")

    def test_5ghz_high(self) -> None:
        self.assertEqual(detect_band(5885), "5GHz")

    def test_unknown(self) -> None:
        self.assertEqual(detect_band(9999), "Unknown")

    def test_boundary_below_2ghz(self) -> None:
        self.assertEqual(detect_band(2399), "Unknown")

    def test_boundary_above_5ghz(self) -> None:
        self.assertEqual(detect_band(6001), "Unknown")


class TestDetectBandFromChannel(unittest.TestCase):
    """Tests for band detection from channel number."""

    def test_2ghz_channels(self) -> None:
        for ch in [1, 6, 11, 14]:
            self.assertEqual(detect_band_from_channel(ch), "2.4GHz")

    def test_5ghz_channels(self) -> None:
        for ch in [36, 40, 149, 165]:
            self.assertEqual(detect_band_from_channel(ch), "5GHz")

    def test_unknown_channel(self) -> None:
        self.assertEqual(detect_band_from_channel(999), "Unknown")


# ===========================================================================
# Overlap Calculation Tests
# ===========================================================================

class TestGetOverlappingChannels(unittest.TestCase):
    """Tests for overlapping channel calculation."""

    def test_2ghz_ch6_at_20mhz(self) -> None:
        """Channel 6 at 20 MHz overlaps with channels 4-8."""
        overlapping = get_overlapping_channels(6, 20)
        self.assertIn(4, overlapping)
        self.assertIn(5, overlapping)
        self.assertIn(6, overlapping)
        self.assertIn(7, overlapping)
        self.assertIn(8, overlapping)
        self.assertNotIn(1, overlapping)
        self.assertNotIn(11, overlapping)

    def test_2ghz_ch1_boundary(self) -> None:
        """Channel 1 at 20 MHz should not go below 1."""
        overlapping = get_overlapping_channels(1, 20)
        self.assertIn(1, overlapping)
        self.assertIn(2, overlapping)
        self.assertIn(3, overlapping)
        for ch in overlapping:
            self.assertGreaterEqual(ch, 1)

    def test_2ghz_ch14_boundary(self) -> None:
        """Channel 14 at 20 MHz should not go above 14."""
        overlapping = get_overlapping_channels(14, 20)
        self.assertIn(14, overlapping)
        for ch in overlapping:
            self.assertLessEqual(ch, 14)

    def test_5ghz_no_overlap_20mhz(self) -> None:
        """5 GHz channels at 20 MHz should not overlap."""
        for ch in [36, 40, 44, 149, 165]:
            overlapping = get_overlapping_channels(ch, 20)
            self.assertEqual(overlapping, [ch])

    def test_unknown_channel(self) -> None:
        """Unknown channel returns itself only."""
        overlapping = get_overlapping_channels(999, 20)
        self.assertEqual(overlapping, [999])

    def test_sorted_result(self) -> None:
        """Result should always be sorted."""
        overlapping = get_overlapping_channels(6, 20)
        self.assertEqual(overlapping, sorted(overlapping))


# ===========================================================================
# String Formatting Tests
# ===========================================================================

class TestPadString(unittest.TestCase):
    """Tests for pad_string formatting."""

    def test_left_pad(self) -> None:
        result = pad_string("hi", 10)
        self.assertEqual(len(result), 10)
        self.assertTrue(result.startswith("hi"))

    def test_right_pad(self) -> None:
        result = pad_string("hi", 10, align="right")
        self.assertEqual(len(result), 10)
        self.assertTrue(result.endswith("hi"))

    def test_center_pad(self) -> None:
        result = pad_string("hi", 10, align="center")
        self.assertEqual(len(result), 10)

    def test_already_wide(self) -> None:
        result = pad_string("hello", 3)
        self.assertEqual(result, "hello")

    def test_empty_string(self) -> None:
        result = pad_string("", 5)
        self.assertEqual(len(result), 5)

    def test_cjk_width(self) -> None:
        """Test CJK characters are counted as double-width."""
        # Two CJK chars = 4 display columns
        result = pad_string("你好", 6)
        self.assertEqual(_display_width(result), 6)


class TestTruncateString(unittest.TestCase):
    """Tests for truncate_string."""

    def test_short_string(self) -> None:
        result = truncate_string("hi", 10)
        self.assertEqual(result, "hi")

    def test_exact_length(self) -> None:
        result = truncate_string("hello", 5)
        self.assertEqual(result, "hello")

    def test_truncated(self) -> None:
        result = truncate_string("hello world", 8)
        self.assertTrue(result.endswith("..."))
        self.assertLessEqual(_display_width(result), 8)

    def test_custom_suffix(self) -> None:
        result = truncate_string("hello world", 8, suffix="..")
        self.assertTrue(result.endswith(".."))


class TestFormatTable(unittest.TestCase):
    """Tests for format_table."""

    def test_basic_table(self) -> None:
        headers = ["Name", "Value"]
        rows = [["a", "1"], ["bb", "22"]]
        result = format_table(headers, rows)
        self.assertIn("Name", result)
        self.assertIn("Value", result)
        self.assertIn("a", result)
        self.assertIn("bb", result)

    def test_empty_table(self) -> None:
        result = format_table([], [])
        self.assertEqual(result, "")

    def test_empty_rows(self) -> None:
        result = format_table(["H1", "H2"], [])
        self.assertEqual(result, "")

    def test_single_row(self) -> None:
        result = format_table(["Col"], [["val"]])
        self.assertIn("Col", result)
        self.assertIn("val", result)

    def test_uneven_rows(self) -> None:
        """Test rows with fewer columns than headers."""
        result = format_table(["A", "B", "C"], [["1"]])
        self.assertIn("1", result)


# ===========================================================================
# File Path Helper Tests
# ===========================================================================

class TestFilePathHelpers(unittest.TestCase):
    """Tests for file path utility functions."""

    def test_ensure_dir_creates(self) -> None:
        """Test ensure_dir creates directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "sub", "dir")
            result = ensure_dir(new_dir)
            self.assertTrue(os.path.isdir(new_dir))
            self.assertEqual(str(result), new_dir)

    def test_ensure_dir_existing(self) -> None:
        """Test ensure_dir works with existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ensure_dir(tmpdir)
            self.assertTrue(os.path.isdir(tmpdir))

    def test_safe_filename_basic(self) -> None:
        self.assertEqual(safe_filename("hello"), "hello")

    def test_safe_filename_special_chars(self) -> None:
        result = safe_filename('file<>:"/\\|?*name')
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)
        self.assertNotIn(":", result)
        self.assertNotIn('"', result)
        self.assertNotIn("/", result)
        self.assertNotIn("\\", result)

    def test_safe_filename_truncation(self) -> None:
        long_name = "a" * 100
        result = safe_filename(long_name, max_length=32)
        self.assertLessEqual(len(result), 32)

    def test_safe_filename_empty(self) -> None:
        result = safe_filename("", max_length=32)
        self.assertEqual(result, "unnamed")

    def test_safe_filename_dots(self) -> None:
        result = safe_filename("...test...")
        self.assertFalse(result.startswith("."))
        self.assertFalse(result.endswith("."))


# ===========================================================================
# Platform Detection Tests
# ===========================================================================

class TestPlatformDetection(unittest.TestCase):
    """Tests for platform detection."""

    def test_platform_info_creation(self) -> None:
        """Test PlatformInfo can be instantiated."""
        info = PlatformInfo()
        self.assertIsInstance(info.system, str)
        self.assertIsNotNone(info.system)

    def test_system_detection(self) -> None:
        """Test that system is detected."""
        info = PlatformInfo()
        self.assertIn(info.system, ["linux", "darwin", "windows"])

    def test_is_linux(self) -> None:
        """Test Linux detection flag."""
        info = PlatformInfo()
        self.assertEqual(info.is_linux, info.system == "linux")

    def test_is_macos(self) -> None:
        """Test macOS detection flag."""
        info = PlatformInfo()
        self.assertEqual(info.is_macos, info.system == "darwin")

    def test_is_windows(self) -> None:
        """Test Windows detection flag."""
        info = PlatformInfo()
        self.assertEqual(info.is_windows, info.system == "windows")

    def test_scan_tool_is_string(self) -> None:
        """Test scan_tool returns a string."""
        info = PlatformInfo()
        self.assertIsInstance(info.scan_tool, str)

    def test_supports_monitor_mode_bool(self) -> None:
        """Test supports_monitor_mode returns bool."""
        info = PlatformInfo()
        self.assertIsInstance(info.supports_monitor_mode, bool)


# ===========================================================================
# CJK Character Tests
# ===========================================================================

class TestCjkDetection(unittest.TestCase):
    """Tests for CJK character width detection."""

    def test_ascii_char(self) -> None:
        self.assertFalse(_is_cjk_char("a"))

    def test_cjk_unified_ideographs(self) -> None:
        self.assertTrue(_is_cjk_char("中"))
        self.assertTrue(_is_cjk_char("日"))
        self.assertTrue(_is_cjk_char("韩"))

    def test_fullwidth_forms(self) -> None:
        self.assertTrue(_is_cjk_char("\uff01"))  # Fullwidth exclamation

    def test_display_width_ascii(self) -> None:
        self.assertEqual(_display_width("hello"), 5)

    def test_display_width_cjk(self) -> None:
        self.assertEqual(_display_width("你好"), 4)

    def test_display_width_mixed(self) -> None:
        self.assertEqual(_display_width("hi你好"), 6)


# ===========================================================================
# Configuration Tests
# ===========================================================================

class TestConfig(unittest.TestCase):
    """Tests for configuration management."""

    def setUp(self) -> None:
        """Reset config before each test."""
        reset_config()

    def test_default_config(self) -> None:
        """Test default configuration values are loaded."""
        cfg = Config()
        self.assertEqual(cfg.get("scan_timeout"), 15)
        self.assertEqual(cfg.get("no_color"), False)
        self.assertEqual(cfg.get("verbose"), False)

    def test_get_with_default(self) -> None:
        """Test get returns default for missing keys."""
        cfg = Config()
        self.assertIsNone(cfg.get("nonexistent"))
        self.assertEqual(cfg.get("nonexistent", 42), 42)

    def test_set_override(self) -> None:
        """Test runtime configuration override."""
        cfg = Config()
        cfg.set("scan_timeout", 30)
        self.assertEqual(cfg.get("scan_timeout"), 30)

    def test_all_returns_copy(self) -> None:
        """Test all() returns a copy, not the internal dict."""
        cfg = Config()
        values = cfg.all()
        values["scan_timeout"] = 999
        self.assertEqual(cfg.get("scan_timeout"), 15)

    def test_config_file_loading(self) -> None:
        """Test loading config from a JSON file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"scan_timeout": 25, "verbose": True}, f)
            f.flush()
            cfg = Config(config_path=f.name)
            self.assertEqual(cfg.get("scan_timeout"), 25)
            self.assertEqual(cfg.get("verbose"), True)
            os.unlink(f.name)

    def test_config_file_corrupted(self) -> None:
        """Test corrupted config file is silently skipped."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{invalid json")
            f.flush()
            cfg = Config(config_path=f.name)
            # Should fall back to defaults
            self.assertEqual(cfg.get("scan_timeout"), 15)
            os.unlink(f.name)

    def test_env_override(self) -> None:
        """Test environment variable override."""
        os.environ["WIFIRADAR_SCAN_TIMEOUT"] = "20"
        try:
            cfg = Config()
            self.assertEqual(cfg.get("scan_timeout"), 20)
        finally:
            del os.environ["WIFIRADAR_SCAN_TIMEOUT"]

    def test_env_override_bool(self) -> None:
        """Test boolean environment variable conversion."""
        os.environ["WIFIRADAR_VERBOSE"] = "true"
        try:
            cfg = Config()
            self.assertEqual(cfg.get("verbose"), True)
        finally:
            del os.environ["WIFIRADAR_VERBOSE"]

    def test_env_override_int(self) -> None:
        """Test integer environment variable conversion."""
        os.environ["WIFIRADAR_TOP_N"] = "5"
        try:
            cfg = Config()
            self.assertEqual(cfg.get("top_n"), 5)
        finally:
            del os.environ["WIFIRADAR_TOP_N"]

    def test_get_config_singleton(self) -> None:
        """Test get_config returns singleton."""
        cfg1 = get_config()
        cfg2 = get_config()
        self.assertIs(cfg1, cfg2)

    def test_reset_config(self) -> None:
        """Test reset_config creates new singleton."""
        cfg1 = get_config()
        reset_config()
        cfg2 = get_config()
        self.assertIsNot(cfg1, cfg2)

    def test_user_config_dir(self) -> None:
        """Test user_config_dir returns expected path."""
        cfg = Config()
        self.assertEqual(
            cfg.user_config_dir,
            Path.home() / ".wifiradar",
        )

    def test_history_dir_expanded(self) -> None:
        """Test history_dir is expanded."""
        cfg = Config()
        history = cfg.history_dir
        self.assertIsInstance(history, Path)
        # Should not contain tilde
        self.assertNotIn("~", str(history))


# ===========================================================================
# Signal Thresholds Tests
# ===========================================================================

class TestSignalThresholds(unittest.TestCase):
    """Tests for signal threshold constants."""

    def test_threshold_ordering(self) -> None:
        """Test thresholds are in correct order."""
        self.assertGreater(SignalThresholds.EXCELLENT, SignalThresholds.GOOD)
        self.assertGreater(SignalThresholds.GOOD, SignalThresholds.FAIR)
        self.assertGreater(SignalThresholds.FAIR, SignalThresholds.POOR)
        self.assertGreater(SignalThresholds.POOR, SignalThresholds.NO_SIGNAL)

    def test_thresholds_are_negative(self) -> None:
        """Test all thresholds are negative dBm values."""
        for attr in ["EXCELLENT", "GOOD", "FAIR", "POOR", "NO_SIGNAL"]:
            value = getattr(SignalThresholds, attr)
            self.assertLess(value, 0)


if __name__ == "__main__":
    unittest.main()
