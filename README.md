<p align="center">
  <h1 align="center">📡 WiFiRadar</h1>
  <p align="center">
    <strong>Lightweight Wi-Fi Signal Intelligent Analysis & Visualization CLI Engine</strong>
  </p>
  <p align="center">
    <a href="#-project-introduction">English</a> ·
    <a href="README_zh.md">简体中文</a> ·
    <a href="README_zh-TW.md">繁體中文</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python 3.8+">
    <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
    <img src="https://img.shields.io/badge/Dependencies-Zero-success.svg" alt="Zero Dependencies">
    <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg" alt="Cross Platform">
    <img src="https://img.shields.io/badge/Tests-148%20Passed-brightgreen.svg" alt="Tests">
  </p>
</p>

---

## 🎉 Project Introduction

**WiFiRadar** is a zero-dependency, cross-platform Wi-Fi signal intelligent analysis and visualization CLI engine. It scans nearby Wi-Fi networks, performs deep analysis on channel congestion, interference levels, and signal quality, then generates actionable optimization recommendations and beautiful reports.

### 💡 Why WiFiRadar?

Ever wondered why your Wi-Fi is slow even with a strong signal? The answer often lies in **channel congestion** and **interference from neighboring networks**. WiFiRadar gives you a complete picture of your wireless environment:

- 📊 **Visualize** all nearby networks with signal strength charts
- 🔍 **Analyze** channel congestion and interference scores
- ✅ **Recommend** the best channels for your router
- 📈 **Track** signal strength changes over time
- 📄 **Export** professional HTML/JSON/Markdown/CSV reports

### 🌟 Differentiation Highlights

| Feature | WiFiRadar | Typical Wi-Fi Tools |
|---------|-----------|-------------------|
| External Dependencies | **Zero** | Often requires GUI frameworks |
| Output Formats | **4 formats** (HTML/JSON/MD/CSV) | Usually 1-2 formats |
| History Tracking | **SQLite-based** with trends | Rarely available |
| Channel Analysis | **Congestion + Interference scoring** | Basic channel list only |
| Cross-Platform | **Linux/macOS/Windows** | Often platform-specific |
| Installation | **Single file copy** | pip install / package manager |

---

## ✨ Core Features

### 📡 Smart Scanning
- **Auto-detect platform**: Uses `nmcli` (Linux), `airport` (macOS), or `netsh` (Windows)
- **Comprehensive data**: SSID, BSSID, signal strength, channel, frequency, security, band
- **Demo mode**: Built-in mock data for testing and demonstration

### 📊 Signal Analysis
- **Channel congestion analysis**: Counts networks per channel with overlap detection
- **Interference scoring**: Weighted scoring based on same-channel and adjacent-channel interference
- **Signal quality grading**: A/B/C/D/F grades based on signal strength and congestion
- **Best channel recommendation**: Optimal channels for both 2.4GHz and 5GHz bands
- **Security assessment**: WPA3/WPA2/WPA/WEP/Open classification and evaluation
- **Band utilization**: 2.4GHz vs 5GHz distribution analysis

### 🎨 Terminal Visualization
- **Signal strength bar chart**: Color-coded (🟢 green / 🟡 yellow / 🔴 red)
- **Channel usage heatmap**: Unicode block characters (█▓▒░) for 2.4GHz and 5GHz
- **Band distribution chart**: ASCII horizontal bar chart
- **Interference score visualization**: Per-channel interference levels
- **Security type distribution**: Protocol usage overview

### 📄 Multi-Format Reports
- **HTML Report**: Self-contained dark-themed page with CSS charts and responsive design
- **JSON Report**: Structured data export for programmatic use
- **Markdown Report**: GitHub/wiki friendly format with tables
- **CSV Report**: Spreadsheet-compatible format for data analysis

### 📈 Scan History
- **SQLite storage**: Persistent scan history with WAL mode
- **Trend analysis**: Signal strength changes over time
- **Change detection**: New/removed networks between scans
- **Data export**: Trend data in CSV/JSON format

### 🖥️ CLI Commands

| Command | Description |
|---------|-------------|
| `wifiradar scan` | Scan and display Wi-Fi networks |
| `wifiradar analyze` | Full analysis with recommendations |
| `wifiradar report` | Generate comprehensive HTML report |
| `wifiradar history` | Manage scan history (list/show/trend/compare/clean) |
| `wifiradar monitor` | Continuous monitoring mode |
| `wifiradar demo` | Run with mock data for demonstration |

---

## 🚀 Quick Start

### 📋 Prerequisites

- **Python 3.8+** (no other dependencies required!)
- **Platform**: Linux, macOS, or Windows
- **Wi-Fi adapter** (for real scanning; demo mode works without)

### ⚡ Installation

```bash
# Clone the repository
git clone https://github.com/gitstq/WiFiRadar.git
cd WiFiRadar

# That's it! No pip install needed - zero dependencies!
# Run directly:
python3 wifiradar.py --version
```

### 🎮 Basic Usage

