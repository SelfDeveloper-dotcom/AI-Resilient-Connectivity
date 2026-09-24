# Model Feature Data Dictionary — MVP 3

## Core rule
All engineered features use only information available **on or before the row's date**. Positive `deterioration` values always mean worsening.

| Feature pattern | Meaning |
|---|---|
| `*_roll3_mean` | Mean over today + previous 2 consecutive reporting days |
| `*_roll7_mean` | Mean over today + previous 6 consecutive reporting days |
| `*_rollN_min/max` | Lowest/highest observed value in the trailing window |
| `*_delta_1d_pp` | Today's KPI minus yesterday's KPI, in percentage points |
| `*_delta_3d_pp` | Today's KPI minus the value 3 calendar days earlier |
| `*_deterioration_1d_pp` | Direction-normalised 1-day worsening; positive = worse |
| `*_deterioration_3d_pp` | Direction-normalised 3-day worsening; positive = worse |
| `total_traffic_erlang_pct_change_1d` | Traffic growth/decline versus yesterday |
| `total_traffic_erlang_pct_change_3d` | Traffic growth/decline versus 3 days earlier |
| `*_deteriorating_flag` | 1 when the KPI worsens beyond the configured Sandbox tolerance |
| `*_deterioration_streak` | Number of consecutive daily worsening steps |
| `concurrent_deterioration_count` | Number of six primary KPIs worsening materially together today |
| `multi_kpi_stress_flag` | 1 when concurrent deterioration count meets configured threshold |
| `date_gap_days` | Calendar days since the previous operator record |
| `feature_ready_3d` | True when a consecutive 3-day history exists |
| `feature_ready_7d` | True when a consecutive 7-day history exists |
| `feature_engineering_status` | READY only when the underlying PP row is model eligible |

## Direction rules

**Higher is normally better:** Availability, CSSR, HOSR. A fall is deterioration.

**Higher is normally worse:** DCR, SDCCH Congestion, TCH Congestion. A rise is deterioration.

**Context only:** Traffic Volume. Higher traffic is not automatically bad; its relationship with the other KPIs is what the later model will learn.

## Sandbox tolerances
The small `epsilon` values in `feature_config.json` distinguish meaningful day-to-day movement from tiny numerical noise. They are **engineering settings for the prototype, not regulatory thresholds**.
