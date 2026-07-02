# Ares Daily Intelligence v0.1-alpha 交接文档

本项目已完成 v0.1-alpha 版本的骨架搭建与核心逻辑实现，成功将代码推送至 GitHub 仓库，并通过了本地单元测试及 Dry-run 完整流程验证。

---

## 1. 架构模块设计与文件关系

当前项目代码已完全遵循您建议的骨架进行重构，实现了各个业务层面的解耦：

- **[main.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/main.py)**: 主入口编排器。加载配置 -> 解析赛事 -> 控制调用预算限制（首周切片限制为 1） -> 遍历扫描单场 -> 生成并保存报告 -> Slack 推送。
- **[config.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/config.py)**: 依靠 `pydantic-settings` 模块规范环境配置与预算参数。
- **[gemini_client.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/gemini_client.py)**: 统一初始化 Google GenAI 客户端。智能切换 Vertex AI（由 ADC 提供免 Key 认证）与 API Key 模式。
- **[match_loader.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/match_loader.py)**: 健壮读取 `matches.yml`（赛事列表）及 `sources.yml`（搜索词模板）。
- **[scan.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/scan.py)**: 单场分析核心。封装 Gemini Google Search Grounding，正则提取 JSON，并在 JSON 提取出错时提供防御性降级逻辑。
- **[report.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/report.py)**: 根据 `daily_scan.md` 渲染最终 Markdown，组装 `run_metadata` 和比赛数据生成总 JSON。
- **[storage.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/storage.py)**: 负责双写保存至本地 `/data/reports/YYYY/MM/DD/` 目录以及云端 GCS，已做好捕获 GCS 上传失败的拦截，避免阻塞 Job 顺利退出。
- **[slack.py](file:///Users/liumingwei/01-project/12-liumw/26-ares-daily-intel/app/slack.py)**: 过滤掉全文，专为 Slack Webhook 定制简明 Markdown 摘要（包含 GCS 内部路径 `gs://...`，不包含任何暴露的公开 URL）。

---

## 2. 避坑指南与技术决策

1. **解决 Grounding Metadata 丢失问题**：
   - 官方 SDK 设计中，如果调用 `client.models.generate_content` 时强制声明了 `response_mime_type="application/json"` 或指定了强 `response_schema`，返回结果的 `grounding_metadata` 将会被清空，导致无法抓取 `source_urls`。
   - **解决方案**：请求普通文本格式，并在 Prompt (`prompts/match_scan.md`) 中约定将 JSON 包含在末尾的代码块中，通过 Python 正则表达式进行软解析。
2. **免密 ADC (Application Default Credentials)**：
   - 运行于 Cloud Run 环境下时，无需也不能硬编码任何 API 密钥。SDK 会自适应加载托管 Service Account 的凭据授权。
   - 环境变量需配置：`GOOGLE_GENAI_USE_VERTEXAI=true`，`GOOGLE_CLOUD_PROJECT`，及固定区域 `GOOGLE_CLOUD_LOCATION=us-central1`。
3. **盘口降级与防爆**：
   - 盘口强制作为 **Market Preview**，若搜索缺乏来源、时间等佐证信息，强制回退判定为 `MARKET_MISSING`，且拒绝输出投注建议。
   - 若解析失败，在 JSON 标记 `parse_status=FAILED` 并在本地或 GCS 双写保留原始大模型响应文本为 `raw_response_{home}_vs_{away}.md`，保证 Job 不会挂断，日常报告稳定产出。

---

## 3. 本地验证与质量指标

- **单元测试**：
  在配置了 `pydantic-settings` 的 venv 下，执行四项单元测试全部成功：
  ```text
  Ran 4 tests in 0.001s
  OK
  ```
- **Dry-run 运行表现**：
  在 `DRY_RUN=True` 下测试，程序成功拦截 GCS 404（桶不存在）和 Slack 未配置错误，仅打印警告，日志显示 `=== Ares Daily Intelligence Job Finished Successfully ===`，符合预期。

---

## 4. 后续部署与 Billing 监控建议

1. **第一周 Billing 验证（Billing Guard）**：
   - 本地将 `DRY_RUN=False` 并在 `.env` 里填入您的 Gemini Key，或者直接在云端跑一次，限制 `MAX_MATCHES=1`。
   - 执行完成后，等待 12–24 小时检查 Google Cloud Billing 中 `GenAI App Builder credit` 或相关的扣减趋势，观察是否完美抵扣。
   - 确认扣减抵扣正常后，方可修改环境变量将 `MAX_MATCHES` 扩展至 5。
2. **GitHub Actions 部署配置**：
   - 需在 GitHub Repo Settings 的 Secrets 中增加 `GCP_SA_KEY`（含有部署权限的 Service Account JSON 密钥）。
   - CI/CD 触发后会自动通过 Dockerfile 打包并部署到您指定的 Cloud Run Job 中。
