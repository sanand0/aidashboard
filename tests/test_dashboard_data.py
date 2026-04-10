import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_data import generate


class DashboardDataTests(unittest.TestCase):
    def test_generate_shape(self):
        payload = generate(seed=42, days=180)
        self.assertIn("metadata", payload)
        self.assertIn("kpis", payload)
        self.assertIn("daily", payload)
        self.assertIn("channel_stats", payload)
        self.assertIn("region_stats", payload)
        self.assertIn("hypotheses", payload)
        self.assertEqual(len(payload["daily"]), 180)
        self.assertEqual({row["channel"] for row in payload["channel_stats"]}, {"Email", "Chat", "Web"})
        self.assertEqual({row["region"] for row in payload["region_stats"]}, {"North America", "EMEA", "APAC"})

    def test_value_ranges(self):
        payload = generate(seed=42, days=180)
        self.assertGreater(payload["kpis"]["tickets_created"], 1000)
        self.assertGreater(payload["kpis"]["tickets_resolved"], 1000)
        self.assertGreater(payload["kpis"]["open_backlog"], 0)
        self.assertTrue(0.5 <= payload["kpis"]["first_response_hours"] <= 18)
        self.assertTrue(0 <= payload["kpis"]["sla_breach_rate"] <= 100)
        self.assertTrue(60 <= payload["kpis"]["csat"] <= 100)

    def test_json_writable(self):
        payload = generate(seed=7, days=30)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dashboard.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["metadata"]["seed"], 7)
            self.assertEqual(len(loaded["daily"]), 30)


if __name__ == "__main__":
    unittest.main()
