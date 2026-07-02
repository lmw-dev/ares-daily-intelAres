import os
import json
import uuid
import datetime
from typing import List, Dict, Any, Tuple
from app.config import settings

PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    "prompts", 
    "daily_scan.md"
)

def load_daily_template() -> str:
    """加载每日汇总报告 Markdown 模板"""
    if not os.path.exists(PROMPT_PATH):
        raise FileNotFoundError(f"Daily scan template file not found at {PROMPT_PATH}")
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()

def generate_daily_reports(
    scan_results: List[Dict[str, Any]], 
    scan_date: str,
    gcs_path: str
) -> Tuple[str, Dict[str, Any]]:
    """
    根据单场比赛的分析结果，组装并生成最终的每日报告 Markdown 字符串和结构化 JSON。
    """
    run_id = str(uuid.uuid4())
    model = settings.gemini_model
    location = settings.google_cloud_location if settings.google_genai_use_vertexai else "local"

    # 1. 统计各项元数据指标
    grounded_requests = len(scan_results) if not settings.dry_run else 0
    all_source_urls = []
    has_parse_failed = False
    
    for r in scan_results:
        all_source_urls.extend(r.get("source_urls", []))
        if r.get("parse_status") == "FAILED":
            has_parse_failed = True

    total_sources_count = len(set(all_source_urls))
    overall_parse_status = "FAILED" if has_parse_failed else "SUCCESS"

    # 2. 组装汇总表格和详细段落
    table_rows = []
    detailed_reports = []
    json_matches = []

    for r in scan_results:
        match_json = r.get("json", {})
        json_matches.append(match_json)
        
        home = match_json.get("home", "Unknown")
        away = match_json.get("away", "Unknown")
        league = match_json.get("league", "Unknown")
        gate_status = match_json.get("gate_status", "MISSING")
        
        market = match_json.get("market_preview", {})
        theo = market.get("theoretical_line", "UNKNOWN")
        actual = market.get("actual_line", "UNKNOWN")
        confidence = market.get("confidence", "LOW")
        
        risk_tags = ", ".join(match_json.get("risk_tags", [])) or "None"

        # 拼接表格行
        row = f"| {league} | {home} vs {away} | {gate_status} | {theo} | {actual} | {confidence} | {risk_tags} |"
        table_rows.append(row)

        # 拼接详细报告
        match_text = r.get("text", "")
        # 移出可能嵌入的 JSON 块以保证日报 Markdown 干净美观
        clean_text = match_text.split("```json")[0].strip()
        
        # 加上 source_urls 部分
        sources_section = "\n\n### 🔗 来源信源 (Source URLs)\n"
        urls = r.get("source_urls", [])
        if urls:
            for url in urls:
                sources_section += f"- [{url.split('//')[-1].split('/')[0]}]({url})\n"
        else:
            sources_section += "- *MARKET_MISSING / NO SOURCE FOUND*\n"

        detailed_reports.append(f"{clean_text}\n{sources_section}\n\n---")

    summary_table_rows = "\n".join(table_rows)
    detailed_reports_text = "\n\n".join(detailed_reports)

    # 3. 渲染 Markdown 报告
    template = load_daily_template()
    markdown_report = template.format(
        scan_date=scan_date,
        model=model,
        location=location,
        run_id=run_id,
        parse_status=overall_parse_status,
        grounded_requests_attempted=grounded_requests,
        grounding_support_urls_count=total_sources_count,
        summary_table_rows=summary_table_rows,
        detailed_reports=detailed_reports_text,
        gcs_path=gcs_path
    )

    # 4. 组装结构化 JSON
    report_json = {
        "run_metadata": {
            "run_id": run_id,
            "model": model,
            "location": location,
            "grounded_requests_attempted": grounded_requests,
            "source_urls_count": total_sources_count,
            "parse_status": overall_parse_status,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        },
        "matches": json_matches
    }

    return markdown_report, report_json
