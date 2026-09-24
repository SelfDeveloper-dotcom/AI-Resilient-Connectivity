from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any


def parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Cannot parse date: {value!r}")


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def read_csv(path: str | Path) -> list[dict[str, str]]:
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


class TargetEngineer:
    """Create a next-day supervised-learning target from model features.

    MVP target is intentionally a SANDBOX PROXY, not an official NCC regulatory label.
    A row at day t receives target=1 when the next consecutive day (t+1):
      - is model eligible; and
      - has multi_kpi_stress_flag == 1.

    Future-derived audit fields are prefixed `target_` so they can be excluded
    from model input features and used only for labelling/audit.
    """

    def __init__(self, config_path: str | Path):
        self.cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self.date_col = self.cfg.get("date_column", "date")
        self.operator_col = self.cfg.get("operator_column", "operator")
        self.tech_col = self.cfg.get("technology_column", "technology")
        self.eligible_col = self.cfg.get("model_eligible_column", "model_eligible")
        self.source_target_col = self.cfg.get("source_target_column", "multi_kpi_stress_flag")
        self.source_count_col = self.cfg.get("source_stress_count_column", "concurrent_deterioration_count")
        self.output_target_col = self.cfg.get("output_target_column", "qos_degradation_next_day")
        self.require_consecutive = bool(self.cfg.get("require_consecutive_next_day", True))
        self.require_next_eligible = bool(self.cfg.get("require_next_day_model_eligible", True))

    def transform_file(self, input_csv: str | Path, output_csv: str | Path) -> list[dict[str, Any]]:
        rows = read_csv(input_csv)
        out = self.transform(rows)
        write_csv(output_csv, out)
        return out

    def transform(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prepared: list[dict[str, Any]] = []
        for order, raw in enumerate(rows):
            row = dict(raw)
            row["__date"] = parse_date(row[self.date_col])
            row["__order"] = order
            prepared.append(row)

        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in prepared:
            key = (str(row.get(self.operator_col, "")).strip(), str(row.get(self.tech_col, "")).strip())
            groups[key].append(row)

        output: list[dict[str, Any]] = []
        for _, group in sorted(groups.items()):
            # Same convention as FeatureEngineer: latest input row wins for duplicate dates.
            by_date: dict[date, dict[str, Any]] = {}
            for row in group:
                by_date[row["__date"]] = row
            series = [by_date[d] for d in sorted(by_date)]

            for i, src in enumerate(series):
                row = {k: v for k, v in src.items() if not k.startswith("__")}
                row["target_definition"] = "SANDBOX_PROXY_NEXT_DAY_MULTI_KPI_STRESS"
                row["target_available"] = False
                row[self.output_target_col] = None
                row["target_next_date"] = None
                row["target_next_day_stress_count"] = None
                row["target_reason"] = "NO_FUTURE_DAY"

                if i + 1 < len(series):
                    nxt = series[i + 1]
                    day_gap = (nxt["__date"] - src["__date"]).days
                    row["target_next_date"] = nxt["__date"].isoformat()
                    row["target_next_day_stress_count"] = nxt.get(self.source_count_col)

                    if self.require_consecutive and day_gap != 1:
                        row["target_reason"] = f"DATE_GAP_{day_gap}_DAYS"
                    elif self.require_next_eligible and not parse_bool(nxt.get(self.eligible_col, False)):
                        row["target_reason"] = "NEXT_DAY_NOT_MODEL_ELIGIBLE"
                    else:
                        raw_target = nxt.get(self.source_target_col)
                        try:
                            target = int(float(raw_target))
                        except (TypeError, ValueError):
                            target = None
                        if target in (0, 1):
                            row[self.output_target_col] = target
                            row["target_available"] = True
                            row["target_reason"] = "NEXT_DAY_MULTI_KPI_STRESS" if target == 1 else "NEXT_DAY_NO_MULTI_KPI_STRESS"
                        else:
                            row["target_reason"] = "NEXT_DAY_TARGET_SOURCE_INVALID"

                output.append(row)

        output.sort(key=lambda r: (str(r.get(self.operator_col, "")), str(r.get(self.tech_col, "")), str(r.get(self.date_col, ""))))
        return output


def main() -> None:
    ap = argparse.ArgumentParser(description="Create sandbox next-day QoS degradation target from model features")
    ap.add_argument("input_csv", help="model_features.csv produced by PP Feature Engineering")
    ap.add_argument("--config", default="config/target_config.json")
    ap.add_argument("--out", default="data/master/training_dataset.csv")
    args = ap.parse_args()

    rows = TargetEngineer(args.config).transform_file(args.input_csv, args.out)
    labelled = [r for r in rows if parse_bool(r.get("target_available"))]
    positives = sum(int(r["qos_degradation_next_day"]) for r in labelled if r.get("qos_degradation_next_day") not in (None, ""))
    print(f"Target engineered {len(rows)} row(s).")
    print(f"Labelled rows: {len(labelled)}; positive proxy labels: {positives}")
    print(f"Output: {Path(args.out).resolve()}")


if __name__ == "__main__":
    main()
