import os
import yaml
from typing import Dict, Any, List

def load_matches_config(filepath: str = "data/matches.yml") -> Dict[str, Any]:
    """
    加载并解析 matches.yml 文件。
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Matches configuration file not found at {filepath}")
    
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
            if not data:
                return {"matches": []}
            return data
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse matches YAML file: {e}")

def load_sources_config(filepath: str = "data/sources.yml") -> Dict[str, Any]:
    """
    加载并解析 sources.yml 文件。
    """
    if not os.path.exists(filepath):
        # 兜底提供默认的搜索模板，保障健壮性
        return {
            "search_queries": [
                "{home} vs {away} team news injury updates",
                "{home} vs {away} predicted lineups predicted xi",
                "{home} vs {away} odds betting preview"
            ]
        }
    
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
            if not data or "search_queries" not in data:
                return {
                    "search_queries": [
                        "{home} vs {away} team news injury updates",
                        "{home} vs {away} predicted lineups"
                    ]
                }
            return data
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse sources YAML file: {e}")

def get_search_queries(home: str, away: str, templates: List[str]) -> List[str]:
    """
    根据主客队名和模板生成具体的搜索词列表。
    """
    queries = []
    for template in templates:
        queries.append(template.format(home=home, away=away))
    return queries
