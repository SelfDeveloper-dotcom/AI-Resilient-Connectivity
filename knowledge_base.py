from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent


def _clean_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"[\t\r]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()


def _flatten(text: str) -> str:
    return re.sub(r"\s+", " ", _clean_text(text)).strip()


def extract_units(path: Path) -> list[dict[str, Any]]:
    """Extract logical document units while retaining PDF page numbers."""
    ext = path.suffix.lower()
    if ext in {".md", ".txt"}:
        text = _flatten(path.read_text(encoding="utf-8", errors="ignore"))
        return [{"text": text, "page": None}] if text else []
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
        text = _flatten("\n".join(parts))
        return [{"text": text, "page": None}] if text else []
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        out = []
        for page_no, page in enumerate(reader.pages, start=1):
            text = _flatten(page.extract_text() or "")
            if text:
                out.append({"text": text, "page": page_no})
        return out
    return []


def chunks(text: str, words: int = 130, overlap: int = 25) -> Iterable[str]:
    toks = re.findall(r"\S+", text)
    step = max(1, words - overlap)
    for i in range(0, len(toks), step):
        part = toks[i:i + words]
        if len(part) >= 18:
            yield " ".join(part)
        if i + words >= len(toks):
            break


def _tokens(text: str) -> set[str]:
    return {x.lower() for x in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]*", text) if len(x) > 1}


def _sentences(text: str) -> list[str]:
    bits = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [b.strip() for b in bits if 20 <= len(b.strip()) <= 700]


