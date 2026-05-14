<p align="center">
  <h1 align="center">📡 WiFiRadar</h1>
  <p align="center">
    <strong>輕量級 Wi-Fi 訊號智慧分析與視覺化 CLI 引擎</strong>
  </p>
  <p align="center">
    <a href="README.md">English</a> ·
    <a href="README_zh.md">简体中文</a> ·
    繁體中文
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

## 🎉 專案介紹

**WiFiRadar** 是一款零依賴、跨平台的 Wi-Fi 訊號智慧分析與視覺化命令列引擎。它能掃描附近的 Wi-Fi 網路，對頻道擁塞、干擾水準和訊號品質進行深度分析，並產生可操作的優化建議和精美的視覺化報告。

### 💡 為什麼需要 WiFiRadar？

你是否遇到過這樣的困惑：Wi-Fi 訊號滿格，但網速卻很慢？答案往往隱藏在**頻道擁塞**和**鄰近網路干擾**中。WiFiRadar 為你呈現完整的無線環境全貌：

- 📊 **視覺化**展示所有附近網路的訊號強度
- 🔍 **深度分析**頻道擁塞度和干擾評分
- ✅ **智慧推薦**路由器最佳頻道
- 📈 **追蹤**訊號強度隨時間的變化趨勢
- 📄 **匯出**專業級 HTML/JSON/Markdown/CSV 報告

### 🌟 差異化亮點

| 特性 | WiFiRadar | 常見 Wi-Fi 工具 |
|------|-----------|----------------|
| 外部依賴 | **零依賴** | 通常需要 GUI 框架 |
| 輸出格式 | **4 種格式**（HTML/JSON/MD/CSV） | 通常僅 1-2 種 |
| 歷史追蹤 | **SQLite 持久化**含趨勢分析 | 極少支援 |
| 頻道分析 | **擁塞度 + 干擾評分** | 僅基礎頻道列表 |
| 跨平台 | **Linux/macOS/Windows** | 通常限定平台 |
| 安裝方式 | **複製即用** | pip install / 套件管理器 |

---

## ✨ 核心特性

### 📡 智慧掃描
- **自動偵測平台**：Linux 使用 `nmcli`，macOS 使用 `airport`，Windows 使用 `netsh`
- **全面資料採集**：SSID、BSSID、訊號強度、頻道、頻率、安全協定、頻段
- **演示模式**：內建模擬資料，無需 Wi-Fi 硬體即可體驗完整功能

### 📊 訊號分析
- **頻道擁塞分析**：統計各頻道網路數量，自動偵測頻道重疊
- **干擾評分**：基於同頻干擾和鄰頻干擾的加權評分演算法
- **訊號品質評級**：綜合訊號強度和擁塞度給出 A/B/C/D/F 等級
- **最佳頻道推薦**：同時為 2.4GHz 和 5GHz 頻段推薦最佳頻道
- **安全評估**：WPA3/WPA2/WPA/WEP/開放網路分類統計與評估
- **頻段利用率分析**：2.4GHz 與 5GHz 網路分佈對比

### 🎨 終端視覺化
- **訊號強度柱狀圖**：顏色編碼（🟢 綠色 / 🟡 黃色 / 🔴 紅色）
- **頻道使用熱力圖**：Unicode 方塊字元（█▓▒░）展示 2.4GHz 和 5GHz 頻道佔用
- **頻段分佈圖**：ASCII 水平條形圖
- **干擾評分視覺化**：逐頻道干擾水準展示
- **安全類型分佈圖**：安全協定使用概況

### 📄 多格式報告
- **HTML 報告**：自包含暗色主題頁面，CSS 圖表，響應式設計
- **JSON 報告**：結構化資料匯出，便於程式整合
- **Markdown 報告**：GitHub/wiki 友善格式，表格展示
- **CSV 報告**：電子表格相容格式，便於資料分析

