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

    def test_language_toggle_buttons_present(self):
        html = Path('site/index.html').read_text(encoding='utf-8')
        for snippet in ['data-lang="en"', 'data-lang="fr"', 'data-lang="zh"']:
            self.assertIn(snippet, html)

    def test_french_translations_present(self):
        html = Path('site/index.html').read_text(encoding='utf-8')
        for snippet in ['Tickets créés', 'Comparaison par canal', "Vérifications d'hypothèses"]:
            self.assertIn(snippet, html)

    def test_chinese_translations_present(self):
        html = Path('site/index.html').read_text(encoding='utf-8')
        for snippet in ['创建的工单', '渠道对比', '假设验证']:
            self.assertIn(snippet, html)


if __name__ == '__main__':
    unittest.main()
