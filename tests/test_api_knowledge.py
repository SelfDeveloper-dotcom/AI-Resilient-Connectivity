import unittest

import api


class APIKnowledgeTests(unittest.TestCase):
    def test_dashboard_contains_knowledge_search(self):
        page = api.dashboard("sandbox")
        self.assertIn("Knowledge Base Search", page)
        self.assertIn("/knowledge?q=", page)

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


if __name__ == "__main__":
    unittest.main()
