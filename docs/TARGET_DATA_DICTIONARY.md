# Target Engineering Data Dictionary

| Field | Meaning |
|---|---|
| `qos_degradation_next_day` | Sandbox binary target: 1 = next consecutive model-eligible day has multi-KPI stress; 0 = it does not |
| `target_available` | Whether the row has a valid next-day label |
| `target_next_date` | Date used to construct the label |
| `target_next_day_stress_count` | Audit-only count of deteriorating KPIs on the next day; never use as an input feature |
| `target_reason` | Why the label is 1, 0, or unavailable |
| `target_definition` | Explicit label definition/version string |

**Leakage rule:** every field beginning with `target_`, plus `qos_degradation_next_day`, is excluded from model input features. They exist only for supervised labelling and audit.
