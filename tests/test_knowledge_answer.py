import json
import tempfile
import unittest
from pathlib import Path

from knowledge_base import KnowledgeBase

ROOT = Path(__file__).resolve().parents[1]


class KBAnswerTests(unittest.TestCase):
    def test_answer_returns_answer_and_evidence(self):
        kb = KnowledgeBase(ROOT / "config/knowledge_config.json")
        kb.build()
        out = kb.answer("Why is human review required before regulatory action?", top_k=5)
        self.assertIn("answer", out)
        self.assertIn("evidence", out)
        self.assertTrue(out["evidence"])
        self.assertIn(out["confidence"], {"LOW", "MEDIUM", "HIGH"})

    def test_acronym_full_meaning_prefers_controlled_grounded_answer(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "source"
            src.mkdir()
            (src / "National_AI_Strategy.txt").write_text(
                "The National Artificial Intelligence Strategy (NAIS) provides a national framework for responsible AI development and adoption in Nigeria. " * 8,
                encoding="utf-8",
            )
            cfg = td / "knowledge.json"
            cfg.write_text(json.dumps({
                "source_dirs": [str(src)],
                "chunk_words": 80,
                "overlap_words": 10,
                "top_k": 5,
                "answer_top_k": 5,
                "answer_evidence": 3,
                "answer_sentences": 2,
                "medium_confidence_score": 0.1,
                "min_score": 0.0,
                "max_features": 5000,
                "supported_extensions": [".txt"],
                "query_aliases": {"NAIS": "National Artificial Intelligence Strategy"},
                "category_boosts": {}
            }), encoding="utf-8")
            kb = KnowledgeBase(cfg)
            # Override because temporary source is absolute and constructor normally roots configured paths.
            kb.sources = [src]
            kb.build()
            out = kb.answer("What is the full meaning of NAIS?", top_k=5)
            self.assertEqual(out["answer"], "NAIS means National Artificial Intelligence Strategy.")
            self.assertEqual(out["confidence"], "HIGH")
            self.assertTrue(out["evidence"])


if __name__ == "__main__":
    unittest.main()
