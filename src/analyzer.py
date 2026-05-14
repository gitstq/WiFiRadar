"""
WiFiRadar - WiFi 信号分析引擎模块

对扫描到的 WiFi 网络数据进行深度分析，包括信道拥塞分析、干扰评分、
信号质量评级、最佳信道推荐、安全评估和频段利用率分析。

使用方式:
    from wifiradar.src.scanner import WiFiScanner
    from wifiradar.src.analyzer import WiFiAnalyzer

    scanner = WiFiScanner(mock_mode=True)
    networks = scanner.scan()

    analyzer = WiFiAnalyzer(networks)
    result = analyzer.analyze()
    print(result.summary_text())
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from .models import AnalysisResult, ChannelInfo, NetworkInfo

logger = logging.getLogger(__name__)


# ======================================================================
# 常量定义
# ======================================================================

# 2.4GHz 信道与相邻重叠信道映射
# 2.4GHz 每个信道带宽约 22MHz，信道间隔 5MHz，因此每个信道与
# 前后各 4 个信道存在频率重叠。
CHANNEL_OVERLAP_2G: Dict[int, List[int]] = {}
for _ch in range(1, 15):
    CHANNEL_OVERLAP_2G[_ch] = [
        c for c in range(_ch - 4, _ch + 5) if 1 <= c <= 14 and c != _ch
    ]

# 2.4GHz 推荐非重叠信道（信道间隔 >= 5）
NON_OVERLAP_2G: List[int] = [1, 6, 11]

# 5GHz 非重叠信道组（DFS 信道可能需要特殊许可，此处仅列出常用信道）
NON_OVERLAP_5G: List[int] = [
    36, 40, 44, 48,
    149, 153, 157, 161, 165,
]

# 5GHz 信道与相邻信道映射（每个信道带宽 20MHz，信道间隔 20MHz）
# 在 20MHz 带宽下，5GHz 信道通常不重叠，但相邻信道仍可能有轻微干扰
CHANNEL_OVERLAP_5G: Dict[int, List[int]] = {}
_5g_channels = [
    36, 40, 44, 48, 52, 56, 60, 64,
    100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144,
    149, 153, 157, 161, 165, 169, 173, 177,
]
for _ch in _5g_channels:
    _idx = _5g_channels.index(_ch)
    _overlap = []
    if _idx > 0:
        _overlap.append(_5g_channels[_idx - 1])
    if _idx < len(_5g_channels) - 1:
        _overlap.append(_5g_channels[_idx + 1])
    CHANNEL_OVERLAP_5G[_ch] = _overlap


class WiFiAnalyzer:
    """WiFi 信号智能分析引擎。

    对扫描到的网络数据进行多维度分析，生成综合评估报告。

    分析维度包括:
    - 信道拥塞分析
    - 干扰评分计算
    - 信号质量评级
    - 最佳信道推荐
    - 安全协议评估
    - 频段利用率分析

    Attributes:
        networks: 待分析的 WiFi 网络列表。
    """

    def __init__(self, networks: List[NetworkInfo]) -> None:
        """初始化分析引擎。

        Args:
            networks: 由 WiFiScanner 扫描得到的网络列表。
        """
        self.networks: List[NetworkInfo] = networks

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def analyze(self) -> AnalysisResult:
        """执行完整的 WiFi 环境分析。

        依次执行以下分析步骤:
        1. 频段分布统计
        2. 信道拥塞分析
        3. 干扰评分计算
        4. 最佳信道推荐
        5. 安全评估
        6. 生成优化建议

        Returns:
            包含所有分析结果的 AnalysisResult 对象。
        """
        if not self.networks:
            logger.info("网络列表为空，返回空分析结果")
            return AnalysisResult()

        # 基本统计
        band_2g, band_5g = self._count_bands()
        total = len(self.networks)

        # 信道分析
        channel_congestion = self._analyze_channel_congestion()
        interference_scores = self._calculate_interference_scores(channel_congestion)
        best_channels = self._recommend_best_channels(channel_congestion)

        # 安全评估
        security_summary = self._assess_security()

        # 优化建议
        recommendations = self._generate_recommendations(
            total=total,
            band_2g=band_2g,
            band_5g=band_5g,
            channel_congestion=channel_congestion,
            security_summary=security_summary,
            best_channels=best_channels,
        )

        return AnalysisResult(
            total_networks=total,
            band_2_4ghz_count=band_2g,
            band_5ghz_count=band_5g,
            channel_congestion=channel_congestion,
            best_channels=best_channels,
            interference_scores=interference_scores,
            security_summary=security_summary,
            recommendations=recommendations,
        )

    # ------------------------------------------------------------------
    # 频段统计
    # ------------------------------------------------------------------

    def _count_bands(self) -> Tuple[int, int]:
        """统计 2.4GHz 和 5GHz 频段的网络数量。

        Returns:
            元组 (band_2_4ghz_count, band_5ghz_count)。
        """
        count_2g = sum(1 for n in self.networks if n.band_2_4ghz)
        count_5g = sum(1 for n in self.networks if n.band_5ghz)
        return count_2g, count_5g

    # ------------------------------------------------------------------
    # 信道拥塞分析
    # ------------------------------------------------------------------

    def _analyze_channel_congestion(self) -> List[ChannelInfo]:
        """分析各信道的拥塞情况。

        对每个被使用的信道计算:
        - 该信道上的网络数量
        - 考虑重叠信道的拥塞评分
        - 相邻重叠信道列表

        Returns:
            按信道编号排序的 ChannelInfo 列表。
        """
        # 按信道分组统计网络数量
        channel_networks: Dict[int, List[NetworkInfo]] = defaultdict(list)
        for net in self.networks:
            channel_networks[net.channel].append(net)

        # 收集所有活跃信道
        active_channels: Set[int] = set(channel_networks.keys())

        channel_infos: List[ChannelInfo] = []

        for channel, networks in sorted(channel_networks.items()):
            frequency = self._get_channel_frequency(channel)
            overlapping = self._get_overlapping_channels(channel)

            # 计算拥塞评分
            # 考虑因素: 本信道网络数 + 重叠信道网络数 + 信号强度权重
            own_count = len(networks)
            neighbor_count = sum(
                len(channel_networks.get(oc, []))
                for oc in overlapping
                if oc in active_channels
            )

            # 信号强度加权: 强信号网络对拥塞的影响更大
            signal_weight = sum(
                max(0, (100 - net.signal_percent) / 100 + 0.3)
                for net in networks
            ) / max(own_count, 1)

            # 拥塞评分公式: (本信道网络 * 1.0 + 重叠信道网络 * 0.5) * 信号权重 * 10
            raw_score = (own_count * 1.0 + neighbor_count * 0.5) * signal_weight * 10
            congestion_score = min(100.0, raw_score)

            channel_infos.append(
                ChannelInfo(
                    channel=channel,
                    frequency=frequency,
                    networks_count=own_count,
                    congestion_score=round(congestion_score, 1),
                    overlapping_channels=overlapping,
                )
            )

        return channel_infos

    # ------------------------------------------------------------------
    # 干扰评分
    # ------------------------------------------------------------------

    def _calculate_interference_scores(
        self, channel_congestion: List[ChannelInfo]
    ) -> Dict[int, float]:
        """计算各信道的干扰评分。

        干扰评分综合考虑:
        - 同信道网络数量（同频干扰，权重最高）
        - 相邻信道网络数量（邻频干扰，权重中等）
        - 网络信号强度（强信号干扰更大）

        Args:
            channel_congestion: 信道拥塞分析结果。

        Returns:
            以信道编号为键、干扰评分为值的字典。
        """
        # 按信道分组网络
        channel_networks: Dict[int, List[NetworkInfo]] = defaultdict(list)
        for net in self.networks:
            channel_networks[net.channel].append(net)

        interference: Dict[int, float] = {}

        for ch_info in channel_congestion:
            ch = ch_info.channel
            own_nets = channel_networks.get(ch, [])

            if not own_nets:
                interference[ch] = 0.0
                continue

            # 同频干扰: 同信道上的其他网络
            co_channel_score = 0.0
            for net in own_nets:
                # 信号越强干扰越大，距离越近
                co_channel_score += (net.signal_percent / 100) * 25

            # 邻频干扰: 重叠信道上的网络
            adj_channel_score = 0.0
            for overlap_ch in ch_info.overlapping_channels:
                for net in channel_networks.get(overlap_ch, []):
                    adj_channel_score += (net.signal_percent / 100) * 10

            total_score = min(100.0, co_channel_score + adj_channel_score)
            interference[ch] = round(total_score, 1)

        return interference

    # ------------------------------------------------------------------
    # 最佳信道推荐
    # ------------------------------------------------------------------

    def _recommend_best_channels(
        self, channel_congestion: List[ChannelInfo]
    ) -> Dict[str, List[int]]:
        """推荐最佳信道。

        分别为 2.4GHz 和 5GHz 频段推荐干扰最小的信道。
        优先推荐非重叠信道，其次推荐拥塞最低的信道。

        Args:
            channel_congestion: 信道拥塞分析结果。

        Returns:
            按频段分组的最佳信道推荐字典。
            格式: {"2.4GHz": [ch1, ch2, ...], "5GHz": [ch1, ch2, ...]}
        """
        # 构建信道 -> 拥塞信息映射
        ch_map: Dict[int, ChannelInfo] = {ci.channel: ci for ci in channel_congestion}

        # 获取各频段使用的信道集合
        used_2g = {ci.channel for ci in channel_congestion if 1 <= ci.channel <= 14}
        used_5g = {ci.channel for ci in channel_congestion if ci.channel >= 15}

        best: Dict[str, List[int]] = {}

        # --- 2.4GHz 推荐 ---
        best_2g = self._rank_channels(
            candidates=NON_OVERLAP_2G,
            used_channels=used_2g,
            ch_map=ch_map,
            overlap_map=CHANNEL_OVERLAP_2G,
            channel_networks=self._group_by_channel(),
        )
        best["2.4GHz"] = best_2g[:3] if best_2g else [1, 6, 11]

        # --- 5GHz 推荐 ---
        best_5g = self._rank_channels(
            candidates=NON_OVERLAP_5G,
            used_channels=used_5g,
            ch_map=ch_map,
            overlap_map=CHANNEL_OVERLAP_5G,
            channel_networks=self._group_by_channel(),
        )
        best["5GHz"] = best_5g[:3] if best_5g else [36, 149, 157]

        return best

    def _rank_channels(
        self,
        candidates: List[int],
        used_channels: Set[int],
        ch_map: Dict[int, ChannelInfo],
        overlap_map: Dict[int, List[int]],
        channel_networks: Dict[int, List[NetworkInfo]],
    ) -> List[int]:
        """根据干扰情况对候选信道进行排序。

        Args:
            candidates: 候选信道列表。
            used_channels: 当前已使用的信道集合。
            ch_map: 信道 -> ChannelInfo 映射。
            overlap_map: 信道 -> 重叠信道映射。
            channel_networks: 信道 -> 网络列表映射。

        Returns:
            按推荐优先级排序的信道列表（最优在前）。
        """
        scored: List[Tuple[int, float]] = []

        for ch in candidates:
            # 基础分: 该信道上的网络数
            own_count = len(channel_networks.get(ch, []))

            # 重叠信道上的网络数
            overlap_count = sum(
                len(channel_networks.get(oc, []))
                for oc in overlap_map.get(ch, [])
                if oc in used_channels
            )

            # 综合评分（越低越好）
            score = own_count * 2.0 + overlap_count * 0.8

            # 如果信道已有信息，加入拥塞评分权重
            if ch in ch_map:
                score += ch_map[ch].congestion_score * 0.3

            scored.append((ch, score))

        # 按评分升序排列
        scored.sort(key=lambda x: x[1])
        return [ch for ch, _ in scored]

    # ------------------------------------------------------------------
    # 安全评估
    # ------------------------------------------------------------------

    def _assess_security(self) -> Dict[str, int]:
        """评估扫描到的网络安全状况。

        将网络按安全协议类型分类统计，并评估整体安全水平。

        Returns:
            安全类型 -> 网络数量的映射字典。
        """
        security_counts: Dict[str, int] = defaultdict(int)

        for net in self.networks:
            sec_upper = net.security.upper()

            if "WPA3" in sec_upper:
                security_counts["WPA3"] += 1
            elif "WPA2" in sec_upper and "WPA" in sec_upper and "WPA2" in sec_upper:
                # 检查是否同时有 WPA 和 WPA2（混合模式）
                if "WPA " in net.security and "WPA2" in sec_upper:
                    security_counts["WPA/WPA2 混合"] += 1
                else:
                    security_counts["WPA2"] += 1
            elif "WPA" in sec_upper:
                security_counts["WPA"] += 1
            elif "WEP" in sec_upper:
                security_counts["WEP"] += 1
            else:
                security_counts["开放网络"] += 1

        return dict(security_counts)

    # ------------------------------------------------------------------
    # 信号质量评级
    # ------------------------------------------------------------------

    @staticmethod
    def grade_signal(
        signal_dbm: int, congestion_score: float = 0.0
    ) -> str:
        """对单个网络的信号质量进行综合评级。

        综合考虑信号强度和信道拥塞程度。

        评级标准:
        - A: 信号优秀 (>= -50 dBm) 且拥塞低
        - B: 信号良好 (>= -60 dBm) 且拥塞中等
        - C: 信号一般 (>= -70 dBm) 或拥塞较高
        - D: 信号较差 (>= -80 dBm) 或拥塞严重
        - F: 信号极差 (< -80 dBm) 或拥塞极度严重

        Args:
            signal_dbm: 信号强度 (dBm)。
            congestion_score: 信道拥塞评分 (0-100)。

        Returns:
            信号质量等级 (A/B/C/D/F)。
        """
        # 基础等级由信号强度决定
        if signal_dbm >= -50:
            base_grade = "A"
        elif signal_dbm >= -60:
            base_grade = "B"
        elif signal_dbm >= -70:
            base_grade = "C"
        elif signal_dbm >= -80:
            base_grade = "D"
        else:
            base_grade = "F"

        # 拥塞降级: 拥塞严重时降低一级
        grade_order = ["A", "B", "C", "D", "F"]
        if congestion_score >= 75 and base_grade != "F":
            idx = grade_order.index(base_grade)
            base_grade = grade_order[min(idx + 1, len(grade_order) - 1)]

        return base_grade

    # ------------------------------------------------------------------
    # 优化建议生成
    # ------------------------------------------------------------------

    def _generate_recommendations(
        self,
        total: int,
        band_2g: int,
        band_5g: int,
        channel_congestion: List[ChannelInfo],
        security_summary: Dict[str, int],
        best_channels: Dict[str, List[int]],
    ) -> List[str]:
        """根据分析结果生成优化建议。

        Args:
            total: 网络总数。
            band_2g: 2.4GHz 网络数。
            band_5g: 5GHz 网络数。
            channel_congestion: 信道拥塞分析结果。
            security_summary: 安全评估摘要。
            best_channels: 最佳信道推荐。

        Returns:
            优化建议字符串列表。
        """
        recommendations: List[str] = []

        # 1. 频段分布建议
        if total > 0 and band_2g > band_5g:
            ratio_2g = band_2g / total * 100
            recommendations.append(
                f"2.4GHz 频段使用率较高 ({ratio_2g:.0f}%)，建议将支持双频的设备"
                f"迁移至 5GHz 频段以减少 2.4GHz 拥塞。"
            )

        # 2. 信道拥塞建议
        high_congestion = [
            ci for ci in channel_congestion if ci.congestion_score >= 60
        ]
        if high_congestion:
            ch_list = ", ".join(str(ci.channel) for ci in high_congestion[:3])
            recommendations.append(
                f"信道 {ch_list} 拥塞严重，建议切换至推荐信道以改善连接质量。"
            )

        # 3. 最佳信道建议
        if best_channels.get("2.4GHz"):
            ch_str = ", ".join(str(c) for c in best_channels["2.4GHz"][:1])
            recommendations.append(
                f"2.4GHz 频段推荐信道: {ch_str}（干扰最低）。"
            )
        if best_channels.get("5GHz"):
            ch_str = ", ".join(str(c) for c in best_channels["5GHz"][:1])
            recommendations.append(
                f"5GHz 频段推荐信道: {ch_str}（干扰最低）。"
            )

        # 4. 安全建议
        open_count = security_summary.get("开放网络", 0)
        wep_count = security_summary.get("WEP", 0)
        wpa_count = security_summary.get("WPA", 0)

        if open_count > 0:
            recommendations.append(
                f"检测到 {open_count} 个开放网络，使用开放网络存在严重安全风险，"
                f"请避免传输敏感信息。"
            )
        if wep_count > 0:
            recommendations.append(
                f"检测到 {wep_count} 个使用 WEP 加密的网络，WEP 协议已被证明不安全，"
                f"建议升级至 WPA2 或 WPA3。"
            )
        if wpa_count > 0:
            recommendations.append(
                f"检测到 {wpa_count} 个仅使用 WPA 加密的网络，建议升级至 WPA2 或 WPA3。"
            )

        wpa3_count = security_summary.get("WPA3", 0)
        if wpa3_count > 0:
            recommendations.append(
                f"检测到 {wpa3_count} 个使用 WPA3 加密的网络，安全性最佳。"
            )

        # 5. 信号质量建议
        weak_networks = [
            n for n in self.networks if n.signal_percent < 30
        ]
        if weak_networks:
            recommendations.append(
                f"检测到 {len(weak_networks)} 个弱信号网络 (< 30%)，"
                f"可能需要调整路由器位置或添加中继器。"
            )

        # 6. 2.4GHz 特定建议
        if band_2g > 0:
            # 检查是否所有 2.4GHz 网络都集中在少数信道
            ch_2g_counts: Dict[int, int] = defaultdict(int)
            for net in self.networks:
                if net.band_2_4ghz:
                    ch_2g_counts[net.channel] += 1

            if ch_2g_counts:
                max_ch = max(ch_2g_counts, key=ch_2g_counts.get)
                max_ratio = ch_2g_counts[max_ch] / band_2g
                if max_ratio > 0.5:
                    recommendations.append(
                        f"2.4GHz 频段超过 50% 的网络集中在信道 {max_ch}，"
                        f"严重干扰风险较高，强烈建议分散到信道 1、6、11。"
                    )

        return recommendations

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _group_by_channel(self) -> Dict[int, List[NetworkInfo]]:
        """将网络按信道分组。

        Returns:
            信道编号 -> 网络列表的映射。
        """
        groups: Dict[int, List[NetworkInfo]] = defaultdict(list)
        for net in self.networks:
            groups[net.channel].append(net)
        return dict(groups)

    @staticmethod
    def _get_channel_frequency(channel: int) -> float:
        """获取信道对应的中心频率。

        Args:
            channel: 信道编号。

        Returns:
            中心频率 (MHz)。未知信道返回 0.0。
        """
        from .scanner import ALL_CHANNEL_FREQ

        return ALL_CHANNEL_FREQ.get(channel, 0.0)

    @staticmethod
    def _get_overlapping_channels(channel: int) -> List[int]:
        """获取与指定信道存在频率重叠的信道列表。

        Args:
            channel: 信道编号。

        Returns:
            重叠信道编号列表。
        """
        if 1 <= channel <= 14:
            return CHANNEL_OVERLAP_2G.get(channel, [])
        else:
            return CHANNEL_OVERLAP_5G.get(channel, [])
