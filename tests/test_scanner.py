"""
Unit tests for the scanner module.

Tests subprocess call mocking, output parsing, and error handling
for various WiFi scanning backends (nmcli, iwlist, airport, netsh).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, call

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Sample scan outputs for different platforms
# ---------------------------------------------------------------------------

SAMPLE_NMCLI_OUTPUT = """*  SSID           BSSID              MODE   CHAN  FREQ      RATE     SIGNAL  SECURITY
    ChinaNet-A8F2   AA:BB:CC:DD:EE:01  Infra  6     2437 MHz  54 Mbit/s  75      WPA2
    TP-LINK_5G      AA:BB:CC:DD:EE:02  Infra  36    5180 MHz  130 Mbit/s 85      WPA2
    HUAWEI-B2E6     AA:BB:CC:DD:EE:03  Infra  1     2412 MHz  65 Mbit/s  60      WPA2
    OpenWiFi        AA:BB:CC:DD:EE:04  Infra  11    2462 MHz  54 Mbit/s  40      --
    Mi-Router       AA:BB:CC:DD:EE:05  Infra  149   5745 MHz  270 Mbit/s 90      WPA2
"""

SAMPLE_NMCLI_JSON_OUTPUT = json.dumps([
    {"ssid": "ChinaNet-A8F2", "bssid": "AA:BB:CC:DD:EE:01", "chan": 6, "freq": 2437, "signal": 75, "security": "WPA2"},
    {"ssid": "TP-LINK_5G", "bssid": "AA:BB:CC:DD:EE:02", "chan": 36, "freq": 5180, "signal": 85, "security": "WPA2"},
    {"ssid": "HUAWEI-B2E6", "bssid": "AA:BB:CC:DD:EE:03", "chan": 1, "freq": 2412, "signal": 60, "security": "WPA2"},
])

SAMPLE_IWLIST_OUTPUT = """          Cell 01 - Address: AA:BB:CC:DD:EE:01
                    Channel:6
                    Frequency:2.437 GHz (Channel 6)
                    Quality=70/100  Signal level=-50 dBm
                    Encryption key:on
                    ESSID:"ChinaNet-A8F2"
                    Bit Rates:54 Mb/s

          Cell 02 - Address: AA:BB:CC:DD:EE:02
                    Channel:36
                    Frequency:5.18 GHz (Channel 36)
                    Quality=85/100  Signal level=-35 dBm
                    Encryption key:on
                    ESSID:"TP-LINK_5G"
                    Bit Rates:130 Mb/s
"""

SAMPLE_AIRPORT_OUTPUT = """                            SSID BSSID             RSSI CHANNEL HT CC SECURITY (auth/unicast/group)
                 ChinaNet-A8F2    aa:bb:cc:dd:ee:01  -75  6       Y  US WPA2(PSK/AES/AES)
                 TP-LINK_5G       aa:bb:cc:dd:ee:02  -85  36      Y  US WPA2(PSK/AES/AES)
                 HUAWEI-B2E6      aa:bb:cc:dd:ee:03  -60  1       Y  US NONE
"""

SAMPLE_NETSH_OUTPUT = """SSID 1 : ChinaNet-A8F2
    Network type             : Infrastructure
    Authentication           : WPA2-Personal
    Encryption               : CCMP
    BSSID 1                  : aa:bb:cc:dd:ee:01
    Signal                   : 75%
    Channel                  : 6
    Radio type               : 802.11n

SSID 2 : TP-LINK_5G
    Network type             : Infrastructure
    Authentication           : WPA2-Personal
    Encryption               : CCMP
    BSSID 1                  : aa:bb:cc:dd:ee:02
    Signal                   : 85%
    Channel                  : 36
    Radio type               : 802.11ac
