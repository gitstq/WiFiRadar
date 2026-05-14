#!/usr/bin/env python3
"""
WiFiRadar - Lightweight Wi-Fi Signal Intelligent Analysis & Visualization CLI.

A zero-dependency command-line tool for scanning, analyzing, and visualizing
Wi-Fi network signals. Supports multiple output formats, historical tracking,
continuous monitoring, and intelligent channel recommendations.

Usage:
    wifiradar scan              Scan and display WiFi networks
    wifiradar analyze           Full analysis with recommendations
    wifiradar report            Generate comprehensive HTML report
    wifiradar monitor           Continuous monitoring mode
    wifiradar history list      View scan history
    wifiradar demo              Run with mock data

Exit Codes:
    0 - Success
    1 - Error (invalid arguments, permission denied, etc.)
    2 - No networks found
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path for imports when running directly
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config import ColorScheme, Config, get_config, reset_config
from src.utils import (
    PlatformInfo,
    dbm_to_percentage,
    dbm_to_quality,
    dbm_to_bars,
    format_table,
    get_history_dir,
    get_platform,
    pad_string,
    safe_filename,
)


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

__version__ = "0.1.0"


# ---------------------------------------------------------------------------
# Color Output Helpers
# ---------------------------------------------------------------------------

class ColorOutput:
    """Manages colored terminal output with --no-color support."""

    def __init__(self, no_color: bool = False) -> None:
        """Initialize ColorOutput.

        Args:
            no_color: If True, all color codes are stripped.
        """
        self.no_color = no_color

    def _wrap(self, text: str, code: str) -> str:
        """Wrap text in ANSI color code if colors are enabled.

        Args:
            text: Text to colorize.
            code: ANSI escape code.

        Returns:
            Colorized text or plain text if no_color is set.
        """
        if self.no_color:
            return text
        return f"{code}{text}{ColorScheme.RESET}"

    def bold(self, text: str) -> str:
        """Return bold text."""
        return self._wrap(text, ColorScheme.BOLD)

    def dim(self, text: str) -> str:
        """Return dimmed text."""
        return self._wrap(text, ColorScheme.DIM)

    def red(self, text: str) -> str:
        """Return red text."""
        return self._wrap(text, ColorScheme.RED)

    def green(self, text: str) -> str:
        """Return green text."""
        return self._wrap(text, ColorScheme.GREEN)

    def yellow(self, text: str) -> str:
        """Return yellow text."""
        return self._wrap(text, ColorScheme.YELLOW)

    def blue(self, text: str) -> str:
        """Return blue text."""
        return self._wrap(text, ColorScheme.BLUE)

    def cyan(self, text: str) -> str:
        """Return cyan text."""
        return self._wrap(text, ColorScheme.CYAN)

    def gray(self, text: str) -> str:
        """Return gray text."""
        return self._wrap(text, ColorScheme.GRAY)

    def signal_color(self, dbm: int) -> str:
        """Return signal value colored by quality.

        Args:
            dbm: Signal strength in dBm.

        Returns:
            Colorized signal string.
        """
        quality = dbm_to_quality(dbm)
        text = f"{dbm} dBm"
        if quality == "Excellent":
            return self._wrap(text, ColorScheme.SIGNAL_EXCELLENT)
        elif quality == "Good":
            return self._wrap(text, ColorScheme.SIGNAL_GOOD)
        elif quality == "Fair":
            return self._wrap(text, ColorScheme.SIGNAL_FAIR)
        elif quality == "Poor":
            return self._wrap(text, ColorScheme.SIGNAL_POOR)
        else:
            return self._wrap(text, ColorScheme.SIGNAL_NONE)

    def band_color(self, band: str) -> str:
        """Return band string colored by type.

        Args:
            band: Band string (e.g. '2.4GHz', '5GHz').

        Returns:
            Colorized band string.
        """
        if band == "2.4GHz":
            return self._wrap(band, ColorScheme.BAND_2GHZ)
        elif band == "5GHz":
            return self._wrap(band, ColorScheme.BAND_5GHZ)
        return self._wrap(band, ColorScheme.BAND_UNKNOWN)

    def security_color(self, security: str) -> str:
        """Return security type colored by safety level.

        Args:
            security: Security type string.

        Returns:
            Colorized security string.
        """
        sec_upper = security.upper()
        if "WPA3" in sec_upper or "WPA2" in sec_upper:
            return self._wrap(security, ColorScheme.SECURE)
        elif "WPA" in sec_upper:
            return self._wrap(security, ColorScheme.SECURE)
        elif "WEP" in sec_upper:
            return self._wrap(security, ColorScheme.WEP)
        elif "OPEN" in sec_upper or sec_upper == "":
            return self._wrap(security or "OPEN", ColorScheme.INSECURE)
        return self._wrap(security, ColorScheme.GRAY)


# ---------------------------------------------------------------------------
# Network Data Model
# ---------------------------------------------------------------------------

def parse_network_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single network entry from scan output.

    This is a generic parser that handles common cell/SSID formats.
    Specific parsers for each tool (nmcli, iwlist, etc.) should be
    implemented in the scanner module.

    Args:
        line: A line of text from scan output.

    Returns:
        Dictionary with network fields, or None if parsing fails.
    """
    line = line.strip()
    if not line or line.startswith("--") or line.startswith("*"):
        return None
    return {"raw": line}


# ---------------------------------------------------------------------------
# Mock Data Generator (for demo mode)
# ---------------------------------------------------------------------------

