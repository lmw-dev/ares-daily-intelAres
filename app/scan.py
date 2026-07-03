import os
import re
import json
import logging
from typing import Dict, Any, Tuple, List
from google import genai
from google.genai import types
from app.config import settings

logger = logging.getLogger(__name__)

# 获取提示词路径
PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    "prompts", 
    "match_scan.md"
)

def load_prompt_template() -> str:
    """加载单场深度分析的提示词模板"""
    if not os.path.exists(PROMPT_PATH):
        raise FileNotFoundError(f"Match scan prompt file not found at {PROMPT_PATH}")
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()

def parse_json_from_response(text: str) -> Tuple[Dict[str, Any], str]:
    """
    使用正则表达式提取 markdown 中的 ```json ... ``` 块。
    返回解析后的 json 字典及解析状态（SUCCESS 或 FAILED）。
    """
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    
    if not match:
        logger.warning("No JSON code block found in response text.")
        return {}, "FAILED"
    
    json_str = match.group(1).strip()
    try:
        data = json.loads(json_str)
        return data, "SUCCESS"
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse extracted JSON string: {e}")
        return {}, "FAILED"

def extract_source_urls(response: Any) -> List[str]:
    """
    从 Gemini Grounding 响应的 metadata 中提取被引用的 web url。
    """
    urls = []
    try:
        # 安全读取候选列表及 metadata 结构
        if not response or not getattr(response, "candidates", None):
            return urls
        
        candidate = response.candidates[0]
        if not getattr(candidate, "grounding_metadata", None):
            return urls
            
        metadata = candidate.grounding_metadata
        if not getattr(metadata, "grounding_chunks", None):
            return urls
            
        for chunk in metadata.grounding_chunks:
            if getattr(chunk, "web", None) and getattr(chunk.web, "uri", None):
                urls.append(chunk.web.uri)
    except Exception as e:
        logger.error(f"Error parsing source urls from grounding metadata: {e}")
    
    # 去重保留顺序
    seen = set()
    return [x for x in urls if not (x in seen or seen.add(x))]

def get_mock_result(match: Dict[str, Any]) -> Dict[str, Any]:
    """
    提供 Dry-run 时的 Mock 数据。
    """
    home = match.get("home", "Home")
    away = match.get("away", "Away")
    league = match.get("league", "League")
    
    mock_md = f"""# Ares 深度分析报告 ({home} vs {away})

1. **Gate 状态**：READY
2. **理论盘口粗判**：主让平半 ({home} -0.25)
3. **实际市场信号**：实际盘口为平半，处于高水区。
4. **战意**：{home} 主场全取三分动力极强；{away} 期望客场全身而退。
5. **伤停与阵容**：双方主力阵容均保持健康，目前无新增停赛。
6. **赛程压力**：双方本周均无杯赛牵绊，赛程压力均等。
7. **战术对位**：{home} 偏向边路高空轰炸；{away} 中路防守强硬，擅长低平反击。
8. **关键反证**：{away} 近期客场连平，防守容错率极高，不可轻视防守硬度。
9. **风险标签**：战术克制、进球效率偏低。
10. **下一步补料**：赛前首发大名单确认。

```json
{{
  "league": "{league}",
  "home": "{home}",
  "away": "{away}",
  "gate_status": "READY",
  "market_preview": {{
    "theoretical_line": "Home -0.25",
    "actual_line": "Home -0.25",
    "confidence": "HIGH",
    "source": "SEARCH_SUMMARY"
  }},
  "key_aspects": {{
    "motivation": "{home} 抢分战意高，{away} 客场防守取分意图明确",
    "injuries_lineups": "双方核心球员均健康，主力阵容齐整",
    "tactical_matchup": "{home} 边路进攻对决 {away} 中路坚盾防守",
    "schedule_pressure": "双方单线作战，休整充足"
  }},
  "counter_evidence": "{away} 具备韧性，已连续3场客场客胜/战平盘口",
  "risk_tags": ["Tactical mismatch", "Under goal dynamic"],
  "next_steps": "Observe initial lineups 1 hour prior to kickoff",
  "fixture_status": {{
    "official_status": "SCHEDULED",
    "confidence": "HIGH",
    "evidence_summary": "Mock Spain vs Austria match scheduled confirmation"
  }}
}}
```"""
    
    parsed_json = {
        "league": league,
        "home": home,
        "away": away,
        "gate_status": "READY",
        "market_preview": {
            "theoretical_line": "Home -0.25",
            "actual_line": "Home -0.25",
            "confidence": "HIGH",
            "source": "SEARCH_SUMMARY"
        },
        "key_aspects": {
            "motivation": f"{home} 抢分战意高，{away} 客场防守取分意图明确",
            "injuries_lineups": "双方核心球员均健康，主力阵容齐整",
            "tactical_matchup": f"{home} 边路进攻对决 {away} 中路坚盾防守",
            "schedule_pressure": "双方单线作战，休整充足"
        },
        "counter_evidence": f"{away} 具备韧性，已连续3场客场客胜/战平盘口",
        "risk_tags": ["Tactical mismatch", "Under goal dynamic"],
        "next_steps": "Observe initial lineups 1 hour prior to kickoff",
        "fixture_status": {
            "official_status": "SCHEDULED",
            "confidence": "HIGH",
            "evidence_summary": "Mock Spain vs Austria match scheduled confirmation"
        }
    }

    return {
        "text": mock_md,
        "json": parsed_json,
        "source_urls": ["https://mock-sports-news.com/preview-match"],
        "parse_status": "SUCCESS",
        "raw_response_text": mock_md
    }

