# Knowledge Base v1.3 — Local Grounded RAG

The Knowledge Base has two modes:

1. **Local grounded RAG (recommended):** uses Ollama locally for semantic embeddings and source-grounded answer generation.
2. **Extractive fallback:** used automatically when Ollama is not running. This is useful for availability, but it is less capable for complex questions.

## Windows setup

Install Ollama for Windows, then from the project folder run:

```powershell
.\setup_knowledge_rag.bat
```

This pulls:

- `embeddinggemma` for semantic retrieval.
- `qwen3:4b` for grounded local answer generation.

Restart the dashboard:

```powershell
.\run_dashboard.bat
```

Check:

```text
http://127.0.0.1:8000/knowledge/stats
```

`answering` should report `Local grounded RAG` and `retrieval` should report `Hybrid semantic + TF-IDF`.

## Accuracy safeguards

- Answers are instructed to use only retrieved evidence.
- Evidence is cited as `[S1]`, `[S2]`, etc.
- The UI shows the exact source file and PDF page where available.
- If evidence is insufficient, the assistant should say so instead of guessing.
- Deterministic acronym expansion is used only when the corpus supports the term.
- External standards/NCC/AI-governance documents remain local and are not required to be committed to Git.

## Recommended validation questions

Build a small "golden question" set for every core document. For example:

- What is the full meaning of NAIS?
- What are the pillars of the National AI Strategy?
- What role does the ML Sandbox play in Y.3172?
- What is MLFO responsible for?
- What KPIs are used in the current 2G project scope?
- Why is traffic growth not automatically degradation?
- What does the project require before regulatory action?

For every question, record the expected answer and authoritative source. Use this set after every KB change to detect regressions.
