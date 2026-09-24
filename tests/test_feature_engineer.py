import unittest

from feature_engineer import FeatureEngineer
from pathlib import Path


def row(day, availability=99.0, cssr=99.0, hosr=99.0, dcr=0.5, sd=0.1, tch=0.1, traffic=1000):
    return {
        "date": day,
        "operator": "Operator A",
        "technology": "2G",
        "model_eligible": "True",
        "quality_status": "PASS",
        "total_traffic_erlang": str(traffic),
        "availability_mean": str(availability),
        "availability_p10": str(availability),
        "cssr_mean": str(cssr),
        "cssr_p10": str(cssr),
        "hosr_mean": str(hosr),
        "hosr_p10": str(hosr),
        "dcr_mean": str(dcr),
        "dcr_p90": str(dcr),
        "sd_congestion_mean": str(sd),
        "sd_congestion_p95": str(sd),
        "tch_congestion_mean": str(tch),
        "tch_congestion_p95": str(tch),
    }


class FeatureEngineerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = FeatureEngineer(Path(__file__).resolve().parents[1] / "config" / "feature_config.json")

    def test_direction_normalisation(self):
        rows = [
            row("2026-01-01"),
            row("2026-01-02", availability=98.8, cssr=98.8, hosr=98.8, dcr=0.7, sd=0.2, tch=0.2, traffic=1100),
        ]
        out = self.engine.transform(rows)[1]
        self.assertGreater(out["availability_mean_deterioration_1d_pp"], 0)
        self.assertGreater(out["cssr_mean_deterioration_1d_pp"], 0)
        self.assertGreater(out["hosr_mean_deterioration_1d_pp"], 0)
        self.assertGreater(out["dcr_mean_deterioration_1d_pp"], 0)
        self.assertGreater(out["sd_congestion_mean_deterioration_1d_pp"], 0)
        self.assertGreater(out["tch_congestion_mean_deterioration_1d_pp"], 0)
        self.assertAlmostEqual(out["total_traffic_erlang_pct_change_1d"], 10.0, places=5)

    def test_gap_suppresses_one_day_lag(self):
        rows = [row("2026-01-01"), row("2026-01-03", cssr=98.0)]
        out = self.engine.transform(rows)[1]
        self.assertEqual(out["date_gap_days"], 2)
        self.assertIsNone(out["cssr_mean_delta_1d_pp"])

    def test_no_future_leakage(self):
        prefix = [row("2026-01-01"), row("2026-01-02", cssr=98.8)]
        full = prefix + [row("2026-01-03", cssr=50.0, dcr=20.0, traffic=999999)]
        prefix_out = self.engine.transform(prefix)
        full_out = self.engine.transform(full)
        # Day 2 engineered features must be identical even if a dramatic future Day 3 exists.
        for key in prefix_out[1]:
            if key not in {"__order", "__date"}:
                self.assertEqual(prefix_out[1].get(key), full_out[1].get(key), key)


if __name__ == "__main__":
    unittest.main()