### 📈 掃描歷史
- **SQLite 儲存**：持久化掃描歷史，WAL 模式提升並發效能
- **趨勢分析**：訊號強度隨時間的變化趨勢
- **變更偵測**：兩次掃描間的新增/消失網路識別
- **資料匯出**：趨勢資料支援 CSV/JSON 格式匯出

### 🖥️ CLI 命令一覽

| 命令 | 說明 |
|------|------|
| `wifiradar scan` | 掃描並展示 Wi-Fi 網路 |
| `wifiradar analyze` | 完整分析並給出優化建議 |
| `wifiradar report` | 產生綜合 HTML 報告 |
| `wifiradar history` | 管理掃描歷史（列表/檢視/趨勢/對比/清理） |
| `wifiradar monitor` | 持續監控模式 |
| `wifiradar demo` | 使用模擬資料執行演示 |

---

## 🚀 快速開始

### 📋 環境需求

- **Python 3.8+**（無需安裝任何其他依賴！）
- **作業系統**：Linux、macOS 或 Windows
- **Wi-Fi 網卡**（真實掃描需要；演示模式無需硬體）

### ⚡ 安裝

```bash
# 複製仓库
git clone https://github.com/gitstq/WiFiRadar.git
cd WiFiRadar

# 就這麼簡單！無需 pip install —— 零依賴！
# 直接執行：
python3 wifiradar.py --version
```

### 🎮 基礎用法

```bash
# 掃描附近的 Wi-Fi 網路
python3 wifiradar.py scan

# 完整分析並獲取優化建議
python3 wifiradar.py analyze

# 產生精美的 HTML 報告
python3 wifiradar.py report

# 演示模式（無需 Wi-Fi 硬體）
python3 wifiradar.py demo

# 顯示訊號最強的前 10 個網路
python3 wifiradar.py scan --top 10

# 僅顯示 5GHz 頻段網路
python3 wifiradar.py scan --filter-band 5GHz

# 匯出掃描結果為 JSON
python3 wifiradar.py scan --json

# 匯出為 CSV 便於表格分析
python3 wifiradar.py scan --csv

# 產生 Markdown 格式報告
python3 wifiradar.py scan --markdown
```

### 📊 進階用法

```bash
# 持續監控（每 30 秒掃描一次）
python3 wifiradar.py monitor --interval 30

# 訊號低於 -70 dBm 時告警
python3 wifiradar.py monitor --alert-threshold -70

# 檢視掃描歷史
python3 wifiradar.py history list

# 檢視指定網路的訊號趨勢
python3 wifiradar.py history trend --bssid AA:BB:CC:DD:EE:FF

# 對比兩次掃描結果
python3 wifiradar.py history compare --scan-ids 1,2

# 產生報告並儲存到指定路徑
python3 wifiradar.py report --output ~/wifi_report.html

# 按頻道排序
python3 wifiradar.py scan --sort-by channel

# 篩選最低訊號強度
python3 wifiradar.py scan --min-signal -60
```

---

## 📖 詳細使用指南

### 訊號品質等級

| 等級 | 訊號 (dBm) | 品質 | 說明 |
|------|-----------|------|------|
| **A** | -30 ~ -50 | 優秀 | 適合所有網路活動 |
| **B** | -51 ~ -60 | 良好 | 串流和遊戲無壓力 |
| **C** | -61 ~ -70 | 一般 | 適合瀏覽和郵件 |
| **D** | -71 ~ -80 | 較差 | 連線不穩定 |
| **F** | < -80 | 無訊號 | 無法使用 |

### 頻道擁塞等級

| 等級 | 評分 | 說明 |
|------|------|------|
| 🟢 **低** | 0-30 | 干擾極小，理想狀態 |
| 🟡 **中** | 31-60 | 存在一定干擾，可接受 |
| 🟠 **高** | 61-80 | 干擾較大，建議切換頻道 |
| 🔴 **嚴重** | 81-100 | 擁堵嚴重，請立即更換頻道 |