def _cos(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if a.ndim == 1:
        a = a.reshape(1, -1)
    an = np.linalg.norm(a, axis=1, keepdims=True)
    bn = np.linalg.norm(b, axis=1, keepdims=True)
    an[an == 0] = 1
    bn[bn == 0] = 1
    return (a / an) @ (b / bn).T


class OllamaClient:
    def __init__(self, base_url: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def embed(self, model: str, inputs: list[str]) -> np.ndarray:
        result = self._post("/api/embed", {"model": model, "input": inputs})
        vals = result.get("embeddings") or []
        if len(vals) != len(inputs):
            raise RuntimeError("Ollama returned an unexpected number of embeddings")
        return np.asarray(vals, dtype=np.float32)

    def generate(self, model: str, system: str, prompt: str, temperature: float = 0.1) -> str:
        result = self._post(
            "/api/generate",
            {
                "model": model,
                "system": system,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"temperature": temperature},
            },
        )
        return str(result.get("response") or "").strip()


def _clean_generated_answer(text: str) -> str:
    """Remove model reasoning/citation markup from the user-facing answer."""
    text = text or ""
    # Qwen-family models may occasionally emit a visible thinking block even
    # when thinking is disabled. Never expose that internal scratch text.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    if "</think>" in text.lower():
        # Defensive handling for a truncated/malformed opening tag.
        text = re.split(r"</think>", text, flags=re.IGNORECASE)[-1]
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
    # Evidence IDs remain available in the API payload, but the analyst-facing
    # prose should read naturally without opaque [S1]/[S2] markers.
    text = re.sub(r"\s*\[S\d+\]", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class KnowledgeBase:
    """Local, source-grounded knowledge service with hybrid semantic RAG.

    Retrieval uses lexical search at all times. When Ollama is available, local
    semantic embeddings are blended with lexical relevance. Answer generation
    is local and constrained to retrieved evidence. If Ollama is unavailable,
    a deterministic extractive fallback remains available.
    """

    def __init__(self, config_path: str | Path = "config/knowledge_config.json"):
        p = Path(config_path)
        p = p if p.is_absolute() else ROOT / p
        self.cfg = json.loads(p.read_text(encoding="utf-8"))
        configured = self.cfg.get("source_dirs")
        self.sources = [Path(x) if Path(x).is_absolute() else ROOT / x for x in configured] if configured else [ROOT / "knowledge_base/source"]
        self.records: list[dict[str, Any]] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self._documents: list[dict[str, Any]] = []
        self.aliases = {str(k).upper(): str(v) for k, v in self.cfg.get("query_aliases", {}).items()}
        self.rag_cfg = self.cfg.get("rag", {})
        self.ollama = OllamaClient(
            self.rag_cfg.get("ollama_url", "http://127.0.0.1:11434"),
            int(self.rag_cfg.get("request_timeout_seconds", 120)),
        )
        self.semantic_matrix: np.ndarray | None = None
        self.semantic_ready = False
        self.semantic_error: str | None = None

    def _metadata(self, path: Path, source_root: Path) -> dict[str, str]:
        try:
            source_label = str(path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            source_label = str(path).replace("\\", "/")
        rel_source = path.relative_to(source_root)
        if source_root == ROOT / "docs":
            category = "PROJECT_DOCS"
        elif len(rel_source.parts) > 1:
            category = rel_source.parts[0]
        else:
            category = "LOCAL_REFERENCE"
        return {
            "source": source_label,
            "title": path.stem.replace("_", " ").replace("-", " "),
            "category": category,
        }

    def _fingerprint(self) -> str:
        h = hashlib.sha256()
        h.update(str(self.rag_cfg.get("embedding_model", "embeddinggemma")).encode())
        for r in self.records:
            h.update(r["source"].encode("utf-8", errors="ignore"))
            h.update(str(r.get("page")).encode())
            h.update(r["text"].encode("utf-8", errors="ignore"))
        return h.hexdigest()[:24]

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
                try:
                    rel_repo_key = str(p.relative_to(ROOT)).replace("\\", "/")
                except ValueError:
                    rel_repo_key = str(p).replace("\\", "/")
                if rel_repo_key in excluded:
                    continue
                resolved = p.resolve()
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                meta = self._metadata(p, source_root)
                units = extract_units(p)
                chunk_count = 0
                chars = 0
                for unit in units:
                    chars += len(unit["text"])
                    for ch in chunks(unit["text"], int(self.cfg.get("chunk_words", 130)), int(self.cfg.get("overlap_words", 25))):
                        records.append({**meta, "chunk": chunk_count, "page": unit.get("page"), "text": ch})
                        chunk_count += 1
                if chunk_count:
                    documents.append({**meta, "chunks": chunk_count, "characters": chars})

        self.records = records
        self._documents = documents
        if records:
            self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=int(self.cfg.get("max_features", 40000)), sublinear_tf=True)
            corpus = [f"{r['title']} {r['category']} {r['text']}" for r in records]
            self.matrix = self.vectorizer.fit_transform(corpus)
        else:
            self.vectorizer = None
            self.matrix = None
        self.semantic_matrix = None
        self.semantic_ready = False
        self.semantic_error = None
        return len(records)

    def _ensure_semantic(self) -> bool:
        if not self.rag_cfg.get("enabled", True):
            return False
        if self.semantic_ready and self.semantic_matrix is not None:
            return True
        if self.matrix is None:
            self.build()
        if not self.records:
            return False
        if not self.ollama.available():
            self.semantic_error = "Ollama is not running. Semantic retrieval is unavailable."
            return False
        cache_dir = ROOT / "knowledge_base/cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        fp = self._fingerprint()
        cache_file = cache_dir / f"embeddings_{fp}.npz"
        if cache_file.exists():
            try:
                self.semantic_matrix = np.load(cache_file)["embeddings"]
                if len(self.semantic_matrix) == len(self.records):
                    self.semantic_ready = True
                    return True
            except Exception:
                pass
        model = self.rag_cfg.get("embedding_model", "embeddinggemma")
        texts = [f"{r['title']}. {r['text']}" for r in self.records]
        batch = int(self.rag_cfg.get("embedding_batch_size", 24))
        pieces = []
        try:
            for i in range(0, len(texts), batch):
                pieces.append(self.ollama.embed(model, texts[i:i + batch]))
            self.semantic_matrix = np.vstack(pieces) if pieces else np.empty((0, 0), dtype=np.float32)
            np.savez_compressed(cache_file, embeddings=self.semantic_matrix)
            self.semantic_ready = True
            self.semantic_error = None
            return True
        except Exception as exc:
            self.semantic_error = f"Semantic embedding unavailable: {exc}"
            self.semantic_matrix = None
            return False

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
        ollama_running = self.ollama.available() if self.rag_cfg.get("enabled", True) else False
        return {
            "documents": len(self._documents),
            "chunks": len(self.records),
            "categories": categories,
            "sources": [str(p.relative_to(ROOT)).replace("\\", "/") if p.is_relative_to(ROOT) else str(p).replace("\\", "/") for p in self.sources if p.exists()],
            "retrieval": "Hybrid semantic + TF-IDF" if ollama_running else "TF-IDF fallback",
            "answering": "Local grounded RAG" if ollama_running else "Controlled extractive fallback",
            "ollama_running": ollama_running,
            "embedding_model": self.rag_cfg.get("embedding_model"),
            "generation_model": self.rag_cfg.get("generation_model"),
            "semantic_error": self.semantic_error,
        }

    def _expand_query(self, q: str) -> tuple[str, list[str]]:
        tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9-]{1,12}\b", q)
        expansions: list[str] = []
        for tok in tokens:
            alias = self.aliases.get(tok.upper())
            if alias and alias.lower() not in q.lower():
                expansions.append(alias)
        return q + (" " + " ".join(expansions) if expansions else ""), expansions

    def _intent_category_boost(self, q: str, category: str) -> float:
        ql = q.lower()
        boost = 0.0
        if any(x in ql for x in ["y.3172", "y3172", "y.3181", "y3181", "itu", "standard", "recommendation"]):
            if category == "01_STANDARDS": boost += 0.16
        if any(x in ql for x in ["nais", "national artificial intelligence strategy", "ai strategy", "ai governance"]):
            if category == "03_AI_GOVERNANCE": boost += 0.18
        if any(x in ql for x in ["ncc", "qos", "business rules", "cssr", "dcr", "hosr", "sdcch", "tch", "availability"]):
            if category == "02_NCC_QOS": boost += 0.14
        if any(x in ql for x in ["project", "target", "feature engineering", "pipeline", "collector", "preprocessor"]):
            if category in {"PROJECT_DOCS", "04_PROJECT_LOCAL"}: boost += 0.10
        return boost

    def query(self, q: str, top_k: int | None = None) -> list[dict[str, Any]]:
        q = (q or "").strip()
        if not q:
            return []
        if self.matrix is None:
            self.build()
        if not self.records or self.vectorizer is None or self.matrix is None:
            return []
        expanded_q, expansions = self._expand_query(q)
        vec = self.vectorizer.transform([expanded_q])
        lex_cos = cosine_similarity(vec, self.matrix)[0]
        semantic_scores = np.zeros(len(self.records), dtype=np.float32)
        semantic_on = self._ensure_semantic()
        if semantic_on and self.semantic_matrix is not None:
            try:
                qemb = self.ollama.embed(self.rag_cfg.get("embedding_model", "embeddinggemma"), [expanded_q])[0]
                semantic_scores = _cos(np.asarray(qemb, dtype=np.float32), self.semantic_matrix)[0]
                semantic_scores = np.clip((semantic_scores + 1.0) / 2.0, 0.0, 1.0)
            except Exception as exc:
                self.semantic_error = f"Query embedding failed: {exc}"
                semantic_on = False

        q_tokens = _tokens(expanded_q)
        category_boosts = self.cfg.get("category_boosts", {})
        sw = float(self.rag_cfg.get("semantic_weight", 0.58)) if semantic_on else 0.0
        lw = float(self.rag_cfg.get("lexical_weight", 0.32)) if semantic_on else 0.75
        bw = float(self.rag_cfg.get("boost_weight", 0.10)) if semantic_on else 0.25
        scores = []
        for i, r in enumerate(self.records):
            hay = f"{r['title']} {r['text']}"
            hay_low = hay.lower()
            hay_tokens = _tokens(hay)
            overlap = len(q_tokens & hay_tokens) / max(1, len(q_tokens))
            boost = float(category_boosts.get(r["category"], 0.0)) + self._intent_category_boost(expanded_q, r["category"])
            for acronym, expansion in self.aliases.items():
                if re.search(rf"\b{re.escape(acronym)}\b", q, flags=re.IGNORECASE):
                    if re.search(rf"\b{re.escape(acronym)}\b", hay, flags=re.IGNORECASE) or expansion.lower() in hay_low:
                        boost += 0.22
            for expansion in expansions:
                if expansion.lower() in hay_low:
                    boost += 0.16
            title_tokens = _tokens(r["title"])
            if q_tokens & title_tokens:
                boost += min(0.12, 0.03 * len(q_tokens & title_tokens))
            lexical = (0.72 * float(lex_cos[i])) + (0.28 * overlap)
            score = (sw * float(semantic_scores[i])) + (lw * lexical) + (bw * min(boost, 1.0))
            scores.append(score)

        k = int(top_k or self.cfg.get("top_k", 6))
        idx = np.argsort(np.asarray(scores))[::-1][:max(k * 4, k)]
        min_score = float(self.cfg.get("min_score", 0.02))
        out = []
        per_source: dict[str, int] = {}
        for i in idx:
            score = float(scores[int(i)])
            if score <= min_score:
                continue
            r = self.records[int(i)]
            # Diversity: no more than 2 chunks per document in the initial result set.
            if per_source.get(r["source"], 0) >= 2:
                continue
            per_source[r["source"]] = per_source.get(r["source"], 0) + 1
            out.append({**r, "score": round(score, 4), "retrieval_mode": "hybrid" if semantic_on else "lexical"})
            if len(out) >= k:
                break
        return out

    def _direct_alias_answer(self, q: str, evidence: list[dict[str, Any]]) -> str | None:
        pats = [
            r"(?:what\s+is\s+)?the\s+full\s+meaning\s+of\s+([A-Za-z][A-Za-z0-9-]{1,12})\b",
            r"(?:what\s+does\s+)?([A-Za-z][A-Za-z0-9-]{1,12})\s+(?:stand|stands)\s+for\b",
            r"(?:meaning\s+of|define)\s+([A-Za-z][A-Za-z0-9-]{1,12})\b",
        ]
        acronym = None
        for pat in pats:
            m = re.search(pat, q, flags=re.IGNORECASE)
            if m:
                acronym = m.group(1).upper(); break
        if not acronym:
            m = re.search(r"^\s*what\s+is\s+([A-Za-z][A-Za-z0-9-]{1,12})\s*[?!.]*\s*$", q, flags=re.IGNORECASE)
            if m: acronym = m.group(1).upper()
        if not acronym or acronym not in self.aliases:
            return None
        expansion = self.aliases[acronym]
        supported = any(re.search(rf"\b{re.escape(acronym)}\b", e["text"], re.I) or expansion.lower() in e["text"].lower() or expansion.lower() in e["title"].lower() for e in evidence)
        return f"{acronym} means {expansion}." if supported else None

    def _extractive_answer(self, q: str, evidence: list[dict[str, Any]]) -> str:
        direct = self._direct_alias_answer(q, evidence)
        if direct:
            return direct
        expanded, _ = self._expand_query(q)
        qtok = _tokens(expanded)
        candidates = []
        for rank, item in enumerate(evidence):
            for sent in _sentences(item["text"]):
                stok = _tokens(sent)
                overlap = len(qtok & stok) / max(1, len(qtok))
                if overlap <= 0: continue
                score = overlap + item["score"] * 0.5 + 0.08 / (rank + 1)
                candidates.append((score, sent))
        candidates.sort(reverse=True, key=lambda x: x[0])
        selected = []
        for _, sent in candidates:
            if sent.lower() not in {x.lower() for x in selected}:
                selected.append(sent)
            if len(selected) >= int(self.cfg.get("answer_sentences", 2)):
                break
        return " ".join(selected) if selected else "The indexed sources may contain related material, but I do not have enough clear evidence to answer this question reliably."

    def _rag_answer(self, q: str, evidence: list[dict[str, Any]]) -> str:
        max_chars = int(self.rag_cfg.get("max_context_chars", 12000))
        blocks = []
        used = 0
        for n, e in enumerate(evidence, 1):
            loc = f", page {e['page']}" if e.get("page") else ""
            block = f"[S{n}] {e['title']} ({e['category']}{loc})\n{e['text']}"
            if used + len(block) > max_chars:
                break
            blocks.append(block); used += len(block)
        context = "\n\n".join(blocks)
        system = (
            "You are the grounded knowledge assistant for the AI Resilient Connectivity project. "
            "Answer ONLY from the supplied evidence. Do not use outside facts or guess. "
            "If the evidence is insufficient or conflicting, say so plainly. "
            "Return ONLY the final answer: never reveal analysis, chain-of-thought, planning, or <think> content. "
            "Write for a professional telecom/regulatory analyst. Keep the answer concise and easy to scan. "
            "Use one or two short paragraphs for explanatory answers. When the question asks for multiple items, "
            "put each item on its own numbered line. Do not include source IDs such as [S1] or [S2] in the final answer. "
            "For acronym questions, give the exact expansion first if supported."
        )
        prompt = (
            f"Question: {q}\n\nEvidence:\n{context}\n\n"
            "Provide the final user-facing answer only. Do not describe your reasoning process."
        )
        raw = self.ollama.generate(
            self.rag_cfg.get("generation_model", "qwen3:4b"), system, prompt,
            float(self.rag_cfg.get("temperature", 0.1)),
        )
        return _clean_generated_answer(raw)

    def answer(self, q: str, top_k: int | None = None) -> dict[str, Any]:
        q = (q or "").strip()
        evidence = self.query(q, top_k=top_k or int(self.cfg.get("answer_top_k", 5)))
        if not evidence:
            return {"question": q, "answer": "I could not find sufficiently relevant evidence in the indexed knowledge base.", "confidence": "LOW", "answer_mode": "no_evidence", "evidence": []}

        direct = self._direct_alias_answer(q, evidence)
        # Deterministic supported acronym answers are more reliable than invoking a generator.
        if direct:
            return {"question": q, "answer": direct, "confidence": "HIGH", "answer_mode": "controlled", "evidence": evidence[:3]}

        if self._ensure_semantic() and self.ollama.available():
            try:
                ans = self._rag_answer(q, evidence)
                if ans:
                    confidence = "HIGH" if evidence[0]["score"] >= 0.24 else "MEDIUM"
                    return {"question": q, "answer": ans, "confidence": confidence, "answer_mode": "local_rag", "evidence": evidence[:int(self.cfg.get("answer_evidence", 4))]}
            except Exception as exc:
                self.semantic_error = f"Local RAG generation unavailable: {exc}"

        ans = self._extractive_answer(q, evidence)
        conf = "MEDIUM" if evidence[0]["score"] >= float(self.cfg.get("medium_confidence_score", 0.18)) else "LOW"
        return {"question": q, "answer": ans, "confidence": conf, "answer_mode": "extractive_fallback", "evidence": evidence[:int(self.cfg.get("answer_evidence", 4))]}


def main() -> None:
    ap = argparse.ArgumentParser(description="Query the local project knowledge base")
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--answer", action="store_true")
    a = ap.parse_args()
    kb = KnowledgeBase()
    if a.stats: print(json.dumps(kb.stats(), indent=2))
    elif a.answer: print(json.dumps(kb.answer(a.query, a.top_k), indent=2))
    else: print(json.dumps(kb.query(a.query, a.top_k), indent=2))


if __name__ == "__main__":
    main()
