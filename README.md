# AI for Resilient Connectivity

### Explainable Multi-KPI Early Warning for Mobile-Network QoS Degradation

**ITU AI for Good Sandbox · Telecommunications / Resilient Connectivity**

> **Synthetic Sandbox data only for demonstration. Real operator submissions remain local and are never committed to the repository.**

---

## Start Here — Evaluator Guide

For a fast understanding of the use case before reviewing the code, start with the project documents below:

1. **[Technical Report](docs/AI_for_Resilient_Connectivity_Technical_Report.pdf)** — end-to-end explanation of the problem, Y.3172 architecture, data pipeline, model, deterministic Policy Node, Sandbox evaluation, Knowledge Base and governance controls.
2. **[One-Page Evaluation Scenario](docs/AI_for_Resilient_Connectivity_Evaluation_One_Page.docx)** — concise evaluation and controlled-deployment pathway.
3. **[Architecture](docs/ARCHITECTURE.md)** — implementation-level component mapping.
4. **[Sandbox Test & Validation Plan](submission/ITU_SANDBOX_TEST_VALIDATION_PLAN.md)** — reproducible validation approach and evaluation measures.
5. Run **`run_submission_demo.bat`** to reproduce the synthetic Sandbox workflow and evidence locally.

> The reports are provided to help evaluators understand the system. They do not contain confidential operator workbooks, credentials or restricted standards documents.

---

## Executive Summary

**The problem.** Telecom regulators receive large volumes of cell-level Quality of Service (QoS) data, but conventional monitoring is mainly retrospective: it shows what has already degraded and often evaluates KPIs independently. A regulator needs a defensible way to recognise coordinated deterioration early without turning an AI score into an automatic regulatory finding.

**The solution.** AI for Resilient Connectivity validates operator submissions, converts cell-level observations into trustworthy Operator × Day records, engineers temporal and multi-KPI features, and estimates whether significant QoS degradation is likely in the **next consecutive reporting period**. A deterministic policy layer converts model probability into `MONITOR`, `WATCH`, `REVIEW` or `HIGH_REVIEW`, and a human analyst remains responsible for any regulatory or operational decision.

**What makes it defensible.** The model predicts; deterministic policy governs the use of that prediction; the Knowledge Base explains standards, KPI definitions and project rules; and the human makes the final decision. The raw submission is preserved unchanged, data-quality failures can block model use, and the real-data model registry is physically separated from the synthetic Sandbox registry.

**Two intelligence systems, never conflated.** The predictive model learns from numerical QoS history. The Knowledge Base answers documentary questions from approved standards, regulations and project documents. A Knowledge Base answer cannot change a model probability, and a model probability cannot create a regulation.

### Submission

- **Knowledge base** — `knowledge_base/source/` plus project `docs/`
- **Live system** — local prototype: `http://127.0.0.1:8000/dashboard?mode=sandbox`
- **Technical report** — [`docs/AI_for_Resilient_Connectivity_Technical_Report.pdf`](docs/AI_for_Resilient_Connectivity_Technical_Report.pdf)

---

## Problem, and Why Existing Monitoring Does Not Solve It

### The regulatory case

A weekly 2G QoS workbook can contain tens of thousands of cell records for each reporting day. The prototype has already processed a real-format daily sheet with more than 84,000 cell observations. Each observation carries geography, traffic and service-performance KPIs. The challenge is not simply storing those records; it is determining whether today's combination of network conditions resembles patterns that precede material service degradation.

### What threshold monitoring misses

A single KPI can move for many reasons. Traffic growth, for example, is not inherently bad. A network can carry more traffic while CSSR, DCR, HOSR and congestion remain stable. Conversely, a modest change in several KPIs together can indicate emerging stress before any single national average looks severe.

> **Traditional QoS monitoring tells the analyst what has degraded. AI for Resilient Connectivity is designed to indicate what may degrade next.**

The project therefore focuses on seven 2G indicators:

- Cell Availability
- Call Setup Success Rate (CSSR)
- Drop Call Rate (DCR)
- Handover Success Rate (HOSR)
- SDCCH Congestion Rate
- TCH Congestion Rate
- Traffic Volume (2G Erlang)

Traffic is treated as **context/load**, not automatically as deterioration.

---

## Architecture — ITU-T Y.3172

```text
SRC ──→ C ──→ PP ──→ M ──→ P ──→ D ──→ SINK
                    ▲
             Knowledge Base

Supporting functions: MLFO · ML Sandbox
```

