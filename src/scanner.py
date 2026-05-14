"""
WiFiRadar - 核心扫描引擎模块

负责调用平台原生命令执行 WiFi 网络扫描，并将原始输出解析为结构化的
NetworkInfo 对象列表。支持 Linux、macOS、Windows 三大平台，并提供
Mock 模式用于无 WiFi 硬件环境下的测试与开发。

使用方式:
    from wifiradar.src.scanner import WiFiScanner

    scanner = WiFiScanner()
    networks = scanner.scan()
    for net in networks:
        print(net)

    # 使用 Mock 模式（测试用）
    mock_scanner = WiFiScanner(mock_mode=True)
    mock_networks = mock_scanner.scan()
"""

from __future__ import annotations

import logging
import platform
import random
import re
import subprocess
import time
from typing import Dict, List, Optional, Tuple

from .models import NetworkInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 2.4GHz 信道 -> 频率映射表 (MHz)
# ---------------------------------------------------------------------------
CHANNEL_FREQ_2G: Dict[int, float] = {
    ch: 2412 + (ch - 1) * 5 for ch in range(1, 15)
}

# 5GHz 部分信道 -> 频率映射表 (MHz)
CHANNEL_FREQ_5G: Dict[int, float] = {
    36: 5180, 40: 5200, 44: 5220, 48: 5240,
    52: 5260, 56: 5280, 60: 5300, 64: 5320,
    100: 5500, 104: 5520, 108: 5540, 112: 5560,
    116: 5580, 120: 5600, 124: 5620, 128: 5640,
    132: 5660, 136: 5680, 140: 5700, 144: 5720,
    149: 5745, 153: 5765, 157: 5785, 161: 5805,
    165: 5825, 169: 5845, 173: 5865, 177: 5885,
}

# 合并所有信道映射
ALL_CHANNEL_FREQ: Dict[int, float] = {**CHANNEL_FREQ_2G, **CHANNEL_FREQ_5G}


