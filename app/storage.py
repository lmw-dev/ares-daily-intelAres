import os
import json
import logging
from typing import Dict, Any, List, Tuple
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

def get_vault_dirs(scan_date: str, ares_vault_path: str) -> Tuple[str, str]:
    """
    根据 scan_date (格式: YYYY-MM-DD) 计算 Obsidian Vault 对应的物理归档目录。
    - 归档数据目录: AresVault/04_RAG_Raw_Data/Prematch_Report/Ares_Daily_Intel/YYYY/MM/DD/
    - 运行日志目录: AresVault/99_Run_Logs/ares-daily-intel/YYYY/MM/DD/
    """
    parts = scan_date.split("-")
    if len(parts) == 3:
        year, month, day = parts[0], parts[1], parts[2]
    else:
        year, month, day = "unknown", "unknown", "unknown"
        
    report_dir = os.path.join(ares_vault_path, "04_RAG_Raw_Data", "Prematch_Report", "Ares_Daily_Intel", year, month, day)
    log_dir = os.path.join(ares_vault_path, "99_Run_Logs", "ares-daily-intel", year, month, day)
    return report_dir, log_dir

def save_to_local(
    scan_date: str, 
    markdown_content: str, 
    json_data: Dict[str, Any],
    raw_responses: List[Dict[str, Any]],
    timestamp: str = ""
) -> str:
    """
    保存报告和原始响应到本地工作目录归档，并同步双写至本地 Obsidian Vault (若存在)。
    """
    report_dir = get_report_dir(scan_date)
    os.makedirs(report_dir, exist_ok=True)

    suffix = f"_{timestamp}" if timestamp else ""
    md_name = f"{scan_date}{suffix}_daily_scan.md"
    json_name = f"{scan_date}{suffix}_daily_scan.json"

    # 1. 保存到本地工作目录归档 (data/reports/)
    md_path = os.path.join(report_dir, md_name)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    logger.info(f"Report Markdown saved locally to {md_path}")

    json_path = os.path.join(report_dir, json_name)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Report JSON saved locally to {json_path}")

    for item in raw_responses:
        if item.get("parse_status") == "FAILED":
            home = item.get("json", {}).get("home", "home").lower().replace(" ", "_")
            away = item.get("json", {}).get("away", "away").lower().replace(" ", "_")
            raw_name = f"raw_response_{home}_vs_{away}{suffix}.md"
            raw_path = os.path.join(report_dir, raw_name)
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(item.get("raw_response_text", ""))
            logger.info(f"Raw response saved to {raw_path}")

    # 2. 尝试同步双写到 Obsidian Vault
    vault_path = settings.ares_vault_path
    if vault_path and os.path.exists(vault_path):
        try:
            vault_report_dir, vault_log_dir = get_vault_dirs(scan_date, vault_path)
            os.makedirs(vault_report_dir, exist_ok=True)
            os.makedirs(vault_log_dir, exist_ok=True)

            # 写入日报 Markdown 到 04_RAG_Raw_Data
            v_md_path = os.path.join(vault_report_dir, md_name)
            with open(v_md_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            logger.info(f"Obsidian Vault report Markdown double-written to {v_md_path}")

            # 写入日报 JSON 到 04_RAG_Raw_Data
            v_json_path = os.path.join(vault_report_dir, json_name)
            with open(v_json_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Obsidian Vault report JSON double-written to {v_json_path}")

            # 写入错误备份/原始响应到 99_Run_Logs
            for item in raw_responses:
                if item.get("parse_status") == "FAILED":
                    home = item.get("json", {}).get("home", "home").lower().replace(" ", "_")
                    away = item.get("json", {}).get("away", "away").lower().replace(" ", "_")
                    v_raw_name = f"raw_response_{home}_vs_{away}{suffix}.md"
                    v_raw_path = os.path.join(vault_log_dir, v_raw_name)
                    with open(v_raw_path, "w", encoding="utf-8") as f:
                        f.write(item.get("raw_response_text", ""))
                    logger.info(f"Obsidian Vault raw log double-written to {v_raw_path}")
        except Exception as e:
            logger.error(f"Failed to double-write to Obsidian Vault: {e}")

    return report_dir

def upload_to_gcs(
    scan_date: str, 
    markdown_content: str, 
    json_data: Dict[str, Any],
    raw_responses: List[Dict[str, Any]],
    timestamp: str = ""
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
    suffix = f"_{timestamp}" if timestamp else ""
    md_name = f"{scan_date}{suffix}_daily_scan.md"
    json_name = f"{scan_date}{suffix}_daily_scan.json"
    
    try:
        # 初始化客户端。在 GCP / Cloud Run 上，会自动载入服务账号凭据
        client = gcs.Client()
        bucket = client.bucket(bucket_name)

        # 1. 上传 scan.md 对应文件名
        md_blob = bucket.blob(f"{gcs_dir}/{md_name}")
        md_blob.upload_from_string(markdown_content, content_type="text/markdown; charset=utf-8")
        logger.info(f"Uploaded scan.md to gs://{bucket_name}/{gcs_dir}/{md_name}")

        # 2. 上传 scan.json 对应文件名
        json_blob = bucket.blob(f"{gcs_dir}/{json_name}")
        json_blob.upload_from_string(
            json.dumps(json_data, ensure_ascii=False, indent=2), 
            content_type="application/json; charset=utf-8"
        )
        logger.info(f"Uploaded scan.json to gs://{bucket_name}/{gcs_dir}/{json_name}")

        # 3. 上传解析失败的 raw_response.md
        for item in raw_responses:
            if item.get("parse_status") == "FAILED":
                home = item.get("json", {}).get("home", "home").lower().replace(" ", "_")
                away = item.get("json", {}).get("away", "away").lower().replace(" ", "_")
                raw_name = f"raw_response_{home}_vs_{away}{suffix}.md"
                raw_blob = bucket.blob(f"{gcs_dir}/{raw_name}")
                raw_blob.upload_from_string(
                    item.get("raw_response_text", ""), 
                    content_type="text/markdown; charset=utf-8"
                )
                logger.info(f"Uploaded raw response to gs://{bucket_name}/{gcs_dir}/{raw_name}")

        return True
    except Exception as e:
        # GCS 写入报错仅打 warning 日志，防止阻碍整个 Job 的退出状态码
        logger.error(f"Failed to upload reports to GCS bucket '{bucket_name}': {e}")
        return False
