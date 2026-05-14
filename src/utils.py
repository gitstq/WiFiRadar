"""
WiFiRadar Utility Functions.

Provides signal conversion, channel/frequency mapping, overlap calculation,
formatting helpers, and platform detection utilities.

All functions are pure (no side effects) unless otherwise noted, making them
easy to test and compose.
"""

from __future__ import annotations

import math
import os
import platform
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from src.config import (
    CHANNEL_FREQ_2GHZ,
    CHANNEL_FREQ_5GHZ,
    FREQ_CHANNEL_MAP,
    NON_OVERLAPPING_2GHZ,
    NON_OVERLAPPING_5GHZ,
    SignalThresholds,
)


# ---------------------------------------------------------------------------
# Signal Conversion
# ---------------------------------------------------------------------------

def dbm_to_percentage(dbm: int) -> int:
    """Convert a signal strength in dBm to a percentage (0-100).

    The conversion uses a linear mapping between the practical range
    of -100 dBm (0%) and -30 dBm (100%). Values outside this range
    are clamped.

    Args:
        dbm: Signal strength in dBm (typically -100 to -20).

    Returns:
        Signal quality as an integer percentage (0 to 100).

    Examples:
        >>> dbm_to_percentage(-30)
        100
        >>> dbm_to_percentage(-50)
        70
        >>> dbm_to_percentage(-100)
        0
    """
    if dbm >= -30:
        return 100
    if dbm <= -100:
        return 0
    # Linear interpolation: -100 dBm -> 0%, -30 dBm -> 100%
    return int(round((dbm + 100) * 100 / 70))


def dbm_to_quality(dbm: int) -> str:
    """Convert a signal strength in dBm to a human-readable quality grade.

    Quality grades are based on standard Wi-Fi signal thresholds:
        - Excellent: >= -50 dBm
        - Good:      >= -60 dBm
        - Fair:      >= -70 dBm
        - Poor:      >= -80 dBm
        - No Signal: <  -80 dBm

    Args:
        dbm: Signal strength in dBm.

    Returns:
        Quality grade string: 'Excellent', 'Good', 'Fair', 'Poor', or 'No Signal'.

    Examples:
        >>> dbm_to_quality(-45)
        'Excellent'
        >>> dbm_to_quality(-55)
        'Good'
        >>> dbm_to_quality(-75)
        'Poor'
    """
    if dbm >= SignalThresholds.EXCELLENT:
        return "Excellent"
    elif dbm >= SignalThresholds.GOOD:
        return "Good"
    elif dbm >= SignalThresholds.FAIR:
        return "Fair"
    elif dbm >= SignalThresholds.POOR:
        return "Poor"
    else:
        return "No Signal"


def dbm_to_bars(dbm: int, max_bars: int = 5) -> str:
    """Convert a signal strength in dBm to a visual bar representation.

    Args:
        dbm: Signal strength in dBm.
        max_bars: Maximum number of bars to display.

    Returns:
        String of filled/empty bar characters, e.g. "████░".
    """
    pct = dbm_to_percentage(dbm)
    filled = math.ceil(pct / 100 * max_bars)
    filled = max(0, min(filled, max_bars))
    return "\u2588" * filled + "\u2591" * (max_bars - filled)


# ---------------------------------------------------------------------------
# Channel / Frequency Mapping
# ---------------------------------------------------------------------------

def channel_to_frequency(channel: int) -> Optional[int]:
    """Convert a Wi-Fi channel number to its center frequency in MHz.

    Supports both 2.4 GHz and 5 GHz bands.

    Args:
        channel: Wi-Fi channel number.

    Returns:
        Center frequency in MHz, or None if the channel is not recognized.

    Examples:
        >>> channel_to_frequency(6)
        2437
        >>> channel_to_frequency(36)
        5180
        >>> channel_to_frequency(999)
        None
    """
    if channel in CHANNEL_FREQ_2GHZ:
        return CHANNEL_FREQ_2GHZ[channel]
    if channel in CHANNEL_FREQ_5GHZ:
        return CHANNEL_FREQ_5GHZ[channel]
    return None


def frequency_to_channel(freq: int) -> Optional[int]:
    """Convert a center frequency in MHz to its Wi-Fi channel number.

    Args:
        freq: Center frequency in MHz.

    Returns:
        Channel number, or None if the frequency is not recognized.

    Examples:
        >>> frequency_to_channel(2437)
        6
        >>> frequency_to_channel(5180)
        36
        >>> frequency_to_channel(9999)
        None
    """
    return FREQ_CHANNEL_MAP.get(freq)


