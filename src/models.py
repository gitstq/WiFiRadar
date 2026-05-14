"""
WiFiRadar - 数据模型模块

定义 WiFi 扫描和分析过程中使用的所有核心数据结构。
所有模型均使用 Python 标准库 dataclasses 实现，零外部依赖。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class NetworkInfo:
    """WiFi 网络信息数据模型。

    表示扫描到的单个 WiFi 网络的所有关键属性，
    包括信号强度、频段、安全协议等信息。

    Attributes:
        ssid: 网络名称（Service Set Identifier）。
        bssid: 接入点的 MAC 地址（Basic Service Set Identifier）。
        signal_dbm: 信号强度，单位 dBm（通常范围 -100 到 0）。
        signal_percent: 信号质量百分比（0-100）。
        channel: 无线信道编号。
        frequency_mhz: 中心频率，单位 MHz。
        security: 安全协议类型（如 WPA2、WPA3、OPEN 等）。
        mode: 网络模式（如 Infrastructure、Ad-Hoc 等）。
        band_2_4ghz: 是否运行在 2.4GHz 频段。
        band_5ghz: 是否运行在 5GHz 频段。
        timestamp: 扫描时间戳（Unix 时间）。
    """

    ssid: str
    bssid: str
    signal_dbm: int
    signal_percent: int
    channel: int
    frequency_mhz: Optional[float]
    security: str
    mode: str
    band_2_4ghz: bool
    band_5ghz: bool
    timestamp: float = field(default_factory=time.time)

    @property
    def signal_grade(self) -> str:
        """根据信号强度返回信号等级。

        Returns:
            信号等级字符串: 'A'(优秀) / 'B'(良好) / 'C'(一般) / 'D'(较差) / 'F'(极差)
        """
        if self.signal_percent >= 80:
            return "A"
        elif self.signal_percent >= 60:
            return "B"
        elif self.signal_percent >= 40:
            return "C"
        elif self.signal_percent >= 20:
            return "D"
        else:
            return "F"

    @property
    def is_secured(self) -> bool:
        """判断网络是否使用了安全加密。

        Returns:
            如果网络使用了任何形式的安全加密则返回 True。
        """
        security_upper = self.security.upper()
        return any(
            proto in security_upper
            for proto in ("WPA", "WEP", "RSN", "IEEE802.1X")
        )

    @property
    def security_level(self) -> int:
        """评估安全等级分数。

        Returns:
            安全等级分数 (0-100)，分数越高表示安全性越好。
        """
        security_upper = self.security.upper()
        if "WPA3" in security_upper:
            return 95
        elif "WPA2" in security_upper and "WPA3" not in security_upper:
            if "SAE" in security_upper:
                return 90
            return 80
        elif "WPA" in security_upper and "WPA2" not in security_upper:
            return 50
        elif "WEP" in security_upper:
            return 20
        else:
            return 0  # 开放网络

    def to_dict(self) -> Dict:
        """将网络信息转换为字典格式。

        Returns:
            包含所有网络属性的字典。
        """
        return {
            "ssid": self.ssid,
            "bssid": self.bssid,
            "signal_dbm": self.signal_dbm,
            "signal_percent": self.signal_percent,
            "signal_grade": self.signal_grade,
            "channel": self.channel,
            "frequency_mhz": self.frequency_mhz,
            "security": self.security,
            "mode": self.mode,
            "band_2_4ghz": self.band_2_4ghz,
            "band_5ghz": self.band_5ghz,
            "is_secured": self.is_secured,
            "security_level": self.security_level,
            "timestamp": self.timestamp,
        }

    def __str__(self) -> str:
        """返回网络信息的可读字符串表示。"""
        band = "2.4G" if self.band_2_4ghz else ("5G" if self.band_5ghz else "未知")
        return (
            f"[{self.signal_grade}] {self.ssid or '(隐藏网络)'} | "
            f"信号: {self.signal_percent}% ({self.signal_dbm} dBm) | "
            f"信道: {self.channel} ({band}) | "
            f"安全: {self.security or '开放'}"
        )


@dataclass
class ChannelInfo:
    """无线信道信息数据模型。

    表示单个信道的详细分析数据，包括拥塞程度和重叠情况。

    Attributes:
        channel: 信道编号。
        frequency: 中心频率（MHz）。
        networks_count: 该信道上的网络数量。
        congestion_score: 拥塞评分 (0-100)，分数越高表示拥塞越严重。
        overlapping_channels: 与该信道存在频率重叠的相邻信道列表。
    """

    channel: int
    frequency: float
    networks_count: int = 0
    congestion_score: float = 0.0
    overlapping_channels: List[int] = field(default_factory=list)

    @property
    def congestion_level(self) -> str:
        """根据拥塞评分返回拥塞等级。

        Returns:
            拥塞等级: '低' / '中' / '高' / '严重'
        """
        if self.congestion_score < 25:
            return "低"
        elif self.congestion_score < 50:
            return "中"
        elif self.congestion_score < 75:
            return "高"
        else:
            return "严重"

    def to_dict(self) -> Dict:
        """将信道信息转换为字典格式。

        Returns:
            包含所有信道属性的字典。
        """
        return {
            "channel": self.channel,
            "frequency": self.frequency,
            "networks_count": self.networks_count,
            "congestion_score": round(self.congestion_score, 1),
            "congestion_level": self.congestion_level,
            "overlapping_channels": self.overlapping_channels,
        }


@dataclass
class AnalysisResult:
    """WiFi 环境分析结果数据模型。

    汇总整个 WiFi 环境的分析数据，包括频段分布、信道拥塞、
    干扰评分、安全评估和优化建议。

    Attributes:
        total_networks: 扫描到的网络总数。
        band_2_4ghz_count: 2.4GHz 频段网络数量。
        band_5ghz_count: 5GHz 频段网络数量。
        channel_congestion: 各信道的拥塞信息列表。
        best_channels: 推荐的最佳信道（按频段分组）。
        interference_scores: 各信道的干扰评分。
        security_summary: 安全评估摘要。
        recommendations: 优化建议列表。
    """

    total_networks: int = 0
    band_2_4ghz_count: int = 0
    band_5ghz_count: int = 0
    channel_congestion: List[ChannelInfo] = field(default_factory=list)
    best_channels: Dict[str, List[int]] = field(default_factory=dict)
    interference_scores: Dict[int, float] = field(default_factory=dict)
    security_summary: Dict[str, int] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """将分析结果转换为字典格式。

        Returns:
            包含所有分析结果的嵌套字典。
        """
        return {
            "total_networks": self.total_networks,
            "band_distribution": {
                "2.4ghz_count": self.band_2_4ghz_count,
                "5ghz_count": self.band_5ghz_count,
                "2.4ghz_ratio": (
                    round(self.band_2_4ghz_count / self.total_networks * 100, 1)
                    if self.total_networks > 0
                    else 0.0
                ),
                "5ghz_ratio": (
                    round(self.band_5ghz_count / self.total_networks * 100, 1)
                    if self.total_networks > 0
                    else 0.0
                ),
            },
            "channel_congestion": [
                ch.to_dict() for ch in self.channel_congestion
            ],
            "best_channels": self.best_channels,
            "interference_scores": {
                str(k): round(v, 1) for k, v in self.interference_scores.items()
            },
            "security_summary": self.security_summary,
            "recommendations": self.recommendations,
        }

    def summary_text(self) -> str:
        """生成分析结果的纯文本摘要。

        Returns:
            格式化的分析结果摘要字符串。
        """
        lines = [
            "=" * 60,
            "  WiFiRadar 环境分析报告",
            "=" * 60,
            "",
            f"  扫描网络总数: {self.total_networks}",
            f"  2.4GHz 网络:  {self.band_2_4ghz_count}",
            f"  5GHz 网络:    {self.band_5ghz_count}",
            "",
        ]

        if self.best_channels:
            lines.append("  推荐信道:")
            for band, channels in self.best_channels.items():
                ch_str = ", ".join(str(c) for c in channels)
                lines.append(f"    {band}: {ch_str}")
            lines.append("")

        if self.security_summary:
            lines.append("  安全评估:")
            for sec_type, count in self.security_summary.items():
                lines.append(f"    {sec_type}: {count} 个网络")
            lines.append("")

        if self.recommendations:
            lines.append("  优化建议:")
            for idx, rec in enumerate(self.recommendations, 1):
                lines.append(f"    {idx}. {rec}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)
