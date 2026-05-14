"""
WiFiRadar - Terminal UI Visualization Module

Provides rich terminal-based visualizations for Wi-Fi scan results including
signal strength bar charts, channel usage heatmaps, band distribution charts,
interference scores, and security type distributions. All visualizations use
cross-platform ANSI escape codes with automatic color support detection.

Usage:
    from visualizer import Visualizer, Color

    viz = Visualizer(scan_results)
    viz.print_all()

Zero external dependencies - uses only Python standard library.
"""

from __future__ import annotations

import os
import sys
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any


# ---------------------------------------------------------------------------
# ANSI Color Support Detection & Safe Color Handling
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Color:
    """Safe ANSI color handler with auto-detection of terminal color support.

    Provides foreground and background color codes, reset sequences, and
    style modifiers. Automatically disables color output when the terminal
    does not support ANSI codes (e.g., piped output, Windows legacy console).

    Attributes:
        enabled: Whether color output is currently active.
    """

    enabled: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'enabled', self._detect_color_support())

    # -- ANSI code constants --------------------------------------------------

    # Foreground colors
    FG_BLACK: int = 30
    FG_RED: int = 31
    FG_GREEN: int = 32
    FG_YELLOW: int = 33
    FG_BLUE: int = 34
    FG_MAGENTA: int = 35
    FG_CYAN: int = 36
    FG_WHITE: int = 37
    FG_BRIGHT_BLACK: int = 90
    FG_BRIGHT_RED: int = 91
    FG_BRIGHT_GREEN: int = 92
    FG_BRIGHT_YELLOW: int = 93
    FG_BRIGHT_BLUE: int = 94
    FG_BRIGHT_MAGENTA: int = 95
    FG_BRIGHT_CYAN: int = 96
    FG_BRIGHT_WHITE: int = 97

    # Background colors
    BG_BLACK: int = 40
    BG_RED: int = 41
    BG_GREEN: int = 42
    BG_YELLOW: int = 43
    BG_BLUE: int = 44
    BG_MAGENTA: int = 45
    BG_CYAN: int = 46
    BG_WHITE: int = 47

    # Styles
    RESET: int = 0
    BOLD: int = 1
    DIM: int = 2
    UNDERLINE: int = 4
    BLINK: int = 5
    REVERSE: int = 7

    @staticmethod
    def _detect_color_support() -> bool:
        """Detect whether the current terminal supports ANSI color codes.

        Checks:
        1. NO_COLOR environment variable (https://no-color.org/)
        2. Force-color flags (FORCE_COLOR, CLICOLOR_FORCE)
        3. Windows: checks for ANSI support via ctypes
        4. Checks if stdout is a TTY
        5. Checks TERM variable

        Returns:
            True if colors should be used, False otherwise.
        """
        # Respect NO_COLOR
        if os.environ.get('NO_COLOR', ''):
            return False

        # Forced color
        if os.environ.get('FORCE_COLOR', '') or os.environ.get('CLICOLOR_FORCE', ''):
            return True

        # Windows legacy console detection
        if sys.platform == 'win32':
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
                # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
                mode = ctypes.c_ulong()
                if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                    if mode.value & 0x0004:
                        return True
                    # Try to enable
                    kernel32.SetConsoleMode(handle, mode.value | 0x0004)
                    return True
                return False
            except Exception:
                return False

        # Unix-like: check if stdout is a TTY
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False

        # Check TERM
        term = os.environ.get('TERM', '')
        if term in ('dumb', ''):
            return False

        return True

    def fg(self, code: int) -> str:
        """Return ANSI foreground color escape sequence.

        Args:
            code: One of the FG_* constants.

        Returns:
            ANSI escape string, or empty string if color is disabled.
        """
        if not self.enabled:
            return ''
        return f'\033[{code}m'

    def bg(self, code: int) -> str:
        """Return ANSI background color escape sequence.

        Args:
            code: One of the BG_* constants.

        Returns:
            ANSI escape string, or empty string if color is disabled.
        """
        if not self.enabled:
            return ''
        return f'\033[{code}m'

    def style(self, code: int) -> str:
        """Return ANSI style escape sequence.

        Args:
            code: One of the style constants (BOLD, DIM, UNDERLINE, etc.).

        Returns:
            ANSI escape string, or empty string if color is disabled.
        """
        if not self.enabled:
            return ''
        return f'\033[{code}m'

    def reset(self) -> str:
        """Return ANSI reset sequence."""
        if not self.enabled:
            return ''
        return '\033[0m'

    def text(self, text: str, fg_code: Optional[int] = None,
             bg_code: Optional[int] = None, styles: Optional[List[int]] = None) -> str:
        """Wrap text with ANSI formatting codes.

        Args:
            text: The text to format.
            fg_code: Foreground color code (e.g., FG_GREEN).
            bg_code: Background color code (e.g., BG_RED).
            styles: List of style codes (e.g., [BOLD, UNDERLINE]).

        Returns:
            Formatted text string with ANSI codes, or plain text if disabled.
        """
        parts: List[str] = []
        if fg_code is not None:
            parts.append(self.fg(fg_code))
        if bg_code is not None:
            parts.append(self.bg(bg_code))
        if styles:
            for s in styles:
                parts.append(self.style(s))
        parts.append(text)
        parts.append(self.reset())
        return ''.join(parts)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class NetworkInfo:
    """Represents a single detected Wi-Fi network.

    Attributes:
        ssid: Network name (may be empty for hidden networks).
        bssid: MAC address of the access point.
        signal_dbm: Signal strength in dBm (typically -100 to -30).
        channel: Wi-Fi channel number.
        band: Frequency band ('2.4GHz' or '5GHz').
        security: Security protocol (e.g., 'WPA2-PSK', 'OPEN', 'WPA3').
        encryption: Encryption cipher (e.g., 'CCMP', 'TKIP').
    """

    ssid: str
    bssid: str
    signal_dbm: int
    channel: int
    band: str
    security: str
    encryption: str = ''


