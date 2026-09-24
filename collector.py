from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pp_engine import PPProcessor, write_csv
from feature_engineer import FeatureEngineer
from target_engineer import TargetEngineer


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value).strip("_")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    fieldnames = list(rows[0].keys())
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        w.writerows(rows)


class Collector:
    """Y.3172 Collector (C) for independent operator weekly workbook submissions."""

    def __init__(self, config_path: str | Path):
        cfg_path = Path(config_path).resolve()
        self.cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        self.base = (cfg_path.parent / self.cfg.get("project_root", ".")).resolve()
        self.source_root = self.base / self.cfg["source_root"]
        self.raw_root = self.base / self.cfg["raw_root"]
        self.processed_root = self.base / self.cfg["processed_root"]
        self.master_root = self.base / self.cfg["master_root"]
        self.registry_file = self.base / self.cfg["registry_file"]
        self.pp_config = self.base / self.cfg["pp_config"]
        self.allowed = {x.lower() for x in self.cfg["allowed_extensions"]}
        self.operators = self.cfg["operators"]
        for folder in self.operators:
            (self.source_root / folder).mkdir(parents=True, exist_ok=True)
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.processed_root.mkdir(parents=True, exist_ok=True)
        self.master_root.mkdir(parents=True, exist_ok=True)

    def processed_hashes(self) -> set[str]:
        return {r.get("sha256", "") for r in read_csv(self.registry_file) if r.get("status") == "PROCESSED"}

    def discover(self) -> list[tuple[str, str, Path]]:
        found = []
        for folder, operator in self.operators.items():
            d = self.source_root / folder
            for p in sorted(d.iterdir()):
                if not p.is_file() or p.name.startswith("~$"):
                    continue
                if p.suffix.lower() not in self.allowed:
                    continue
                found.append((folder, operator, p))
        return found

    def scan(self, sheet: str | None = None) -> None:
        known = self.processed_hashes()
        discovered = self.discover()
        if not discovered:
            print(f"No new .xlsx submissions found under {self.source_root}")
            return

        for folder, operator, src in discovered:
            digest = sha256_file(src)
            if digest in known:
                print(f"SKIP duplicate: {operator} / {src.name}")
                continue
            self.process_one(folder, operator, src, digest, sheet=sheet)
            known.add(digest)

    def process_one(self, folder: str, operator: str, src: Path, digest: str, sheet: str | None = None) -> None:
        received_at = utcnow()
        submission_id = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{digest[:10]}"
        raw_dir = self.raw_root / folder / submission_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / src.name
        shutil.copy2(src, raw_path)

        out_dir = self.processed_root / folder / submission_id
        out_dir.mkdir(parents=True, exist_ok=True)

        registry_base = {
            "submission_id": submission_id,
            "received_at_utc": received_at,
            "operator": operator,
            "source_folder": folder,
            "source_filename": src.name,
            "raw_archive_path": str(raw_path.relative_to(self.base)),
            "sha256": digest,
            "technology": self.cfg.get("technology", "2G"),
        }

        try:
            processor = PPProcessor(self.pp_config, operator_override=operator)
            summaries, validations = processor.process_workbook(raw_path, sheet_name=sheet)
            summary_rows = []
            for s in summaries:
                r = asdict(s)
                r.update({
                    "submission_id": submission_id,
                    "source_filename": src.name,
                    "sha256": digest,
                })
                summary_rows.append(r)
            validation_rows = []
            for v in validations:
                r = dict(v)
                r.update({
                    "submission_id": submission_id,
                    "operator": operator,
                    "source_filename": src.name,
                })
                validation_rows.append(r)

            write_csv(out_dir / "operator_day_features.csv", summary_rows)
            write_csv(out_dir / "validation_report.csv", validation_rows)
            master_daily = self.master_root / "operator_day_features.csv"
            append_csv(master_daily, summary_rows)
            append_csv(self.master_root / "validation_report.csv", validation_rows)

            # PP Milestone 2: rebuild time-based model features from the accumulated master table.
            feature_cfg = self.base / self.cfg.get("feature_config", "feature_config.json")
            feature_out = self.base / self.cfg.get("feature_output", "data/master/model_features.csv")
            if feature_cfg.exists():
                FeatureEngineer(feature_cfg).transform_file(master_daily, feature_out)

                # Milestone 3: rebuild sandbox supervised-learning target/training table.
                target_cfg = self.base / self.cfg.get("target_config", "target_config.json")
                target_out = self.base / self.cfg.get("target_output", "data/master/training_dataset.csv")
                if target_cfg.exists():
                    TargetEngineer(target_cfg).transform_file(feature_out, target_out)

            eligible_days = sum(bool(r["model_eligible"]) for r in summary_rows)
            status = "PROCESSED"
            reg = registry_base | {
                "status": status,
                "daily_sheets_processed": len(summary_rows),
                "model_eligible_days": eligible_days,
                "processed_at_utc": utcnow(),
                "message": "",
            }
            append_csv(self.registry_file, [reg])
            print(f"PROCESSED: {operator} / {src.name} -> {len(summary_rows)} day(s), {eligible_days} model eligible")
        except Exception as e:
            reg = registry_base | {
                "status": "FAILED",
                "daily_sheets_processed": 0,
                "model_eligible_days": 0,
                "processed_at_utc": utcnow(),
                "message": f"{type(e).__name__}: {e}",
            }
            append_csv(self.registry_file, [reg])
            print(f"FAILED: {operator} / {src.name}: {e}")


def main():
    ap = argparse.ArgumentParser(description="Y.3172 SRC/C Collector for independent operator QoS workbooks")
    ap.add_argument("--config", default="config/collector_config.json")
    ap.add_argument("--watch", action="store_true", help="Keep scanning the inbox periodically")
    ap.add_argument("--interval", type=int, default=60, help="Watch interval in seconds")
    ap.add_argument("--sheet", default=None, help="Development/testing only: process one named worksheet")
    args = ap.parse_args()

    collector = Collector(args.config)
    if not args.watch:
        collector.scan(sheet=args.sheet)
        return

    print(f"Watching {collector.source_root} every {args.interval}s. Press Ctrl+C to stop.")
    try:
        while True:
            collector.scan(sheet=args.sheet)
            time.sleep(max(5, args.interval))
    except KeyboardInterrupt:
        print("Collector stopped.")


if __name__ == "__main__":
    main()
