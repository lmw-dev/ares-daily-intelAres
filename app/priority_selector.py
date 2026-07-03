import datetime
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def parse_iso_time(time_str: str) -> datetime.datetime:
    """
    尝试解析 ISO-8601 格式的时间，返回带 tz 信息的 datetime。
    解析失败时返回极早的时间 (datetime.min)。
    """
    if not time_str or time_str == "UNKNOWN":
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    try:
        # 支持以 Z 结尾或带偏移的时区表示
        if time_str.endswith("Z"):
            time_str = time_str[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(time_str)
    except Exception:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

def select_priority_matches(candidates: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    根据配置规则，从候选比赛池中筛选出优先级最高的比赛，限制返回数量不超过 max_matches。
    优先级排序规则：
    1. manual_matches 优先
    2. knockout_match 优先
    3. World Cup / major tournament 优先
    4. watch_teams 命中优先
    5. confidence HIGH 优先
    6. source_urls 多的优先
    7. fixture_status=SCHEDULED 或 LIVE 优先，COMPLETE 只在过去 24 小时内允许进入
    """
    manual_matches = config.get("manual_matches", [])
    total_pool = []
    seen_pairs = set()

    # 1. 注入人工兜底赛事，打上最高优先级 manual 标识并排重
    for m in manual_matches:
        if isinstance(m, dict) and m.get("home") and m.get("away"):
            m_copy = dict(m)
            m_copy["is_manual"] = True
            m_copy["fixture_status"] = m_copy.get("fixture_status", "SCHEDULED")
            m_copy["confidence"] = m_copy.get("confidence", "HIGH")
            m_copy["discovery_reason"] = m_copy.get("discovery_reason", "manual_match")
            m_copy["source_urls"] = m_copy.get("source_urls", [])
            
            pair = (m_copy["home"].strip().lower(), m_copy["away"].strip().lower())
            seen_pairs.add(pair)
            total_pool.append(m_copy)

    # 2. 合并自动发现的比赛，排重过滤
    for c in candidates:
        if isinstance(c, dict) and c.get("home") and c.get("away"):
            pair = (c["home"].strip().lower(), c["away"].strip().lower())
            if pair not in seen_pairs:
                c_copy = dict(c)
                c_copy["is_manual"] = False
                seen_pairs.add(pair)
                total_pool.append(c_copy)

    # 3. 完赛状态时间差校验，过滤超过 24 小时已完赛的比赛
    now = datetime.datetime.now(datetime.timezone.utc)
    filtered_pool = []
    for match in total_pool:
        status = str(match.get("fixture_status", "SCHEDULED")).upper()
        if status == "COMPLETE":
            kickoff_str = match.get("kickoff_time", "")
            dt = parse_iso_time(kickoff_str)
            time_diff = now - dt
            # 若时间解析失败或已完赛超 24 小时 (86400 秒)，则舍弃
            if dt == datetime.datetime.min.replace(tzinfo=datetime.timezone.utc) or time_diff.total_seconds() > 86400:
                logger.info(f"Filtering out complete match past 24h: {match.get('home')} vs {match.get('away')}")
                continue
        filtered_pool.append(match)

    # 4. 定义打分计算权重规则
    watch_teams = [t.lower() for t in config.get("watch_teams", [])]

    def calculate_score(match_item: Dict[str, Any]) -> int:
        score = 0
        
        # Rule 1: manual_matches 拥有决定性额外加分
        if match_item.get("is_manual"):
            score += 1000
            
        # Rule 2: 淘汰赛优先
        reason = str(match_item.get("discovery_reason", "")).lower()
        league = str(match_item.get("league", "")).lower()
        if "knockout" in reason or "淘汰" in reason or "knockout" in league or "淘汰" in league:
            score += 100
            
        # Rule 3: 重点杯赛优先 (世界杯等)
        if "world cup" in league or "世界杯" in league or "club world cup" in league or "世俱杯" in league:
            score += 50
            
        # Rule 4: 关注球队命中最优
        home = str(match_item.get("home", "")).lower()
        away = str(match_item.get("away", "")).lower()
        for team in watch_teams:
            if team in home or team in away:
                score += 20
                break
                
        # Rule 5: 检索信心高优先
        confidence = str(match_item.get("confidence", "LOW")).upper()
        if confidence == "HIGH":
            score += 10
        elif confidence == "MEDIUM":
            score += 5
            
        # Rule 6: 支持信源多的优先
        urls = match_item.get("source_urls", [])
        score += len(urls)
        
        # Rule 7: 正在进行或待开球优先
        status = str(match_item.get("fixture_status", "SCHEDULED")).upper()
        if status in ("SCHEDULED", "LIVE"):
            score += 5
            
        return score

    # 执行大到小排序
    filtered_pool.sort(key=calculate_score, reverse=True)
    
    # 裁剪最大输出数量
    max_matches = config.get("max_matches", 3)
    selected = filtered_pool[:max_matches]
    
    logger.info(f"Selected {len(selected)} priority matches from {len(filtered_pool)} candidates.")
    return selected