| **Node** | **Role in Y.3172** | **Implementation in AI for Resilient Connectivity** |
|---|---|---|
| **SRC** | Source of data | Operator weekly QoS workbooks in local operator folders; Box is the planned source adapter |
| **C** | Collector | File discovery, operator identification, SHA-256 deduplication, immutable raw archive and submission registry |
| **PP** | Preprocessor | Schema/date/cell/KPI validation, missing-value handling, Operator × Day aggregation, feature engineering and data-quality gating |
| **M** | Model | Next-period QoS degradation classifier; Logistic Regression and Random Forest are benchmarked chronologically |
| **P** | Policy | Deterministic probability-to-review rules with explicit human-review guardrails |
| **D** | Distributor | Routes review states to alerts and latest-status datasets |
| **SINK** | Target of ML output | Browser dashboard / analyst interface and API |
| **MLFO** | ML management and orchestration | Versioned model registry, evaluation metadata and explicit active-model switching |
| **ML Sandbox** | Safe train/test environment | Synthetic Operator × Day history, separate Sandbox model registry and scenario validation |

ITU-T Y.3172 defines the ML pipeline nodes SRC, C, PP, M, P, D and SINK, together with ML management/orchestration functions. ITU-T Y.3181 provides the architectural framework for an ML Sandbox in future networks.

### The Policy Node

`P` is deterministic code. It does not retrain or reinterpret the model.

| State | Current Sandbox rule | Meaning |
|---|---|---|
| `NO_DECISION` | prediction unavailable, ineligible input or data-quality `FAIL` | Do not issue a model-based view |
| `MONITOR` | probability < 0.35 | Routine monitoring |
| `WATCH` | 0.35 ≤ probability < 0.55 | Analyst watchlist |
| `REVIEW` | probability ≥ 0.55 and not escalated to `HIGH_REVIEW` | Analyst review recommended |
| `HIGH_REVIEW` | probability ≥ 0.75 **and** ≥2 concurrent deteriorating KPIs | Priority analyst review |

Three design commitments make the use of model output auditable:

1. **No autonomous regulatory action.** The model returns risk; the policy node returns a review state; a human validates the evidence before any action.
2. **Data-quality gating.** Invalid or incomplete inputs can produce `NO_DECISION`; the system does not force a prediction from unusable data.
3. **Sandbox/real separation.** Synthetic data and Sandbox models are stored separately and cannot silently become the active real-data model.

---

## Data Pipeline — From Cell Records to a Prediction

```text
Operator workbook
      │
      ▼
Raw Cell × Day data
      │
      ▼
Validation and cleaning
      │
      ▼
Operator × Day aggregation
      │
      ▼
Feature engineering
      │
      ▼
Next-day target / training table
      │
      ▼
Model probability
      │
      ▼
Policy state + analyst review
```

### PP validation

The preprocessor checks, among other things, mandatory fields, reporting date, technology, duplicate `Date + Cell` keys, missing KPI values, percentage ranges and model eligibility. Missing is never silently converted to zero. Mathematically invalid rate values are excluded from clean analytical calculations but remain preserved in the raw archive.

### Feature engineering

The model does not see only today's KPI levels. PP also creates recent context such as:

- 1-day and 3-day KPI change
- 3-day and 7-day rolling context
- direction-normalised deterioration (`positive = worse`)
- deterioration streaks
- traffic growth
- concurrent deterioration count
- multi-KPI stress flag

Features are calculated using only information available up to that day; future data is not used.

### Target

The current supervised label is deliberately marked **Sandbox proxy**:

`qos_degradation_next_day = 1` when the next consecutive, model-eligible reporting day has `multi_kpi_stress_flag = 1`.

This is a development target, **not an NCC regulatory definition of degradation**. It must be refined against longer historical data and an approved operational definition before real deployment.

---

## Sandbox and Data Protection

The reproducible Sandbox configuration generates **4 synthetic operators × 240 days = 960 Operator-Day rows** using a fixed random seed. It introduces normal variation and deterministic stress periods so the complete pipeline can be demonstrated without exposing confidential operator data.

Real and Sandbox modes are deliberately separated:

- `data/sandbox/` is synthetic only.
- `models/sandbox_registry/` cannot activate the real model.
- real workbooks remain in ignored local folders and immutable raw storage.
- real operator names can be anonymised for public demonstrations.
- the system does not control a live network.

---

## Evaluation — Reproducible Sandbox Baseline

Run:

```powershell
.\run_submission_demo.bat
```

The current deterministic Sandbox baseline (`seed = 42`) produced 932 labelled, feature-ready rows. A chronological 75/25 split trained on 699 rows and tested on 233 rows.

| Model | Precision | Recall | F1 | ROC-AUC | Average Precision |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 0.329 | 0.563 | 0.415 | 0.654 | 0.497 |
| **Random Forest (selected)** | **0.810** | **0.354** | **0.493** | **0.750** | **0.608** |

These are **synthetic Sandbox results only**. They demonstrate the end-to-end ML lifecycle; they do not establish operational performance on Nigerian networks.

The same run produced the following policy states across 960 Sandbox rows:

| Policy state | Count |
|---|---:|
| MONITOR | 642 |
| WATCH | 58 |
| REVIEW | 131 |
| HIGH_REVIEW | 105 |
| NO_DECISION | 24 |

### Representative reproducible cases

