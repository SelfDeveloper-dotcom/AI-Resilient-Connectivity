import unittest

import api


class APIKnowledgeTests(unittest.TestCase):
    def test_dashboard_contains_knowledge_search(self):
        page = api.dashboard("sandbox")
        self.assertIn("Knowledge Base Search", page)
        self.assertIn("/knowledge/answer?q=", page)

    def test_knowledge_stats_available(self):
        stats = api.knowledge_stats()
        self.assertGreater(stats["documents"], 0)
        self.assertGreater(stats["chunks"], 0)

    def test_knowledge_source_inventory_available(self):
        sources = api.knowledge_sources()
        self.assertTrue(sources)
        self.assertIn("source", sources[0])
        self.assertIn("category", sources[0])

    def test_knowledge_endpoint_returns_sources(self):
        results = api.knowledge("What KPIs are used in the current 2G scope?", 5)
        self.assertTrue(results)
        self.assertIn("source", results[0])
        self.assertIn("text", results[0])

    def test_knowledge_answer_endpoint_returns_grounded_structure(self):
        result = api.knowledge_answer("What KPIs are used in the current 2G scope?", 5)
        self.assertIn("answer", result)
        self.assertIn("evidence", result)
        self.assertTrue(result["evidence"])



if __name__ == "__main__":
    unittest.main()
