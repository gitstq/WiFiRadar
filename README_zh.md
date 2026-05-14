<p align="center">
  <h1 align="center">📡 WiFiRadar</h1>
  <p align="center">
    <strong>轻量级 Wi-Fi 信号智能分析与可视化 CLI 引擎</strong>
  </p>
  <p align="center">
    <a href="README.md">English</a> ·
    简体中文 ·
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

## 🎉 项目介绍

**WiFiRadar** 是一款零依赖、跨平台的 Wi-Fi 信号智能分析与可视化命令行引擎。它能扫描附近的 Wi-Fi 网络，对信道拥塞、干扰水平和信号质量进行深度分析，并生成可操作的优化建议和精美的可视化报告。

### 💡 为什么需要 WiFiRadar？

你是否遇到过这样的困惑：Wi-Fi 信号满格，但网速却很慢？答案往往隐藏在**信道拥塞**和**邻近网络干扰**中。WiFiRadar 为你呈现完整的无线环境全貌：

- 📊 **可视化**展示所有附近网络的信号强度
- 🔍 **深度分析**信道拥塞度和干扰评分
- ✅ **智能推荐**路由器最佳信道
- 📈 **追踪**信号强度随时间的变化趋势
- 📄 **导出**专业级 HTML/JSON/Markdown/CSV 报告

### 🌟 差异化亮点

| 特性 | WiFiRadar | 常见 Wi-Fi 工具 |
|------|-----------|----------------|
| 外部依赖 | **零依赖** | 通常需要 GUI 框架 |
| 输出格式 | **4 种格式**（HTML/JSON/MD/CSV） | 通常仅 1-2 种 |
| 历史追踪 | **SQLite 持久化**含趋势分析 | 极少支持 |
| 信道分析 | **拥塞度 + 干扰评分** | 仅基础信道列表 |
| 跨平台 | **Linux/macOS/Windows** | 通常限定平台 |
| 安装方式 | **复制即用** | pip install / 包管理器 |

---

## ✨ 核心特性

### 📡 智能扫描
- **自动检测平台**：Linux 使用 `nmcli`，macOS 使用 `airport`，Windows 使用 `netsh`
- **全面数据采集**：SSID、BSSID、信号强度、信道、频率、安全协议、频段
- **演示模式**：内置模拟数据，无需 Wi-Fi 硬件即可体验完整功能

### 📊 信号分析
- **信道拥塞分析**：统计各信道网络数量，自动检测信道重叠
- **干扰评分**：基于同频干扰和邻频干扰的加权评分算法
- **信号质量评级**：综合信号强度和拥塞度给出 A/B/C/D/F 等级
- **最佳信道推荐**：同时为 2.4GHz 和 5GHz 频段推荐最优信道
- **安全评估**：WPA3/WPA2/WPA/WEP/开放网络分类统计与评估
- **频段利用率分析**：2.4GHz 与 5GHz 网络分布对比

### 🎨 终端可视化
- **信号强度柱状图**：颜色编码（🟢 绿色 / 🟡 黄色 / 🔴 红色）
- **信道使用热力图**：Unicode 方块字符（█▓▒░）展示 2.4GHz 和 5GHz 信道占用
- **频段分布图**：ASCII 水平条形图
- **干扰评分可视化**：逐信道干扰水平展示
- **安全类型分布图**：安全协议使用概况

### 📄 多格式报告
- **HTML 报告**：自包含暗色主题页面，CSS 图表，响应式设计
- **JSON 报告**：结构化数据导出，便于程序集成
- **Markdown 报告**：GitHub/wiki 友好格式，表格展示
- **CSV 报告**：电子表格兼容格式，便于数据分析

### 📈 扫描历史
- **SQLite 存储**：持久化扫描历史，WAL 模式提升并发性能
- **趋势分析**：信号强度随时间的变化趋势
- **变更检测**：两次扫描间的新增/消失网络识别
- **数据导出**：趋势数据支持 CSV/JSON 格式导出

### 🖥️ CLI 命令一览

| 命令 | 说明 |
|------|------|
| `wifiradar scan` | 扫描并展示 Wi-Fi 网络 |
| `wifiradar analyze` | 完整分析并给出优化建议 |
| `wifiradar report` | 生成综合 HTML 报告 |
| `wifiradar history` | 管理扫描历史（列表/查看/趋势/对比/清理） |
| `wifiradar monitor` | 持续监控模式 |
| `wifiradar demo` | 使用模拟数据运行演示 |

---

## 🚀 快速开始

### 📋 环境要求

- **Python 3.8+**（无需安装任何其他依赖！）
- **操作系统**：Linux、macOS 或 Windows
- **Wi-Fi 网卡**（真实扫描需要；演示模式无需硬件）

### ⚡ 安装

```bash
# 克隆仓库
git clone https://github.com/gitstq/WiFiRadar.git
cd WiFiRadar

# 就这么简单！无需 pip install —— 零依赖！
# 直接运行：
python3 wifiradar.py --version
```

### 🎮 基础用法

```bash
# 扫描附近的 Wi-Fi 网络
python3 wifiradar.py scan

# 完整分析并获取优化建议
python3 wifiradar.py analyze

# 生成精美的 HTML 报告
python3 wifiradar.py report

# 演示模式（无需 Wi-Fi 硬件）
python3 wifiradar.py demo

# 显示信号最强的前 10 个网络
python3 wifiradar.py scan --top 10

# 仅显示 5GHz 频段网络
python3 wifiradar.py scan --filter-band 5GHz

# 导出扫描结果为 JSON
python3 wifiradar.py scan --json

# 导出为 CSV 便于表格分析
python3 wifiradar.py scan --csv

# 生成 Markdown 格式报告
python3 wifiradar.py scan --markdown
```