def detect_band(freq: int) -> str:
    """Detect the Wi-Fi band from a frequency.

    Args:
        freq: Frequency in MHz.

    Returns:
        Band string: '2.4GHz', '5GHz', or 'Unknown'.

    Examples:
        >>> detect_band(2437)
        '2.4GHz'
        >>> detect_band(5180)
        '5GHz'
        >>> detect_band(9999)
        'Unknown'
    """
    if 2400 <= freq <= 2500:
        return "2.4GHz"
    elif 5000 <= freq <= 6000:
        return "5GHz"
    return "Unknown"


def detect_band_from_channel(channel: int) -> str:
    """Detect the Wi-Fi band from a channel number.

    Args:
        channel: Wi-Fi channel number.

    Returns:
        Band string: '2.4GHz', '5GHz', or 'Unknown'.
    """
    if channel in CHANNEL_FREQ_2GHZ:
        return "2.4GHz"
    elif channel in CHANNEL_FREQ_5GHZ:
        return "5GHz"
    return "Unknown"


# ---------------------------------------------------------------------------
# Channel Overlap Calculation
# ---------------------------------------------------------------------------

def get_overlapping_channels(channel: int, channel_width: int = 20) -> List[int]:
    """Get all channels that overlap with the given channel.

    For 2.4 GHz, channels are 5 MHz apart with a typical 20 MHz channel width,
    meaning each channel overlaps with 4 adjacent channels on each side.

    For 5 GHz, most channels are spaced 20 MHz apart, so there is typically
    no overlap between adjacent channels at 20 MHz width.

    Args:
        channel: The reference channel number.
        channel_width: Channel width in MHz (default 20).

    Returns:
        Sorted list of channel numbers that overlap with the given channel.
    """
    freq = channel_to_frequency(channel)
    if freq is None:
        return [channel]

    band = detect_band(freq)

    if band == "2.4GHz":
        # 2.4 GHz channels are 5 MHz apart
        # A 20 MHz wide channel covers 4 adjacent channels on each side
        half_width_channels = channel_width // 5
        start_ch = max(1, channel - half_width_channels)
        end_ch = min(14, channel + half_width_channels)
        return list(range(start_ch, end_ch + 1))
    else:
        # 5 GHz channels are typically 20 MHz apart
        # No overlap at 20 MHz width; wider channels would overlap
        if channel_width <= 20:
            return [channel]
        # For wider channels (40, 80, 160 MHz), calculate overlap
        half_width_mhz = channel_width // 2
        low_freq = freq - half_width_mhz
        high_freq = freq + half_width_mhz
        overlapping = []
        for ch, ch_freq in CHANNEL_FREQ_5GHZ.items():
            ch_half = 10  # 20 MHz channel, half = 10 MHz
            if (ch_freq - ch_half < high_freq) and (ch_freq + ch_half > low_freq):
                overlapping.append(ch)
        return sorted(overlapping)


def calculate_channel_congestion(
    channel: int,
    nearby_networks: List[Dict],
    channel_width: int = 20,
) -> Dict[str, int]:
    """Calculate congestion metrics for a specific channel.

    Args:
        channel: The channel to analyze.
        nearby_networks: List of network dicts, each containing at least
                         a 'channel' key.
        channel_width: Channel width in MHz (default 20).

    Returns:
        Dictionary with congestion metrics:
            - 'co_channel': Networks on the same channel
            - 'overlapping': Networks on overlapping channels
            - 'total_interfering': Total interfering networks
    """
    overlapping_chs = set(get_overlapping_channels(channel, channel_width))
    overlapping_chs.discard(channel)  # Exclude the channel itself

    co_channel = 0
    overlapping = 0

    for net in nearby_networks:
        net_ch = net.get("channel")
        if net_ch is None:
            continue
        if net_ch == channel:
            co_channel += 1
        elif net_ch in overlapping_chs:
            overlapping += 1

    return {
        "co_channel": co_channel,
        "overlapping": overlapping,
        "total_interfering": co_channel + overlapping,
    }


