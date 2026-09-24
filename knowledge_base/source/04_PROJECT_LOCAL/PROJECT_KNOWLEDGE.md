# AI Resilient Connectivity — Project Knowledge

The prototype is a human-in-the-loop early-warning decision-support system for mobile-network QoS resilience. The current 2G scope uses Cell Availability, CSSR, HOSR, Drop Call Rate, SDCCH Congestion Rate, TCH Congestion Rate, and 2G Erlang traffic.

Raw operator submissions are preserved unchanged. Preprocessing validates schema, dates, cell identity, technology, geography, missing values, duplicates, mathematical KPI ranges, and completeness before creating Operator × Day analytical features.

Model outputs are not autonomous regulatory decisions. Predictions are routed through a configurable policy layer, and human analyst validation is required before operational or regulatory action.

The current supervised target is a sandbox proxy: day t is labelled positive when the next consecutive, model-eligible day enters coordinated multi-KPI stress. This target must be reviewed and refined using historical data before it is treated as an operational definition of degradation.
