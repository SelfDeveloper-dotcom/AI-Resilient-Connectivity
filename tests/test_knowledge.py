import unittest
from pathlib import Path

from knowledge_base import KnowledgeBase

ROOT = Path(__file__).resolve().parents[1]


class KBTests(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase(ROOT / "config/knowledge_config.json")
        self.kb.build()

    def test_build_indexes_multiple_project_sources(self):
        stats = self.kb.stats()
        self.assertGreaterEqual(stats["documents"], 5)
        self.assertGreater(stats["chunks"], 5)
        self.assertIn("PROJECT_DOCS", stats["categories"])

    def test_query_returns_grounded_metadata(self):
        r = self.kb.query("human review model prediction", top_k=5)
        self.assertTrue(r)
        self.assertIn("source", r[0])
        self.assertIn("title", r[0])
        self.assertIn("category", r[0])
        self.assertGreater(r[0]["score"], 0)

    def test_kpi_query_finds_project_knowledge(self):
        r = self.kb.query("Cell Availability CSSR HOSR DCR SDCCH TCH traffic", top_k=5)
        joined = " ".join(x["text"] for x in r).lower()
        self.assertIn("cssr", joined)
        self.assertIn("hosr", joined)


if __name__ == "__main__":
    unittest.main()
