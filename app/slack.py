import logging
import requests
from typing import Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

def make_slack_summary(report_json: Dict[str, Any], scan_date: str, timestamp: str = "") -> str:
    """
    根据 report.json 生成用于 Slack 推送的简明摘要 Markdown 文本。
    包含元数据、赛事表格汇总、内部 GCS 归档路径，且无公开 GCS 链接。
    """
    metadata = report_json.get("run_metadata", {})
    matches = report_json.get("matches", [])
    
    run_id = metadata.get("run_id", "N/A")
    overall_status = metadata.get("parse_status", "SUCCESS")
    grounded_count = metadata.get("grounded_requests_attempted", 0)
    urls_count = metadata.get("source_urls_count", 0)

    summary_text = (
        f"📅 *Ares Daily Intelligence Scan ({scan_date})*\n"
        f"• *Status*: `{overall_status}` (JSON Parse)\n"
        f"• *Grounding Stats*: {grounded_count} attempts | {urls_count} source URLs\n"
        f"• *Run ID*: `{run_id[:8]}`\n\n"
        f"*⚽ Match Summaries:*\n"
    )

    for idx, match in enumerate(matches, 1):
        home = match.get("home", "Unknown")
        away = match.get("away", "Unknown")
        league = match.get("league", "Unknown")
        gate_status = match.get("gate_status", "MISSING")
        
        # 容错解析失败时的情况
        parse_failed = match.get("parse_status") == "FAILED"
        
        if parse_failed:
            summary_text += f"{idx}. *[{league}] {home} vs {away}*\n   ⚠️ _JSON extraction failed for this match._\n"
        else:
            market = match.get("market_preview", {})
            theo = market.get("theoretical_line", "N/A")
            actual = market.get("actual_line", "N/A")
            conf = market.get("confidence", "LOW")
            source = market.get("source", "MARKET_MISSING")
            
            risk_tags = ", ".join(match.get("risk_tags", [])) or "None"
            
            summary_text += (
                f"{idx}. *[{league}] {home} vs {away}*\n"
                f"   • *Gate*: `{gate_status}`\n"
                f"   • *Market*: Theoretical `{theo}` | Actual `{actual}` (Conf: `{conf}` / Src: `{source}`)\n"
                f"   • *Risks*: `{risk_tags}`\n"
            )

    # 附带 GCS 内部路径
    parts = scan_date.split("-")
    gcs_dir = f"{parts[0]}/{parts[1]}/{parts[2]}" if len(parts) == 3 else "unknown"
    suffix = f"_{timestamp}" if timestamp else ""
    md_name = f"{scan_date}{suffix}_daily_scan.md"
    json_name = f"{scan_date}{suffix}_daily_scan.json"
    gcs_path = f"gs://{settings.gcs_bucket}/{gcs_dir}/{md_name}"
    
    summary_text += f"\n📦 *Internal Archive:*\n• `{gcs_path}`\n• `{gcs_path.replace(md_name, json_name)}`"
    
    return summary_text

def push_to_slack(report_json: Dict[str, Any], scan_date: str, timestamp: str = "") -> bool:
    """
    将扫描摘要推送至 Slack Webhook 频道。
    """
    webhook_url = settings.slack_webhook_url
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL environment variable is not configured. Skipping Slack push.")
        return False

    summary_markdown = make_slack_summary(report_json, scan_date, timestamp)
    
    # 构造 Slack Block Kit 或普通的 attachments 消息
    payload = {
        "text": f"Ares Daily Intelligence Summary ({scan_date})",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": summary_markdown
                }
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Successfully pushed scan summary to Slack.")
            return True
        else:
            logger.error(f"Slack Webhook returned error (status {response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send Slack Webhook: {e}")
        return False