| Scenario | Example outcome |
|---|---|
| High traffic but resilient | +5.29% daily traffic growth, only 1 deteriorating KPI, risk 0.181 → `MONITOR` |
| Coordinated multi-KPI stress | 6 deteriorating KPIs, risk 0.982 → `HIGH_REVIEW` |
| Recovery | After a prior high-review episode, concurrent deterioration returned to 0 and risk fell to 0.111 → `MONITOR` |
| Insufficient feature history | First days do not yet have 7-day history → `NO_DECISION` rather than a forced prediction |

The key operational metrics for future real-data validation are **precision, recall, F1, false-alarm rate, missed-event rate and early-warning lead time**.

---

## Knowledge Base

The Knowledge Base is a separate source-grounded RAG service. It indexes project documentation and authorised local references in:

```text
knowledge_base/source/
├── 01_STANDARDS/
├── 02_NCC_QOS/
├── 03_AI_GOVERNANCE/
└── 04_PROJECT_LOCAL/
```

It supports Markdown, TXT, DOCX and text-searchable PDF. Local Ollama models provide semantic retrieval and grounded answer generation; the dashboard shows the concise answer, while raw source evidence remains available through the API for audit/debugging.

The Knowledge Base may explain questions such as:

- What is the role of the PP node under Y.3172?
- Why is traffic growth not automatically degradation?
- What are the NAIS strategic pillars?
- Why is human review required before operational or regulatory action?

**It cannot change the prediction and it cannot create a regulatory requirement.**

---

## Nigeria NAIS and ITU AI Readiness Alignment

The project most directly supports three pillars of Nigeria's National Artificial Intelligence Strategy (NAIS):

| NAIS pillar | Evidence in the project |
|---|---|
| **Pillar 3 — Accelerating AI Adoption and Sector Transformation** | Applies AI to telecommunications QoS/resilience decision support |
| **Pillar 4 — Ensuring Responsible and Ethical AI Development and Deployment** | Human oversight, explainability, data-quality gates and explicit limitations |
| **Pillar 5 — Developing a Robust AI Governance Framework** | Model registry, audit metadata, policy separation and controlled model activation |

It also demonstrates several ITU AI Readiness factors: usable data, standards alignment, open/reproducible code, deployment capability, and Sandbox-based model validation.

---

## Operational Gaps the Prototype Makes Explicit

The prototype intentionally exposes what must be resolved before real operational use:

| Gap | Required next step |
|---|---|
| Sandbox proxy target is not a formal regulatory definition | Agree and document an operational degradation label using historical evidence and regulatory expertise |
| Cell-level rate KPIs are submitted as percentages | Where possible, obtain numerator/denominator counters for mathematically correct network aggregation |
| Limited real historical labelled data | Ingest several months of consecutive operator submissions and quantify class/event balance |
| Local directory is the active SRC | Connect the existing Box adapter when Box credentials/folder structure are approved |
| Sandbox metrics are not real-network evidence | Re-evaluate chronologically on representative historical data before any operational claim |

---

## Reproduce the System

### Windows setup

```powershell
.\setup_windows.bat
```

### Run Sandbox and generate submission results

```powershell
.\run_submission_demo.bat
```

### Launch dashboard

```powershell
.\run_dashboard.bat
```

Open:

```text
http://127.0.0.1:8000/dashboard?mode=sandbox
```

### Real local submissions

Place weekly workbooks under:

```text
data/inbox/Operator_A/
data/inbox/Operator_B/
data/inbox/Operator_C/
data/inbox/Operator_D/
```

Then run:

```powershell
.\run_real_pipeline.bat
```

Training is deliberately blocked if there is insufficient labelled, feature-ready real history.

---

## Primary References

| Document | Authority | Link / location |
|---|---|---|
| ITU-T Y.3172 — Architectural framework for machine learning in future networks including IMT-2020 | ITU-T | https://www.itu.int/rec/T-REC-Y.3172/en |
| ITU-T Y.3181 — Architectural framework for machine learning sandbox in future networks including IMT-2020 | ITU-T | https://www.itu.int/rec/T-REC-Y.3181/en |
| ITU AI for Good Sandbox | ITU | https://aiforgood.itu.int/ai-for-good-sandbox/ |
| National Artificial Intelligence Strategy | Federal Republic of Nigeria / NCAIR-NITDA | https://ncair.nitda.gov.ng/wp-content/uploads/2025/09/National-Artificial-Intelligence-Strategy-19092025.pdf |
| NCC QoS regulatory/business-rule material | NCC | Authorised local Knowledge Base copy / official NCC publication as applicable |
| Project Requirements v2.1 | Project | `docs/AI_Resilient_Connectivity_Y3172_NAIS_Use_Case_Requirements_v2_1.docx` |

---

## Licence and Data Notice

Code licence: `<select before public release>`.

No API keys, operator workbooks or restricted local Knowledge Base documents should be committed. Synthetic Sandbox data is generated locally and clearly separated from real regulatory data.
