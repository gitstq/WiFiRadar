"""
WiFiRadar - 轻量级 WiFi 信号智能分析与可视化 CLI 引擎

一个零外部依赖的 WiFi 环境分析工具，支持跨平台扫描、信号分析、
信道推荐和安全评估。

模块:
    models   - 核心数据模型（NetworkInfo, AnalysisResult, ChannelInfo）
    scanner  - 跨平台 WiFi 扫描引擎
    analyzer - WiFi 信号智能分析引擎

使用示例:
    from wifiradar.src import WiFiScanner, WiFiAnalyzer

    # 扫描 WiFi 网络
    scanner = WiFiScanner()
    networks = scanner.scan()

    # 分析扫描结果
    analyzer = WiFiAnalyzer(networks)
    result = analyzer.analyze()
    print(result.summary_text())
"""

__version__ = "1.0.0"
__author__ = "WiFiRadar Team"
__description__ = "轻量级 WiFi 信号智能分析与可视化 CLI 引擎"

from .analyzer import WiFiAnalyzer
from .models import AnalysisResult, ChannelInfo, NetworkInfo
from .scanner import WiFiScanner, dbm_to_percent, determine_bands

__all__ = [
    "WiFiScanner",
    "WiFiAnalyzer",
    "NetworkInfo",
    "AnalysisResult",
    "ChannelInfo",
    "dbm_to_percent",
    "determine_bands",
]
