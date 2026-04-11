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


    def test_csat_control_chart(self):
        payload = generate(seed=42, days=180)
        cc = payload["csat_control_chart"]

        # required keys
        for key in ("lsl", "usl", "center_line", "ucl", "lcl", "sigma_hat",
                    "mr_bar", "ucl_mr", "lcl_mr", "cpk", "sigma_level",
                    "violations", "daily"):
            self.assertIn(key, cc, f"Missing key: {key}")

        # control limit ordering
        self.assertGreater(cc["ucl"], cc["center_line"])
        self.assertLess(cc["lcl"], cc["center_line"])
        self.assertGreaterEqual(cc["lcl"], 0)

        # MR chart limits
        self.assertGreater(cc["ucl_mr"], cc["mr_bar"])
        self.assertEqual(cc["lcl_mr"], 0)

        # positive capability — CSAT should comfortably exceed LSL=75
        self.assertGreater(cc["cpk"], 0)
        self.assertGreater(cc["sigma_level"], 0)

        # daily list matches the number of generated days
        self.assertEqual(len(cc["daily"]), 180)

        # first point has no moving range; all subsequent points do
        self.assertIsNone(cc["daily"][0]["moving_range"])
        for row in cc["daily"][1:]:
            self.assertIsNotNone(row["moving_range"])
            self.assertGreaterEqual(row["moving_range"], 0)

        # out-of-control flags are booleans
        for row in cc["daily"]:
            self.assertIsInstance(row["i_out_of_control"], bool)
            self.assertIsInstance(row["mr_out_of_control"], bool)


if __name__ == "__main__":
    unittest.main()
