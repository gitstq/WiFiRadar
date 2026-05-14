"""
WiFiRadar - Multi-Format Report Generator

Generates comprehensive reports from Wi-Fi scan results in multiple formats:
HTML (self-contained with inline CSS), JSON (structured data), Markdown
(for GitHub/wiki), and CSV (for spreadsheet analysis).

All reports include timestamp, scan metadata, analysis results, and
optimization recommendations.

Usage:
    from reporter import ReportGenerator

    gen = ReportGenerator(scan_result)
    gen.save_html('report.html')
    gen.save_json('report.json')
    gen.save_markdown('report.md')
    gen.save_csv('report.csv')

Zero external dependencies - uses only Python standard library.
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Re-use data models from visualizer module
from visualizer import NetworkInfo, ScanResult, Visualizer


# ---------------------------------------------------------------------------
# Analysis Helpers
# ---------------------------------------------------------------------------

def _analyze_networks(networks: List[NetworkInfo]) -> Dict[str, Any]:
    """Perform comprehensive analysis on scan results.

    Calculates statistics, interference scores, channel recommendations,
    and security assessment.

    Args:
        networks: List of detected NetworkInfo objects.

    Returns:
        Dictionary containing analysis results.
    """
    if not networks:
        return {
            'total_networks': 0,
            'avg_signal_dbm': 0,
            'strongest_network': None,
            'weakest_network': None,
            'band_distribution': {'2.4GHz': 0, '5GHz': 0},
            'channel_usage': {},
            'security_distribution': {},
            'interference_scores': {},
            'recommendations': ['No networks detected for analysis.'],
            'best_channels_24': [],
            'best_channels_5': [],
        }

    # Basic statistics
    signals = [n.signal_dbm for n in networks]
    avg_signal = sum(signals) / len(signals)
    strongest = max(networks, key=lambda n: n.signal_dbm)
    weakest = min(networks, key=lambda n: n.signal_dbm)

    # Band distribution
    band_dist: Dict[str, int] = {'2.4GHz': 0, '5GHz': 0}
    for n in networks:
        if n.band in band_dist:
            band_dist[n.band] += 1
        else:
            band_dist[n.band] = band_dist.get(n.band, 0) + 1

    # Channel usage
    channel_usage: Dict[int, int] = {}
    for n in networks:
        channel_usage[n.channel] = channel_usage.get(n.channel, 0) + 1

    # Security distribution
    sec_dist: Dict[str, int] = {}
    for n in networks:
        sec = n.security if n.security else 'UNKNOWN'
        sec_dist[sec] = sec_dist.get(sec, 0) + 1

    # Interference scores
    interference: Dict[int, float] = {}
    for n in networks:
        ch = n.channel
        sig_factor = (100 + n.signal_dbm) / 70
        if n.band == '2.4GHz':
            for adj in range(max(1, ch - 4), min(14, ch + 5)):
                w = 1.0 if adj == ch else (0.5 if abs(adj - ch) <= 2 else 0.2)
                interference[adj] = interference.get(adj, 0) + sig_factor * w
        else:
            interference[ch] = interference.get(ch, 0) + sig_factor

    # Find best channels (lowest interference)
    best_24: List[int] = []
    best_5: List[int] = []
    if interference:
        ch24 = sorted([c for c in interference if 1 <= c <= 13], key=lambda c: interference[c])
        ch5 = sorted([c for c in interference if c > 13], key=lambda c: interference[c])
        best_24 = ch24[:3]
        best_5 = ch5[:3]

    # Recommendations
    recommendations: List[str] = []
    if best_24:
        recommendations.append(
            f"Recommended 2.4GHz channels: {', '.join(str(c) for c in best_24)} "
            f"(lowest interference)"
        )
    if best_5:
        recommendations.append(
            f"Recommended 5GHz channels: {', '.join(str(c) for c in best_5)} "
            f"(lowest interference)"
        )

    # Channel congestion warnings
    for ch, count in channel_usage.items():
        if count >= 5:
            recommendations.append(
                f"WARNING: Channel {ch} is heavily congested with {count} networks. "
                f"Consider switching to a less crowded channel."
            )

    # Security recommendations
    open_nets = [n for n in networks if n.security and n.security.upper() in ('OPEN', 'OPN', '')]
    if open_nets:
        recommendations.append(
            f"SECURITY: {len(open_nets)} open (unsecured) network(s) detected. "
            f"Avoid connecting to open networks."
        )

    wep_nets = [n for n in networks if n.security and 'WEP' in n.security.upper()]
    if wep_nets:
        recommendations.append(
            f"SECURITY: {len(wep_nets)} network(s) using deprecated WEP encryption. "
            f"These networks are not secure."
        )

    if avg_signal > -55:
        recommendations.append(
            "Signal environment is excellent. Most networks have strong signals."
        )
    elif avg_signal < -75:
        recommendations.append(
            "Overall signal environment is weak. Consider moving closer to access "
            "points or removing sources of interference."
        )

    return {
        'total_networks': len(networks),
        'avg_signal_dbm': round(avg_signal, 1),
        'strongest_network': {
            'ssid': strongest.ssid,
            'bssid': strongest.bssid,
            'signal_dbm': strongest.signal_dbm,
            'channel': strongest.channel,
        },
        'weakest_network': {
            'ssid': weakest.ssid,
            'bssid': weakest.bssid,
            'signal_dbm': weakest.signal_dbm,
            'channel': weakest.channel,
        },
        'band_distribution': band_dist,
        'channel_usage': channel_usage,
        'security_distribution': sec_dist,
        'interference_scores': {k: round(v, 2) for k, v in interference.items()},
        'recommendations': recommendations,
        'best_channels_24': best_24,
        'best_channels_5': best_5,
    }


# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Multi-format report generator for Wi-Fi scan results.

    Generates self-contained HTML, JSON, Markdown, and CSV reports
    with comprehensive analysis and optimization recommendations.

    Args:
        scan_result: The scan result data to report on.

    Example:
        >>> gen = ReportGenerator(scan_result)
        >>> gen.save_html('/path/to/report.html')
        >>> gen.save_json('/path/to/report.json')
    """

    def __init__(self, scan_result: ScanResult) -> None:
        self.scan = scan_result
        self.analysis = _analyze_networks(scan_result.networks)
        self._generated_at = datetime.now(timezone.utc).isoformat()

    # -- HTML Report -----------------------------------------------------------

    def generate_html(self) -> str:
        """Generate a self-contained HTML report with inline CSS.

        Features:
        - Dark theme with gradient background
        - Signal strength bar charts using CSS
        - Channel congestion heatmap table
        - Band distribution using CSS-based charts
        - Security assessment summary
        - Optimization recommendations
        - Responsive design for mobile viewing

        Returns:
            Complete HTML string with inline styles.
        """
        networks = self.scan.networks
        analysis = self.analysis

        # Build network rows
        network_rows = ''
        sorted_nets = sorted(networks, key=lambda n: n.signal_dbm, reverse=True)
        for i, net in enumerate(sorted_nets):
            pct = Visualizer.dbm_to_percent(net.signal_dbm)
            quality = Visualizer.signal_quality_label(net.signal_dbm)
            if net.signal_dbm >= -60:
                bar_color = '#4ade80'  # green
                quality_color = '#4ade80'
            elif net.signal_dbm >= -75:
                bar_color = '#facc15'  # yellow
                quality_color = '#facc15'
            else:
                bar_color = '#f87171'  # red
                quality_color = '#f87171'

            ssid_display = net.ssid if net.ssid else '<em>(Hidden)</em>'
            security_display = net.security if net.security else 'UNKNOWN'

            network_rows += f'''
            <tr class="{'even' if i % 2 == 0 else 'odd'}">
                <td>{i + 1}</td>
                <td class="ssid">{ssid_display}</td>
                <td class="mono">{net.bssid}</td>
                <td class="mono">{net.signal_dbm} dBm</td>
                <td>
                    <div class="signal-bar-container">
                        <div class="signal-bar" style="width: {pct}%; background: {bar_color};"></div>
                        <span class="signal-pct">{pct}%</span>
                    </div>
                </td>
                <td style="color: {quality_color}; font-weight: bold;">{quality}</td>
                <td class="mono">Ch {net.channel}</td>
                <td>{net.band}</td>
                <td><span class="security-badge">{security_display}</span></td>
            </tr>'''

        # Channel usage heatmap
        channel_rows_24 = ''
        max_usage = max(analysis['channel_usage'].values()) if analysis['channel_usage'] else 1
        for ch in range(1, 14):
            count = analysis['channel_usage'].get(ch, 0)
            intensity = count / max_usage if max_usage > 0 else 0
            # Color gradient: green (low) -> yellow (mid) -> red (high)
            if intensity == 0:
                bg_color = '#1e293b'
            elif intensity < 0.33:
                bg_color = '#166534'
            elif intensity < 0.66:
                bg_color = '#854d0e'
            else:
                bg_color = '#991b1b'
            channel_rows_24 += f'''
            <td style="background: {bg_color}; text-align: center; padding: 8px; font-weight: bold;">
                <div>Ch {ch}</div>
                <div style="font-size: 0.85em; opacity: 0.8;">{count} net{'' if count == 1 else 's'}</div>
            </td>'''

        # Band distribution bars
        band_total = sum(analysis['band_distribution'].values())
        band_bars = ''
        band_colors = {'2.4GHz': '#3b82f6', '5GHz': '#8b5cf6'}
        for band, count in analysis['band_distribution'].items():
            pct = (count / band_total * 100) if band_total > 0 else 0
            color = band_colors.get(band, '#6b7280')
            band_bars += f'''
            <div class="band-item">
                <div class="band-label">{band}</div>
                <div class="band-bar-container">
                    <div class="band-bar" style="width: {pct}%; background: {color};"></div>
                </div>
                <div class="band-count">{count} ({pct:.1f}%)</div>
            </div>'''

        # Security distribution
        sec_items = ''
        sec_colors = {
            'WPA3': '#4ade80', 'WPA3-SAE': '#4ade80',
            'WPA2': '#22d3ee', 'WPA2-PSK': '#22d3ee', 'WPA2/WPA3': '#22d3ee',
            'WPA1': '#facc15', 'WPA-PSK': '#facc15', 'WPA': '#facc15',
            'WEP': '#f87171', 'OPEN': '#ef4444', 'OPN': '#ef4444',
        }
        for sec_type, count in sorted(analysis['security_distribution'].items(),
                                       key=lambda x: x[1], reverse=True):
            color = sec_colors.get(sec_type, '#9ca3af')
            sec_items += f'''
            <div class="security-item">
                <span class="security-dot" style="background: {color};"></span>
                <span class="security-name">{sec_type}</span>
                <span class="security-count">{count}</span>
            </div>'''

        # Recommendations
        rec_items = ''
        for rec in analysis['recommendations']:
            is_warning = rec.startswith('WARNING') or rec.startswith('SECURITY')
            rec_class = 'recommendation warning' if is_warning else 'recommendation'
            icon = '&#9888;' if is_warning else '&#10003;'
            rec_items += f'<div class="{rec_class}">{icon} {rec}</div>'

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WiFiRadar Report - {self.scan.timestamp}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
            color: #e2e8f0;
            min-height: 100vh;
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .header {{
            text-align: center;
            padding: 40px 20px;
            margin-bottom: 30px;
            background: linear-gradient(135deg, #1e293b, #334155);
            border-radius: 16px;
            border: 1px solid #334155;
        }}

        .header h1 {{
            font-size: 2.5em;
            background: linear-gradient(135deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
        }}

        .header .meta {{
            color: #94a3b8;
            font-size: 0.95em;
        }}

        .header .stats {{
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 20px;
            flex-wrap: wrap;
        }}

        .header .stat {{
            text-align: center;
        }}

        .header .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #60a5fa;
        }}

        .header .stat-label {{
            font-size: 0.85em;
            color: #94a3b8;
        }}

        .card {{
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            border: 1px solid #334155;
        }}

        .card h2 {{
            font-size: 1.3em;
            color: #60a5fa;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid #334155;
        }}

        .card h3 {{
            font-size: 1.1em;
            color: #94a3b8;
            margin: 16px 0 8px 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }}

        th {{
            background: #334155;
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            color: #e2e8f0;
            white-space: nowrap;
        }}

        td {{
            padding: 8px 12px;
            border-bottom: 1px solid #1e293b;
        }}

        tr.even {{ background: #1e293b; }}
        tr.odd {{ background: #253349; }}

        tr:hover {{ background: #334155; }}

        .mono {{ font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace; font-size: 0.85em; }}
        .ssid {{ font-weight: 600; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

        .signal-bar-container {{
            width: 100%;
            min-width: 80px;
            background: #0f172a;
            border-radius: 4px;
            height: 20px;
            position: relative;
            overflow: hidden;
        }}

        .signal-bar {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }}

        .signal-pct {{
            position: absolute;
            right: 8px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 0.75em;
            font-weight: bold;
            color: #e2e8f0;
        }}

        .security-badge {{
            background: #334155;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 500;
        }}

        .heatmap-table td {{
            border: 1px solid #334155;
            border-radius: 4px;
        }}

        .band-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }}

        .band-label {{
            width: 60px;
            font-weight: 600;
            font-size: 0.9em;
        }}

        .band-bar-container {{
            flex: 1;
            background: #0f172a;
            border-radius: 4px;
            height: 24px;
            overflow: hidden;
        }}

        .band-bar {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }}

        .band-count {{
            width: 100px;
            text-align: right;
            font-size: 0.9em;
            color: #94a3b8;
        }}

        .security-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 0;
            border-bottom: 1px solid #1e293b;
        }}

        .security-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            flex-shrink: 0;
        }}

        .security-name {{
            flex: 1;
            font-weight: 500;
        }}

        .security-count {{
            background: #334155;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.85em;
        }}

        .recommendation {{
            padding: 12px 16px;
            margin-bottom: 8px;
            background: #1e3a5f;
            border-radius: 8px;
            border-left: 4px solid #3b82f6;
            font-size: 0.9em;
        }}

        .recommendation.warning {{
            background: #3b1f1f;
            border-left-color: #ef4444;
        }}

        .footer {{
            text-align: center;
            padding: 20px;
            color: #64748b;
            font-size: 0.85em;
            margin-top: 20px;
        }}

        @media (max-width: 768px) {{
            body {{ padding: 10px; }}
            .header h1 {{ font-size: 1.8em; }}
            .header .stats {{ gap: 20px; }}
            table {{ font-size: 0.8em; }}
            th, td {{ padding: 6px 8px; }}
            .card {{ padding: 16px; }}
        }}

        @media (max-width: 480px) {{
            .header h1 {{ font-size: 1.4em; }}
            .header .stats {{ flex-direction: column; gap: 10px; }}
            .band-item {{ flex-wrap: wrap; }}
            .band-count {{ width: auto; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>WiFiRadar Analysis Report</h1>
            <div class="meta">
                Scan Time: {self.scan.timestamp} | Interface: {self.scan.interface} |
                Report Generated: {self._generated_at}
            </div>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{analysis['total_networks']}</div>
                    <div class="stat-label">Networks Found</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{analysis['avg_signal_dbm']} dBm</div>
                    <div class="stat-label">Avg Signal</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{analysis['band_distribution'].get('2.4GHz', 0)}</div>
                    <div class="stat-label">2.4 GHz</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{analysis['band_distribution'].get('5GHz', 0)}</div>
                    <div class="stat-label">5 GHz</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Detected Networks</h2>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>SSID</th>
                            <th>BSSID</th>
                            <th>Signal</th>
                            <th>Strength</th>
                            <th>Quality</th>
                            <th>Channel</th>
                            <th>Band</th>
                            <th>Security</th>
                        </tr>
                    </thead>
                    <tbody>
                        {network_rows}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card">
            <h2>Channel Congestion Heatmap (2.4 GHz)</h2>
            <table class="heatmap-table">
                <tr>
                    {channel_rows_24}
                </tr>
            </table>
            <div style="margin-top: 12px; font-size: 0.85em; color: #94a3b8;">
                <span style="display: inline-block; width: 12px; height: 12px; background: #1e293b; border: 1px solid #475569; vertical-align: middle; border-radius: 2px;"></span> Empty
                &nbsp;&nbsp;
                <span style="display: inline-block; width: 12px; height: 12px; background: #166534; vertical-align: middle; border-radius: 2px;"></span> Low
                &nbsp;&nbsp;
                <span style="display: inline-block; width: 12px; height: 12px; background: #854d0e; vertical-align: middle; border-radius: 2px;"></span> Medium
                &nbsp;&nbsp;
                <span style="display: inline-block; width: 12px; height: 12px; background: #991b1b; vertical-align: middle; border-radius: 2px;"></span> High
            </div>
        </div>

        <div class="card">
            <h2>Band Distribution</h2>
            {band_bars}
        </div>

        <div class="card">
            <h2>Security Assessment</h2>
            {sec_items}
        </div>

        <div class="card">
            <h2>Optimization Recommendations</h2>
            {rec_items if rec_items else '<p style="color: #94a3b8;">No specific recommendations at this time.</p>'}
        </div>

        <div class="footer">
            Generated by WiFiRadar | {self._generated_at} UTC
        </div>
    </div>
</body>
</html>'''
        return html

    # -- JSON Report -----------------------------------------------------------

    def generate_json(self) -> str:
        """Generate structured JSON report.

        Returns:
            JSON string containing scan metadata, network data, and analysis.
        """
        networks_data = []
        for net in self.scan.networks:
            networks_data.append({
                'ssid': net.ssid,
                'bssid': net.bssid,
                'signal_dbm': net.signal_dbm,
                'signal_percent': Visualizer.dbm_to_percent(net.signal_dbm),
                'signal_quality': Visualizer.signal_quality_label(net.signal_dbm),
                'channel': net.channel,
                'band': net.band,
                'security': net.security,
                'encryption': net.encryption,
            })

        report = {
            'report_info': {
                'generated_at': self._generated_at,
                'generator': 'WiFiRadar',
                'version': '1.0.0',
            },
            'scan_metadata': {
                'timestamp': self.scan.timestamp,
                'interface': self.scan.interface,
                'total_networks': len(self.scan.networks),
                'extra': self.scan.metadata,
            },
            'networks': networks_data,
            'analysis': self.analysis,
        }

        return json.dumps(report, indent=2, ensure_ascii=False, default=str)

    # -- Markdown Report -------------------------------------------------------

    def generate_markdown(self) -> str:
        """Generate Markdown report suitable for GitHub/wiki.

        Returns:
            Markdown formatted string with tables and analysis.
        """
        lines: List[str] = []
        analysis = self.analysis

        lines.append('# WiFiRadar Analysis Report')
        lines.append('')
        lines.append(f'**Scan Time:** {self.scan.timestamp}  ')
        lines.append(f'**Interface:** {self.scan.interface}  ')
        lines.append(f'**Networks Found:** {analysis["total_networks"]}  ')
        lines.append(f'**Average Signal:** {analysis["avg_signal_dbm"]} dBm  ')
        lines.append(f'**Report Generated:** {self._generated_at}  ')
        lines.append('')

        # Summary
        lines.append('## Summary')
        lines.append('')
        lines.append(f'| Metric | Value |')
        lines.append(f'|--------|-------|')
        lines.append(f'| Total Networks | {analysis["total_networks"]} |')
        lines.append(f'| Average Signal | {analysis["avg_signal_dbm"]} dBm |')
        if analysis['strongest_network']:
            sn = analysis['strongest_network']
            lines.append(f'| Strongest Signal | {sn["ssid"]} ({sn["signal_dbm"]} dBm) |')
        if analysis['weakest_network']:
            wn = analysis['weakest_network']
            lines.append(f'| Weakest Signal | {wn["ssid"]} ({wn["signal_dbm"]} dBm) |')
        lines.append(f'| 2.4 GHz Networks | {analysis["band_distribution"].get("2.4GHz", 0)} |')
        lines.append(f'| 5 GHz Networks | {analysis["band_distribution"].get("5GHz", 0)} |')
        lines.append('')

        # Network table
        lines.append('## Detected Networks')
        lines.append('')
        lines.append('| # | SSID | BSSID | Signal | Quality | Channel | Band | Security |')
        lines.append('|---|------|-------|--------|---------|---------|------|----------|')

        sorted_nets = sorted(self.scan.networks, key=lambda n: n.signal_dbm, reverse=True)
        for i, net in enumerate(sorted_nets):
            pct = Visualizer.dbm_to_percent(net.signal_dbm)
            quality = Visualizer.signal_quality_label(net.signal_dbm)
            ssid = net.ssid if net.ssid else '*(Hidden)*'
            sec = net.security if net.security else 'UNKNOWN'
            lines.append(
                f'| {i + 1} | {ssid} | `{net.bssid}` | {net.signal_dbm} dBm '
                f'({pct}%) | {quality} | Ch {net.channel} | {net.band} | {sec} |'
            )
        lines.append('')

        # Channel usage
        lines.append('## Channel Usage (2.4 GHz)')
        lines.append('')
        lines.append('| Channel | Networks | Interference Score |')
        lines.append('|---------|----------|-------------------|')
        for ch in range(1, 14):
            count = analysis['channel_usage'].get(ch, 0)
            score = analysis['interference_scores'].get(ch, 0)
            bar = '#' * count if count > 0 else '-'
            lines.append(f'| {ch} | {count} ({bar}) | {score:.2f} |')
        lines.append('')

        # 5GHz channels
        gh5_active = sorted(set(
            n.channel for n in self.scan.networks if n.band == '5GHz'
        ))
        if gh5_active:
            lines.append('## Channel Usage (5 GHz)')
            lines.append('')
            lines.append('| Channel | Networks | Interference Score |')
            lines.append('|---------|----------|-------------------|')
            for ch in gh5_active:
                count = analysis['channel_usage'].get(ch, 0)
                score = analysis['interference_scores'].get(ch, 0)
                bar = '#' * count if count > 0 else '-'
                lines.append(f'| {ch} | {count} ({bar}) | {score:.2f} |')
            lines.append('')

        # Band distribution
        lines.append('## Band Distribution')
        lines.append('')
        total = sum(analysis['band_distribution'].values())
        for band, count in analysis['band_distribution'].items():
            pct = (count / total * 100) if total > 0 else 0
            bar_len = int(pct / 5)
            bar = '#' * bar_len
            lines.append(f'- **{band}**: {count} networks ({pct:.1f}%) {bar}')
        lines.append('')

        # Security
        lines.append('## Security Assessment')
        lines.append('')
        for sec_type, count in sorted(analysis['security_distribution'].items(),
                                       key=lambda x: x[1], reverse=True):
            lines.append(f'- **{sec_type}**: {count} networks')
        lines.append('')

        # Recommendations
        lines.append('## Recommendations')
        lines.append('')
        for rec in analysis['recommendations']:
            if rec.startswith('WARNING') or rec.startswith('SECURITY'):
                lines.append(f'- :warning: {rec}')
            else:
                lines.append(f'- :white_check_mark: {rec}')
        lines.append('')

        lines.append('---')
        lines.append(f'*Generated by WiFiRadar at {self._generated_at} UTC*')

        return '\n'.join(lines)

    # -- CSV Report ------------------------------------------------------------

    def generate_csv(self) -> str:
        """Generate CSV export for spreadsheet analysis.

        Returns:
            CSV formatted string with network data and analysis columns.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            'SSID', 'BSSID', 'Signal_dBm', 'Signal_Percent', 'Signal_Quality',
            'Channel', 'Band', 'Security', 'Encryption',
            'Channel_Networks', 'Channel_Interference_Score',
        ])

        # Data rows
        sorted_nets = sorted(self.scan.networks, key=lambda n: n.signal_dbm, reverse=True)
        for net in sorted_nets:
            pct = Visualizer.dbm_to_percent(net.signal_dbm)
            quality = Visualizer.signal_quality_label(net.signal_dbm)
            ch_count = self.analysis['channel_usage'].get(net.channel, 0)
            ch_interference = self.analysis['interference_scores'].get(net.channel, 0)

            writer.writerow([
                net.ssid or '(Hidden)',
                net.bssid,
                net.signal_dbm,
                pct,
                quality,
                net.channel,
                net.band,
                net.security or 'UNKNOWN',
                net.encryption,
                ch_count,
                round(ch_interference, 2),
            ])

        return output.getvalue()

    # -- Save Methods ----------------------------------------------------------

    def save_html(self, filepath: str) -> str:
        """Generate and save HTML report to file.

        Args:
            filepath: Output file path for the HTML report.

        Returns:
            Absolute path of the saved file.

        Raises:
            OSError: If the file cannot be written.
        """
        content = self.generate_html()
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path) if os.path.dirname(abs_path) else '.', exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return abs_path

    def save_json(self, filepath: str) -> str:
        """Generate and save JSON report to file.

        Args:
            filepath: Output file path for the JSON report.

        Returns:
            Absolute path of the saved file.

        Raises:
            OSError: If the file cannot be written.
        """
        content = self.generate_json()
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path) if os.path.dirname(abs_path) else '.', exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return abs_path

    def save_markdown(self, filepath: str) -> str:
        """Generate and save Markdown report to file.

        Args:
            filepath: Output file path for the Markdown report.

        Returns:
            Absolute path of the saved file.

        Raises:
            OSError: If the file cannot be written.
        """
        content = self.generate_markdown()
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path) if os.path.dirname(abs_path) else '.', exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return abs_path

    def save_csv(self, filepath: str) -> str:
        """Generate and save CSV report to file.

        Args:
            filepath: Output file path for the CSV report.

        Returns:
            Absolute path of the saved file.

        Raises:
            OSError: If the file cannot be written.
        """
        content = self.generate_csv()
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path) if os.path.dirname(abs_path) else '.', exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        return abs_path

    def save_all(self, output_dir: str, base_name: str = 'wifiradar_report') -> Dict[str, str]:
        """Generate and save all report formats.

        Args:
            output_dir: Directory to save reports into.
            base_name: Base filename (without extension) for reports.

        Returns:
            Dictionary mapping format name to saved file path.
        """
        os.makedirs(output_dir, exist_ok=True)
        return {
            'html': self.save_html(os.path.join(output_dir, f'{base_name}.html')),
            'json': self.save_json(os.path.join(output_dir, f'{base_name}.json')),
            'markdown': self.save_markdown(os.path.join(output_dir, f'{base_name}.md')),
            'csv': self.save_csv(os.path.join(output_dir, f'{base_name}.csv')),
        }
