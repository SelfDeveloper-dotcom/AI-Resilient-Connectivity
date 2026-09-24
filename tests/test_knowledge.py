import unittest
from pathlib import Path
from knowledge_base import KnowledgeBase
ROOT=Path(__file__).resolve().parents[1]
class KBTests(unittest.TestCase):
    def test_query(self):
        kb=KnowledgeBase(ROOT/"config/knowledge_config.json")
        kb.build()
        r=kb.query("human review model prediction")
        self.assertIsInstance(r,list)
if __name__=="__main__": unittest.main()
