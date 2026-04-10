import unittest
from pathlib import Path


class DashboardPageTests(unittest.TestCase):
    def test_index_contains_expected_sections(self):
        html = Path('site/index.html').read_text(encoding='utf-8')
        for snippet in [
            'Support Operations Health',
            'Hypothesis checks',
            'Channel comparison',
            'Region comparison',
            "fetch('./data/dashboard.json'",
        ]:
            self.assertIn(snippet, html)

    def test_index_has_moving_average(self):
        html = Path('site/index.html').read_text(encoding='utf-8')
        self.assertIn('movingAverage', html)
        self.assertIn('_ma7', html)
        self.assertIn('7-day avg', html)


if __name__ == '__main__':
    unittest.main()