@dataclass
class ScanResult:
    """Container for a complete Wi-Fi scan result set.

    Attributes:
        timestamp: ISO 8601 timestamp of the scan.
        interface: Network interface used for scanning.
        networks: List of detected networks.
        metadata: Additional scan metadata.
    """

    timestamp: str
    interface: str
    networks: List[NetworkInfo]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Visualizer
# ---------------------------------------------------------------------------

class Visualizer:
    """Terminal UI visualization engine for Wi-Fi scan results.

    Generates various ASCII-based visualizations including signal strength
    bar charts, channel usage heatmaps, band distribution pie charts,
    interference scores, and security type distributions.

    Args:
        scan_result: The scan result data to visualize.
        color: Optional Color instance for ANSI handling. If None, creates one.

    Example:
        >>> networks = [NetworkInfo('HomeWiFi', 'AA:BB:CC:DD:EE:FF', -45, 6, '2.4GHz', 'WPA2-PSK')]
        >>> scan = ScanResult('2025-01-01T12:00:00', 'wlan0', networks)
        >>> viz = Visualizer(scan)
        >>> viz.print_signal_chart()
    """

    # Unicode block characters for heatmap (full to empty)
    HEAT_BLOCKS: List[str] = ['\u2588', '\u2593', '\u2592', '\u2591', ' ']
    # Full block for bar charts
    BAR_FULL: str = '\u2588'
    BAR_EMPTY: str = '\u2500'
    # Box drawing characters
    BOX_TL: str = '\u250c'
    BOX_TR: str = '\u2510'
    BOX_BL: str = '\u2514'
    BOX_BR: str = '\u2518'
    BOX_H: str = '\u2500'
    BOX_V: str = '\u2502'

    def __init__(self, scan_result: ScanResult, color: Optional[Color] = None) -> None:
        self.scan = scan_result
        self.color = color or Color()

    # -- Signal Quality Helpers ------------------------------------------------

    @staticmethod
    def dbm_to_percent(dbm: int) -> int:
        """Convert dBm signal strength to percentage (0-100).

        Uses a linear mapping from -100 dBm (0%) to -30 dBm (100%).

        Args:
            dbm: Signal strength in dBm.

        Returns:
            Signal quality as percentage (0-100).
        """
        if dbm >= -30:
            return 100
        if dbm <= -100:
            return 0
        return int(round((dbm + 100) * 100 / 70))

    @staticmethod
    def signal_quality_label(dbm: int) -> str:
        """Get human-readable signal quality label.

        Args:
            dbm: Signal strength in dBm.

        Returns:
            Quality label string: 'Excellent', 'Good', 'Fair', or 'Weak'.
        """
        if dbm >= -50:
            return 'Excellent'
        elif dbm >= -60:
            return 'Good'
        elif dbm >= -70:
            return 'Fair'
        else:
            return 'Weak'

    def signal_color(self, dbm: int) -> int:
        """Get ANSI foreground color code for signal strength.

        Args:
            dbm: Signal strength in dBm.

        Returns:
            Color.FG_GREEN, Color.FG_YELLOW, or Color.FG_RED.
        """
        if dbm >= -60:
            return self.color.FG_GREEN
        elif dbm >= -75:
            return self.color.FG_YELLOW
        else:
            return self.color.FG_RED

    # -- Signal Strength Bar Chart ---------------------------------------------

    def signal_chart(self, max_bars: int = 40) -> str:
        """Generate ASCII signal strength bar chart for all detected networks.

        Networks are sorted by signal strength (strongest first). Each bar
        is color-coded: green (>= -60 dBm), yellow (>= -75 dBm), red (< -75 dBm).

        Args:
            max_bars: Maximum width of the signal bar in characters.

        Returns:
            Multi-line string containing the bar chart.
        """
        if not self.scan.networks:
            return self.color.text('  No networks detected.', self.color.FG_YELLOW)

        sorted_nets = sorted(self.scan.networks, key=lambda n: n.signal_dbm, reverse=True)

        # Calculate column widths
        ssid_width = max(len(n.ssid) if n.ssid else 12 for n in sorted_nets)
        ssid_width = max(ssid_width, 12)  # minimum width
        ssid_width = min(ssid_width, 30)   # maximum width

        lines: List[str] = []
        header = f"  {'SSID':<{ssid_width}}  {'dBm':>5}  {'%':>4}  {'Quality':<10}  Signal"
        lines.append(self.color.text(header, self.color.FG_BRIGHT_WHITE, styles=[self.color.BOLD]))
        lines.append(f"  {'─' * ssid_width}  {'─' * 5}  {'─' * 4}  {'─' * 10}  {'─' * max_bars}")

        for net in sorted_nets:
            display_ssid = net.ssid if net.ssid and len(net.ssid) <= ssid_width else (net.ssid[:ssid_width - 2] + '..' if net.ssid else '(Hidden)')
            pct = self.dbm_to_percent(net.signal_dbm)
            quality = self.signal_quality_label(net.signal_dbm)
            color_code = self.signal_color(net.signal_dbm)

            bar_len = int(max_bars * pct / 100)
            bar = self.BAR_FULL * bar_len + self.BAR_EMPTY * (max_bars - bar_len)

            line = f"  {display_ssid:<{ssid_width}}  {net.signal_dbm:>5}  {pct:>3}%  "
            line += self.color.text(f'{quality:<10}', color_code)
            line += '  ' + self.color.text(bar, color_code)
            lines.append(line)

        return '\n'.join(lines)

    # -- Channel Usage Heatmap -------------------------------------------------

    def channel_heatmap(self) -> str:
        """Generate channel usage heatmap for 2.4GHz and 5GHz bands.

        Uses Unicode block characters to represent usage density:
        █ (full) = high usage, ▓ (dark shade), ▒ (medium shade),
        ░ (light shade), (space) = no usage.

        Returns:
            Multi-line string containing the heatmap.
        """
        # Count networks per channel
        channel_counts: Dict[int, int] = {}
        for net in self.scan.networks:
            channel_counts[net.channel] = channel_counts.get(net.channel, 0) + 1

        max_count = max(channel_counts.values()) if channel_counts else 1

        lines: List[str] = []

        # 2.4GHz heatmap (channels 1-13)
        lines.append('')
        lines.append(self.color.text('  2.4 GHz Channel Usage', self.color.FG_BRIGHT_CYAN, styles=[self.color.BOLD]))
        lines.append('  ' + '─' * 62)

        header_24 = '  Ch  '
        for ch in range(1, 14):
            header_24 += f'{ch:>3}'
        lines.append(self.color.text(header_24, self.color.FG_BRIGHT_WHITE))
        lines.append('  ' + '─' * 62)

        # Build heatmap row
        row_24 = '  Bar  '
        for ch in range(1, 14):
            count = channel_counts.get(ch, 0)
            if count == 0:
                block = ' '
            else:
                intensity = count / max_count
                idx = min(int((1 - intensity) * 4), 3)
                block = self.HEAT_BLOCKS[idx]
            row_24 += f'  {block}'
        lines.append(row_24)

        # Count row
        count_24 = '  Num  '
        for ch in range(1, 14):
            count = channel_counts.get(ch, 0)
            if count > 0:
                count_24 += f'{count:>3}'
            else:
                count_24 += '  ·'
        lines.append(self.color.text(count_24, self.color.FG_BRIGHT_BLACK))

        # 5GHz heatmap (channels 36, 40, 44, 48, 52, 56, 60, 64,
        #                100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165)
        gh5_channels = [36, 40, 44, 48, 52, 56, 60, 64,
                        100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144,
                        149, 153, 157, 161, 165]

        # Only show channels that exist or a reasonable subset
        active_5ghz = [ch for ch in gh5_channels if ch in channel_counts]
        if active_5ghz or any(n.band == '5GHz' for n in self.scan.networks):
            lines.append('')
            lines.append(self.color.text('  5 GHz Channel Usage', self.color.FG_BRIGHT_CYAN, styles=[self.color.BOLD]))
            lines.append('  ' + '─' * 62)

            # Show channels in groups of 8
            for group_start in range(0, len(gh5_channels), 8):
                group = gh5_channels[group_start:group_start + 8]
                header_5 = '  Ch  '
                for ch in group:
                    header_5 += f'{ch:>4}'
                lines.append(self.color.text(header_5, self.color.FG_BRIGHT_WHITE))

                row_5 = '  Bar  '
                for ch in group:
                    count = channel_counts.get(ch, 0)
                    if count == 0:
                        block = ' '
                    else:
                        intensity = count / max_count
                        idx = min(int((1 - intensity) * 4), 3)
                        block = self.HEAT_BLOCKS[idx]
                    row_5 += f'  {block}'
                lines.append(row_5)

                count_5 = '  Num  '
                for ch in group:
                    count = channel_counts.get(ch, 0)
                    if count > 0:
                        count_5 += f'{count:>4}'
                    else:
                        count_5 += '   ·'
                lines.append(self.color.text(count_5, self.color.FG_BRIGHT_BLACK))

        # Legend
        lines.append('')
        lines.append('  Legend: ')
        for i, block in enumerate(self.HEAT_BLOCKS[:-1]):
            label = ['High', 'Med-Hi', 'Med-Lo', 'Low'][i]
            lines.append(f'    {block} {label}')
        lines.append(f'    ·  None')

        return '\n'.join(lines)

    # -- Band Distribution Pie Chart -------------------------------------------

    def band_pie_chart(self, width: int = 30, height: int = 15) -> str:
        """Generate ASCII art pie chart showing band distribution.

        Uses a simple filled-circle approach with ASCII characters to
        represent the proportion of 2.4GHz vs 5GHz networks.

        Args:
            width: Width of the pie chart area.
            height: Height of the pie chart area.

        Returns:
            Multi-line string containing the pie chart.
        """
        count_24 = sum(1 for n in self.scan.networks if n.band == '2.4GHz')
        count_5 = sum(1 for n in self.scan.networks if n.band == '5GHz')
        total = count_24 + count_5

        if total == 0:
            return self.color.text('  No band data available.', self.color.FG_YELLOW)

        ratio_24 = count_24 / total
        ratio_5 = count_5 / total

        lines: List[str] = []
        lines.append('')
        lines.append(self.color.text('  Band Distribution', self.color.FG_BRIGHT_CYAN, styles=[self.color.BOLD]))

        # Simple ASCII pie using horizontal bar representation
        bar_total = width
        bar_24 = int(bar_total * ratio_24)
        bar_5 = bar_total - bar_24

        bar = ''
        if bar_24 > 0:
            bar += self.color.text(self.BAR_FULL * bar_24, self.color.FG_GREEN)
        if bar_5 > 0:
            bar += self.color.text(self.BAR_FULL * bar_5, self.color.FG_BLUE)

        lines.append(f'')
        lines.append(f'  {bar}')
        lines.append(f'')
        lines.append(f'  {self.color.text(self.BAR_FULL, self.color.FG_GREEN)} 2.4GHz: {count_24} networks ({ratio_24:.1%})')
        lines.append(f'  {self.color.text(self.BAR_FULL, self.color.FG_BLUE)} 5GHz:   {count_5} networks ({ratio_5:.1%})')
        lines.append(f'  Total:   {total} networks')

        return '\n'.join(lines)

    # -- Interference Score Visualization --------------------------------------

    def interference_chart(self, max_bars: int = 30) -> str:
        """Calculate and visualize interference scores per channel.

        Interference score is based on:
        - Number of networks on the same channel (co-channel interference)
        - Number of networks on adjacent channels (adjacent channel interference)
        - Signal strength of interfering networks (stronger = more interference)

        For 2.4GHz, adjacent channels overlap (channels 1, 6, 11 are non-overlapping).
        For 5GHz, channels are generally non-overlapping (20MHz width assumed).

        Args:
            max_bars: Maximum width of the interference bar.

        Returns:
            Multi-line string containing the interference chart.
        """
        if not self.scan.networks:
            return self.color.text('  No networks for interference analysis.', self.color.FG_YELLOW)

        # Calculate interference per channel
        channel_interference: Dict[int, float] = {}

        for net in self.scan.networks:
            ch = net.channel
            signal_factor = (100 + net.signal_dbm) / 70  # 0-1 range

            if net.band == '2.4GHz':
                # 2.4GHz: adjacent channels overlap significantly
                # Channel width ~22MHz, channels spaced 5MHz apart
                for adj_ch in range(max(1, ch - 4), min(14, ch + 5)):
                    if adj_ch == ch:
                        weight = 1.0  # Same channel: full weight
                    elif abs(adj_ch - ch) <= 2:
                        weight = 0.5  # Heavy overlap
                    else:
                        weight = 0.2  # Minor overlap
                    channel_interference[adj_ch] = (
                        channel_interference.get(adj_ch, 0) + signal_factor * weight
                    )
            else:
                # 5GHz: generally non-overlapping
                channel_interference[ch] = (
                    channel_interference.get(ch, 0) + signal_factor
                )

        if not channel_interference:
            return self.color.text('  No interference data.', self.color.FG_YELLOW)

        max_interference = max(channel_interference.values())
        if max_interference == 0:
            max_interference = 1

        lines: List[str] = []
        lines.append('')
        lines.append(self.color.text('  Channel Interference Scores', self.color.FG_BRIGHT_CYAN, styles=[self.color.BOLD]))
        lines.append('  ' + '─' * 55)

        # Show 2.4GHz channels
        lines.append(self.color.text('  2.4 GHz:', self.color.FG_BRIGHT_WHITE, styles=[self.color.BOLD]))
        for ch in range(1, 14):
            score = channel_interference.get(ch, 0)
            pct = score / max_interference
            bar_len = int(max_bars * pct)

            if pct < 0.3:
                color_code = self.color.FG_GREEN
            elif pct < 0.6:
                color_code = self.color.FG_YELLOW
            else:
                color_code = self.color.FG_RED

            bar = self.BAR_FULL * bar_len + self.BAR_EMPTY * (max_bars - bar_len)
            line = f'  Ch {ch:>2}  '
            line += self.color.text(bar, color_code)
            line += f'  {score:.1f}'
            lines.append(line)

        # Show 5GHz channels (only those with activity)
        gh5_active = sorted(set(
            n.channel for n in self.scan.networks if n.band == '5GHz'
        ))
        if gh5_active:
            lines.append('')
            lines.append(self.color.text('  5 GHz:', self.color.FG_BRIGHT_WHITE, styles=[self.color.BOLD]))
            for ch in gh5_active:
                score = channel_interference.get(ch, 0)
                pct = score / max_interference
                bar_len = int(max_bars * pct)

                if pct < 0.3:
                    color_code = self.color.FG_GREEN
                elif pct < 0.6:
                    color_code = self.color.FG_YELLOW
                else:
                    color_code = self.color.FG_RED

                bar = self.BAR_FULL * bar_len + self.BAR_EMPTY * (max_bars - bar_len)
                line = f'  Ch {ch:>3}  '
                line += self.color.text(bar, color_code)
                line += f'  {score:.1f}'
                lines.append(line)

        return '\n'.join(lines)

    # -- Security Type Distribution Chart --------------------------------------

    def security_chart(self, max_bars: int = 30) -> str:
        """Generate security type distribution chart.

        Counts the number of networks using each security protocol and
        displays a horizontal bar chart sorted by frequency.

        Args:
            max_bars: Maximum width of the distribution bar.

        Returns:
            Multi-line string containing the security chart.
        """
        if not self.scan.networks:
            return self.color.text('  No networks for security analysis.', self.color.FG_YELLOW)

        # Count security types
        sec_counts: Dict[str, int] = {}
        for net in self.scan.networks:
            sec_type = net.security if net.security else 'UNKNOWN'
            sec_counts[sec_type] = sec_counts.get(sec_type, 0) + 1

        sorted_sec = sorted(sec_counts.items(), key=lambda x: x[1], reverse=True)
        max_count = sorted_sec[0][1] if sorted_sec else 1

        # Color mapping for security types
        sec_colors: Dict[str, int] = {
            'WPA3': self.color.FG_GREEN,
            'WPA3-SAE': self.color.FG_GREEN,
            'WPA2': self.color.FG_BRIGHT_GREEN,
            'WPA2-PSK': self.color.FG_BRIGHT_GREEN,
            'WPA2/WPA3': self.color.FG_CYAN,
            'WPA1': self.color.FG_YELLOW,
            'WPA-PSK': self.color.FG_YELLOW,
            'WPA': self.color.FG_YELLOW,
            'WEP': self.color.FG_RED,
            'OPEN': self.color.FG_BRIGHT_RED,
            'OPN': self.color.FG_BRIGHT_RED,
        }

        lines: List[str] = []
        lines.append('')
        lines.append(self.color.text('  Security Type Distribution', self.color.FG_BRIGHT_CYAN, styles=[self.color.BOLD]))
        lines.append('  ' + '─' * 55)

        for sec_type, count in sorted_sec:
            pct = count / max_count
            bar_len = int(max_bars * pct)
            color_code = sec_colors.get(sec_type, self.color.FG_WHITE)

            bar = self.BAR_FULL * bar_len + self.BAR_EMPTY * (max_bars - bar_len)
            line = f'  {sec_type:<14} '
            line += self.color.text(bar, color_code)
            line += f'  {count}'
            lines.append(line)

        # Summary
        lines.append('')
        secure_count = sum(
            c for t, c in sorted_sec
            if any(s in t.upper() for s in ('WPA2', 'WPA3'))
        )
        total = sum(c for _, c in sorted_sec)
        if total > 0:
            ratio = secure_count / total
            if ratio >= 0.8:
                sec_status = self.color.text('GOOD', self.color.FG_GREEN)
            elif ratio >= 0.5:
                sec_status = self.color.text('MODERATE', self.color.FG_YELLOW)
            else:
                sec_status = self.color.text('POOR', self.color.FG_RED)
            lines.append(f'  Security posture: {sec_status} ({secure_count}/{total} networks secured)')

        return '\n'.join(lines)

    # -- Composite Output Methods ----------------------------------------------

    def print_signal_chart(self) -> None:
        """Print signal strength bar chart to stdout."""
        print(self.signal_chart())

    def print_channel_heatmap(self) -> None:
        """Print channel usage heatmap to stdout."""
        print(self.channel_heatmap())

    def print_band_pie(self) -> None:
        """Print band distribution pie chart to stdout."""
        print(self.band_pie_chart())

    def print_interference(self) -> None:
        """Print interference score visualization to stdout."""
        print(self.interference_chart())

    def print_security(self) -> None:
        """Print security type distribution to stdout."""
        print(self.security_chart())

    def print_all(self) -> None:
        """Print all visualizations to stdout in a formatted layout."""
        self._print_header()
        print()
        self.print_signal_chart()
        print()
        self.print_channel_heatmap()
        print()
        self.print_band_pie()
        print()
        self.print_interference()
        print()
        self.print_security()
        print()

    def _print_header(self) -> None:
        """Print scan header with timestamp and summary."""
        width = 60
        top = f'  {self.color.text(self.BOX_TL + self.BOX_H * width + self.BOX_TR, self.color.FG_CYAN)}'
        mid = f'  {self.color.text(self.BOX_V, self.color.FG_CYAN)}'
        end_mid = self.color.text(self.BOX_V, self.color.FG_CYAN)

        title = self.color.text(' WiFiRadar - Signal Analysis ', self.color.FG_BRIGHT_WHITE, styles=[self.color.BOLD])
        padding = width - len(' WiFiRadar - Signal Analysis ')
        title_line = f'  {mid}{title}{" " * padding}{end_mid}'

        info = f'  Scan: {self.scan.timestamp}  |  Interface: {self.scan.interface}  |  Networks: {len(self.scan.networks)}'
        info_padding = width - len(info) + 4
        info_line = f'  {mid}{self.color.text(info, self.color.FG_BRIGHT_BLACK)}{" " * info_padding}{end_mid}'

        bottom = f'  {self.color.text(self.BOX_BL + self.BOX_H * width + self.BOX_BR, self.color.FG_CYAN)}'

        print(top)
        print(title_line)
        print(info_line)
        print(bottom)

    def get_all_text(self) -> str:
        """Get all visualizations as a single string.

        Returns:
            Combined string of all visualizations.
        """
        parts: List[str] = []
        parts.append(self.signal_chart())
        parts.append('')
        parts.append(self.channel_heatmap())
        parts.append('')
        parts.append(self.band_pie_chart())
        parts.append('')
        parts.append(self.interference_chart())
        parts.append('')
        parts.append(self.security_chart())
        return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_visualizer(networks_data: Optional[List[Dict[str, Any]]] = None,
                      timestamp: str = '',
                      interface: str = 'unknown') -> Visualizer:
    """Create a Visualizer from raw network data dictionaries.

    Convenience function that converts a list of dictionaries into
    NetworkInfo objects and constructs a ScanResult.

    Args:
        networks_data: List of dicts with keys: ssid, bssid, signal_dbm,
                       channel, band, security, encryption (optional).
        timestamp: ISO 8601 timestamp string.
        interface: Network interface name.

    Returns:
        Configured Visualizer instance.
    """
    if networks_data is None:
        networks_data = []

    networks: List[NetworkInfo] = []
    for nd in networks_data:
        networks.append(NetworkInfo(
            ssid=nd.get('ssid', ''),
            bssid=nd.get('bssid', ''),
            signal_dbm=int(nd.get('signal_dbm', -100)),
            channel=int(nd.get('channel', 0)),
            band=nd.get('band', '2.4GHz'),
            security=nd.get('security', 'UNKNOWN'),
            encryption=nd.get('encryption', ''),
        ))

    scan = ScanResult(
        timestamp=timestamp,
        interface=interface,
        networks=networks,
    )
    return Visualizer(scan)
