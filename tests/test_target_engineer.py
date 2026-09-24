import tempfile
import unittest
from pathlib import Path
import json

from target_engineer import TargetEngineer


class TargetEngineerTests(unittest.TestCase):
    def make_engine(self):
        td = tempfile.TemporaryDirectory()
        cfg = Path(td.name) / "target_config.json"
        cfg.write_text(json.dumps({
            "date_column": "date",
            "operator_column": "operator",
            "technology_column": "technology",
            "model_eligible_column": "model_eligible",
            "source_target_column": "multi_kpi_stress_flag",
            "source_stress_count_column": "concurrent_deterioration_count",
            "output_target_column": "qos_degradation_next_day",
            "require_consecutive_next_day": True,
            "require_next_day_model_eligible": True
        }))
        return td, TargetEngineer(cfg)

    def test_next_day_label_shift(self):
        td, eng = self.make_engine()
        try:
            rows = [
                {"date":"2026-08-07","operator":"A","technology":"2G","model_eligible":"True","multi_kpi_stress_flag":"0","concurrent_deterioration_count":"1"},
                {"date":"2026-08-08","operator":"A","technology":"2G","model_eligible":"True","multi_kpi_stress_flag":"1","concurrent_deterioration_count":"4"},
                {"date":"2026-08-09","operator":"A","technology":"2G","model_eligible":"True","multi_kpi_stress_flag":"0","concurrent_deterioration_count":"0"}
            ]
            out = eng.transform(rows)
            self.assertEqual(out[0]["qos_degradation_next_day"], 1)
            self.assertEqual(out[1]["qos_degradation_next_day"], 0)
            self.assertFalse(out[2]["target_available"])
        finally:
            td.cleanup()

    def test_gap_has_no_label(self):
        td, eng = self.make_engine()
        try:
            rows = [
                {"date":"2026-08-07","operator":"A","technology":"2G","model_eligible":"True","multi_kpi_stress_flag":"0","concurrent_deterioration_count":"1"},
                {"date":"2026-08-09","operator":"A","technology":"2G","model_eligible":"True","multi_kpi_stress_flag":"1","concurrent_deterioration_count":"4"}
            ]
            out = eng.transform(rows)
            self.assertFalse(out[0]["target_available"])
            self.assertEqual(out[0]["target_reason"], "DATE_GAP_2_DAYS")
        finally:
            td.cleanup()

    def test_ineligible_next_day_has_no_label(self):
        td, eng = self.make_engine()
        try:
            rows = [
                {"date":"2026-08-07","operator":"A","technology":"2G","model_eligible":"True","multi_kpi_stress_flag":"0","concurrent_deterioration_count":"1"},
                {"date":"2026-08-08","operator":"A","technology":"2G","model_eligible":"False","multi_kpi_stress_flag":"1","concurrent_deterioration_count":"4"}
            ]
            out = eng.transform(rows)
            self.assertFalse(out[0]["target_available"])
            self.assertEqual(out[0]["target_reason"], "NEXT_DAY_NOT_MODEL_ELIGIBLE")
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