def get_best_channels(
    networks: List[Dict],
    band: str = "2.4GHz",
    channel_width: int = 20,
) -> List[Tuple[int, Dict[str, int]]]:
    """Recommend the best channels with the least interference.

    Args:
        networks: List of network dicts with 'channel' and 'frequency' keys.
        band: Which band to analyze ('2.4GHz' or '5GHz').
        channel_width: Channel width in MHz.

    Returns:
        List of (channel, congestion_metrics) tuples, sorted by least
        interference first.
    """
    if band == "2.4GHz":
        candidates = list(CHANNEL_FREQ_2GHZ.keys())
    elif band == "5GHz":
        candidates = list(CHANNEL_FREQ_5GHZ.keys())
    else:
        return []

    # Filter networks by band
    band_networks = [
        n for n in networks
        if detect_band_from_channel(n.get("channel", 0)) == band
    ]

    results = []
    for ch in candidates:
        metrics = calculate_channel_congestion(ch, band_networks, channel_width)
        results.append((ch, metrics))

    # Sort by total interference, then by co-channel
    results.sort(key=lambda x: (x[1]["total_interfering"], x[1]["co_channel"]))
    return results


# ---------------------------------------------------------------------------
# String Formatting Helpers
# ---------------------------------------------------------------------------

def pad_string(text: str, width: int, align: str = "left") -> str:
    """Pad a string to a specified width with alignment.

    Args:
        text: The string to pad.
        width: Target width in characters.
        align: Alignment - 'left', 'right', or 'center'.

    Returns:
        Padded string.

    Examples:
        >>> pad_string("hi", 10)
        'hi        '
        >>> pad_string("hi", 10, align="right")
        '        hi'
        >>> pad_string("hi", 10, align="center")
        '    hi    '
    """
    # Account for CJK characters which are double-width
    display_width = _display_width(text)
    padding = max(0, width - display_width)

    if align == "right":
        return " " * padding + text
    elif align == "center":
        left_pad = padding // 2
        right_pad = padding - left_pad
        return " " * left_pad + text + " " * right_pad
    else:
        return text + " " * padding


def truncate_string(text: str, max_width: int, suffix: str = "...") -> str:
    """Truncate a string to fit within a maximum display width.

    Args:
        text: The string to truncate.
        max_width: Maximum display width.
        suffix: Suffix to append when truncated.

    Returns:
        Truncated string with suffix if needed.
    """
    display_w = _display_width(text)
    if display_w <= max_width:
        return text
    suffix_width = _display_width(suffix)
    available = max(0, max_width - suffix_width)
    # Truncate character by character
    result = ""
    current_width = 0
    for ch in text:
        ch_width = 2 if _is_cjk_char(ch) else 1
        if current_width + ch_width > available:
            break
        result += ch
        current_width += ch_width
    return result + suffix


