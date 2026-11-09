from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from openpyxl import load_workbook


KPI_KEYS = [
    "availability",
    "cssr",
    "sd_congestion",
    "tch_congestion",
    "dcr",
    "hosr",
]

LOWER_TAIL_KEYS = {"availability", "cssr", "hosr"}
UPPER_TAIL_KEYS = {"sd_congestion", "tch_congestion", "dcr"}


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def normalize_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                pass
    return None


@dataclass
class DailySummary:
    sheet: str
    date: str | None
    operator: str
    technology: str
    total_rows: int
    unique_cells: int
    duplicate_cell_rows: int
    states: int
    lgas: int
    total_traffic_erlang: float | None
    availability_mean: float | None
    availability_p10: float | None
    cssr_mean: float | None
    cssr_p10: float | None
    sd_congestion_mean: float | None
    sd_congestion_p95: float | None
    tch_congestion_mean: float | None
    tch_congestion_p95: float | None
    dcr_mean: float | None
    dcr_p90: float | None
    hosr_mean: float | None
    hosr_p10: float | None
    quality_status: str
    model_eligible: bool


class PPProcessor:
    """Milestone 1 Y.3172 PP engine: validate and aggregate one operator workbook."""

    def __init__(self, config_path: str | Path, operator_override: str | None = None):
        cfg_path = Path(config_path).resolve()
        self.config = json.loads(cfg_path.read_text(encoding="utf-8"))
        self.project_root = cfg_path.parent.parent
        self.cols = self.config["columns"]
        self.operator = operator_override or self.config["operator"]
        self.expected_tech = self.config["technology"]
        self.min_complete = float(self.config["minimum_kpi_completeness_for_model"])
        self.valid_geo_pairs: set[tuple[str, str]] = set()
        geo_rel = self.config.get("geography_master_csv")
        if geo_rel:
            geo_path = self.project_root / geo_rel
            if geo_path.exists() and geo_path.stat().st_size > 0:
                with geo_path.open(newline="", encoding="utf-8-sig") as f:
                    for r in csv.DictReader(f):
                        state = str(r.get("STATE", "")).strip().casefold()
                        lga = str(r.get("LGA", "")).strip().casefold()
                        if state and lga:
                            self.valid_geo_pairs.add((state, lga))

    def process_workbook(self, workbook_path: str | Path, sheet_name: str | None = None):
        wb = load_workbook(workbook_path, read_only=True, data_only=True)
        try:
            summaries: list[DailySummary] = []
            validation_rows: list[dict[str, Any]] = []

            sheet_names = [sheet_name] if sheet_name else list(wb.sheetnames)
            for current_sheet in sheet_names:
                if current_sheet not in wb.sheetnames:
                    raise ValueError(f"Worksheet not found: {current_sheet}. Available: {wb.sheetnames}")
                summary, validations = self._process_sheet(wb[current_sheet])
                summaries.append(summary)
                validation_rows.extend(validations)

            return summaries, validation_rows
        finally:
            # Explicitly release the underlying Excel file handle. This is
            # essential on Windows, where an open read-only workbook prevents
            # temporary/submitted .xlsx files from being moved or deleted.
            wb.close()

    def _process_sheet(self, ws):
        rows = ws.iter_rows(values_only=True)
        headers = next(rows, None)
        if not headers:
            summary = self._failed_empty_sheet(ws.title)
            return summary, [{"sheet": ws.title, "level": "FAIL", "rule": "FILE-EMPTY", "field": "", "count": 1, "message": "Worksheet is empty."}]

        header_map = {str(h).strip() if h is not None else "": idx for idx, h in enumerate(headers)}
        expected_headers = {key: str(name).strip() for key, name in self.cols.items()}
        missing_headers = [name for name in expected_headers.values() if name not in header_map]
        if missing_headers:
            summary = self._failed_schema_sheet(ws.title)
            return summary, [{"sheet": ws.title, "level": "FAIL", "rule": "SCHEMA-MISSING", "field": ", ".join(missing_headers), "count": len(missing_headers), "message": "Mandatory column(s) missing."}]

        idx = {key: header_map[name] for key, name in expected_headers.items()}
        total_rows = 0
        cells_seen: set[str] = set()
        duplicate_rows = 0
        states: set[str] = set()
        lgas: set[str] = set()
        dates = Counter()
        techs = Counter()
        missing = Counter()
        invalid = Counter()
        traffic_values: list[float] = []
        kpi_values: dict[str, list[float]] = {k: [] for k in KPI_KEYS}

        for row in rows:
            # Ignore completely blank Excel rows.
            if not any(v is not None and v != "" for v in row):
                continue
            total_rows += 1

            d = normalize_date(row[idx["date"]])
            if d is None:
                invalid["date"] += 1
            else:
                dates[d.isoformat()] += 1

            cell_raw = row[idx["cell"]]
            cell = str(cell_raw).strip() if cell_raw not in (None, "") else ""
            if not cell:
                missing["cell"] += 1
            elif cell in cells_seen:
                duplicate_rows += 1
            else:
                cells_seen.add(cell)

            tech_raw = row[idx["technology"]]
            tech = str(tech_raw).strip() if tech_raw not in (None, "") else ""
            if not tech:
                missing["technology"] += 1
            else:
                techs[tech] += 1

            state_raw = row[idx["state"]]
            state = str(state_raw).strip() if state_raw not in (None, "") else ""
            if state:
                states.add(state)
            else:
                missing["state"] += 1

            lga_raw = row[idx["lga"]]
            lga = str(lga_raw).strip() if lga_raw not in (None, "") else ""
            if lga:
                lgas.add(lga)
            else:
                missing["lga"] += 1
            if self.valid_geo_pairs and state and lga and (state.casefold(), lga.casefold()) not in self.valid_geo_pairs:
                invalid["state_lga"] += 1

            tv = number(row[idx["traffic"]])
            if tv is None:
                missing["traffic"] += 1
            elif tv < 0:
                invalid["traffic"] += 1
            else:
                traffic_values.append(tv)

            for key in KPI_KEYS:
                x = number(row[idx[key]])
                if x is None:
                    missing[key] += 1
                elif x < 0 or x > 100:
                    invalid[key] += 1
                else:
                    kpi_values[key].append(x)

        validations: list[dict[str, Any]] = []

        # Structural validations.
        if invalid["date"]:
            validations.append(self._v(ws.title, "FAIL", "DATE-PARSE", "DATE_SUBMITTED", invalid["date"], "Unparseable reporting date."))
        if len(dates) > 1:
            validations.append(self._v(ws.title, "FAIL", "DATE-MIXED", "DATE_SUBMITTED", sum(dates.values()), f"Multiple dates present: {dict(dates)}"))
        if missing["cell"]:
            validations.append(self._v(ws.title, "FAIL", "CELL-MISSING", "CELL", missing["cell"], "Cell identifier missing."))
        if duplicate_rows:
            validations.append(self._v(ws.title, "FAIL", "CELL-DUPLICATE", "CELL", duplicate_rows, "Duplicate cell identifier within daily sheet."))
        wrong_tech_count = sum(c for t, c in techs.items() if t != self.expected_tech)
        if wrong_tech_count:
            validations.append(self._v(ws.title, "FAIL", "TECH-MISMATCH", "Technology", wrong_tech_count, f"Expected {self.expected_tech}; found {dict(techs)}"))

        # Field-level KPI/data warnings.
        display_names = {
            "traffic": "2G Erlang",
            "availability": "Availability",
            "cssr": "CSSR",
            "sd_congestion": "SDCCH Congestion Rate",
            "tch_congestion": "TCH Congestion Rate",
            "dcr": "Drop Call Rate",
            "hosr": "Handover Success Rate",
            "state": "STATE",
            "lga": "LGA",
        }
        for key in ["state", "lga", "traffic"] + KPI_KEYS:
            if missing[key]:
                validations.append(self._v(ws.title, "WARNING", "MISSING", display_names[key], missing[key], "Missing value(s); NULL is not treated as zero."))
            if invalid[key]:
                validations.append(self._v(ws.title, "WARNING", "INVALID-RANGE", display_names[key], invalid[key], "Value excluded from clean analytical calculation; raw value retained."))
        if invalid["state_lga"]:
            validations.append(self._v(ws.title, "WARNING", "GEO-MISMATCH", "STATE/LGA", invalid["state_lga"], "State/LGA pair not found in configured master list; KPI values retained but geography requires review."))

        # Completeness determines model eligibility, not mere presence of warnings.
        completeness_failures = []
        if total_rows > 0:
            for key in KPI_KEYS:
                valid_count = len(kpi_values[key])
                completeness = valid_count / total_rows
                if completeness < self.min_complete:
                    completeness_failures.append((key, completeness))
                    validations.append(self._v(ws.title, "FAIL", "COMPLETENESS", display_names[key], total_rows - valid_count, f"Valid completeness {completeness:.2%} below configured minimum {self.min_complete:.0%}."))

        structural_fail = any(v["level"] == "FAIL" for v in validations if v["rule"] != "COMPLETENESS")
        model_eligible = not structural_fail and not completeness_failures and total_rows > 0
        quality_status = "FAIL" if not model_eligible else ("WARNING" if validations else "PASS")

        main_date = dates.most_common(1)[0][0] if dates else None

        def mean(key):
            vals = kpi_values[key]
            return fmean(vals) if vals else None

        summary = DailySummary(
            sheet=ws.title,
            date=main_date,
            operator=self.operator,
            technology=self.expected_tech,
            total_rows=total_rows,
            unique_cells=len(cells_seen),
            duplicate_cell_rows=duplicate_rows,
            states=len(states),
            lgas=len(lgas),
            total_traffic_erlang=sum(traffic_values) if traffic_values else None,
            availability_mean=mean("availability"),
            availability_p10=percentile(kpi_values["availability"], 0.10),
            cssr_mean=mean("cssr"),
            cssr_p10=percentile(kpi_values["cssr"], 0.10),
            sd_congestion_mean=mean("sd_congestion"),
            sd_congestion_p95=percentile(kpi_values["sd_congestion"], 0.95),
            tch_congestion_mean=mean("tch_congestion"),
            tch_congestion_p95=percentile(kpi_values["tch_congestion"], 0.95),
            dcr_mean=mean("dcr"),
            dcr_p90=percentile(kpi_values["dcr"], 0.90),
            hosr_mean=mean("hosr"),
            hosr_p10=percentile(kpi_values["hosr"], 0.10),
            quality_status=quality_status,
            model_eligible=model_eligible,
        )
        return summary, validations

    @staticmethod
    def _v(sheet, level, rule, field, count, message):
        return {"sheet": sheet, "level": level, "rule": rule, "field": field, "count": count, "message": message}

    def _failed_empty_sheet(self, sheet):
        return DailySummary(sheet, None, self.operator, self.expected_tech, 0, 0, 0, 0, 0, None, None, None, None, None, None, None, None, None, None, None, None, None, None, "FAIL", False)

    def _failed_schema_sheet(self, sheet):
        return DailySummary(sheet, None, self.operator, self.expected_tech, 0, 0, 0, 0, 0, None, None, None, None, None, None, None, None, None, None, None, None, None, None, "FAIL", False)


def write_csv(path: str | Path, rows: list[dict[str, Any]]):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Y.3172 PP Milestone 1: validate and aggregate weekly 2G QoS workbook")
    ap.add_argument("workbook", help="Path to operator weekly Excel workbook")
    ap.add_argument("--config", default="config/pp_config.json")
    ap.add_argument("--out", default="output")
    ap.add_argument("--sheet", default=None, help="Optional: process only one worksheet, e.g. '3rd August'")
    args = ap.parse_args()

    processor = PPProcessor(args.config)
    summaries, validations = processor.process_workbook(args.workbook, sheet_name=args.sheet)

    out = Path(args.out)
    write_csv(out / "operator_day_features.csv", [asdict(s) for s in summaries])
    write_csv(out / "validation_report.csv", validations)

    print(f"Processed {len(summaries)} daily sheet(s).")
    for s in summaries:
        print(f"{s.date or s.sheet}: rows={s.total_rows:,}, cells={s.unique_cells:,}, quality={s.quality_status}, model_eligible={s.model_eligible}")
    print(f"\nOutputs written to: {out.resolve()}")


if __name__ == "__main__":
    main()
