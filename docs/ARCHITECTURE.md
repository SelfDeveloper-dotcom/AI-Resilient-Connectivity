# Architecture

```text
Local SRC now / Box later
          |
          v
C — Collector
  fingerprint, deduplicate, immutable raw archive, registry
          |
          v
PP — Validation / Cleaning / Aggregation
  Cell × Day -> Operator × Day
          |
          v
PP — Feature Engineering
  lags, rolling context, deterioration, streaks, stress count
          |
          v
Target Engineering
  sandbox next-day label
          |
          v
M — Model
  train/evaluate/register/predict/explain
          |
          v
P — Policy
  configurable thresholds + human-review guardrails
          |
          v
D — Decision Router
  alerts + latest status
          |
          v
SINK
  API + browser dashboard

Supporting functions:
- MLFO: model registry / active-model switching
- ML Sandbox: synthetic safe test data
- Knowledge Base: retrieval over authoritative local documents
```

## Observation levels

- Raw source: **Operator × Cell × Day**
- Initial ML feature table: **Operator × Day**
- Prediction: next consecutive reporting day

## Data-governance principle

Raw operator submissions are never overwritten. Invalid analytical values are excluded from clean calculations but remain available in the immutable raw archive.