def format_table(
    headers: List[str],
    rows: List[List[str]],
    padding: int = 2,
) -> str:
    """Format data as a fixed-width text table.

    Args:
        headers: Column header strings.
        rows: List of rows, each row is a list of string cell values.
        padding: Number of spaces between columns.

    Returns:
        Formatted table string.
    """
    if not headers or not rows:
        return ""

    # Calculate column widths
    num_cols = len(headers)
    col_widths = [_display_width(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < num_cols:
                col_widths[i] = max(col_widths[i], _display_width(str(cell)))

    # Build separator line
    sep = "+" + "+".join("-" * (w + padding * 2) for w in col_widths) + "+"

    # Build header line
    header_line = (
        "|"
        + "|".join(
            " " * padding + pad_string(h, w) + " " * padding
            for h, w in zip(headers, col_widths)
        )
        + "|"
    )

    # Build data rows
    data_lines = []
    for row in rows:
        cells = []
        for i in range(num_cols):
            cell = str(row[i]) if i < len(row) else ""
            cells.append(" " * padding + pad_string(cell, col_widths[i]) + " " * padding)
        data_lines.append("|" + "|".join(cells) + "|")

    return "\n".join([sep, header_line, sep] + data_lines + [sep])


# ---------------------------------------------------------------------------
# File Path Helpers
# ---------------------------------------------------------------------------

def ensure_dir(path: str | Path) -> Path:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to create.

    Returns:
        Path object for the directory.
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_data_dir() -> Path:
    """Get the WiFiRadar data directory, creating it if needed.

    Returns:
        Path to ~/.wifiradar/
    """
    data_dir = Path.home() / ".wifiradar"
    return ensure_dir(data_dir)


def get_history_dir() -> Path:
    """Get the scan history directory, creating it if needed.

    Returns:
        Path to ~/.wifiradar/history/
    """
    history_dir = Path.home() / ".wifiradar" / "history"
    return ensure_dir(history_dir)


def safe_filename(name: str, max_length: int = 64) -> str:
    """Convert a string to a safe filename.

    Removes or replaces characters that are unsafe for filenames.

    Args:
        name: Desired filename string.
        max_length: Maximum filename length.

    Returns:
        Sanitized filename string.
    """
    # Replace unsafe characters
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # Remove leading/trailing spaces and dots
    safe = safe.strip(" .")
    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)
    # Truncate
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip("_")
    return safe or "unnamed"


# ---------------------------------------------------------------------------
# Platform Detection
# ---------------------------------------------------------------------------

class PlatformInfo:
    """Detected platform information for WiFi scanning."""

    def __init__(self) -> None:
        self.system: str = platform.system().lower()
        self.release: str = platform.release()
        self.machine: str = platform.machine()
        self.is_linux: bool = self.system == "linux"
        self.is_macos: bool = self.system == "darwin"
        self.is_windows: bool = self.system == "windows"
        self.has_nmcli: bool = self._command_exists("nmcli")
        self.has_iwlist: bool = self._command_exists("iwlist")
        self.has_iw: bool = self._command_exists("iw")
        self.has_airport: bool = self._command_exists("/System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport")
        self.has_netsh: bool = self._command_exists("netsh")

    @property
    def scan_tool(self) -> str:
        """Return the best available scanning tool for this platform.

        Returns:
            Name of the scanning tool: 'nmcli', 'iwlist', 'iw', 'airport', 'netsh', or 'unknown'.
        """
        if self.is_linux:
            if self.has_nmcli:
                return "nmcli"
            if self.has_iw:
                return "iw"
            if self.has_iwlist:
                return "iwlist"
        elif self.is_macos:
            if self.has_airport:
                return "airport"
        elif self.is_windows:
            if self.has_netsh:
                return "netsh"
        return "unknown"

    @property
    def supports_monitor_mode(self) -> bool:
        """Check if the platform supports monitor mode scanning.

        Returns:
            True if monitor mode is likely supported.
        """
        return self.is_linux and self.has_iw

    @staticmethod
    def _command_exists(cmd: str) -> bool:
        """Check if a command-line tool exists on the system.

        Args:
            cmd: Command name or path to check.

        Returns:
            True if the command is found in PATH or exists as an absolute path.
        """
        return shutil.which(cmd) is not None


def get_platform() -> PlatformInfo:
    """Get platform information (cached per call).

    Returns:
        PlatformInfo instance with detected platform details.
    """
    if not hasattr(get_platform, "_cache"):
        get_platform._cache = PlatformInfo()  # type: ignore[attr-defined]
    return get_platform._cache  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _display_width(text: str) -> int:
    """Calculate the display width of a string, accounting for CJK characters.

    CJK (Chinese, Japanese, Korean) characters occupy 2 columns in most
    terminal emulators.

    Args:
        text: Input string.

    Returns:
        Display width in terminal columns.
    """
    width = 0
    for ch in text:
        if _is_cjk_char(ch):
            width += 2
        else:
            width += 1
    return width


def _is_cjk_char(ch: str) -> bool:
    """Check if a character is a CJK (wide) character.

    Args:
        ch: A single character.

    Returns:
        True if the character is CJK (double-width in terminals).
    """
    cp = ord(ch)
    # CJK Unified Ideographs
    if 0x4E00 <= cp <= 0x9FFF:
        return True
    # CJK Extension A
    if 0x3400 <= cp <= 0x4DBF:
        return True
    # CJK Extension B
    if 0x20000 <= cp <= 0x2A6DF:
        return True
    # CJK Compatibility Ideographs
    if 0xF900 <= cp <= 0xFAFF:
        return True
    # Fullwidth Forms
    if 0xFF01 <= cp <= 0xFF60:
        return True
    # Halfwidth Katakana (not fullwidth, but still wide)
    if 0xFF61 <= cp <= 0xFFDC:
        return True
    # Hangul Syllables
    if 0xAC00 <= cp <= 0xD7AF:
        return True
    return False
