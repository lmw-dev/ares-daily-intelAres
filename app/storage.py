import os
import json
import logging
from typing import Dict, Any, List
from app.config import settings

logger = logging.getLogger(__name__)

# 是否能正常引入 google-cloud-storage
try:
    from google.cloud import storage as gcs
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    logger.warning("google-cloud-storage package is not installed. GCS uploading is disabled.")

def get_report_dir(scan_date: str) -> str:
    """
    根据 scan_date (格式: YYYY-MM-DD) 计算本地报告存放目录。
    例如: data/reports/2026/07/03/
    """
    parts = scan_date.split("-")
    if len(parts) == 3:
        year, month, day = parts[0], parts[1], parts[2]
    else:
        # 兜底
        year, month, day = "unknown", "unknown", "unknown"
    
    report_dir = os.path.join("data", "reports", year, month, day)
    return report_dir

def get_gcs_path(scan_date: str) -> str:
    """
    计算 GCS 上的文件相对路径。
    例如: 2026/07/03/
    """
    parts = scan_date.split("-")
    if len(parts) == 3:
        return f"{parts[0]}/{parts[1]}/{parts[2]}"
    return "unknown"

def save_to_local(
    scan_date: str, 
    markdown_content: str, 
    json_data: Dict[str, Any],
    raw_responses: List[Dict[str, Any]]
) -> str:
    """
    保存报告和原始响应到本地。
    """
    report_dir = get_report_dir(scan_date)
    os.makedirs(report_dir, exist_ok=True)

    # 1. 保存 scan.md
    md_path = os.path.join(report_dir, "scan.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    logger.info(f"Report Markdown saved locally to {md_path}")

    # 2. 保存 scan.json
    json_path = os.path.join(report_dir, "scan.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Report JSON saved locally to {json_path}")

    # 3. 保存解析失败的 raw_response.md
    for item in raw_responses:
        if item.get("parse_status") == "FAILED":
            home = item.get("json", {}).get("home", "home").lower().replace(" ", "_")
            away = item.get("json", {}).get("away", "away").lower().replace(" ", "_")
            raw_path = os.path.join(report_dir, f"raw_response_{home}_vs_{away}.md")
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(item.get("raw_response_text", ""))
            logger.info(f"Raw response for failed parse saved to {raw_path}")

    return report_dir

def upload_to_gcs(
    scan_date: str, 
    markdown_content: str, 
    json_data: Dict[str, Any],
    raw_responses: List[Dict[str, Any]]
) -> bool:
    """
    将文件上传至 Google Cloud Storage。
    """
    if not GCS_AVAILABLE:
        logger.info("GCS is not available. Skipping cloud upload.")
        return False

    bucket_name = settings.gcs_bucket
    if not bucket_name:
        logger.warning("GCS_BUCKET environment variable is not set. Skipping cloud upload.")
        return False

    gcs_dir = get_gcs_path(scan_date)
    
    try:
        # 初始化客户端。在 GCP / Cloud Run 上，会自动载入服务账号凭据
        client = gcs.Client()
        bucket = client.bucket(bucket_name)

        # 1. 上传 scan.md
        md_blob = bucket.blob(f"{gcs_dir}/scan.md")
        md_blob.upload_from_string(markdown_content, content_type="text/markdown; charset=utf-8")
        logger.info(f"Uploaded scan.md to gs://{bucket_name}/{gcs_dir}/scan.md")

        # 2. 上传 scan.json
        json_blob = bucket.blob(f"{gcs_dir}/scan.json")
        json_blob.upload_from_string(
            json.dumps(json_data, ensure_ascii=False, indent=2), 
            content_type="application/json; charset=utf-8"
        )
        logger.info(f"Uploaded scan.json to gs://{bucket_name}/{gcs_dir}/scan.json")

        # 3. 上传解析失败的 raw_response.md
        for item in raw_responses:
            if item.get("parse_status") == "FAILED":
                home = item.get("json", {}).get("home", "home").lower().replace(" ", "_")
                away = item.get("json", {}).get("away", "away").lower().replace(" ", "_")
                raw_blob = bucket.blob(f"{gcs_dir}/raw_response_{home}_vs_{away}.md")
                raw_blob.upload_from_string(
                    item.get("raw_response_text", ""), 
                    content_type="text/markdown; charset=utf-8"
                )
                logger.info(f"Uploaded raw response to gs://{bucket_name}/{gcs_dir}/raw_response_{home}_vs_{away}.md")

        return True
    except Exception as e:
        # GCS 写入报错仅打 warning 日志，防止阻碍整个 Job 的退出状态码
        logger.error(f"Failed to upload reports to GCS bucket '{bucket_name}': {e}")
        return False