### 輸出格式說明

- **HTML**：自包含暗色主題報告，內嵌 CSS 圖表，響應式設計 —— 適合分享
- **JSON**：結構化資料，含完整分析結果 —— 適合程式整合和自動化
- **Markdown**：表格格式 —— 適合 GitHub Issue、Wiki 和文件
- **CSV**：電子表格格式 —— 適合 Excel/Google Sheets 資料分析

---

## 💡 設計思路與迭代規劃

### 設計理念

1. **零依賴優先**：純 Python 標準函式庫實作 —— 無需 pip install，無版本衝突
2. **跨平台一致**：Linux、macOS、Windows 三平台體驗完全一致
3. **隱私至上**：所有資料本地儲存 —— 無雲端服務，無資料採集
4. **開發者友善**：結構化輸出格式，便於與其他工具整合
5. **漸進增強**：CLI → TUI → HTML 報告，按需使用

### 技術棧

- **語言**：Python 3.8+（僅標準函式庫）
- **儲存**：SQLite3（內建）
- **CLI**：argparse（內建）
- **視覺化**：ANSI 跳脫碼 + Unicode 字元
- **報告**：HTML/CSS（內嵌）、JSON、Markdown、CSV

### 🗺️ 迭代規劃

- [ ] **v1.1**：即時訊號監控儀表板
- [ ] **v1.2**：Wi-Fi 測速功能整合
- [ ] **v1.3**：地理熱力圖匯出（GPS 座標）
- [ ] **v1.4**：定時自動掃描與告警
- [ ] **v2.0**：Web UI 遠端監控面板
- [ ] **v2.1**：多網卡同時掃描支援
- [ ] **v2.2**：企業級 PDF 報告匯出

---

## 📦 打包與部署

### 作為獨立腳本

```bash
# 直接複製到任意目錄即可使用
cp wifiradar.py /usr/local/bin/wifiradar
chmod +x /usr/local/bin/wifiradar

# 現在可以在任何位置執行
wifiradar scan
```

### 作為 Python 套件安裝

```bash
# 開發模式安裝
cd WiFiRadar
pip install -e .

# 直接使用 wifiradar 命令
wifiradar scan
wifiradar analyze
wifiradar report
```

### Systemd 服務（Linux）

```bash
# 建立監控服務
sudo cp wifiradar.service /etc/systemd/system/
sudo systemctl enable wifiradar
sudo systemctl start wifiradar
```

### 排程任務（Cron）

```bash
# 新增到 crontab - 每小時掃描一次
0 * * * * /usr/bin/python3 /path/to/wifiradar.py scan --json >> /var/log/wifiradar.log
```

---

## 🤝 貢獻指南

歡迎貢獻程式碼！請遵循以下規範：

### 貢獻流程

1. **Fork** 本倉庫
2. **建立**功能分支（`git checkout -b feature/amazing-feature`）
3. **撰寫**程式碼，新增型別註解和文件字串
4. **測試**你的修改（`python -m pytest tests/`）
5. **提交**使用規範格式（`git commit -m 'feat: 新增某某功能'`）
6. **推送**到你的分支（`git push origin feature/amazing-feature`）
7. **發起** Pull Request

### 提交規範

| 類型 | 說明 |
|------|------|
| `feat:` | 新功能 |
| `fix:` | 修復 Bug |
| `docs:` | 文件更新 |
| `refactor:` | 程式碼重構 |
| `test:` | 測試相關 |
| `chore:` | 建構/工具變更 |

### 問題回饋

提交 Issue 時，請包含以下資訊：
- 作業系統和版本
- Python 版本
- `wifiradar --version` 的輸出
- 錯誤訊息或異常行為
- 重現步驟

---

## 📄 開源協議

本專案基於 **MIT 協議** 開源。

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
  用 ❤️ 製作 by <a href="https://github.com/gitstq">gitstq</a>
</p>
