from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import fmean
from typing import Any


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


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


def number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # Preserve first-seen order while allowing later engineered fields.
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


class FeatureEngineer:
    """Y.3172 PP feature-engineering stage for Operator x Day QoS data.

    Design rules:
    - Features are calculated separately for each operator + technology.
    - Only current/past observations are used. No future data enters a feature.
    - Percentage KPIs use percentage-point deltas, not percent change.
    - Traffic uses percent change because its scale is large and contextual.
    - Positive `*_deterioration_*` always means "worse", regardless of KPI direction.
    """

    def __init__(self, config_path: str | Path):
        self.cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self.date_col = self.cfg["date_column"]
        self.operator_col = self.cfg["operator_column"]
        self.tech_col = self.cfg["technology_column"]
        self.traffic_col = self.cfg["traffic_column"]
        self.good_high = list(self.cfg["good_high_kpis"])
        self.bad_high = list(self.cfg["bad_high_kpis"])
        self.kpis = self.good_high + self.bad_high
        self.windows = sorted(set(int(x) for x in self.cfg.get("rolling_windows", [3, 7])))
        self.lags = sorted(set(int(x) for x in self.cfg.get("change_lags", [1, 3])))
        self.primary = self.cfg["primary_stress_kpis"]
        self.stress_min = int(self.cfg.get("multi_kpi_stress_min_count", 3))
        self.require_consecutive = bool(self.cfg.get("require_consecutive_dates_for_lag_features", True))

    def transform_file(self, input_csv: str | Path, output_csv: str | Path) -> list[dict[str, Any]]:
        rows = read_csv(input_csv)
        out = self.transform(rows)
        write_csv(output_csv, out)
        return out

    def transform(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prepared: list[dict[str, Any]] = []
        for order, raw in enumerate(rows):
            row = dict(raw)
            row["__order"] = order
            row["__date"] = parse_date(row[self.date_col])
            prepared.append(row)

        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in prepared:
            key = (str(row.get(self.operator_col, "")).strip(), str(row.get(self.tech_col, "")).strip())
            groups[key].append(row)

        result: list[dict[str, Any]] = []
        for _, group in sorted(groups.items()):
            # For overlapping/resubmitted dates, the latest row in the input wins.
            by_date: dict[date, dict[str, Any]] = {}
            for row in group:
                by_date[row["__date"]] = row
            series = [by_date[d] for d in sorted(by_date)]
            result.extend(self._transform_group(series))

        result.sort(key=lambda r: (str(r.get(self.operator_col, "")), str(r.get(self.tech_col, "")), str(r.get(self.date_col, ""))))
        return result

    def _transform_group(self, series: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        streaks = {k: 0 for k in self.primary}

        for i, src in enumerate(series):
            row = {k: v for k, v in src.items() if not k.startswith("__")}
            current_date: date = src["__date"]

            if i == 0:
                row["date_gap_days"] = None
            else:
                row["date_gap_days"] = (current_date - series[i - 1]["__date"]).days

            # Rolling mean/min/max: trailing windows only (includes current day, never future days).
            for metric in [self.traffic_col] + self.kpis:
                for window in self.windows:
                    start = max(0, i - window + 1)
                    vals = [number(series[j].get(metric)) for j in range(start, i + 1)]
                    vals = [v for v in vals if v is not None]
                    row[f"{metric}_roll{window}_mean"] = round_or_none(fmean(vals) if vals else None)
                    # Min/max are simple interpretable context features.
                    row[f"{metric}_roll{window}_min"] = round_or_none(min(vals) if vals else None)
                    row[f"{metric}_roll{window}_max"] = round_or_none(max(vals) if vals else None)

            # Lag changes.
            for lag in self.lags:
                prev_i = i - lag
                lag_ok = prev_i >= 0
                if lag_ok and self.require_consecutive:
                    lag_ok = (current_date - series[prev_i]["__date"]).days == lag

                # Traffic: percent change is meaningful and scale independent.
                traffic_now = number(src.get(self.traffic_col))
                traffic_prev = number(series[prev_i].get(self.traffic_col)) if lag_ok else None
                if traffic_now is not None and traffic_prev not in (None, 0):
                    row[f"{self.traffic_col}_pct_change_{lag}d"] = round_or_none(((traffic_now / traffic_prev) - 1.0) * 100.0)
                else:
                    row[f"{self.traffic_col}_pct_change_{lag}d"] = None

                for metric in self.kpis:
                    now = number(src.get(metric))
                    prev = number(series[prev_i].get(metric)) if lag_ok else None
                    delta = (now - prev) if (now is not None and prev is not None) else None
                    row[f"{metric}_delta_{lag}d_pp"] = round_or_none(delta)
                    if delta is None:
                        deterioration = None
                    elif metric in self.good_high:
                        deterioration = -delta
                    else:
                        deterioration = delta
                    row[f"{metric}_deterioration_{lag}d_pp"] = round_or_none(deterioration)

            # Primary same-day stress flags + streaks. Positive deterioration means worse.
            stress_count = 0
            for metric, spec in self.primary.items():
                direction = spec["direction"]
                epsilon = float(spec.get("epsilon", 0.0))
                now = number(src.get(metric))
                prev = number(series[i - 1].get(metric)) if i > 0 and (not self.require_consecutive or row["date_gap_days"] == 1) else None
                if now is None or prev is None:
                    deteriorating = False
                    streaks[metric] = 0
                else:
                    delta = now - prev
                    deterioration = (-delta) if direction == "good_high" else delta
                    deteriorating = deterioration >= epsilon
                    streaks[metric] = streaks[metric] + 1 if deteriorating else 0
                row[f"{metric}_deteriorating_flag"] = int(deteriorating)
                row[f"{metric}_deterioration_streak"] = streaks[metric]
                stress_count += int(deteriorating)

            row["concurrent_deterioration_count"] = stress_count
            row["multi_kpi_stress_flag"] = int(stress_count >= self.stress_min)

            # Feature readiness says whether enough consecutive history exists for the stated window.
            for window in self.windows:
                if i + 1 < window:
                    ready = False
                elif self.require_consecutive:
                    ready = (current_date - series[i - window + 1]["__date"]).days == window - 1
                else:
                    ready = True
                row[f"feature_ready_{window}d"] = ready

            # Keep PP/model eligibility explicit; do not let feature engineering override PP quality decisions.
            row["feature_engineering_status"] = "READY" if parse_bool(row.get(self.cfg["model_eligible_column"], False)) else "SOURCE_NOT_MODEL_ELIGIBLE"
            out.append(row)
        return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Y.3172 PP Milestone 2: time-based feature engineering for Operator x Day QoS data")
    ap.add_argument("input_csv", help="Master operator_day_features.csv produced by PP/Collector")
    ap.add_argument("--config", default="config/feature_config.json")
    ap.add_argument("--out", default="data/master/model_features.csv")
    args = ap.parse_args()

    engine = FeatureEngineer(args.config)
    rows = engine.transform_file(args.input_csv, args.out)
    print(f"Feature engineered {len(rows)} Operator x Day row(s).")
    print(f"Output: {Path(args.out).resolve()}")
    if rows:
        print("Latest row:")
        latest = rows[-1]
        for key in [
            "date", "operator", "total_traffic_erlang_pct_change_1d",
            "availability_mean_deterioration_1d_pp", "cssr_mean_deterioration_1d_pp",
            "dcr_mean_deterioration_1d_pp", "hosr_mean_deterioration_1d_pp",
            "concurrent_deterioration_count", "multi_kpi_stress_flag", "feature_ready_7d"
        ]:
            if key in latest:
                print(f"  {key}: {latest[key]}")


if __name__ == "__main__":
    main()
