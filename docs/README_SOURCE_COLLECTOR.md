# SRC + Collector — Local MVP

This component removes the need to upload operator workbooks to ChatGPT.

## 1. Source (SRC)
Each operator gets an independent drop folder:

```text
data/inbox/
  Operator_A/
  Operator_B/
  Operator_C/
  Operator_D/
```

Place the operator's original weekly `.xlsx` workbook in the appropriate folder. The original file is not edited.

## 2. Collector (C)
`collector.py`:
- detects new `.xlsx` submissions;
- derives operator identity from the source folder;
- computes a SHA-256 fingerprint so the same workbook is not processed twice;
- copies the exact original workbook into an immutable-style Raw archive;
- records source filename, operator, hash and timestamps in a submission registry;
- invokes the PP engine automatically;
- stores per-submission PP outputs;
- appends Operator × Day results to master feature and validation tables.

## 3. One-shot use

```bash
python setup_folders.py
python collector.py --config collector_config.json
```

On Windows, double-click `run_collector.bat` after Python is installed.

## 4. Continuous local watch

```bash
python collector.py --config collector_config.json --watch --interval 60
```

On Windows, `watch_collector.bat` runs the same watcher. Leave the terminal open while you want automatic collection.

## 5. Data flow

```text
Operator workbook
    ↓
data/inbox/Operator_X
    ↓
Collector
    ├─ SHA-256 duplicate check
    ├─ raw archive copy
    ├─ submission registry
    └─ invoke PP
          ↓
data/processed/Operator_X/<submission_id>/
          ↓
data/master/operator_day_features.csv
```

## 6. Important design principle
ChatGPT is not part of the operational data path. The MVP runs on your own machine/server. Later the `Source` can be replaced by Box, SharePoint, SFTP or an API without changing the PP logic.
