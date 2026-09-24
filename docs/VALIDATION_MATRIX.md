# PP Validation Matrix

| Area | Rule | Default outcome | Processing action |
|---|---|---|---|
| File | Workbook readable and daily worksheet non-empty | FAIL | Stop affected submission/sheet |
| Schema | Mandatory fields present | FAIL | Do not aggregate affected sheet |
| Date | Parseable and one reporting date per daily sheet | FAIL | Quarantine affected sheet |
| Cell | Cell ID present | FAIL | Affected day not model eligible |
| Cell | Duplicate cell within daily sheet | FAIL | Affected day not model eligible |
| Technology | Expected 2G value in 2G workbook | FAIL | Exclude mismatched submission/day |
| State/LGA | Missing value | WARNING | Retain KPI but flag geography |
| State/LGA | Pair absent from configured master list | WARNING | Retain KPI but flag geography |
| Traffic | Numeric and >= 0 | WARNING per invalid field | Exclude invalid traffic value only |
| Availability | 0–100 | WARNING per invalid field | Exclude invalid value only |
| CSSR | 0–100 | WARNING per invalid field | Exclude invalid value only |
| HOSR | 0–100 | WARNING per invalid field | Exclude invalid value only |
| DCR | 0–100 | WARNING per invalid field | Exclude invalid value only |
| SDCCH congestion | 0–100 | WARNING per invalid field | Exclude invalid value only |
| TCH congestion | 0–100 | WARNING per invalid field | Exclude invalid value only |
| Missing KPI | NULL remains distinct from zero | WARNING | Exclude missing field only |
| KPI completeness | Below configured minimum (default 95%) | FAIL | Day not model eligible |
| Outlier within mathematical range | Unusual but possible value | Retain | Do not delete genuine degradation |

The 95% completeness value is a configurable Sandbox/analytical setting, not a regulatory threshold.
