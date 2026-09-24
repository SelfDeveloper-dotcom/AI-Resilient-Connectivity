from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent


def extract_text(path: Path) -> str:
    """Extract searchable text from a supported local document.

    DOCX extraction includes both paragraphs and table cells. PDF extraction
    relies on embedded text; scanned/image-only PDFs should be converted to a
    text-searchable PDF before they are added to the knowledge corpus.
    """
    ext = path.suffix.lower()
    if ext in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if ext == ".docx":
        from docx import Document

        doc = Document(path)
        parts: list[str] = []
        parts.extend(p.text.strip() for p in doc.paragraphs if p.text.strip())
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        return "\n".join(parts)
    if ext == ".pdf":
        from pypdf import PdfReader

        return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
    return ""


def chunks(text: str, words: int = 180, overlap: int = 30) -> Iterable[str]:
    toks = re.findall(r"\S+", text)
    step = max(1, words - overlap)
    for i in range(0, len(toks), step):
        part = toks[i : i + words]
        if len(part) >= 20:
            yield " ".join(part)
        if i + words >= len(toks):
            break


class KnowledgeBase:
    """Local retrieval service for authoritative project/standards documents.

    Retrieval only: this module does not invent policy, change a model output,
    or autonomously enforce a regulatory decision. It returns source-grounded
    evidence for analyst review.
    """

    def __init__(self, config_path: str | Path = "config/knowledge_config.json"):
        p = Path(config_path)
        p = p if p.is_absolute() else ROOT / p
        self.cfg = json.loads(p.read_text(encoding="utf-8"))
        configured = self.cfg.get("source_dirs")
        if configured:
            self.sources = [ROOT / x for x in configured]
        else:
            self.sources = [ROOT / self.cfg.get("source_dir", "knowledge_base/source")]
        self.records: list[dict[str, Any]] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self._documents: list[dict[str, Any]] = []

    def _metadata(self, path: Path, source_root: Path) -> dict[str, str]:
        rel_repo = path.relative_to(ROOT)
        rel_source = path.relative_to(source_root)
        if source_root == ROOT / "docs":
            category = "PROJECT_DOCS"
        elif len(rel_source.parts) > 1:
            category = rel_source.parts[0]
        else:
            category = "LOCAL_REFERENCE"
        return {
            "source": str(rel_repo).replace("\\", "/"),
            "title": path.stem.replace("_", " "),
            "category": category,
        }

    def build(self) -> int:
        allowed = set(self.cfg["supported_extensions"])
        excluded = {x.replace("\\", "/") for x in self.cfg.get("excluded_files", [])}
        records: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []
        seen_paths: set[Path] = set()

        for source_root in self.sources:
            if not source_root.exists():
                continue
            for p in sorted(source_root.rglob("*")):
                if not p.is_file() or p.suffix.lower() not in allowed:
                    continue
                rel_repo_key = str(p.relative_to(ROOT)).replace("\\", "/")
                if rel_repo_key in excluded:
                    continue
                resolved = p.resolve()
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                text = extract_text(p).strip()
                if not text:
                    continue
                meta = self._metadata(p, source_root)
                doc_chunks = list(
                    chunks(
                        text,
                        int(self.cfg.get("chunk_words", 180)),
                        int(self.cfg.get("overlap_words", 30)),
                    )
                )
                if not doc_chunks:
                    continue
                documents.append({**meta, "chunks": len(doc_chunks), "characters": len(text)})
                for n, ch in enumerate(doc_chunks):
                    records.append({**meta, "chunk": n, "text": ch})

        self.records = records
        self._documents = documents
        if records:
            self.vectorizer = TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
                max_features=int(self.cfg.get("max_features", 30000)),
                sublinear_tf=True,
            )
            self.matrix = self.vectorizer.fit_transform([r["text"] for r in records])
        else:
            self.vectorizer = None
            self.matrix = None
        return len(records)

    def documents(self) -> list[dict[str, Any]]:
        if self.matrix is None:
            self.build()
        return [dict(d) for d in self._documents]

    def stats(self) -> dict[str, Any]:
        if self.matrix is None:
            self.build()
        categories: dict[str, int] = {}
        for d in self._documents:
            categories[d["category"]] = categories.get(d["category"], 0) + 1
        return {
            "documents": len(self._documents),
            "chunks": len(self.records),
            "categories": categories,
            "sources": [str(p.relative_to(ROOT)).replace("\\", "/") for p in self.sources if p.exists()],
            "retrieval": "TF-IDF cosine similarity",
            "generative_answering": False,
        }

    def query(self, q: str, top_k: int | None = None) -> list[dict[str, Any]]:
        q = (q or "").strip()
        if not q:
            return []
        if self.matrix is None:
            self.build()
        if not self.records or self.vectorizer is None or self.matrix is None:
            return []
        vec = self.vectorizer.transform([q])
        sims = cosine_similarity(vec, self.matrix)[0]
        k = int(top_k or self.cfg.get("top_k", 5))
        idx = np.argsort(sims)[::-1][:k]
        min_score = float(self.cfg.get("min_score", 0.0))
        return [
            {**self.records[int(i)], "score": round(float(sims[int(i)]), 4)}
            for i in idx
            if sims[int(i)] > min_score
        ]


def main() -> None:
    ap = argparse.ArgumentParser(description="Query the local project knowledge base")
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    kb = KnowledgeBase()
    if a.stats:
        print(json.dumps(kb.stats(), indent=2))
    else:
        print(json.dumps(kb.query(a.query, a.top_k), indent=2))


if __name__ == "__main__":
    main()
