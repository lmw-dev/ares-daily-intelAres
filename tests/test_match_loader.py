import os
import unittest
from app.match_loader import load_matches_config, load_sources_config, get_search_queries

class TestMatchLoader(unittest.TestCase):
    def test_load_matches_config(self):
        # 确保能成功读取我们手工填的 matches.yml
        data = load_matches_config("data/matches.yml")
        self.assertIn("scan_date", data)
        self.assertIn("matches", data)
        self.assertTrue(len(data["matches"]) > 0)
        
        # 验证比赛字段结构
        match = data["matches"][0]
        self.assertIn("league", match)
        self.assertIn("home", match)
        self.assertIn("away", match)
        self.assertIn("kickoff_time", match)

    def test_load_sources_config(self):
        data = load_sources_config("data/sources.yml")
        self.assertIn("search_queries", data)
        self.assertTrue(len(data["search_queries"]) > 0)

    def test_get_search_queries(self):
        templates = ["{home} vs {away} news", "{home} vs {away} odds"]
        queries = get_search_queries("Arsenal", "Chelsea", templates)
        self.assertEqual(len(queries), 2)
        self.assertEqual(queries[0], "Arsenal vs Chelsea news")
        self.assertEqual(queries[1], "Arsenal vs Chelsea odds")

if __name__ == "__main__":
    unittest.main()
