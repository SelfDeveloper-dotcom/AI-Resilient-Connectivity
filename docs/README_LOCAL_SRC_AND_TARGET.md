# Local SRC and Target Engineering

## Current operational source

Box is the intended production source, but the MVP uses a local directory adapter:

```text
data/inbox/
  Operator_A/
  Operator_B/
  Operator_C/
  Operator_D/
```

Drop each operator's weekly `.xlsx` file into the correct folder. You do not need to upload it to ChatGPT.

Run once:

```bash
python collector.py --config collector_config.json
```

Or continuously:

```bash
python collector.py --config collector_config.json --watch --interval 60
```

The pipeline is:

```text
Local SRC → Collector → PP Validation/Aggregation → Feature Engineering → Target Engineering
```

## Historical ingestion

You can place several historical weekly files into an operator folder at once. The Collector uses SHA-256 fingerprints to avoid processing an identical workbook twice. The original source workbooks are copied unchanged to `data/raw/`.

Master outputs:

- `data/master/submission_registry.csv`
- `data/master/validation_report.csv`
- `data/master/operator_day_features.csv`
- `data/master/model_features.csv`
- `data/master/training_dataset.csv`

## Sandbox target

For development, the label for day **t** is based on what happens on **t+1**:

- target = `1` if the next consecutive day is model eligible and has `multi_kpi_stress_flag = 1`;
- target = `0` if the next consecutive day is model eligible and has no multi-KPI stress;
- target = blank if the next day is unavailable, there is a date gap, or the next day is not model eligible.

This is intentionally a **proxy training label**, not an NCC regulatory threshold. Its purpose is to let us build and test the prediction workflow while retaining a transparent definition. We should refine it after ingesting several months of real history.

## Why the target is shifted

The features on 7 August can be used to predict whether 8 August becomes degraded. Therefore the 8 August stress state is attached as the target on the 7 August row. No future-day values are included among the input features.
