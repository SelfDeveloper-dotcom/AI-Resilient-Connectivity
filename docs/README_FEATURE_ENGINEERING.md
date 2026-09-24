# PP Feature Engineering — Milestone 2

This stage runs **after** SRC → Collector → PP validation/aggregation.
It reads the accumulated `Operator × Day` table and creates time-based features for the future prediction model.

## Input

`data/master/operator_day_features.csv`

One row = one operator on one reporting day.

## Output

`data/master/model_features.csv`

The original daily fields are retained and new features are appended.

## Why feature engineering is needed

A prediction model should not see only `CSSR = 99.50`. It should also be able to see whether CSSR is falling, whether DCR is rising, whether congestion has been increasing for several days, and whether several KPIs are deteriorating together.

## Feature groups

### 1. Current level
Already created by the first PP stage, for example:
- `availability_mean`, `availability_p10`
- `cssr_mean`, `cssr_p10`
- `dcr_mean`, `dcr_p90`
- `hosr_mean`, `hosr_p10`
- `sd_congestion_mean`, `sd_congestion_p95`
- `tch_congestion_mean`, `tch_congestion_p95`
- `total_traffic_erlang`

### 2. Trailing rolling features
For 3-day and 7-day windows:
- `*_roll3_mean`, `*_roll3_min`, `*_roll3_max`
- `*_roll7_mean`, `*_roll7_min`, `*_roll7_max`

These windows include today and previous days only. No future data is used.

### 3. Recent change
For percentage KPIs the system uses **percentage-point changes**, e.g.:
- `cssr_mean_delta_1d_pp`
- `dcr_mean_delta_3d_pp`

For Traffic Volume it uses percent change, e.g.:
- `total_traffic_erlang_pct_change_1d`
- `total_traffic_erlang_pct_change_3d`

Traffic is contextual: an increase is not automatically labelled bad.

### 4. Direction-normalised deterioration
To make different KPI directions consistent:
- For Availability/CSSR/HOSR, a fall is deterioration.
- For DCR/SD Congestion/TCH Congestion, a rise is deterioration.

The derived `*_deterioration_*` fields are defined so that:

**positive value = worsening**

This makes later model interpretation easier.

### 5. Deterioration flags and streaks
For six primary KPIs, PP creates:
- `*_deteriorating_flag`
- `*_deterioration_streak`

The small sensitivity values in `feature_config.json` are **Sandbox engineering tolerances**, not regulatory thresholds.

### 6. Multi-KPI stress
- `concurrent_deterioration_count` = how many primary KPIs materially worsened versus yesterday.
- `multi_kpi_stress_flag` = 1 when at least the configured number deteriorate together (default 3).

This is not the final AI risk score. It is only an interpretable model input.

### 7. Readiness and data continuity
- `date_gap_days`
- `feature_ready_3d`
- `feature_ready_7d`

Lag features are only calculated when the expected calendar continuity is present. This prevents a missing reporting day from being mistaken for a normal one-day trend.

## Run manually

```bash
python feature_engineer.py data/master/operator_day_features.csv --config feature_config.json --out data/master/model_features.csv
```

or double-click `run_feature_engineering.bat` on Windows.

## Learning rule to remember

**Raw KPI → daily analytical level → recent behaviour → model feature.**

Example:

`CSSR = 99.50%` → `CSSR fell 0.12 percentage points since yesterday` → `CSSR has deteriorated for 2 consecutive days`.

The prediction model comes later. This stage only describes the network condition and recent trajectory without using future information.
