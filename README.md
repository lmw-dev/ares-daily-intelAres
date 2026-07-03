# Ares Daily Intelligence (Ares 每日赛事战力情报)

这是一个最小闭环的 Python 项目，用于定时（或手动触发）分析指定赛事，通过 Gemini 搜索增强（Grounding with Google Search）抓取伤停、阵容预测、战意和赔率 preview，按照 Ares 分析方法论输出结构化情报，双写保存至本地及 Google Cloud Storage (GCS)，并向 Slack 发送摘要通知。

## 目录结构
```text
ares-daily-intel/
├── app/
│   ├── main.py          # 主入口
│   ├── config.py        # 配置管理 (Pydantic Settings)
│   ├── gemini_client.py # 封装 Gemini / Vertex AI 客户端
│   ├── match_loader.py  # matches.yml & sources.yml 加载
│   ├── scan.py          # 单场比赛分析与 JSON 提取
│   ├── report.py        # 报告汇总与格式化
│   ├── storage.py       # 本地与 GCS 双写持久化
│   └── slack.py         # Slack Webhook 摘要推送
├── data/
│   ├── matches.yml      # 待扫描的比赛配置
│   └── sources.yml      # 搜索词模板
├── prompts/
│   ├── daily_scan.md    # 汇总日报 Prompt 模板
│   └── match_scan.md    # 单场深度分析 Prompt 模板
├── tests/
│   ├── test_match_loader.py
│   └── test_report.py
├── Dockerfile           # 容器化构建
└── requirements.txt     # 项目依赖
```

## 运行配置
本项目支持两种认证与执行环境：
1. **本地开发 (API Key Fallback)**：配置 `.env` 里的 `GEMINI_API_KEY`，并设置 `GOOGLE_GENAI_USE_VERTEXAI=false`。
2. **云端运行 (Cloud Run / Vertex AI)**：
   使用 Application Default Credentials (ADC) 获取 IAM 权限，由 Cloud Run Service Account 提供安全凭证。配置以下环境变量：
   - `GOOGLE_GENAI_USE_VERTEXAI=true`
   - `GOOGLE_CLOUD_PROJECT=vertex-project-493203`
   - `GOOGLE_CLOUD_LOCATION=us-central1`

## 本地运行
1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 本地执行 (支持 `DRY_RUN=true` 测试流程)：
   ```bash
   python app/main.py
   ```

## Sync GCS reports to Obsidian
由于 Cloud Run Job 部署在云端只能向 GCS 存储桶进行文件归档，为使本地 Obsidian / Ares Vault 保持同步以提供 RAG 分析，您需要在本机手动或配置脚本定期拉取同步。

我们提供了同步脚本 `scripts/sync_gcs_to_obsidian.sh`：
1. **默认执行**（同步北京时间当天归档）：
   ```bash
   ./scripts/sync_gcs_to_obsidian.sh
   ```
2. **手动指定日期同步**（格式 `YYYY/MM/DD`）：
   ```bash
   SYNC_DATE=2026/07/03 ./scripts/sync_gcs_to_obsidian.sh
   ```

**同步归档规则**：
- 日报与元数据（`*_daily_scan.md` & `*.json`）将同步至本地：
  `04_RAG_Raw_Data/Prematch_Report/Ares_Daily_Intel/YYYY/MM/DD/`
- 解析异常的原始备份将同步至本地：
  `99_Run_Logs/ares-daily-intel/YYYY/MM/DD/`