### 📊 进阶用法

```bash
# 持续监控（每 30 秒扫描一次）
python3 wifiradar.py monitor --interval 30

# 信号低于 -70 dBm 时告警
python3 wifiradar.py monitor --alert-threshold -70

# 查看扫描历史
python3 wifiradar.py history list

# 查看指定网络的信号趋势
python3 wifiradar.py history trend --bssid AA:BB:CC:DD:EE:FF

# 对比两次扫描结果
python3 wifiradar.py history compare --scan-ids 1,2

# 生成报告并保存到指定路径
python3 wifiradar.py report --output ~/wifi_report.html

# 按信道排序
python3 wifiradar.py scan --sort-by channel

# 筛选最低信号强度
python3 wifiradar.py scan --min-signal -60
```

---

## 📖 详细使用指南

### 信号质量等级

| 等级 | 信号 (dBm) | 质量 | 说明 |
|------|-----------|------|------|
| **A** | -30 ~ -50 | 优秀 | 适合所有网络活动 |
| **B** | -51 ~ -60 | 良好 | 流媒体和游戏无压力 |
| **C** | -61 ~ -70 | 一般 | 适合浏览和邮件 |
| **D** | -71 ~ -80 | 较差 | 连接不稳定 |
| **F** | < -80 | 无信号 | 无法使用 |

### 信道拥塞等级

| 等级 | 评分 | 说明 |
|------|------|------|
| 🟢 **低** | 0-30 | 干扰极小，理想状态 |
| 🟡 **中** | 31-60 | 存在一定干扰，可接受 |
| 🟠 **高** | 61-80 | 干扰较大，建议切换信道 |
| 🔴 **严重** | 81-100 | 拥堵严重，请立即更换信道 |

### 输出格式说明

- **HTML**：自包含暗色主题报告，内嵌 CSS 图表，响应式设计 —— 适合分享
- **JSON**：结构化数据，含完整分析结果 —— 适合程序集成和自动化
- **Markdown**：表格格式 —— 适合 GitHub Issue、Wiki 和文档
- **CSV**：电子表格格式 —— 适合 Excel/Google Sheets 数据分析

---

## 💡 设计思路与迭代规划

### 设计理念

1. **零依赖优先**：纯 Python 标准库实现 —— 无需 pip install，无版本冲突
2. **跨平台一致**：Linux、macOS、Windows 三平台体验完全一致
3. **隐私至上**：所有数据本地存储 —— 无云端服务，无数据采集
4. **开发者友好**：结构化输出格式，便于与其他工具集成
5. **渐进增强**：CLI → TUI → HTML 报告，按需使用

### 技术栈

- **语言**：Python 3.8+（仅标准库）
- **存储**：SQLite3（内置）
- **CLI**：argparse（内置）
- **可视化**：ANSI 转义码 + Unicode 字符
- **报告**：HTML/CSS（内联）、JSON、Markdown、CSV

### 🗺️ 迭代规划

- [ ] **v1.1**：实时信号监控仪表板
- [ ] **v1.2**：Wi-Fi 测速功能集成
- [ ] **v1.3**：地理热力图导出（GPS 坐标）
- [ ] **v1.4**：定时自动扫描与告警
- [ ] **v2.0**：Web UI 远程监控面板
- [ ] **v2.1**：多网卡同时扫描支持
- [ ] **v2.2**：企业级 PDF 报告导出

---

## 📦 打包与部署

### 作为独立脚本

```bash
# 直接复制到任意目录即可使用
cp wifiradar.py /usr/local/bin/wifiradar
chmod +x /usr/local/bin/wifiradar

# 现在可以在任何位置运行
wifiradar scan
```

### 作为 Python 包安装

```bash
# 开发模式安装
cd WiFiRadar
pip install -e .

# 直接使用 wifiradar 命令
wifiradar scan
wifiradar analyze
wifiradar report
```

### Systemd 服务（Linux）

```bash
# 创建监控服务
sudo cp wifiradar.service /etc/systemd/system/
sudo systemctl enable wifiradar
sudo systemctl start wifiradar
```

### 定时任务（Cron）

```bash
# 添加到 crontab - 每小时扫描一次
0 * * * * /usr/bin/python3 /path/to/wifiradar.py scan --json >> /var/log/wifiradar.log
```

---

## 🤝 贡献指南

欢迎贡献代码！请遵循以下规范：

### 贡献流程

1. **Fork** 本仓库
2. **创建**功能分支（`git checkout -b feature/amazing-feature`）
3. **编写**代码，添加类型注解和文档字符串
4. **测试**你的修改（`python -m pytest tests/`）
5. **提交**使用规范格式（`git commit -m 'feat: 新增某某功能'`）
6. **推送**到你的分支（`git push origin feature/amazing-feature`）
7. **发起** Pull Request

### 提交规范

| 类型 | 说明 |
|------|------|
| `feat:` | 新功能 |
| `fix:` | 修复 Bug |
| `docs:` | 文档更新 |
| `refactor:` | 代码重构 |
| `test:` | 测试相关 |
| `chore:` | 构建/工具变更 |

### 问题反馈

提交 Issue 时，请包含以下信息：
- 操作系统和版本
- Python 版本
- `wifiradar --version` 的输出
- 错误信息或异常行为
- 复现步骤

---

## 📄 开源协议

本项目基于 **MIT 协议** 开源。

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
  用 ❤️ 制作 by <a href="https://github.com/gitstq">gitstq</a>
</p>
