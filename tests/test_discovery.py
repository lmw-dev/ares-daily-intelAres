import unittest
import os
import yaml
from unittest.mock import MagicMock, patch
from app.priority_selector import select_priority_matches
from app.report import generate_daily_reports
from app.scan import scan_single_match

class TestDiscovery(unittest.TestCase):
    
    def test_scan_config_loading(self):
        """测试 scan_config.yml 可以正常加载并结构合规"""
        path = "data/scan_config.yml"
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        self.assertIsNotNone(config)
        self.assertEqual(config.get("mode"), "auto_discovery")
        self.assertIn("competitions", config)
        self.assertIn("watch_teams", config)
        self.assertIn("manual_matches", config)

    def test_manual_matches_priority(self):
        """测试 manual_matches 的最高优先权以及与自动候选的去重合并"""
        config = {
            "max_matches": 2,
            "watch_teams": ["Spain"],
            "manual_matches": [
                {"league": "FIFA World Cup", "home": "England", "away": "France"}
            ]
        }
        candidates = [
            {"league": "FIFA World Cup", "home": "Spain", "away": "Austria", "fixture_status": "SCHEDULED", "confidence": "HIGH", "discovery_reason": "watch_team_spain"},
            {"league": "FIFA World Cup", "home": "Brazil", "away": "Germany", "fixture_status": "SCHEDULED", "confidence": "HIGH", "discovery_reason": "world_cup_match"},
            # 重复的候选比赛，应排重
            {"league": "FIFA World Cup", "home": "England", "away": "France", "fixture_status": "SCHEDULED", "confidence": "LOW"}
        ]
        
        selected = select_priority_matches(candidates, config)
        
        # 裁剪到 2，首个必为手动指定的 England vs France 且去重合并
        self.assertEqual(len(selected), 2)
        self.assertEqual(selected[0]["home"], "England")
        self.assertEqual(selected[0]["away"], "France")
        self.assertTrue(selected[0]["is_manual"])

    def test_priority_selector_max_matches_limit(self):
        """测试 selector 裁剪不超过 max_matches 配置"""
        config = {
            "max_matches": 1,
            "watch_teams": [],
            "manual_matches": []
        }
        candidates = [
            {"league": "FIFA World Cup", "home": "Spain", "away": "Austria", "fixture_status": "SCHEDULED", "confidence": "HIGH"},
            {"league": "FIFA World Cup", "home": "Brazil", "away": "Germany", "fixture_status": "SCHEDULED", "confidence": "HIGH"}
        ]
        selected = select_priority_matches(candidates, config)
        self.assertEqual(len(selected), 1)

    def test_no_fixtures_handling(self):
        """测试无比赛时生成 HOLD 报告不抛异常"""
        gcs_full_path = "gs://mock-bucket/2026/07/03/scan.md"
        markdown_report, report_json = generate_daily_reports([], "2026-07-03", gcs_full_path)
        
        self.assertIn("No Fixtures Discovered", markdown_report)
        self.assertEqual(report_json["run_metadata"]["parse_status"], "HOLD")
        self.assertEqual(len(report_json["matches"]), 0)

    @patch('app.scan.settings')
    def test_search_summary_confidence_enforcement(self, mock_settings):
        """测试当博彩盘口来源为 SEARCH_SUMMARY 且信心为 HIGH 时，自动被后置降级修剪为 MEDIUM"""
        mock_settings.dry_run = False
        mock_settings.gemini_model = "gemini-3.5-flash"

        # 模拟模型输出含有 SEARCH_SUMMARY 且信心为 HIGH 的 JSON
        mock_response = MagicMock()
        mock_response.text = """
        这是深度分析文本部分。
        ```json
        {
          "league": "FIFA World Cup",
          "home": "Spain",
          "away": "Austria",
          "gate_status": "READY",
          "market_preview": {
            "theoretical_line": "Home -0.5",
            "actual_line": "Home -0.25",
            "confidence": "HIGH",
            "source": "SEARCH_SUMMARY"
          },
          "fixture_status": {
            "official_status": "SCHEDULED",
            "confidence": "HIGH",
            "evidence_summary": "Schedule matches"
          }
        }
        ```
        """
        mock_response.candidates = []

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        match_info = {"league": "FIFA World Cup", "home": "Spain", "away": "Austria", "kickoff_time": "2026-07-03"}
        result = scan_single_match(mock_client, match_info)

        # 验证后置降级机制是否生效
        self.assertEqual(result["json"]["market_preview"]["confidence"], "MEDIUM")