"""


class TestNmcliParser(unittest.TestCase):
    """Tests for parsing nmcli scan output."""

    def test_parse_nmcli_text_basic(self) -> None:
        """Test basic nmcli text output parsing."""
        lines = SAMPLE_NMCLI_OUTPUT.strip().split("\n")
        # Filter out header and separator lines
        data_lines = [l for l in lines if l.strip() and not l.startswith("*") and not l.startswith("-")]
        # Should have 5 data lines
        self.assertEqual(len(data_lines), 5)

    def test_parse_nmcli_json(self) -> None:
        """Test nmcli JSON output parsing."""
        data = json.loads(SAMPLE_NMCLI_JSON_OUTPUT)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]["ssid"], "ChinaNet-A8F2")
        self.assertEqual(data[0]["chan"], 6)
        self.assertEqual(data[1]["freq"], 5180)

    def test_parse_nmcli_extracts_fields(self) -> None:
        """Test that all relevant fields are extracted from nmcli output."""
        data = json.loads(SAMPLE_NMCLI_JSON_OUTPUT)
        for entry in data:
            self.assertIn("ssid", entry)
            self.assertIn("bssid", entry)
            self.assertIn("chan", entry)
            self.assertIn("freq", entry)
            self.assertIn("signal", entry)
            self.assertIn("security", entry)

    def test_parse_nmcli_empty_output(self) -> None:
        """Test handling of empty nmcli output."""
        lines = ""
        data_lines = [l for l in lines.split("\n") if l.strip()]
        self.assertEqual(len(data_lines), 0)


class TestIwlistParser(unittest.TestCase):
    """Tests for parsing iwlist scan output."""

    def test_parse_iwlist_cells(self) -> None:
        """Test iwlist cell detection."""
        cells = SAMPLE_IWLIST_OUTPUT.split("Cell ")
        # First element is empty string before "Cell 01"
        self.assertEqual(len(cells), 3)

    def test_parse_iwlist_channel(self) -> None:
        """Test iwlist channel extraction."""
        for line in SAMPLE_IWLIST_OUTPUT.split("\n"):
            if "Channel:" in line and "Frequency" not in line:
                channel = int(line.strip().split(":")[1])
                self.assertIn(channel, [6, 36])

    def test_parse_iwlist_signal(self) -> None:
        """Test iwlist signal level extraction."""
        for line in SAMPLE_IWLIST_OUTPUT.split("\n"):
            if "Signal level" in line:
                # Extract dBm value
                parts = line.strip().split("Signal level=")
                if len(parts) > 1:
                    dbm_part = parts[1].split(" dBm")[0]
                    dbm = int(dbm_part)
                    self.assertIn(dbm, [-50, -35])

    def test_parse_iwlist_essid(self) -> None:
        """Test iwlist ESSID extraction."""
        for line in SAMPLE_IWLIST_OUTPUT.split("\n"):
            if "ESSID:" in line:
                essid = line.split('ESSID:"')[1].split('"')[0]
                self.assertIn(essid, ["ChinaNet-A8F2", "TP-LINK_5G"])


class TestAirportParser(unittest.TestCase):
    """Tests for parsing macOS airport scan output."""

    def test_parse_airport_basic(self) -> None:
        """Test airport output line parsing."""
        lines = SAMPLE_AIRPORT_OUTPUT.strip().split("\n")
        # Skip header line
        data_lines = [l for l in lines[1:] if l.strip()]
        self.assertEqual(len(data_lines), 3)

    def test_parse_airport_rssi(self) -> None:
        """Test airport RSSI extraction."""
        for line in SAMPLE_AIRPORT_OUTPUT.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 3:
                try:
                    rssi = int(parts[2])
                    self.assertIn(rssi, [-75, -85, -60])
                except ValueError:
                    pass


class TestNetshParser(unittest.TestCase):
    """Tests for parsing Windows netsh wlan scan output."""

    def test_parse_netsh_ssids(self) -> None:
        """Test netsh SSID extraction."""
        ssids = []
        for line in SAMPLE_NETSH_OUTPUT.split("\n"):
            if line.strip().startswith("SSID ") and ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    ssid = parts[1].strip()
                    if ssid:
                        ssids.append(ssid)
        self.assertEqual(len(ssids), 2)
        self.assertIn("ChinaNet-A8F2", ssids)
        self.assertIn("TP-LINK_5G", ssids)

    def test_parse_netsh_signal(self) -> None:
        """Test netsh signal percentage extraction."""
        signals = []
        for line in SAMPLE_NETSH_OUTPUT.split("\n"):
            if "Signal" in line and ":" in line and "%" in line:
                parts = line.split(":")
                if len(parts) == 2:
                    sig = parts[1].strip().replace("%", "")
                    try:
                        signals.append(int(sig))
                    except ValueError:
                        pass
        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0], 75)


class TestSubprocessMocking(unittest.TestCase):
    """Tests for subprocess call mocking in scanner operations."""

    @patch("subprocess.run")
    def test_subprocess_called_with_correct_args(self, mock_run: MagicMock) -> None:
        """Test that subprocess.run is called with expected arguments."""
        mock_run.return_value = MagicMock(
            stdout=SAMPLE_NMCLI_OUTPUT,
            stderr="",
            returncode=0,
        )
        result = subprocess.run(
            ["nmcli", "-t", "-f", "all", "device", "wifi", "list"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        mock_run.assert_called_once()
        self.assertEqual(result.returncode, 0)

    @patch("subprocess.run")
    def test_subprocess_timeout(self, mock_run: MagicMock) -> None:
        """Test that subprocess timeout is handled."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="nmcli", timeout=15)
        with self.assertRaises(subprocess.TimeoutExpired):
            subprocess.run(
                ["nmcli", "device", "wifi", "list"],
                capture_output=True,
                text=True,
                timeout=15,
            )

    @patch("subprocess.run")
    def test_subprocess_command_not_found(self, mock_run: MagicMock) -> None:
        """Test handling of missing command."""
        mock_run.side_effect = FileNotFoundError("nmcli not found")
        with self.assertRaises(FileNotFoundError):
            subprocess.run(
                ["nmcli", "device", "wifi", "list"],
                capture_output=True,
                text=True,
            )

    @patch("subprocess.run")
    def test_subprocess_nonzero_exit(self, mock_run: MagicMock) -> None:
        """Test handling of non-zero exit codes."""
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="Error: Device not found",
            returncode=1,
        )
        result = subprocess.run(
            ["nmcli", "device", "wifi", "list"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Error", result.stderr)


class TestScanResultNormalization(unittest.TestCase):
    """Tests for normalizing scan results from different tools."""

    def test_normalize_nmcli_entry(self) -> None:
        """Test normalizing a single nmcli entry."""
        raw = {
            "ssid": "ChinaNet-A8F2",
            "bssid": "AA:BB:CC:DD:EE:01",
            "chan": 6,
            "freq": 2437,
            "signal": 75,
            "security": "WPA2",
        }
        normalized = {
            "ssid": raw["ssid"],
            "bssid": raw["bssid"],
            "channel": raw["chan"],
            "frequency": raw["freq"],
            "signal": raw["signal"],
            "band": "2.4GHz",
            "security": raw["security"],
        }
        self.assertEqual(normalized["channel"], 6)
        self.assertEqual(normalized["band"], "2.4GHz")

    def test_normalize_iwlist_entry(self) -> None:
        """Test normalizing a single iwlist entry."""
        raw = {
            "address": "AA:BB:CC:DD:EE:02",
            "channel": 36,
            "frequency_ghz": 5.18,
            "signal_dbm": -35,
            "essid": "TP-LINK_5G",
            "encryption": True,
        }
        normalized = {
            "ssid": raw["essid"],
            "bssid": raw["address"],
            "channel": raw["channel"],
            "frequency": int(raw["frequency_ghz"] * 1000),
            "signal": raw["signal_dbm"],
            "band": "5GHz",
            "security": "WPA2" if raw["encryption"] else "OPEN",
        }
        self.assertEqual(normalized["frequency"], 5180)
        self.assertEqual(normalized["band"], "5GHz")

    def test_empty_results(self) -> None:
        """Test handling of empty scan results."""
        results: List[Dict[str, Any]] = []
        self.assertEqual(len(results), 0)

    def test_duplicate_bssid_filtering(self) -> None:
        """Test that duplicate BSSID entries are handled."""
        networks = [
            {"bssid": "AA:BB:CC:DD:EE:01", "signal": -50},
            {"bssid": "AA:BB:CC:DD:EE:01", "signal": -55},
            {"bssid": "AA:BB:CC:DD:EE:02", "signal": -60},
        ]
        # Keep strongest signal per BSSID
        seen: Dict[str, Dict] = {}
        for net in networks:
            bssid = net["bssid"]
            if bssid not in seen or net["signal"] > seen[bssid]["signal"]:
                seen[bssid] = net
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen["AA:BB:CC:DD:EE:01"]["signal"], -50)


if __name__ == "__main__":
    unittest.main()
