# v1.4.0 — Interactive Dashboard

- Redesigned the analyst dashboard with a modern regulatory-operations layout.
- Added Real/Sandbox mode switch in the header.
- Added summary KPI cards for operators, alerts, high-review items and knowledge sources.
- Added clickable operator status cards with risk gauges and policy-decision badges.
- Added an interactive degradation-risk trend chart using local browser canvas (no external CDN).
- Added a live KPI snapshot panel for Cell Availability, CSSR, DCR, HOSR, SDCCH/TCH congestion, traffic and concurrent deterioration.
- Improved alert presentation and Knowledge Base styling.
- Kept the dashboard fully local/offline and retained the human-review guardrail.

# Changelog

## v1.2.0 — Knowledge Answering Upgrade

- Replaced raw-chunk-first dashboard experience with **Answer first, Evidence second**.
- Added `/knowledge/answer` endpoint.
- Added controlled acronym/query expansion (including NAIS, MLFO, QoS and 2G KPI acronyms).
- Added hybrid retrieval ranking using TF-IDF, lexical overlap, exact acronym/entity matches and source-category boosts.
- Added clean text normalisation for PDF/DOCX extraction.
- Added controlled/extractive answer synthesis; no unrestricted generative model is required.
- Added grounding confidence and collapsible supporting evidence in the dashboard.
- Added tests for grounded answer structure and acronym expansion.


## v1.1.1
- Fixed Windows `WinError 32` during PP tests by explicitly closing Excel workbooks after processing.
- Updated PP tests to close temporary workbooks before cleanup.
- Includes all v1.1.0 Knowledge Base improvements.

## v1.1.0 - Knowledge Base completion
- Index project `docs/` automatically alongside dedicated local knowledge sources.
- Add standards, NCC QoS, AI governance and local project corpus folders.
- Improve DOCX ingestion to include table text.
- Add document/category/source metadata and knowledge-base statistics.
- Add `/knowledge/stats` and a dashboard Knowledge Base Search interface.
- Redirect `/` to the real dashboard.
- Expand automated Knowledge Base tests and documentation.

## v1.0.0 — Complete prototype baseline

- Local-directory SRC with Box migration boundary
- Collector with SHA-256 deduplication, raw archive and submission registry
- PP validation, cleaning and Operator × Day aggregation
- Time-based feature engineering and next-day target engineering
- Chronological ML training/evaluation and model registry (MLFO)
- Separate Sandbox model registry
- Batch inference and bounded model-agnostic local explanations
- Human-review policy engine and decision router
- FastAPI dashboard/API SINK
- Local document knowledge retrieval
- Synthetic ML Sandbox generator
- Windows setup/run scripts, tests and project documentation
## 1.3.0 - Knowledge accuracy upgrade
- Replaced raw extractive-only answering with optional local grounded RAG through Ollama.
- Added semantic embeddings using `embeddinggemma` with TF-IDF hybrid retrieval.
- Added local answer generation using `qwen3:4b`, constrained to retrieved evidence.
- Added inline evidence references `[S1]`, `[S2]`, etc.
- Preserved PDF page numbers in evidence and improved source-aware query routing.
- Added deterministic fallback and abstention when Ollama/evidence is unavailable.
- Added `setup_knowledge_rag.bat` and Knowledge RAG setup documentation.