def generate_mock_networks(count: int = 15) -> List[Dict[str, Any]]:
    """Generate realistic mock network data for demonstration.

    Args:
        count: Number of mock networks to generate.

    Returns:
        List of network dictionaries.
    """
    import random

    ssids_2ghz = [
        "ChinaNet-A8F2", "TP-LINK_5G_03E2", "HUAWEI-B2E6",
        "MERCURY_3A7C", "Mi-Router-HD", "Tenda_6F3B",
        "FAST_WIFI_9D2A", "ChinaNet-K3D5", "FiberHome-AA12",
        "ZTE-5G-C8E1",
    ]
    ssids_5ghz = [
        "ChinaNet-A8F2_5G", "TP-LINK_5G_03E2", "HUAWEI-B2E6_5G",
        "Mi-Router-HD_5G", "Xiaomi_Router_Pro", "ASUS-5G-4A1B",
        "Netgear-5G-E7C3", "HUAWEI-5G-F2D8",
    ]
    security_types = ["WPA2-PSK", "WPA2/WPA3-PSK", "WPA3-SAE", "WPA-PSK", "WEP", "OPEN"]
    channels_2ghz = [1, 6, 6, 6, 11, 11, 3, 4, 8, 9]
    channels_5ghz = [36, 40, 44, 48, 149, 153, 157, 161, 165]

    networks = []
    random.seed(42)  # Reproducible results

    for i in range(count):
        if i < count * 0.6:
            # 2.4 GHz network
            ssid = random.choice(ssids_2ghz)
            channel = random.choice(channels_2ghz)
            freq = 2412 + (channel - 1) * 5
            band = "2.4GHz"
        else:
            # 5 GHz network
            ssid = random.choice(ssids_5ghz)
            channel = random.choice(channels_5ghz)
            freq_map = {36: 5180, 40: 5200, 44: 5220, 48: 5240,
                        149: 5745, 153: 5765, 157: 5785, 161: 5805, 165: 5825}
            freq = freq_map.get(channel, 5180)
            band = "5GHz"

        signal = random.randint(-90, -25)
        security = random.choice(security_types)
        bssid = ":".join(f"{random.randint(0, 255):02X}" for _ in range(6))

        networks.append({
            "ssid": ssid,
            "bssid": bssid,
            "signal": signal,
            "channel": channel,
            "frequency": freq,
            "band": band,
            "security": security,
            "quality": dbm_to_quality(signal),
            "signal_pct": dbm_to_percentage(signal),
        })

    # Sort by signal strength descending
    networks.sort(key=lambda n: n["signal"], reverse=True)
    return networks


# ---------------------------------------------------------------------------
# Output Formatters
# ---------------------------------------------------------------------------

def format_as_table(
    networks: List[Dict[str, Any]],
    colors: ColorOutput,
) -> str:
    """Format networks as a colored terminal table.

    Args:
        networks: List of network dictionaries.
        colors: ColorOutput instance for coloring.

    Returns:
        Formatted table string.
    """
    headers = [
        colors.bold("#"),
        colors.bold("SSID"),
        colors.bold("BSSID"),
        colors.bold("Signal"),
        colors.bold("Quality"),
        colors.bold("Channel"),
        colors.bold("Band"),
        colors.bold("Security"),
    ]

    rows = []
    for i, net in enumerate(networks, 1):
        ssid = net.get("ssid", "N/A")
        bssid = net.get("bssid", "N/A")
        signal = net.get("signal", -100)
        quality = net.get("quality", dbm_to_quality(signal))
        channel = net.get("channel", "N/A")
        band = net.get("band", "Unknown")
        security = net.get("security", "N/A")

        rows.append([
            str(i),
            ssid,
            bssid,
            colors.signal_color(signal),
            quality,
            str(channel),
            colors.band_color(str(band)),
            colors.security_color(str(security)),
        ])

    return format_table(headers, rows)


def format_as_markdown(networks: List[Dict[str, Any]]) -> str:
    """Format networks as a Markdown table.

    Args:
        networks: List of network dictionaries.

    Returns:
        Markdown table string.
    """
    lines = [
        "| # | SSID | BSSID | Signal | Quality | Channel | Band | Security |",
        "|---|------|-------|--------|---------|---------|------|----------|",
    ]
    for i, net in enumerate(networks, 1):
        lines.append(
            f"| {i} | {net.get('ssid', 'N/A')} | {net.get('bssid', 'N/A')} "
            f"| {net.get('signal', 'N/A')} dBm | {net.get('quality', 'N/A')} "
            f"| {net.get('channel', 'N/A')} | {net.get('band', 'N/A')} "
            f"| {net.get('security', 'N/A')} |"
        )
    return "\n".join(lines)


