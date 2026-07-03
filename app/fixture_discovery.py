import os
import logging
from typing import Dict, Any, List
from google.genai import types
from app.config import settings
from app.gemini_client import get_gemini_client
from app.scan import parse_json_from_response, extract_source_urls

logger = logging.getLogger(__name__)

def load_discovery_prompt_template() -> str:
    path = os.path.join("prompts", "fixture_discovery.md")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def discover_fixtures(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    使用 Gemini Grounding 搜索未来 lookahead_hours 内 competitions 中的真实比赛赛程。
    """
    logger.info("Starting automatic fixture discovery via Gemini Grounding...")
    
    competitions = config.get("competitions", [])
    watch_teams = config.get("watch_teams", [])
    lookahead_hours = config.get("lookahead_hours", 72)
    
    if not competitions:
        logger.warning("No competitions configured for auto_discovery. Returning empty candidates list.")
        return []

    # 1. 拼装 Prompt
    try:
        template = load_discovery_prompt_template()
        prompt = template.format(
            competitions=", ".join(competitions),
            watch_teams=", ".join(watch_teams),
            lookahead_hours=lookahead_hours
        )
    except Exception as e:
        logger.error(f"Failed to render fixture discovery prompt template: {e}")
        return []

    # 2. 调用 API
    candidates = []
    try:
        client = get_gemini_client()
        logger.info("Invoking Gemini generate_content for schedule discovery with search tool...")
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        response_text = response.text or ""
        source_urls = extract_source_urls(response)
        
        # 3. 提取 JSON 代码块
        # parse_json_from_response 返回 (parsed_json_obj, status_str)
        # 针对列表解析，parse_json_from_response 内置了 list/dict 解析容错
        parsed_data, status = parse_json_from_response(response_text)
        
        if status == "SUCCESS" and isinstance(parsed_data, list):
            for match_item in parsed_data:
                if isinstance(match_item, dict):
                    # 补齐 source_urls 字段
                    match_item["source_urls"] = source_urls
                    candidates.append(match_item)
            logger.info(f"Discovered {len(candidates)} raw match candidates.")
        else:
            logger.warning(f"Failed to parse match list JSON block from discovery response. Status: {status}")
    except Exception as e:
        logger.error(f"Error during fixture discovery execution: {e}")
        
    return candidates
