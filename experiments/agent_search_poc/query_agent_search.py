import os
import sys
import re
from typing import List

# 尝试载入 .env 配置文件
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    load_dotenv()
except ImportError:
    pass

def load_queries(path: str = "sample_queries.md") -> List[str]:
    target_path = path
    if not os.path.exists(target_path):
        target_path = os.path.join(os.path.dirname(__file__), path)
    if not os.path.exists(target_path):
        return []
        
    queries = []
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                # 匹配类似 '1. 问题内容' 的行
                match = re.match(r'^\d+\.\s*(.*)', line.strip())
                if match:
                    queries.append(match.group(1).strip())
    except Exception as e:
        print(f"Error reading queries file: {e}")
    return queries

def main():
    project_id = os.environ.get("PROJECT_ID", "ares-daily-intel")
    location = os.environ.get("LOCATION", "global")
    engine_id = os.environ.get("ENGINE_ID", "ares-daily-intel-search")
    query_limit = int(os.environ.get("QUERY_LIMIT", "5"))

    # 读取 5 个测试问题
    queries = load_queries("sample_queries.md")
    if not queries:
        queries = [
            "最近哪些比赛 gate_status 是 READY？",
            "Spain vs Austria 的关键反证是什么？"
        ]

    queries = queries[:query_limit]

    print("=== Ares Agent Search POC Query Session ===")
    print(f"GCP Project: {project_id}")
    print(f"Location:    {location}")
    print(f"Engine ID:   {engine_id}")
    print(f"Queries count: {len(queries)}")
    print("===========================================")

    # 引入 Discovery Engine SDK
    try:
        from google.cloud import discoveryengine_v1 as discoveryengine
    except ImportError:
        print("ERROR: 'google-cloud-discoveryengine' Python library is not installed.")
        print("Please install dependencies: pip install -r requirements.txt")
        sys.exit(1)

    try:
        client = discoveryengine.SearchServiceClient()
        # 拼接服务配置的绝对资源地址
        serving_config = f"projects/{project_id}/locations/{location}/collections/default_collection/engines/{engine_id}/servingConfigs/default_serving_config"
        
        for idx, query_text in enumerate(queries, 1):
            print(f"\n[{idx}/{len(queries)}] Query: '{query_text}'")
            print("-" * 50)
            
            try:
                request = discoveryengine.SearchRequest(
                    serving_config=serving_config,
                    query=query_text,
                    page_size=3
                )
                response = client.search(request)
                
                results_count = 0
                for result in response.results:
                    results_count += 1
                    doc = result.document
                    doc_id = doc.name.split("/")[-1] if hasattr(doc, "name") and doc.name else "unknown"
                    
                    # 兼容读取 struct_data 或 derived_struct_data
                    struct_data = {}
                    if hasattr(doc, "struct_data") and doc.struct_data:
                        struct_data = dict(doc.struct_data)
                    elif hasattr(doc, "derived_struct_data") and doc.derived_struct_data:
                        struct_data = dict(doc.derived_struct_data)
                        
                    title = struct_data.get("title", "Unknown Title")
                    source_path = struct_data.get("source_path", "N/A")
                    
                    # 尝试从搜索返回的派生块中提取 snippet，作为替代摘要展示
                    summary = ""
                    if hasattr(result, "derived_struct_data") and result.derived_struct_data:
                        summary = dict(result.derived_struct_data).get("snippet", "")
                    if not summary:
                        content = struct_data.get("content", "")
                        summary = content[:150] + "..." if len(content) > 150 else content

                    print(f"  Result {results_count}:")
                    print(f"    - Doc ID:      {doc_id}")
                    print(f"    - Title:       {title}")
                    print(f"    - Source Path: {source_path}")
                    print(f"    - Snippet:     {summary.strip().replace('\n', ' ')}")
                    print()
                
                if results_count == 0:
                    print("  No matching documents found in GCS Data Store.")
                    
            except Exception as e:
                print(f"  API execution failed: {e}")
                print("  (Tip: Make sure the Discovery Engine API is enabled, data is imported, and Engine ID is correct)")
                
    except Exception as e:
        print(f"CRITICAL: Failed to initialize SearchServiceClient: {e}")
        sys.exit(1)

    print("\n=== Session Finished ===")

if __name__ == "__main__":
    main()