```bash
# Scan nearby Wi-Fi networks
python3 wifiradar.py scan

# Full analysis with optimization recommendations
python3 wifiradar.py analyze

# Generate a beautiful HTML report
python3 wifiradar.py report

# Run demo mode (no Wi-Fi hardware needed)
python3 wifiradar.py demo

# Show top 10 strongest networks
python3 wifiradar.py scan --top 10

# Filter by 5GHz band only
python3 wifiradar.py scan --filter-band 5GHz

# Export scan results as JSON
python3 wifiradar.py scan --json

# Export as CSV for spreadsheet analysis
python3 wifiradar.py scan --csv

# Generate Markdown report
python3 wifiradar.py scan --markdown
```

### 📊 Advanced Usage

```bash
# Continuous monitoring (scan every 30 seconds)
python3 wifiradar.py monitor --interval 30

# Monitor with alert when signal drops below -70 dBm
python3 wifiradar.py monitor --alert-threshold -70

# View scan history
python3 wifiradar.py history list

# Show signal trend for a specific network
python3 wifiradar.py history trend --bssid AA:BB:CC:DD:EE:FF

# Compare two scans
python3 wifiradar.py history compare --scan-ids 1,2

# Generate report and save to custom path
python3 wifiradar.py report --output ~/wifi_report.html

# Sort results by channel
python3 wifiradar.py scan --sort-by channel

# Filter networks with minimum signal strength
python3 wifiradar.py scan --min-signal -60
```

---

## 📖 Detailed Guide

### Signal Quality Grades

| Grade | Signal (dBm) | Quality | Description |
|-------|-------------|---------|-------------|
| **A** | -30 to -50 | Excellent | Perfect for all activities |
| **B** | -51 to -60 | Good | Great for streaming and gaming |
| **C** | -61 to -70 | Fair | Suitable for browsing and email |
| **D** | -71 to -80 | Poor | Intermittent connectivity |
| **F** | < -80 | No Signal | Unusable |

### Channel Congestion Levels

| Level | Score | Description |
|-------|-------|-------------|
| 🟢 **Low** | 0-30 | Minimal interference, ideal |
| 🟡 **Medium** | 31-60 | Some interference, acceptable |
| 🟠 **High** | 61-80 | Significant interference, consider switching |
| 🔴 **Critical** | 81-100 | Severe congestion, change channel immediately |

### Output Formats

- **HTML**: Self-contained report with dark theme, CSS charts, responsive design — perfect for sharing
- **JSON**: Structured data with full analysis results — ideal for integration and automation
- **Markdown**: Table-based format — great for GitHub issues, wikis, and documentation
- **CSV**: Spreadsheet-ready format — perfect for data analysis in Excel/Google Sheets

---

## 💡 Design Philosophy & Roadmap

### Design Principles

1. **Zero Dependencies**: Pure Python standard library — no pip install, no version conflicts
2. **Cross-Platform**: Works identically on Linux, macOS, and Windows
3. **Privacy First**: All data stays local — no cloud services, no data collection
4. **Developer-Friendly**: Structured output formats for integration with other tools
5. **Progressive Enhancement**: CLI → TUI → HTML reports, use what you need

### Tech Stack

- **Language**: Python 3.8+ (standard library only)
- **Storage**: SQLite3 (built-in)
- **CLI**: argparse (built-in)
- **Visualization**: ANSI escape codes + Unicode characters
- **Reports**: HTML/CSS (inline), JSON, Markdown, CSV

### 🗺️ Roadmap

- [ ] **v1.1**: Real-time signal monitoring dashboard
- [ ] **v1.2**: Wi-Fi speed testing integration
- [ ] **v1.3**: Geographic heatmap export (GPS coordinates)
- [ ] **v1.4**: Scheduled automatic scanning with alerts
- [ ] **v2.0**: Web UI dashboard for remote monitoring
- [ ] **v2.1**: Multi-interface support (simultaneous scanning)
- [ ] **v2.2**: Enterprise reporting with PDF export

---

## 📦 Packaging & Deployment

### As a Standalone Script

```bash
# Simply copy wifiradar.py to any directory
cp wifiradar.py /usr/local/bin/wifiradar
chmod +x /usr/local/bin/wifiradar

# Now you can run it from anywhere
wifiradar scan
```

### As a Python Package

```bash
# Install in development mode
cd WiFiRadar
pip install -e .

# Now use the wifiradar command directly
wifiradar scan
wifiradar analyze
wifiradar report
```

### Systemd Service (Linux)

```bash
# Create a monitoring service
sudo cp wifiradar.service /etc/systemd/system/
sudo systemctl enable wifiradar
sudo systemctl start wifiradar
```

### Cron Job (Scheduled Scanning)

```bash
# Add to crontab - scan every hour
0 * * * * /usr/bin/python3 /path/to/wifiradar.py scan --json >> /var/log/wifiradar.log
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

### How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Write** code with proper type hints and docstrings
4. **Test** your changes (`python -m pytest tests/`)
5. **Commit** with conventional commits (`git commit -m 'feat: add amazing feature'`)
6. **Push** to your branch (`git push origin feature/amazing-feature`)
7. **Open** a Pull Request

### Commit Convention

| Type | Description |
|------|-------------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation update |
| `refactor:` | Code refactoring |
| `test:` | Test additions/modifications |
| `chore:` | Build/tooling changes |

### Issue Reporting

When reporting issues, please include:
- Operating system and version
- Python version
- Output of `wifiradar --version`
- Error message or unexpected behavior
- Steps to reproduce

---

## 📄 License

This project is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2026 gitstq

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/gitstq">gitstq</a>
</p>
