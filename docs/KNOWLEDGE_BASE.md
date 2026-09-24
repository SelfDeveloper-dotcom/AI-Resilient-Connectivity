# Knowledge Base Design and Validation

## Purpose

The Knowledge Base provides source-grounded evidence to analysts using the AI Resilient Connectivity prototype. It is deliberately separated from the ML prediction model and the policy engine.

The service **retrieves evidence**; it does not change a prediction, infer a regulatory breach by itself, or automatically trigger enforcement.

## Indexed corpus

The application automatically indexes:

1. `docs/` — project-owned requirements, architecture, validation, feature/target dictionaries, model governance and deployment documentation.
2. `knowledge_base/source/` — authorised local source documents added by the project team.

Recommended local folders:

- `01_STANDARDS` — ITU-T Y.3172, Y.3181 and related authorised standards material.
- `02_NCC_QOS` — applicable NCC QoS rules, Business Rules, KPI definitions and approved methodology notes.
- `03_AI_GOVERNANCE` — Nigeria National AI Strategy and approved responsible-AI/governance references.
- `04_PROJECT_LOCAL` — local project notes not already in `docs/`.

## Supported formats

- Markdown (`.md`)
- Text (`.txt`)
- Microsoft Word (`.docx`), including paragraph and table text
- Text-searchable PDF (`.pdf`)

Scanned/image-only PDFs should be converted to searchable text before ingestion.

## Retrieval method

The v1.1 knowledge service uses TF-IDF with unigram/bigram features and cosine similarity. Results contain:

- document title
- source path
- category
- chunk number
- relevance score
- retrieved evidence text

This is intentionally transparent and deterministic for the Sandbox baseline.

## User interfaces

Command line:

```powershell
python knowledge_base.py --stats
python knowledge_base.py "Why is human review required?"
```

API:

```text
GET /knowledge?q=Why%20is%20human%20review%20required?
GET /knowledge/stats
GET /knowledge/sources
```

Dashboard:

Open `/dashboard?mode=real` or `/dashboard?mode=sandbox` and use the **Knowledge Base Search** panel.

## Validation questions

Use at least these questions during the Sandbox demonstration:

1. What KPIs are used in the current 2G scope?
2. Why is human review required before operational or regulatory action?
3. What is the role of PP in the Y.3172-aligned pipeline?
4. How is `qos_degradation_next_day` currently defined?
5. Why is traffic growth not automatically classified as degradation?
6. What happens when KPI data is missing or mathematically invalid?
7. What is the difference between the Sandbox model registry and the real-data model registry?

For external standards/regulatory questions, the corresponding authorised source document must first be placed in the relevant local corpus folder.

## Future RAG layer

A later version may add an LLM to synthesize a natural-language answer from retrieved evidence. Any such layer should:

- cite/identify the retrieved source documents;
- abstain when evidence is insufficient;
- remain separate from the ML prediction and policy decision;
- never create or modify regulatory requirements not supported by authoritative sources.

## Source governance

`GET /knowledge/sources` lists the documents currently indexed by the running application. `knowledge_base/SOURCE_INVENTORY_TEMPLATE.csv` can be used to maintain the project team's approval/access inventory.

The `.gitignore` excludes files placed under `01_STANDARDS`, `02_NCC_QOS`, and `03_AI_GOVERNANCE` by default while retaining the folder placeholders. This allows authorised local references to be used without automatically publishing them to GitHub.
