import unittest
import api

class DashboardUITests(unittest.TestCase):
    def test_dashboard_contains_interactive_operations_ui(self):
        page = api.dashboard('sandbox')
        for text in [
            'Network resilience overview',
            'Operator status',
            'Degradation risk trend',
            'KPI snapshot',
            'Recent alerts',
            'Knowledge Base Search',
            'Real',
            'Sandbox',
        ]:
            self.assertIn(text, page)
        self.assertIn('riskChart', page)
        self.assertIn('selectOperator', page)

if __name__ == '__main__':
    unittest.main()
