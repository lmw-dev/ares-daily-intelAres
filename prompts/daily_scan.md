# Ares Daily Intelligence Report ({scan_date})

**运行环境/配置**:
- Model: {model}
- Runtime: {runtime}
- Cloud Run Region: {cloud_run_region}
- Google Cloud Location: {google_cloud_location}
- Run ID: {run_id}
- Run Status: JSON Parse {parse_status}
- Stats: Grounded Requests: {grounded_requests_attempted} | Support URLs: {grounding_support_urls_count}

---

## ⚽ 赛事速览 (Overview)
| 联赛 | 对阵 | Gate 状态 | 理论盘口 | 实际盘口 | 信心指数 | 风险标签 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{summary_table_rows}

---

## 🔍 深度战力情报 (Deep Scans)
{detailed_reports}

---
*GCS 存储路径: {gcs_path}*
