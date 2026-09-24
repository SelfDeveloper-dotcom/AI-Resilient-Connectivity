# Prototype Demonstration Script

1. Run `python pipeline.py sandbox-demo`.
2. Show `models/registry/active.json` and the registered model metadata.
3. Open `data/sandbox/model_features.csv` and explain lag/trend features.
4. Show predictions and the local explanation field.
5. Show policy decisions and emphasize human-review guardrails.
6. Start `python pipeline.py serve` and open `/dashboard`.
7. Demonstrate a knowledge query using `/knowledge?q=human+review`.
8. Explain that real operation replaces Sandbox data with independently submitted operator workbooks through the local Collector, and later Box can replace the local SRC adapter.
