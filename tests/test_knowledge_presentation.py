import unittest
from knowledge_base import _clean_generated_answer
import api

class KnowledgePresentationTests(unittest.TestCase):
    def test_think_content_and_source_markers_removed(self):
        raw = '<think>internal reasoning that must not be shown</think>Final answer [S1] and more [S2].'
        cleaned = _clean_generated_answer(raw)
        self.assertEqual(cleaned, 'Final answer and more.')
        self.assertNotIn('internal reasoning', cleaned)
        self.assertNotIn('[S1]', cleaned)

    def test_dashboard_hides_supporting_evidence_section(self):
        page = api.dashboard('sandbox')
        self.assertNotIn('<h3>Supporting evidence</h3>', page)
        self.assertIn('formatAnswer', page)
        self.assertIn('Answer grounded in the local Knowledge Base.', page)

if __name__ == '__main__':
    unittest.main()