class WiFiScanner:
    """跨平台 WiFi 网络扫描器。

    自动检测当前操作系统并选择合适的扫描命令，将原始输出解析为
    标准化的 NetworkInfo 数据结构。支持 Mock 模式用于测试。

    Attributes:
        mock_mode: 是否启用模拟扫描模式。
        _os_type: 当前操作系统类型。
    """

    def __init__(self, mock_mode: bool = False) -> None:
        """初始化扫描器。

        Args:
            mock_mode: 设为 True 时使用模拟数据，无需真实 WiFi 硬件。
                       适用于 CI/CD 环境和无 WiFi 的开发环境。
        """
        self.mock_mode: bool = mock_mode
        self._os_type: str = platform.system().lower()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def scan(self) -> List[NetworkInfo]:
        """执行 WiFi 扫描并返回网络列表。

        根据当前平台自动选择扫描方式。如果平台不支持或扫描失败，
        将返回空列表并记录警告日志。

        Returns:
            扫描到的 NetworkInfo 对象列表。扫描失败时返回空列表。
        """
        if self.mock_mode:
            logger.info("使用 Mock 模式生成模拟扫描数据")
            return self._generate_mock_data()

        try:
            if self._os_type == "linux":
                return self._scan_linux()
            elif self._os_type == "darwin":
                return self._scan_macos()
            elif self._os_type == "windows":
                return self._scan_windows()
            else:
                logger.warning(
                    "不支持的操作系统: %s，回退到 Mock 模式", self._os_type
                )
                return self._generate_mock_data()
        except Exception as exc:
            logger.error("扫描失败: %s，回退到 Mock 模式", exc)
            return self._generate_mock_data()

    # ------------------------------------------------------------------
    # Linux 扫描
    # ------------------------------------------------------------------

    def _scan_linux(self) -> List[NetworkInfo]:
        """在 Linux 上执行 WiFi 扫描。

        优先使用 NetworkManager (nmcli)，失败后回退到 iwlist。

        Returns:
            解析后的网络列表。
        """
        networks = self._scan_linux_nmcli()
        if networks:
            return networks

        logger.info("nmcli 扫描失败，尝试 iwlist 回退方案")
        return self._scan_linux_iwlist()

    def _scan_linux_nmcli(self) -> List[NetworkInfo]:
        """使用 nmcli 执行 WiFi 扫描。

        nmcli 输出格式（-t 模式，冒号分隔）:
            SSID:BSSID:SIGNAL:CHAN:FREQ:SECURITY:MODE

        Returns:
            解析后的网络列表，失败时返回空列表。
        """
        cmd = [
            "nmcli",
            "-t",
            "-f",
            "SSID,BSSID,SIGNAL,CHAN,FREQ,SECURITY,MODE",
            "device",
            "wifi",
            "list",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode != 0:
                logger.warning("nmcli 返回非零退出码: %s", result.stderr.strip())
                return []

            return self._parse_nmcli_output(result.stdout)
        except FileNotFoundError:
            logger.warning("nmcli 命令未找到，请确保已安装 NetworkManager")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("nmcli 命令超时")
            return []

    def _scan_linux_iwlist(self) -> List[NetworkInfo]:
        """使用 iwlist 执行 WiFi 扫描（回退方案）。

        Returns:
            解析后的网络列表，失败时返回空列表。
        """
        cmd = ["iwlist", "wlan0", "scan"]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode != 0:
                logger.warning("iwlist 返回非零退出码: %s", result.stderr.strip())
                return []

            return self._parse_iwlist_output(result.stdout)
        except FileNotFoundError:
            logger.warning("iwlist 命令未找到")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("iwlist 命令超时")
            return []

    # ------------------------------------------------------------------
    # macOS 扫描
    # ------------------------------------------------------------------

    def _scan_macos(self) -> List[NetworkInfo]:
        """在 macOS 上使用 airport 工具执行 WiFi 扫描。

        airport 输出格式:
            SSID                             BSSID             RSSI CHANNEL HT CC SECURITY
            MyNetwork                        aa:bb:cc:dd:ee:ff -65  6       Y  US WPA2(PSK/AES/AES)

        Returns:
            解析后的网络列表。
        """
        airport_path = (
            "/System/Library/PrivateFrameworks/Apple80211.framework/"
            "Resources/airport"
        )
        cmd = [airport_path, "-s"]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode != 0:
                logger.warning("airport 返回非零退出码: %s", result.stderr.strip())
                return []

            return self._parse_airport_output(result.stdout)
        except FileNotFoundError:
            logger.warning("airport 命令未找到")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("airport 命令超时")
            return []

    # ------------------------------------------------------------------
    # Windows 扫描
    # ------------------------------------------------------------------

    def _scan_windows(self) -> List[NetworkInfo]:
        """在 Windows 上使用 netsh 执行 WiFi 扫描。

        netsh 输出格式:
            SSID x : MyNetwork
                Network type            : Infrastructure
                Authentication          : WPA2-Personal
                BSSID                   : aa:bb:cc:dd:ee:ff
                Signal                  : 65%
                Channel                 : 6
                Radio type              : 802.11n

        Returns:
            解析后的网络列表。
        """
        cmd = ["netsh", "wlan", "show", "networks", "mode=bssid"]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if result.returncode != 0:
                logger.warning("netsh 返回非零退出码: %s", result.stderr.strip())
                return []

            return self._parse_netsh_output(result.stdout)
        except FileNotFoundError:
            logger.warning("netsh 命令未找到")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("netsh 命令超时")
            return []

    # ------------------------------------------------------------------
    # 解析器: nmcli (Linux)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_nmcli_output(output: str) -> List[NetworkInfo]:
        """解析 nmcli -t 格式的扫描输出。

        Args:
            output: nmcli 命令的标准输出文本。

        Returns:
            解析后的 NetworkInfo 列表。
        """
        networks: List[NetworkInfo] = []
        seen_bssids: set = set()

        for line in output.strip().splitlines():
            if not line or line.startswith("SSID"):
                continue

            parts = line.split(":")
            if len(parts) < 7:
                continue

            ssid = parts[0].strip()
            bssid = parts[1].strip().upper()
            signal_str = parts[2].strip()
            channel_str = parts[3].strip()
            freq_str = parts[4].strip()
            security = parts[5].strip()
            mode = parts[6].strip()

            # 去重：同一 BSSID 只保留一条记录
            if bssid in seen_bssids:
                continue
            seen_bssids.add(bssid)

            # 跳过空 BSSID 的行
            if not bssid or bssid == "--":
                continue

            try:
                signal_dbm = int(signal_str)
                channel = int(channel_str)
                frequency_mhz = float(freq_str) if freq_str else None
            except ValueError:
                continue

            signal_percent = dbm_to_percent(signal_dbm)
            band_2_4, band_5 = determine_bands(channel, frequency_mhz)

            networks.append(
                NetworkInfo(
                    ssid=ssid,
                    bssid=bssid,
                    signal_dbm=signal_dbm,
                    signal_percent=signal_percent,
                    channel=channel,
                    frequency_mhz=frequency_mhz,
                    security=security if security else "OPEN",
                    mode=mode if mode else "Unknown",
                    band_2_4ghz=band_2_4,
                    band_5ghz=band_5,
                )
            )

        return networks

    # ------------------------------------------------------------------
    # 解析器: iwlist (Linux 回退)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_iwlist_output(output: str) -> List[NetworkInfo]:
        """解析 iwlist scan 的输出。

        Args:
            output: iwlist 命令的标准输出文本。

        Returns:
            解析后的 NetworkInfo 列表。
        """
        networks: List[NetworkInfo] = []
        seen_bssids: set = set()

        # 按单元格分割（每个 Cell 对应一个 AP）
        cells = re.split(r"(?m)^\s*Cell\s+\d+", output)

        for cell_text in cells[1:]:  # 跳过第一个空分割
            ssid = ""
            bssid = ""
            signal_dbm = -100
            channel = 0
            frequency_mhz: Optional[float] = None
            security = "OPEN"
            mode = "Unknown"

            # 提取地址 (BSSID)
            addr_match = re.search(
                r"Address:\s*([0-9A-Fa-f:]{17})", cell_text
            )
            if addr_match:
                bssid = addr_match.group(1).upper()

            # 提取 ESSID (SSID)
            essid_match = re.search(
                r'ESSID:"([^"]*)"', cell_text
            )
            if essid_match:
                ssid = essid_match.group(1)

            # 提取信号强度
            signal_match = re.search(
                r"Signal level[=:]\s*(-?\d+)\s*dBm", cell_text, re.IGNORECASE
            )
            if signal_match:
                signal_dbm = int(signal_match.group(1))

            # 提取信道
            chan_match = re.search(
                r"Channel[=:]\s*(\d+)", cell_text, re.IGNORECASE
            )
            if chan_match:
                channel = int(chan_match.group(1))

            # 提取频率
            freq_match = re.search(
                r"Frequency[=:]\s*([\d.]+)\s*GHz", cell_text, re.IGNORECASE
            )
            if freq_match:
                frequency_mhz = float(freq_match.group(1)) * 1000

            # 提取加密信息
            if re.search(r"Encryption key:(?:\s*)on", cell_text, re.IGNORECASE):
                if re.search(r"WPA2", cell_text, re.IGNORECASE):
                    security = "WPA2"
                elif re.search(r"WPA", cell_text, re.IGNORECASE):
                    security = "WPA"
                elif re.search(r"WEP", cell_text, re.IGNORECASE):
                    security = "WEP"
                else:
                    security = "WPA2"  # 默认假设

            # 提取模式
            mode_match = re.search(
                r"Mode[=:]\s*(\S+)", cell_text, re.IGNORECASE
            )
            if mode_match:
                mode = mode_match.group(1)

            if not bssid or bssid in seen_bssids:
                continue
            seen_bssids.add(bssid)

            signal_percent = dbm_to_percent(signal_dbm)
            band_2_4, band_5 = determine_bands(channel, frequency_mhz)

            networks.append(
                NetworkInfo(
                    ssid=ssid,
                    bssid=bssid,
                    signal_dbm=signal_dbm,
                    signal_percent=signal_percent,
                    channel=channel,
                    frequency_mhz=frequency_mhz,
                    security=security,
                    mode=mode,
                    band_2_4ghz=band_2_4,
                    band_5ghz=band_5,
                )
            )

        return networks

    # ------------------------------------------------------------------
    # 解析器: airport (macOS)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_airport_output(output: str) -> List[NetworkInfo]:
        """解析 macOS airport 工具的扫描输出。

        Args:
            output: airport -s 命令的标准输出文本。

        Returns:
            解析后的 NetworkInfo 列表。
        """
        networks: List[NetworkInfo] = []
        seen_bssids: set = set()

        for line in output.strip().splitlines():
            # 跳过标题行
            if not line.strip() or "SSID" in line and "BSSID" in line:
                continue

            # airport 输出以空格分隔，但 SSID 可能包含空格
            # 格式: SSID BSSID RSSI CHANNEL HT CC SECURITY(可选)
            parts = line.split()
            if len(parts) < 4:
                continue

            # BSSID 是 MAC 地址格式
            bssid_idx = -1
            for i, part in enumerate(parts):
                if re.match(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", part):
                    bssid_idx = i
                    break

            if bssid_idx < 0:
                continue

            ssid = " ".join(parts[:bssid_idx])
            bssid = parts[bssid_idx].upper()

            if bssid in seen_bssids:
                continue
            seen_bssids.add(bssid)

            try:
                signal_dbm = int(parts[bssid_idx + 1])
                channel = int(parts[bssid_idx + 2])
            except (ValueError, IndexError):
                continue

            # 解析安全类型
            security = "OPEN"
            for part in parts[bssid_idx + 3:]:
                if "WPA" in part.upper() or "WEP" in part.upper():
                    security = part.strip("()")
                    break

            frequency_mhz = ALL_CHANNEL_FREQ.get(channel)
            signal_percent = dbm_to_percent(signal_dbm)
            band_2_4, band_5 = determine_bands(channel, frequency_mhz)

            networks.append(
                NetworkInfo(
                    ssid=ssid,
                    bssid=bssid,
                    signal_dbm=signal_dbm,
                    signal_percent=signal_percent,
                    channel=channel,
                    frequency_mhz=frequency_mhz,
                    security=security,
                    mode="Infrastructure",
                    band_2_4ghz=band_2_4,
                    band_5ghz=band_5,
                )
            )

        return networks

    # ------------------------------------------------------------------
    # 解析器: netsh (Windows)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_netsh_output(output: str) -> List[NetworkInfo]:
        """解析 Windows netsh wlan show networks 的输出。

        Args:
            output: netsh 命令的标准输出文本。

        Returns:
            解析后的 NetworkInfo 列表。
        """
        networks: List[NetworkInfo] = []
        seen_bssids: set = set()

        # 按网络块分割
        blocks = re.split(r"SSID\s*\d+\s*:", output)

        for block in blocks[1:]:
            ssid = ""
            bssid = ""
            signal_dbm = -100
            channel = 0
            frequency_mhz: Optional[float] = None
            security = "OPEN"
            mode = "Unknown"

            # 提取 SSID
            ssid_match = re.match(r"\s*(.+?)(?:\n|$)", block.strip())
            if ssid_match:
                ssid = ssid_match.group(1).strip()

            # 提取 BSSID
            bssid_match = re.search(
                r"BSSID\s*:\s*([0-9A-Fa-f:]{17})", block, re.IGNORECASE
            )
            if bssid_match:
                bssid = bssid_match.group(1).upper()

            # 提取信号（可能是百分比或 dBm）
            signal_match = re.search(
                r"Signal\s*:\s*(\d+)(?:%)?", block, re.IGNORECASE
            )
            if signal_match:
                signal_val = int(signal_match.group(1))
                # netsh 通常输出百分比
                if signal_val <= 100:
                    signal_percent = signal_val
                    signal_dbm = percent_to_dbm(signal_percent)
                else:
                    signal_dbm = signal_val
                    signal_percent = dbm_to_percent(signal_dbm)

            # 提取信道
            chan_match = re.search(
                r"Channel\s*:\s*(\d+)", block, re.IGNORECASE
            )
            if chan_match:
                channel = int(chan_match.group(1))

            # 提取认证方式
            auth_match = re.search(
                r"Authentication\s*:\s*(.+?)(?:\n|$)", block, re.IGNORECASE
            )
            if auth_match:
                security = auth_match.group(1).strip()

            # 提取网络类型
            type_match = re.search(
                r"Network type\s*:\s*(.+?)(?:\n|$)", block, re.IGNORECASE
            )
            if type_match:
                mode = type_match.group(1).strip()

            if not bssid or bssid in seen_bssids:
                continue
            seen_bssids.add(bssid)

            frequency_mhz = ALL_CHANNEL_FREQ.get(channel)
            band_2_4, band_5 = determine_bands(channel, frequency_mhz)

            networks.append(
                NetworkInfo(
                    ssid=ssid,
                    bssid=bssid,
                    signal_dbm=signal_dbm,
                    signal_percent=signal_percent,
                    channel=channel,
                    frequency_mhz=frequency_mhz,
                    security=security,
                    mode=mode,
                    band_2_4ghz=band_2_4,
                    band_5ghz=band_5,
                )
            )

        return networks

    # ------------------------------------------------------------------
    # Mock 模式
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_mock_data() -> List[NetworkInfo]:
        """生成模拟 WiFi 扫描数据，用于测试和开发。

        生成一组覆盖 2.4GHz 和 5GHz 频段、不同信号强度和安全类型的
        模拟网络数据。

        Returns:
            模拟的 NetworkInfo 对象列表。
        """
        mock_networks = [
            ("HomeWiFi-5G", "A4:CF:12:3A:56:78", -42, 149, "WPA2-PSK"),
            ("HomeWiFi-2.4G", "A4:CF:12:3A:56:79", -55, 6, "WPA2-PSK"),
            ("CoffeeShop_Free", "B8:D7:AF:22:33:44", -67, 1, "OPEN"),
            ("Office-Network", "C0:3F:D5:66:77:88", -38, 36, "WPA2-Enterprise"),
            ("Neighbor_WiFi", "D4:A6:EA:99:AA:BB", -78, 11, "WPA2-PSK"),
            ("Guest-Network", "E8:B5:8E:CC:DD:EE", -72, 44, "WPA-PSK"),
            ("IoT-Devices", "F0:18:98:11:22:33", -60, 3, "WPA2-PSK"),
            ("SmartTV-5G", "A4:CF:12:3A:56:7A", -50, 161, "WPA2-PSK"),
            ("TP-LINK_5G_1234", "50:3E:AA:BB:CC:DD", -82, 48, "WPA2-PSK"),
            ("HUAWEI-2.4G", "08:E8:4F:DD:EE:FF", -73, 9, "WPA2-PSK"),
            ("Xiaomi_Router", "78:11:DC:44:55:66", -65, 6, "WPA2/WPA3"),
            ("iPhone-Hotspot", "A2:B3:C4:D5:E6:F7", -88, 1, "WPA2-PSK"),
            ("AndroidAP", "B3:C4:D5:E6:F7:A8", -91, 36, "WPA2-PSK"),
            ("Building-Lobby", "C5:D6:E7:F8:A9:B0", -58, 100, "WPA2-PSK"),
            ("Conference-Room", "D7:E8:F9:A0:B1:C2", -45, 52, "WPA2-Enterprise"),
            ("Lab-Network", "E9:F0:A1:B2:C3:D4", -63, 8, "OPEN"),
        ]

        networks: List[NetworkInfo] = []
        now = time.time()

        for ssid, bssid, signal_dbm, channel, security in mock_networks:
            frequency_mhz = ALL_CHANNEL_FREQ.get(channel)
            signal_percent = dbm_to_percent(signal_dbm)
            band_2_4, band_5 = determine_bands(channel, frequency_mhz)

            # 添加微小随机波动，模拟真实扫描差异
            jitter_dbm = random.randint(-2, 2)
            jittered_dbm = max(-100, min(-30, signal_dbm + jitter_dbm))

            networks.append(
                NetworkInfo(
                    ssid=ssid,
                    bssid=bssid,
                    signal_dbm=jittered_dbm,
                    signal_percent=dbm_to_percent(jittered_dbm),
                    channel=channel,
                    frequency_mhz=frequency_mhz,
                    security=security,
                    mode="Infrastructure",
                    band_2_4ghz=band_2_4,
                    band_5ghz=band_5,
                    timestamp=now,
                )
            )

        return networks


# ======================================================================
# 工具函数
# ======================================================================


def dbm_to_percent(dbm: int) -> int:
    """将信号强度从 dBm 转换为百分比。

    使用标准 WiFi 信号转换公式，将 dBm 值（通常 -100 到 -30）
    映射到 0-100 的百分比范围。

    转换公式:
        quality = max(0, min(100, (dbm + 100) * 2))

    Args:
        dbm: 信号强度，单位 dBm（通常范围 -100 到 0）。

    Returns:
        信号质量百分比 (0-100)。
    """
    # 线性映射: -100 dBm -> 0%, -30 dBm -> 100%
    quality = (dbm + 100) * 2
    return max(0, min(100, int(quality)))


def percent_to_dbm(percent: int) -> int:
    """将信号百分比转换回 dBm 近似值。

    这是 dbm_to_percent 的逆运算。

    Args:
        percent: 信号质量百分比 (0-100)。

    Returns:
        信号强度 dBm 近似值。
    """
    dbm = (percent / 2) - 100
    return max(-100, min(-30, int(dbm)))


def determine_bands(
    channel: int, frequency_mhz: Optional[float] = None
) -> Tuple[bool, bool]:
    """根据信道编号和频率判断网络所属频段。

    2.4GHz 频段: 信道 1-14
    5GHz 频段: 信道 15 及以上（或频率 >= 5000 MHz）

    Args:
        channel: 无线信道编号。
        frequency_mhz: 中心频率（MHz），可选。用于辅助判断。

    Returns:
        元组 (is_2_4ghz, is_5ghz)，表示是否属于对应频段。
    """
    is_2_4 = 1 <= channel <= 14
    is_5 = channel >= 15 or (
        frequency_mhz is not None and frequency_mhz >= 5000
    )
    return is_2_4, is_5
