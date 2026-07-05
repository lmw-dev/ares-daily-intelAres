import os
import sys
import json
import glob
import re
import argparse
from typing import Dict, Any, List

def parse_args():
    parser = argparse.ArgumentParser(description="Prepare document JSONL for Agent Search POC")
    parser.add_argument("--dry-run", action="store_true", help="Print extracted metadata without writing jsonl file")
    return parser.parse_known_args()

def clean_id(name: str) -> str:
    """Discovery Engine 要求 ID 只能是字母数字下划线或连字符"""
    cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    # 确保不以连字符或下划线开头
    if cleaned.startswith(('-', '_')):
        cleaned = 'doc' + cleaned
    return cleaned

def scan_documents(vault_path: str, max_docs: int) -> List[Dict[str, Any]]:
    target_dir = os.path.join(vault_path, "04_RAG_Raw_Data", "Prematch_Report", "Ares_Daily_Intel")
    if not os.path.exists(target_dir):
        print(f"WARNING: Vault directory does not exist: {target_dir}")
        return []

    # 1. 寻找所有的 json 配置文件
    json_pattern = os.path.join(target_dir, "**", "*_daily_scan.json")
    json_files = sorted(glob.glob(json_pattern, recursive=True), reverse=True) # 最近在前的日期优先

    documents = []
    processed_files = set()

    for j_file in json_files:
        if len(documents) >= max_docs:
            break

        try:
            with open(j_file, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        except Exception as e:
            print(f"Error reading JSON {j_file}: {e}")
            continue

        # 配对的 md 报告内容
        md_file = j_file.replace(".json", ".md")
        content = ""
        if os.path.exists(md_file):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"Error reading MD {md_file}: {e}")
        
        metadata = json_data.get("run_metadata", {})
        matches_list = json_data.get("matches", [])
        
        match_names = []
        gate_statuses = []
        for m in matches_list:
            if isinstance(m, dict):
                home = m.get("home", "Unknown")
                away = m.get("away", "Unknown")
                match_names.append(f"{home} vs {away}")
                gate_statuses.append(m.get("gate_status", "MISSING"))

        file_basename = os.path.basename(j_file).replace(".json", "")
        doc_id = clean_id(file_basename)
        
        # 封装为 Discovery Engine 标准的 structData schema 结构
        doc = {
            "id": doc_id,
            "structData": {
                "title": file_basename,
                "content": content if content else f"No Markdown report content. Metadata: {json.dumps(json_data)}",
                "date": metadata.get("scan_date", "2026-07-04"),
                "source_path": j_file,
                "document_type": "ares_daily_intel",
                "metadata": {
                    "matches": match_names,
                    "gate_statuses": gate_statuses,
                    "source_urls_count": metadata.get("source_urls_count", 0),
                    "parse_status": metadata.get("parse_status", "SUCCESS")
                }
            }
        }
        documents.append(doc)
        processed_files.add(j_file)
        processed_files.add(md_file)

    # 2. 如果文件数不足，继续查找只有 md 没有 json 的报告
    if len(documents) < max_docs:
        md_pattern = os.path.join(target_dir, "**", "*.md")
        md_files = sorted(glob.glob(md_pattern, recursive=True), reverse=True)
        for m_file in md_files:
            if len(documents) >= max_docs:
                break
            if m_file in processed_files:
                continue

            try:
                with open(m_file, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"Error reading MD {m_file}: {e}")
                continue

            file_basename = os.path.basename(m_file).replace(".md", "")
            doc_id = clean_id(file_basename)
            
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', file_basename)
            doc_date = date_match.group(0) if date_match else "2026-07-04"

            doc = {
                "id": doc_id,
                "structData": {
                    "title": file_basename,
                    "content": content,
                    "date": doc_date,
                    "source_path": m_file,
                    "document_type": "ares_daily_intel",
                    "metadata": {
                        "matches": [],
                        "gate_statuses": [],
                        "source_urls_count": 0,
                        "parse_status": "UNKNOWN"
                    }
                }
            }
            documents.append(doc)
            processed_files.add(m_file)

    return documents

def main():
    args, unknown = parse_args()
    
    # 优先使用环境变量，否则使用默认配置
    vault_path = os.environ.get("ARES_VAULT_ROOT", "/Users/liumingwei/vaults/AresVault")
    output_path = os.environ.get("OUTPUT_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "ares_documents.jsonl"))
    max_docs = int(os.environ.get("MAX_DOCS", "20"))
    
    print(f"Scanning vaults path: {vault_path}")
    docs = scan_documents(vault_path, max_docs)
    print(f"Scan complete. Extracted {len(docs)} documents.")

    if args.dry_run:
        print("=== DRY RUN MODE: Document preview ===")
        for d in docs[:3]:
            print(f"ID: {d['id']}")
            print(f"Title: {d['structData']['title']}")
            print(f"Date: {d['structData']['date']}")
            print(f"Metadata matches: {d['structData']['metadata']['matches']}")
            print("---")
        return

    if not docs:
        print("No documents extracted. Exiting.")
        sys.exit(0)

    # 写入 JSONL 文件
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for d in docs:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        print(f"Successfully wrote {len(docs)} documents to {output_path}")
    except Exception as e:
        print(f"Failed to write output JSONL: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
