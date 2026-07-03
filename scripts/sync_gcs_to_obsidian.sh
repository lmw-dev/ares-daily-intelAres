#!/usr/bin/env bash

set -euo pipefail

# 默认环境变量配置
GCS_BUCKET="${GCS_BUCKET:-ares-daily-intel-reports-20260702}"
ARES_VAULT_ROOT="${ARES_VAULT_ROOT:-/Users/liumingwei/vaults/AresVault}"

# SYNC_DATE 默认使用当前日期 (格式: YYYY/MM/DD)
if [ -z "${SYNC_DATE:-}" ]; then
    SYNC_DATE=$(date +"%Y/%m/%d")
fi

echo "=== Ares Daily Intel GCS Sync Starting ==="
echo "GCS Bucket:  ${GCS_BUCKET}"
echo "Sync Date:   ${SYNC_DATE}"
echo "Vault Root:  ${ARES_VAULT_ROOT}"
echo "=========================================="

# 1. 连通性与源路径访问校验
# 若 GCS 路径整体不可访问或不存在，则直接抛错退出
echo "Checking GCS connection and listing source files..."
if ! files=$(gcloud storage ls "gs://${GCS_BUCKET}/${SYNC_DATE}/" 2>/dev/null); then
    echo "ERROR: GCS source path 'gs://${GCS_BUCKET}/${SYNC_DATE}/' is not accessible or project context is missing." >&2
    exit 1
fi

if [ -z "$files" ]; then
    echo "ERROR: GCS source path 'gs://${GCS_BUCKET}/${SYNC_DATE}/' exists but contains no files." >&2
    exit 1
fi

# 2. 定义局部归档路径
DEST_REPORT_DIR="${ARES_VAULT_ROOT}/04_RAG_Raw_Data/Prematch_Report/Ares_Daily_Intel/${SYNC_DATE}"
DEST_LOG_DIR="${ARES_VAULT_ROOT}/99_Run_Logs/ares-daily-intel/${SYNC_DATE}"

# 用于追踪同步的文件列表
synced_files=()

# 定义防御性同步函数，针对没有匹配到某类文件时仅发出 Warning
sync_by_pattern() {
    local label="$1"
    local regex_pattern="$2"
    local target_dir="$3"

    # 匹配过滤 GCS 文件名
    local matched_files
    matched_files=$(echo "$files" | grep -E "$regex_pattern" || true)

    if [ -z "$matched_files" ]; then
        echo "WARNING: No files found matching label '$label' ($regex_pattern) in GCS."
        return 0
    fi

    mkdir -p "$target_dir"

    while read -r gcs_file; do
        if [ -n "$gcs_file" ]; then
            # 提取纯文件名
            local filename
            filename=$(basename "$gcs_file")
            echo "Syncing: $filename -> $target_dir"
            
            # 使用 gcloud storage cp 进行同步下载
            gcloud storage cp "$gcs_file" "$target_dir/"
            synced_files+=("$filename")
        fi
    done <<< "$matched_files"
}

# 3. 按照规则执行同步
echo "Starting file download..."

# 同步日报报告和元数据
sync_by_pattern "Daily Scan Markdown" "_daily_scan\.md$|/scan\.md$" "${DEST_REPORT_DIR}"
sync_by_pattern "Daily Scan JSON" "_daily_scan\.json$|/scan\.json$" "${DEST_REPORT_DIR}"

# 同步运行错误或原始日志备份
sync_by_pattern "Raw Response Logs" "raw_response.*\.md$" "${DEST_LOG_DIR}"

# 4. 输出执行汇总结果
echo "=========================================="
echo "=== Ares Daily Intel Sync Complete ==="
echo "GCS Source Path: gs://${GCS_BUCKET}/${SYNC_DATE}/"
echo "Obsidian Target: ${DEST_REPORT_DIR}/"

if [ ${#synced_files[@]} -eq 0 ]; then
    echo "Files Synced:    None"
else
    echo "Files Synced:"
    for f in "${synced_files[@]}"; do
        echo "  - $f"
    done
fi

echo "💡 Suggestion: Please open Obsidian and refresh the file tree to see updated reports."
echo "=========================================="
exit 0
