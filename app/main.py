import os
import sys

# 动态注入项目根目录到 python path 中以防止 ModuleNotFoundError
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from dotenv import load_dotenv

# 加载本地环境变量（如果在生产环境容器内没有 .env 文件，直接读取容器环境变量）
load_dotenv()

# 初始化日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ares-daily-intel")

from app.config import settings
from app.match_loader import load_matches_config, load_sources_config
from app.gemini_client import get_gemini_client
from app.scan import scan_single_match
from app.report import generate_daily_reports
from app.storage import save_to_local, upload_to_gcs, get_gcs_path
from app.slack import push_to_slack

def main():
    logger.info("=== Ares Daily Intelligence System Starting ===")
    logger.info(f"Configuration profile: DRY_RUN={settings.dry_run}, VertexAI={settings.google_genai_use_vertexai}")
    
    # 1. 加载比赛和搜索源配置
    try:
        matches_data = load_matches_config()
        scan_date = matches_data.get("scan_date", "2026-07-03")
        matches = matches_data.get("matches", [])
        logger.info(f"Loaded matches config. Scan date: {scan_date}. Found {len(matches)} matches.")
    except Exception as e:
        logger.critical(f"Failed to load match configurations: {e}")
        sys.exit(1)

    if not matches:
        logger.info("No matches configuration found for today. Exiting.")
        sys.exit(0)

    # 2. 成本预算控制：最大比赛数切片限制 (Billing Guard)
    max_matches = settings.max_matches
    if len(matches) > max_matches:
        logger.warning(f"Today's matches count ({len(matches)}) exceeds MAX_MATCHES ({max_matches}). Slicing match list to comply with billing budget.")
        matches = matches[:max_matches]

    # 3. 初始化 Gemini SDK 客户端 (如果是 Dry-run 则不要求初始化成功，以支持离线开发测试)
    client = None
    if not settings.dry_run:
        try:
            client = get_gemini_client()
            logger.info("Gemini / Vertex AI Client initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize Gemini / Vertex Client: {e}")
            sys.exit(1)

    # 4. 逐场进行赛事扫描与深度分析
    scan_results = []
    grounded_prompts_attempted = 0
    max_grounded_prompts = settings.max_grounded_prompts_per_run

    for match in matches:
        # 预算控制：限制总请求数
        if grounded_prompts_attempted >= max_grounded_prompts:
            logger.warning(f"Grounded prompt limit reached ({max_grounded_prompts}). Aborting remaining scans for budget safety.")
            break

        # 开始扫描
        result = scan_single_match(client, match)
        scan_results.append(result)
        
        if not settings.dry_run:
            grounded_prompts_attempted += 1

    logger.info(f"All matches scanned. Total analyzed: {len(scan_results)} matches.")

    # 计算当前运行北京时间的时间戳 (%H%M)，防覆盖且用于分类归档
    import datetime
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    timestamp_str = now.strftime("%H%M")

    # 5. 生成汇总报告 (计算 GCS 保存路径用于报告内展示)
    gcs_dir = get_gcs_path(scan_date)
    gcs_full_path = f"gs://{settings.gcs_bucket}/{gcs_dir}/{scan_date}_{timestamp_str}_daily_scan.md"
    
    try:
        markdown_report, report_json = generate_daily_reports(scan_results, scan_date, gcs_full_path)
        logger.info("Successfully generated daily Markdown and JSON reports.")
    except Exception as e:
        logger.error(f"Failed to compile report summaries: {e}")
        sys.exit(1)

    # 6. 保存报告（双写：本地 + 谷歌云存储，同时支持 Obsidian Vault 分类归档）
    try:
        save_to_local(scan_date, markdown_report, report_json, scan_results, timestamp=timestamp_str)
    except Exception as e:
        logger.error(f"Failed to save reports locally: {e}")

    try:
        upload_to_gcs(scan_date, markdown_report, report_json, scan_results, timestamp=timestamp_str)
    except Exception as e:
        logger.error(f"Failed to upload reports to GCS: {e}")

    # 7. 推送消息至 Slack
    try:
        push_to_slack(report_json, scan_date, timestamp=timestamp_str)
    except Exception as e:
        logger.error(f"Failed to trigger Slack Webhook push: {e}")

    logger.info("=== Ares Daily Intelligence Job Finished Successfully ===")
    sys.exit(0)

if __name__ == "__main__":
    main()
