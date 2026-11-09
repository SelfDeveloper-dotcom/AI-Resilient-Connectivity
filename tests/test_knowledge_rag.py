import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from knowledge_base import KnowledgeBase


class KnowledgeRAGTests(unittest.TestCase):
    def make_kb(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        src = root / "03_AI_GOVERNANCE"
        src.mkdir()
        (src / "nais.md").write_text(
            "The National Artificial Intelligence Strategy (NAIS) provides a strategic framework for AI development. "
            "Responsible AI includes governance, risk management, accountability and human oversight.", encoding="utf-8"
        )
        cfg = root / "cfg.json"
        cfg.write_text(json.dumps({
            "source_dirs": [str(root)], "chunk_words": 80, "overlap_words": 10,
            "top_k": 5, "answer_top_k": 5, "answer_evidence": 3, "answer_sentences": 2,
            "medium_confidence_score": 0.1, "min_score": 0.0, "max_features": 5000,
            "supported_extensions": [".md"], "excluded_files": [],
            "category_boosts": {"03_AI_GOVERNANCE": 0.1},
            "query_aliases": {"NAIS": "National Artificial Intelligence Strategy"},
            "rag": {"enabled": True, "ollama_url": "http://127.0.0.1:11434", "embedding_model": "embeddinggemma", "generation_model": "qwen3:4b"}
        }), encoding="utf-8")
        kb = KnowledgeBase(cfg)
        return td, kb

    def test_supported_acronym_is_answered_deterministically(self):
        td, kb = self.make_kb()
        try:
            with patch.object(kb.ollama, "available", return_value=False):
                result = kb.answer("What is the full meaning of NAIS?")
            self.assertIn("National Artificial Intelligence Strategy", result["answer"])
            self.assertEqual(result["answer_mode"], "controlled")
        finally:
            td.cleanup()

    def test_rag_answer_uses_generator_when_available(self):
        td, kb = self.make_kb()
        try:
            fake_doc_emb = np.array([[1.0, 0.0]], dtype=np.float32)
            fake_q_emb = np.array([[1.0, 0.0]], dtype=np.float32)
            with patch.object(kb.ollama, "available", return_value=True), \
                 patch.object(kb.ollama, "embed", side_effect=[fake_doc_emb, fake_q_emb]), \
                 patch.object(kb.ollama, "generate", return_value="Responsible AI requires human oversight [S1]."):
                result = kb.answer("Why is human oversight important?")
            self.assertEqual(result["answer_mode"], "local_rag")
            self.assertNotIn("[S1]", result["answer"])
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
