# AI Resilient Connectivity

End-to-end prototype for **next-period mobile-network QoS degradation early warning**, aligned conceptually with ITU-T Y.3172 pipeline roles.

## What is implemented

- **SRC** — local operator submission directories (Box adapter scaffold included for later migration)
- **C / Collector** — file discovery, SHA-256 deduplication, immutable raw archive, submission registry
- **PP** — schema/date/cell/technology/KPI validation, missing-value handling, completeness checks and Operator × Day aggregation
- **PP Feature Engineering** — lag changes, rolling context, deterioration direction normalization, streaks and coordinated stress features
- **Target Engineering** — next-day sandbox proxy label for supervised learning
- **M** — chronological training/evaluation of Logistic Regression and Random Forest, model registration and activation
- **Explainability** — global importance plus local sensitivity explanation on material-risk/latest predictions
- **P** — configurable policy guardrails translating probability into MONITOR/WATCH/REVIEW/HIGH_REVIEW
- **D** — alert routing and latest-status outputs
- **SINK** — FastAPI service and browser dashboard
- **MLFO** — versioned model registry and active-model switching
- **ML Sandbox** — synthetic historical Operator × Day data for safe end-to-end demonstration
- **Knowledge service** — local TF-IDF retrieval over Markdown, TXT, DOCX and PDF documents

## Important governance boundary

The current target (`qos_degradation_next_day`) is a **sandbox proxy**, not an official NCC regulatory definition. Model outputs support analyst review only. They must not trigger autonomous regulatory action.

## Recommended environment

- Windows 10/11
- Python 3.11 (64-bit)
- VS Code
- Git

Create and activate a virtual environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 1. Run the synthetic end-to-end demo first

```powershell
python pipeline.py sandbox-demo
```

This generates synthetic history, engineers features and targets, trains/registers a model in a **separate Sandbox registry**, runs predictions, applies the policy layer and creates sandbox alerts. It does not activate or overwrite the real-data model registry.

## 2. Start the browser dashboard/API

```powershell
python pipeline.py serve
```

Open:

- Real-data dashboard: `http://127.0.0.1:8000/dashboard?mode=real`
- Sandbox dashboard: `http://127.0.0.1:8000/dashboard?mode=sandbox`
- API docs: `http://127.0.0.1:8000/docs`

## 3. Use real local operator submissions

Place each weekly workbook in the appropriate folder:

```text
data/inbox/Operator_A/
data/inbox/Operator_B/
data/inbox/Operator_C/
data/inbox/Operator_D/
```

Run:

```powershell
python pipeline.py all
```

The Collector archives each new workbook, deduplicates it, runs PP, rebuilds feature/target tables and—if sufficient history and an active model exist—runs prediction and policy routing.

### Real-data outputs

```text
data/master/submission_registry.csv
data/master/validation_report.csv
data/master/operator_day_features.csv
data/master/model_features.csv
data/master/training_dataset.csv
data/master/predictions.csv
data/master/policy_decisions.csv
data/master/alerts.csv
data/master/latest_status.csv
```

## 4. Train/retrain once enough real history exists

```powershell
python pipeline.py train
python pipeline.py predict
python pipeline.py policy
```

Training is deliberately blocked when there are too few usable rows or too few positive/negative events.

## 5. Model registry / MLFO

```powershell
python mlfo.py list
python mlfo.py activate model_YYYYMMDDTHHMMSSZ
```

## 6. Knowledge base

Copy authoritative source documents into `knowledge_base/source/`, then query locally:

```powershell
python knowledge_base.py "What does the project require for human review?"
```

The API also exposes `/knowledge?q=...`.

## 7. Automated tests

```powershell
python -m unittest discover -s tests -v
```

## Repository/data separation

Do **not** commit operator workbooks, processed regulatory data, model binaries, secrets or Box credentials. `.gitignore` is configured for that separation.

## Box later

The active SRC is the local directory. `box_source_adapter.py` and `requirements-box.txt` reserve the Box integration boundary so the source can later change without redesigning PP, ML, Policy or SINK.
