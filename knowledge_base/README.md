# Knowledge Base Corpus

The Knowledge Base is a **local, source-grounded retrieval service**. It is intentionally separate from the prediction model and the policy engine.

## Automatically indexed

- `docs/` — project requirements, architecture, feature/target dictionaries, validation matrix, model governance and deployment notes.
- `knowledge_base/source/` — additional authoritative local references supplied by the project team.

## Recommended local corpus structure

- `01_STANDARDS/` — authorised copies or extracts of ITU-T Y.3172, Y.3181 and other relevant standards.
- `02_NCC_QOS/` — applicable QoS Regulations, Business Rules, KPI definitions and approved methodologies.
- `03_AI_GOVERNANCE/` — Nigeria National AI Strategy and other approved responsible-AI/governance references.
- `04_PROJECT_LOCAL/` — additional project-specific notes that are not already under `docs/`.

Do **not** commit confidential, restricted or copyrighted source documents to a public repository unless you have permission. Local files can remain untracked while still being indexed by the application.

## Supported formats

Markdown, TXT, DOCX and text-searchable PDF. Image-only/scanned PDFs should be converted to text-searchable PDFs first.

## Test from the command line

```powershell
python knowledge_base.py --stats
python knowledge_base.py "What are the seven 2G KPIs?"
python knowledge_base.py "Why is human review required?"
```

The current implementation performs retrieval only; it returns relevant evidence and source paths. A later RAG layer may generate natural-language answers from those retrieved sources, but it must remain grounded in the retrieved evidence and must not alter model predictions or autonomously enforce policy.