def format_as_csv(networks: List[Dict[str, Any]]) -> str:
    """Format networks as CSV.

    Args:
        networks: List of network dictionaries.

    Returns:
        CSV string.
    """
    import csv
    import io

    if not networks:
        return ""

    fieldnames = ["ssid", "bssid", "signal", "quality", "channel", "frequency", "band", "security"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for net in networks:
        writer.writerow(net)
    return output.getvalue()


def format_as_html_table(networks: List[Dict[str, Any]]) -> str:
    """Format networks as an HTML table fragment.

    Args:
        networks: List of network dictionaries.

    Returns:
        HTML table string.
    """
    rows_html = ""
    for i, net in enumerate(networks, 1):
        signal = net.get("signal", -100)
        quality = net.get("quality", dbm_to_quality(signal))
        # Determine CSS class based on signal quality
        if quality == "Excellent":
            q_class = "signal-excellent"
        elif quality == "Good":
            q_class = "signal-good"
        elif quality == "Fair":
            q_class = "signal-fair"
        else:
            q_class = "signal-poor"

        rows_html += f"""    <tr>
      <td>{i}</td>
      <td>{_html_escape(net.get('ssid', 'N/A'))}</td>
      <td><code>{_html_escape(net.get('bssid', 'N/A'))}</code></td>
      <td class="{q_class}">{signal} dBm</td>
      <td>{quality}</td>
      <td>{net.get('channel', 'N/A')}</td>
      <td>{net.get('band', 'N/A')}</td>
      <td>{_html_escape(net.get('security', 'N/A'))}</td>
    </tr>\n"""

    return f"""<table>
  <thead>
    <tr>
      <th>#</th><th>SSID</th><th>BSSID</th><th>Signal</th>
      <th>Quality</th><th>Channel</th><th>Band</th><th>Security</th>
    </tr>
  </thead>
  <tbody>
{rows_html}  </tbody>
</table>"""


def format_as_json(networks: List[Dict[str, Any]], indent: int = 2) -> str:
    """Format networks as JSON.

    Args:
        networks: List of network dictionaries.
        indent: JSON indentation level.

    Returns:
        JSON string.
    """
    return json.dumps(networks, indent=indent, ensure_ascii=False)


def _html_escape(text: str) -> str:
    """Escape HTML special characters.

    Args:
        text: Raw text.

    Returns:
        HTML-escaped text.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace, colors: ColorOutput) -> int:
    """Handle the 'scan' command.

    Scans for Wi-Fi networks and displays results in the requested format.

    Args:
        args: Parsed command-line arguments.
        colors: ColorOutput instance.

    Returns:
        Exit code: 0 success, 1 error, 2 no networks.
    """
    if args.demo:
        networks = generate_mock_networks()
    else:
        # Real scan would go here - for now use mock data
        # with a message indicating it's a placeholder
        colors.yellow("# Note: Real scanning requires platform-specific tools.\n")
        colors.yellow("# Using mock data. Use --demo flag explicitly to suppress this message.\n\n")
        networks = generate_mock_networks()

    if not networks:
        colors.red("No networks found.\n")
        return 2

    # Apply filters
    if args.min_signal is not None:
        networks = [n for n in networks if n.get("signal", -100) >= args.min_signal]

    if args.filter_band:
        networks = [n for n in networks if n.get("band", "") == args.filter_band]

    if args.top:
        networks = networks[:args.top]

    # Sort
    if args.sort_by:
        sort_key = args.sort_by.lower()
        reverse = True  # Default descending for signal
        if sort_key == "ssid":
            networks.sort(key=lambda n: n.get("ssid", ""), reverse=False)
        elif sort_key == "channel":
            networks.sort(key=lambda n: n.get("channel", 0), reverse=False)
        elif sort_key == "signal":
            networks.sort(key=lambda n: n.get("signal", -100), reverse=True)
        elif sort_key == "band":
            networks.sort(key=lambda n: n.get("band", ""), reverse=False)

    if not networks:
        colors.red("No networks match the specified filters.\n")
        return 2

    # Output
    if args.json:
        print(format_as_json(networks))
    elif args.csv:
        print(format_as_csv(networks), end="")
    elif args.html:
        print(format_as_html_table(networks))
    elif args.markdown:
        print(format_as_markdown(networks))
    else:
        # Default: colored table
        print(format_as_table(networks, colors))
        print(f"\n{colors.dim(f'Total: {len(networks)} networks found')}")

    return 0


def cmd_analyze(args: argparse.Namespace, colors: ColorOutput) -> int:
    """Handle the 'analyze' command.

    Performs full analysis of Wi-Fi environment with channel recommendations.

    Args:
        args: Parsed command-line arguments.
        colors: ColorOutput instance.

    Returns:
        Exit code: 0 success, 1 error, 2 no networks.
    """
    from src.utils import get_best_channels, calculate_channel_congestion

    networks = generate_mock_networks()

    if not networks:
        colors.red("No networks found.\n")
        return 2

    # Separate by band
    networks_2ghz = [n for n in networks if n.get("band") == "2.4GHz"]
    networks_5ghz = [n for n in networks if n.get("band") == "5GHz"]

    # Build analysis
    analysis: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "total_networks": len(networks),
        "band_2ghz_count": len(networks_2ghz),
        "band_5ghz_count": len(networks_5ghz),
        "networks": networks,
    }

    # Channel analysis
    best_2ghz = get_best_channels(networks, "2.4GHz")
    best_5ghz = get_best_channels(networks, "5GHz")

    analysis["recommendations"] = {
        "best_2ghz_channels": [(ch, m) for ch, m in best_2ghz[:3]],
        "best_5ghz_channels": [(ch, m) for ch, m in best_5ghz[:3]],
    }

    # Output
    if args.json:
        # Convert tuples to lists for JSON serialization
        serializable = dict(analysis)
        recs = serializable["recommendations"]
        recs["best_2ghz_channels"] = [
            {"channel": ch, **metrics} for ch, metrics in recs["best_2ghz_channels"]
        ]
        recs["best_5ghz_channels"] = [
            {"channel": ch, **metrics} for ch, metrics in recs["best_5ghz_channels"]
        ]
        print(format_as_json(serializable))
    elif args.html:
        _print_analysis_html(analysis, colors)
    elif args.markdown:
        _print_analysis_markdown(analysis, colors)
    else:
        _print_analysis_terminal(analysis, colors)

    return 0


def _print_analysis_terminal(analysis: Dict[str, Any], colors: ColorOutput) -> None:
    """Print analysis results to terminal with colors.

    Args:
        analysis: Analysis data dictionary.
        colors: ColorOutput instance.
    """
    print(colors.bold("\n=== WiFiRadar Analysis Report ===\n"))
    print(f"  Timestamp:       {analysis['timestamp']}")
    print(f"  Total Networks:  {analysis['total_networks']}")
    print(f"  2.4 GHz Networks: {analysis['band_2ghz_count']}")
    print(f"  5 GHz Networks:  {analysis['band_5ghz_count']}")

    recs = analysis["recommendations"]
    print(colors.bold("\n--- Channel Recommendations ---\n"))

    print(colors.cyan("  Best 2.4 GHz Channels:"))
    for ch, metrics in recs["best_2ghz_channels"][:3]:
        print(
            f"    Channel {ch:2d}: "
            f"co-channel={metrics['co_channel']}, "
            f"overlapping={metrics['overlapping']}, "
            f"total={colors.yellow(str(metrics['total_interfering']))}"
        )

    print(colors.cyan("\n  Best 5 GHz Channels:"))
    for ch, metrics in recs["best_5ghz_channels"][:3]:
        print(
            f"    Channel {ch:3d}: "
            f"co-channel={metrics['co_channel']}, "
            f"overlapping={metrics['overlapping']}, "
            f"total={colors.yellow(str(metrics['total_interfering']))}"
        )

    print()


def _print_analysis_markdown(analysis: Dict[str, Any], colors: ColorOutput) -> None:
    """Print analysis results as Markdown.

    Args:
        analysis: Analysis data dictionary.
        colors: ColorOutput instance (unused for markdown).
    """
    print("# WiFiRadar Analysis Report\n")
    print(f"- **Timestamp:** {analysis['timestamp']}")
    print(f"- **Total Networks:** {analysis['total_networks']}")
    print(f"- **2.4 GHz:** {analysis['band_2ghz_count']} networks")
    print(f"- **5 GHz:** {analysis['band_5ghz_count']} networks")
    print("\n## Channel Recommendations\n")
    print("### Best 2.4 GHz Channels\n")
    print("| Channel | Co-Channel | Overlapping | Total Interfering |")
    print("|---------|------------|-------------|-------------------|")
    for ch, m in analysis["recommendations"]["best_2ghz_channels"][:3]:
        print(f"| {ch} | {m['co_channel']} | {m['overlapping']} | {m['total_interfering']} |")
    print("\n### Best 5 GHz Channels\n")
    print("| Channel | Co-Channel | Overlapping | Total Interfering |")
    print("|---------|------------|-------------|-------------------|")
    for ch, m in analysis["recommendations"]["best_5ghz_channels"][:3]:
        print(f"| {ch} | {m['co_channel']} | {m['overlapping']} | {m['total_interfering']} |")


def _print_analysis_html(analysis: Dict[str, Any], colors: ColorOutput) -> None:
    """Print analysis results as HTML.

    Args:
        analysis: Analysis data dictionary.
        colors: ColorOutput instance (unused for HTML).
    """
    print("<div class=\"analysis-report\">")
    print(f"  <h2>WiFiRadar Analysis Report</h2>")
    print(f"  <p>Timestamp: {analysis['timestamp']}</p>")
    print(f"  <p>Total Networks: {analysis['total_networks']}</p>")
    print(f"  <p>2.4 GHz: {analysis['band_2ghz_count']} | 5 GHz: {analysis['band_5ghz_count']}</p>")
    print("  <h3>Channel Recommendations</h3>")
    print("  <h4>Best 2.4 GHz</h4>")
    print("  <ul>")
    for ch, m in analysis["recommendations"]["best_2ghz_channels"][:3]:
        print(f"    <li>Channel {ch}: co-channel={m['co_channel']}, overlapping={m['overlapping']}, total={m['total_interfering']}</li>")
    print("  </ul>")
    print("  <h4>Best 5 GHz</h4>")
    print("  <ul>")
    for ch, m in analysis["recommendations"]["best_5ghz_channels"][:3]:
        print(f"    <li>Channel {ch}: co-channel={m['co_channel']}, overlapping={m['overlapping']}, total={m['total_interfering']}</li>")
    print("  </ul>")
    print("</div>")


def cmd_history(args: argparse.Namespace, colors: ColorOutput) -> int:
    """Handle the 'history' command.

    Manages scan history with subcommands: list, show, trend, compare, clean.

    Args:
        args: Parsed command-line arguments.
        colors: ColorOutput instance.

    Returns:
        Exit code: 0 success, 1 error.
    """
    history_dir = get_history_dir()

    if args.history_action == "list":
        return _history_list(history_dir, colors)
    elif args.history_action == "show":
        return _history_show(history_dir, args.history_id, colors)
    elif args.history_action == "trend":
        return _history_trend(history_dir, colors)
    elif args.history_action == "compare":
        return _history_compare(history_dir, args.history_ids, colors)
    elif args.history_action == "clean":
        return _history_clean(history_dir, colors)
    else:
        colors.red(f"Unknown history action: {args.history_action}\n")
        return 1


def _history_list(history_dir: Path, colors: ColorOutput) -> int:
    """List all scan history entries.

    Args:
        history_dir: Path to history directory.
        colors: ColorOutput instance.

    Returns:
        Exit code.
    """
    entries = sorted(history_dir.glob("*.json")) if history_dir.exists() else []

    if not entries:
        colors.yellow("No scan history found.\n")
        print(f"  History directory: {history_dir}")
        return 0

    print(colors.bold(f"\nScan History ({len(entries)} entries):\n"))
    for entry in entries:
        try:
            with open(entry, "r", encoding="utf-8") as f:
                data = json.load(f)
            ts = data.get("timestamp", "unknown")
            count = data.get("total_networks", "?")
            print(f"  {colors.cyan(entry.stem)}  {ts}  ({count} networks)")
        except (OSError, json.JSONDecodeError):
            print(f"  {colors.red(entry.stem)}  [corrupted]")

    print()
    return 0


def _history_show(history_dir: Path, entry_id: str, colors: ColorOutput) -> int:
    """Show details of a specific history entry.

    Args:
        history_dir: Path to history directory.
        entry_id: Entry identifier.
        colors: ColorOutput instance.

    Returns:
        Exit code.
    """
    filepath = history_dir / f"{entry_id}.json"
    if not filepath.exists():
        colors.red(f"History entry '{entry_id}' not found.\n")
        return 1

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except (OSError, json.JSONDecodeError) as e:
        colors.red(f"Error reading history entry: {e}\n")
        return 1

    return 0


def _history_trend(history_dir: Path, colors: ColorOutput) -> int:
    """Show signal trends across history entries.

    Args:
        history_dir: Path to history directory.
        colors: ColorOutput instance.

    Returns:
        Exit code.
    """
    entries = sorted(history_dir.glob("*.json")) if history_dir.exists() else []

    if len(entries) < 2:
        colors.yellow("Need at least 2 history entries to show trends.\n")
        return 0

    print(colors.bold("\nSignal Trend:\n"))
    for entry in entries[-10:]:  # Last 10 entries
        try:
            with open(entry, "r", encoding="utf-8") as f:
                data = json.load(f)
            ts = data.get("timestamp", "unknown")[:19]
            count = data.get("total_networks", "?")
            avg_signal = data.get("avg_signal", "N/A")
            print(f"  {ts}  networks={count}  avg_signal={avg_signal} dBm")
        except (OSError, json.JSONDecodeError):
            pass

    print()
    return 0


def _history_compare(history_dir: Path, ids: List[str], colors: ColorOutput) -> int:
    """Compare two or more history entries.

    Args:
        history_dir: Path to history directory.
        ids: List of entry IDs to compare.
        colors: ColorOutput instance.

    Returns:
        Exit code.
    """
    if len(ids) < 2:
        colors.red("Need at least 2 entry IDs to compare. Usage: history compare ID1 ID2\n")
        return 1

    for entry_id in ids:
        filepath = history_dir / f"{entry_id}.json"
        if not filepath.exists():
            colors.red(f"History entry '{entry_id}' not found.\n")
            return 1

    print(colors.bold("\nComparison:\n"))
    for entry_id in ids:
        filepath = history_dir / f"{entry_id}.json"
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            ts = data.get("timestamp", "unknown")
            count = data.get("total_networks", "?")
            print(f"  {colors.cyan(entry_id)}: {ts} ({count} networks)")
        except (OSError, json.JSONDecodeError):
            colors.red(f"  {entry_id}: [error reading]\n")

    print()
    return 0


def _history_clean(history_dir: Path, colors: ColorOutput) -> int:
    """Clean all scan history entries.

    Args:
        history_dir: Path to history directory.
        colors: ColorOutput instance.

    Returns:
        Exit code.
    """
    entries = list(history_dir.glob("*.json")) if history_dir.exists() else []

    if not entries:
        colors.yellow("No history entries to clean.\n")
        return 0

    for entry in entries:
        try:
            entry.unlink()
        except OSError:
            pass

    colors.green(f"Cleaned {len(entries)} history entries.\n")
    return 0


def cmd_report(args: argparse.Namespace, colors: ColorOutput) -> int:
    """Handle the 'report' command.

    Generates a comprehensive HTML report.

    Args:
        args: Parsed command-line arguments.
        colors: ColorOutput instance.

    Returns:
        Exit code: 0 success, 1 error.
    """
    networks = generate_mock_networks()

    if not networks:
        colors.red("No networks to report.\n")
        return 2

    from src.utils import get_best_channels

    # Build report data
    report_data: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "version": __version__,
        "networks": networks,
        "total": len(networks),
    }

    best_2ghz = get_best_channels(networks, "2.4GHz")
    best_5ghz = get_best_channels(networks, "5GHz")
    report_data["best_channels_2ghz"] = best_2ghz[:3]
    report_data["best_channels_5ghz"] = best_5ghz[:3]

    # Generate HTML
    html = _generate_full_html_report(report_data)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"wifiradar_report_{timestamp_str}.html")

    # Write file
    try:
        output_path.write_text(html, encoding="utf-8")
        colors.green(f"Report saved to: {output_path}\n")
    except OSError as e:
        colors.red(f"Error writing report: {e}\n")
        return 1

    # Auto-open
    if args.open:
        import webbrowser
        try:
            webbrowser.open(str(output_path.resolve()))
        except Exception:
            colors.yellow("Could not open browser automatically.\n")

    return 0


def _generate_full_html_report(data: Dict[str, Any]) -> str:
    """Generate a full standalone HTML report.

    Args:
        data: Report data dictionary.

    Returns:
        Complete HTML string.
    """
    # Build network rows
    net_rows = ""
    for i, net in enumerate(data["networks"], 1):
        signal = net.get("signal", -100)
        quality = net.get("quality", dbm_to_quality(signal))
        pct = net.get("signal_pct", dbm_to_percentage(signal))
        net_rows += f"""    <tr>
      <td>{i}</td>
      <td>{_html_escape(net.get('ssid', 'N/A'))}</td>
      <td><code>{_html_escape(net.get('bssid', 'N/A'))}</code></td>
      <td>
        <div class="signal-bar" style="width:{pct}%;background:{_signal_bar_color(quality)}"></div>
        <span>{signal} dBm ({pct}%)</span>
      </td>
      <td class="quality-{quality.lower()}">{quality}</td>
      <td>{net.get('channel', 'N/A')}</td>
      <td>{net.get('band', 'N/A')}</td>
      <td>{_html_escape(net.get('security', 'N/A'))}</td>
    </tr>\n"""

    # Build recommendation rows
    rec_rows_2ghz = ""
    for ch, m in data.get("best_channels_2ghz", []):
        rec_rows_2ghz += f"<tr><td>{ch}</td><td>{m['co_channel']}</td><td>{m['overlapping']}</td><td>{m['total_interfering']}</td></tr>\n"

    rec_rows_5ghz = ""
    for ch, m in data.get("best_channels_5ghz", []):
        rec_rows_5ghz += f"<tr><td>{ch}</td><td>{m['co_channel']}</td><td>{m['overlapping']}</td><td>{m['total_interfering']}</td></tr>\n"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WiFiRadar Report - {data['timestamp'][:10]}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background: #f5f7fa; color: #333; line-height: 1.6; padding: 2rem; }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ color: #2c3e50; margin-bottom: 0.5rem; }}
    .meta {{ color: #7f8c8d; margin-bottom: 2rem; }}
    .card {{ background: white; border-radius: 8px; padding: 1.5rem;
             margin-bottom: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
    h2 {{ color: #2c3e50; margin-bottom: 1rem; font-size: 1.3rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th {{ background: #34495e; color: white; padding: 0.75rem 1rem; text-align: left; }}
    td {{ padding: 0.6rem 1rem; border-bottom: 1px solid #ecf0f1; }}
    tr:hover {{ background: #f8f9fa; }}
    .signal-bar {{ height: 8px; border-radius: 4px; margin-bottom: 4px; }}
    .quality-excellent {{ color: #27ae60; font-weight: bold; }}
    .quality-good {{ color: #2ecc71; }}
    .quality-fair {{ color: #f39c12; }}
    .quality-poor {{ color: #e74c3c; }}
    .quality-no signal {{ color: #95a5a6; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px;
              font-size: 0.8rem; font-weight: bold; }}
    .badge-2ghz {{ background: #fef3c7; color: #92400e; }}
    .badge-5ghz {{ background: #cffafe; color: #155e75; }}
    .footer {{ text-align: center; color: #95a5a6; margin-top: 2rem; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>WiFiRadar Analysis Report</h1>
    <p class="meta">
      Generated: {data['timestamp']} | Networks Found: {data['total']} | WiFiRadar v{data['version']}
    </p>

    <div class="card">
      <h2>Network List</h2>
      <table>
        <thead>
          <tr>
            <th>#</th><th>SSID</th><th>BSSID</th><th>Signal</th>
            <th>Quality</th><th>Channel</th><th>Band</th><th>Security</th>
          </tr>
        </thead>
        <tbody>
{net_rows}        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>Channel Recommendations - 2.4 GHz</h2>
      <table>
        <thead><tr><th>Channel</th><th>Co-Channel</th><th>Overlapping</th><th>Total Interfering</th></tr></thead>
        <tbody>{rec_rows_2ghz}</tbody>
      </table>
    </div>

    <div class="card">
      <h2>Channel Recommendations - 5 GHz</h2>
      <table>
        <thead><tr><th>Channel</th><th>Co-Channel</th><th>Overlapping</th><th>Total Interfering</th></tr></thead>
        <tbody>{rec_rows_5ghz}</tbody>
      </table>
    </div>

    <div class="footer">
      Generated by <strong>WiFiRadar v{data['version']}</strong> - Zero-dependency Wi-Fi Analysis CLI
    </div>
  </div>
</body>
</html>"""


def _signal_bar_color(quality: str) -> str:
    """Return CSS color for signal bar based on quality.

    Args:
        quality: Quality grade string.

    Returns:
        CSS color string.
    """
    colors_map = {
        "Excellent": "#27ae60",
        "Good": "#2ecc71",
        "Fair": "#f39c12",
        "Poor": "#e74c3c",
        "No Signal": "#bdc3c7",
    }
    return colors_map.get(quality, "#bdc3c7")


def cmd_monitor(args: argparse.Namespace, colors: ColorOutput) -> int:
    """Handle the 'monitor' command.

    Continuously monitors Wi-Fi networks at regular intervals.

    Args:
        args: Parsed command-line arguments.
        colors: ColorOutput instance.

    Returns:
        Exit code: 0 success, 1 error.
    """
    interval = args.interval
    duration = args.duration
    alert_threshold = args.alert_threshold

    print(colors.bold(f"\n=== WiFiRadar Monitor Mode ===\n"))
    print(f"  Interval:    {interval}s")
    print(f"  Alert:       {alert_threshold} dBm")
    if duration > 0:
        print(f"  Duration:    {duration}s")
    else:
        print(f"  Duration:    continuous (Ctrl+C to stop)")
    print()

    start_time = time.time()
    scan_count = 0

    try:
        while True:
            # Check duration
            if duration > 0:
                elapsed = time.time() - start_time
                if elapsed >= duration:
                    colors.green(f"\nMonitor completed after {scan_count} scans.\n")
                    break

            scan_count += 1
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(colors.bold(f"[{now}] Scan #{scan_count}"))

            networks = generate_mock_networks()

            # Check for alerts
            weak_networks = [
                n for n in networks
                if n.get("signal", 0) < alert_threshold
            ]
            if weak_networks:
                for n in weak_networks:
                    colors.red(
                        f"  ALERT: {n.get('ssid', 'N/A')} signal is "
                        f"{n.get('signal', 'N/A')} dBm (threshold: {alert_threshold} dBm)"
                    )

            print(f"  Found {len(networks)} networks")
            print()

            time.sleep(interval)

    except KeyboardInterrupt:
        colors.yellow(f"\nMonitor stopped after {scan_count} scans.\n")

    return 0


def cmd_demo(args: argparse.Namespace, colors: ColorOutput) -> int:
    """Handle the 'demo' command.

    Runs WiFiRadar with mock data for demonstration purposes.

    Args:
        args: Parsed command-line arguments.
        colors: ColorOutput instance.

    Returns:
        Exit code: 0 success.
    """
    print(colors.bold("\n=== WiFiRadar Demo Mode ===\n"))
    colors.dim("Running with mock data for demonstration purposes.\n\n")

    networks = generate_mock_networks()

    # Show scan results
    print(colors.bold("--- Scan Results ---\n"))
    print(format_as_table(networks, colors))
    print(f"\n{colors.dim(f'Total: {len(networks)} networks')}")

    # Show analysis
    print(colors.bold("\n--- Quick Analysis ---\n"))
    from src.utils import get_best_channels
    best_2ghz = get_best_channels(networks, "2.4GHz")
    best_5ghz = get_best_channels(networks, "5GHz")

    print(colors.cyan("  Recommended 2.4 GHz channels:"))
    for ch, m in best_2ghz[:3]:
        marker = " <-- best" if m["total_interfering"] == best_2ghz[0][1]["total_interfering"] else ""
        print(f"    Channel {ch:2d}: {m['total_interfering']} interfering networks{marker}")

    print(colors.cyan("\n  Recommended 5 GHz channels:"))
    for ch, m in best_5ghz[:3]:
        marker = " <-- best" if m["total_interfering"] == best_5ghz[0][1]["total_interfering"] else ""
        print(f"    Channel {ch:3d}: {m['total_interfering']} interfering networks{marker}")

    print()
    return 0


# ---------------------------------------------------------------------------
# Argument Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the main argument parser with all commands and options.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="wifiradar",
        description=(
            "WiFiRadar - Lightweight Wi-Fi Signal Intelligent Analysis & Visualization CLI\n"
            "\n"
            "A zero-dependency tool for scanning, analyzing, and visualizing Wi-Fi networks.\n"
            "Supports multiple output formats, historical tracking, and channel optimization."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  wifiradar scan                    Scan and display networks\n"
            "  wifiradar scan --json             Output as JSON\n"
            "  wifiradar scan --top 10           Show top 10 strongest signals\n"
            "  wifiradar scan --filter-band 5GHz Show only 5 GHz networks\n"
            "  wifiradar analyze                 Full analysis with recommendations\n"
            "  wifiradar analyze --markdown      Output analysis as Markdown\n"
            "  wifiradar report --output report.html  Generate HTML report\n"
            "  wifiradar monitor --interval 60   Monitor every 60 seconds\n"
            "  wifiradar history list            List scan history\n"
            "  wifiradar demo                    Run with mock data\n"
            "\n"
            "Exit Codes:\n"
            "  0  Success\n"
            "  1  Error (invalid args, permission denied, etc.)\n"
            "  2  No networks found\n"
        ),
    )

    # Global options
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="Disable colored output",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable verbose output",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        default=False,
        help="Suppress non-essential output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"WiFiRadar v{__version__}",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # -- scan ----------------------------------------------------------------
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan WiFi networks and show results",
        description="Scan for nearby WiFi networks and display results in various formats.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  wifiradar scan                     Default table output\n"
            "  wifiradar scan --json              JSON output\n"
            "  wifiradar scan --csv               CSV output\n"
            "  wifiradar scan --html              HTML table output\n"
            "  wifiradar scan --markdown          Markdown table output\n"
            "  wifiradar scan --sort-by ssid      Sort by SSID\n"
            "  wifiradar scan --filter-band 5GHz  Only 5 GHz networks\n"
            "  wifiradar scan --min-signal -60    Only strong signals\n"
            "  wifiradar scan --top 5             Top 5 networks\n"
        ),
    )
    scan_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    scan_parser.add_argument("--csv", action="store_true", help="Output in CSV format")
    scan_parser.add_argument("--html", action="store_true", help="Output as HTML table")
    scan_parser.add_argument("--markdown", action="store_true", help="Output as Markdown table")
    scan_parser.add_argument(
        "--sort-by",
        choices=["signal", "ssid", "channel", "band"],
        default="signal",
        help="Sort results by field (default: signal)",
    )
    scan_parser.add_argument(
        "--filter-band",
        choices=["2.4GHz", "5GHz"],
        help="Filter by frequency band",
    )
    scan_parser.add_argument(
        "--min-signal",
        type=int,
        metavar="DBM",
        help="Minimum signal strength in dBm (e.g., -60)",
    )
    scan_parser.add_argument(
        "--top",
        type=int,
        metavar="N",
        help="Show only top N networks",
    )
    scan_parser.add_argument(
        "--demo",
        action="store_true",
        help="Use mock data instead of real scan",
    )

    # -- analyze --------------------------------------------------------------
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Full analysis with recommendations",
        description="Perform comprehensive analysis of WiFi environment with channel recommendations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  wifiradar analyze                Terminal output with colors\n"
            "  wifiradar analyze --json         JSON output\n"
            "  wifiradar analyze --html         HTML output\n"
            "  wifiradar analyze --markdown     Markdown output\n"
        ),
    )
    analyze_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    analyze_parser.add_argument("--html", action="store_true", help="Output as HTML")
    analyze_parser.add_argument("--markdown", action="store_true", help="Output as Markdown")

    # -- history --------------------------------------------------------------
    history_parser = subparsers.add_parser(
        "history",
        help="Manage scan history",
        description="View and manage saved scan history entries.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  wifiradar history list           List all saved scans\n"
            "  wifiradar history show ID        Show details of a scan\n"
            "  wifiradar history trend          Show signal trends\n"
            "  wifiradar history compare ID1 ID2  Compare two scans\n"
            "  wifiradar history clean          Clear all history\n"
        ),
    )
    history_subparsers = history_parser.add_subparsers(dest="history_action", help="History actions")

    history_subparsers.add_parser("list", help="List all scan history entries")
    history_subparsers.add_parser("trend", help="Show signal trends over time")
    history_subparsers.add_parser("clean", help="Clear all scan history")

    show_parser = history_subparsers.add_parser("show", help="Show details of a scan entry")
    show_parser.add_argument("history_id", help="History entry ID")

    compare_parser = history_subparsers.add_parser("compare", help="Compare scan entries")
    compare_parser.add_argument("history_ids", nargs="+", help="History entry IDs to compare")

    # -- report ---------------------------------------------------------------
    report_parser = subparsers.add_parser(
        "report",
        help="Generate comprehensive HTML report",
        description="Generate a comprehensive HTML report with network data and recommendations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  wifiradar report                          Save to default filename\n"
            "  wifiradar report --output my_report.html  Save to specific file\n"
            "  wifiradar report --open                   Generate and open in browser\n"
        ),
    )
    report_parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Output file path (default: wifiradar_report_TIMESTAMP.html)",
    )
    report_parser.add_argument(
        "--open",
        action="store_true",
        help="Open the report in the default browser after generation",
    )

    # -- monitor --------------------------------------------------------------
    monitor_parser = subparsers.add_parser(
        "monitor",
        help="Continuous monitoring mode",
        description="Continuously monitor WiFi networks with optional alerts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  wifiradar monitor                     Monitor every 30s\n"
            "  wifiradar monitor --interval 60        Monitor every 60s\n"
            "  wifiradar monitor --alert-threshold -70  Alert below -70 dBm\n"
            "  wifiradar monitor --duration 3600      Monitor for 1 hour\n"
        ),
    )
    monitor_parser.add_argument(
        "--interval",
        type=int,
        default=30,
        metavar="SECONDS",
        help="Scan interval in seconds (default: 30)",
    )
    monitor_parser.add_argument(
        "--alert-threshold",
        type=int,
        default=-75,
        metavar="DBM",
        help="Signal threshold for alerts in dBm (default: -75)",
    )
    monitor_parser.add_argument(
        "--duration",
        type=int,
        default=0,
        metavar="SECONDS",
        help="Monitoring duration in seconds (0 = infinite, default: 0)",
    )

    # -- demo -----------------------------------------------------------------
    demo_parser = subparsers.add_parser(
        "demo",
        help="Run with mock data for demonstration",
        description="Run WiFiRadar with realistic mock data for testing and demonstration.",
    )

    return parser


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the WiFiRadar CLI.

    Parses command-line arguments and dispatches to the appropriate
    command handler.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code: 0 success, 1 error, 2 no networks found.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Initialize color output
    colors = ColorOutput(no_color=args.no_color)

    # Handle no command
    if not args.command:
        parser.print_help()
        return 0

    # Verbose mode
    if args.verbose:
        platform_info = get_platform()
        colors.dim(f"Platform: {platform_info.system} {platform_info.release}\n")
        colors.dim(f"Scan tool: {platform_info.scan_tool}\n")

    # Dispatch to command handler
    handlers = {
        "scan": cmd_scan,
        "analyze": cmd_analyze,
        "history": cmd_history,
        "report": cmd_report,
        "monitor": cmd_monitor,
        "demo": cmd_demo,
    }

    handler = handlers.get(args.command)
    if handler is None:
        colors.red(f"Unknown command: {args.command}\n")
        parser.print_help()
        return 1

    try:
        return handler(args, colors)
    except KeyboardInterrupt:
        colors.yellow("\nOperation cancelled.\n")
        return 1
    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        else:
            colors.red(f"Error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