def scan_single_match(client: genai.Client, match: Dict[str, Any]) -> Dict[str, Any]:
    """
    扫描并分析单场赛事。如果是 DRY_RUN，直接返回 Mock 结果。
    否则调用 Gemini Grounding 获取最新的分析结果，并尝试提取 JSON 元数据。
    """
    if settings.dry_run:
        logger.info(f"Dry-run mode is enabled. Mocking scan results for {match.get('home')} vs {match.get('away')}")
        return get_mock_result(match)

    home = match.get("home")
    away = match.get("away")
    league = match.get("league")
    kickoff_time = match.get("kickoff_time")

    logger.info(f"Scanning match: {home} vs {away} ({league})")
    
    # 1. 替换 Prompt 模板参数
    template = load_prompt_template()
    prompt = template.format(
        league=league,
        home=home,
        away=away,
        kickoff_time=kickoff_time
    )

    # 2. 调用 Gemini Web Search Grounding API
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        response_text = response.text or ""
    except Exception as e:
        logger.error(f"Gemini API invocation failed for {home} vs {away}: {e}")
        # 异常兜底，不导致程序直接挂掉，返回标记为 FAILED 的结果
        failed_text = f"## API Error\nFailed to invoke Gemini API for this match: {e}"
        return {
            "text": failed_text,
            "json": {
                "league": league,
                "home": home,
                "away": away,
                "gate_status": "MISSING",
                "parse_status": "FAILED",
                "fixture_status": {
                    "official_status": "UNKNOWN",
                    "confidence": "LOW",
                    "evidence_summary": "Failed to call Gemini API due to remote network or permission error"
                }
            },
            "source_urls": [],
            "parse_status": "FAILED",
            "raw_response_text": failed_text
        }

    # 3. 提取 Grounding Source URLs
    source_urls = extract_source_urls(response)

    # 4. 从返回文本中提取结构化 JSON 块
    parsed_json, parse_status = parse_json_from_response(response_text)

    # 5. 若 JSON 解析失败，则组装基本的兜底 JSON 以免程序崩掉
    if parse_status == "FAILED":
        parsed_json = {
            "league": league,
            "home": home,
            "away": away,
            "gate_status": "MISSING",
            "market_preview": {
                "theoretical_line": "UNKNOWN",
                "actual_line": "UNKNOWN",
                "confidence": "LOW",
                "source": "MARKET_MISSING"
            },
            "parse_status": "FAILED",
            "fixture_status": {
                "official_status": "UNKNOWN",
                "confidence": "LOW",
                "evidence_summary": "JSON extraction failed from response text"
            }
        }

    # 返回单场扫描结果
    return {
        "text": response_text,
        "json": parsed_json,
        "source_urls": source_urls,
        "parse_status": parse_status,
        "raw_response_text": response_text
    }
