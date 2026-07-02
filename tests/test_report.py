import unittest
from app.config import settings
from app.report import generate_daily_reports

class TestReport(unittest.TestCase):
    def setUp(self):
        settings.dry_run = False
        # 准备 Mock 的单场扫描结果，包含一个 SUCCESS 和一个 FAILED
        self.mock_scan_results = [
            {
                "text": "Report 1 content ```json {\"home\": \"Arsenal\", \"away\": \"Chelsea\", \"gate_status\": \"READY\", \"risk_tags\": [\"derby\"]} ```",
                "json": {
                    "home": "Arsenal",
                    "away": "Chelsea",
                    "league": "Premier League",
                    "gate_status": "READY",
                    "market_preview": {
                        "theoretical_line": "Home -0.75",
                        "actual_line": "Home -0.75",
                        "confidence": "HIGH",
                        "source": "SEARCH_SUMMARY"
                    },
                    "risk_tags": ["derby"]
                },
                "source_urls": ["http://url1.com", "http://url2.com"],
                "parse_status": "SUCCESS"
            },
            {
                "text": "Report 2 failed text without json block",
                "json": {
                    "home": "Inter",
                    "away": "Roma",
                    "league": "Serie A",
                    "gate_status": "MISSING",
                    "parse_status": "FAILED"
                },
                "source_urls": [],
                "parse_status": "FAILED"
            }
        ]

    def test_generate_daily_reports_failed_status(self):
        md, js = generate_daily_reports(
            self.mock_scan_results, 
            "2026-07-03", 
            "gs://bucket/2026/07/03/scan.md"
        )
        
        # 1. 验证 JSON 结构和元数据统计
        self.assertIn("run_metadata", js)
        metadata = js["run_metadata"]
        
        # 只要有一场 FAILED，总状态即为 FAILED
        self.assertEqual(metadata["parse_status"], "FAILED")
        # 统计 grounded_requests
        self.assertEqual(metadata["grounded_requests_attempted"], 2)
        # 统计去重后的 URL 数量
        self.assertEqual(metadata["source_urls_count"], 2)
        
        # 验证包含的赛事详情
        self.assertEqual(len(js["matches"]), 2)
        self.assertEqual(js["matches"][0]["home"], "Arsenal")
        self.assertEqual(js["matches"][1]["home"], "Inter")

        # 2. 验证 Markdown 内容是否被正确填入
        self.assertIn("Ares Daily Intelligence Report", md)
        self.assertIn("Arsenal vs Chelsea", md)
        self.assertIn("Inter vs Roma", md)
        self.assertIn("gs://bucket/2026/07/03/scan.md", md)
        self.assertIn("FAILED", md)

if __name__ == "__main__":
    unittest.main()
