from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT=Path(__file__).resolve().parent

def extract_text(path: Path) -> str:
    ext=path.suffix.lower()
    if ext in {".md",".txt"}: return path.read_text(encoding="utf-8",errors="ignore")
    if ext==".docx":
        from docx import Document
        return "\n".join(p.text for p in Document(path).paragraphs)
    if ext==".pdf":
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
    return ""

def chunks(text: str, words=180, overlap=30):
    toks=re.findall(r"\S+",text); step=max(1,words-overlap)
    for i in range(0,len(toks),step):
        part=toks[i:i+words]
        if len(part)>=20: yield " ".join(part)
        if i+words>=len(toks): break

class KnowledgeBase:
    """Local retrieval service for authoritative project/standards documents.

    Retrieval only: this module does not invent or autonomously enforce policy.
    """
    def __init__(self,config_path="config/knowledge_config.json"):
        p=Path(config_path); p=p if p.is_absolute() else ROOT/p; self.cfg=json.loads(p.read_text())
        self.source=ROOT/self.cfg["source_dir"]
        self.records=[]; self.vectorizer=None; self.matrix=None

    def build(self):
        allowed=set(self.cfg["supported_extensions"]); records=[]
        for p in sorted(self.source.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in allowed: continue
            text=extract_text(p)
            for n,ch in enumerate(chunks(text,int(self.cfg["chunk_words"]),int(self.cfg["overlap_words"]))):
                records.append({"source":str(p.relative_to(ROOT)),"chunk":n,"text":ch})
        self.records=records
        if records:
            self.vectorizer=TfidfVectorizer(stop_words="english",ngram_range=(1,2),max_features=20000)
            self.matrix=self.vectorizer.fit_transform([r["text"] for r in records])
        return len(records)

    def query(self,q: str,top_k: int|None=None):
        if self.matrix is None: self.build()
        if not self.records: return []
        vec=self.vectorizer.transform([q]); sims=cosine_similarity(vec,self.matrix)[0]
        k=int(top_k or self.cfg.get("top_k",5)); idx=np.argsort(sims)[::-1][:k]
        return [{**self.records[int(i)],"score":round(float(sims[int(i)]),4)} for i in idx if sims[int(i)]>0]

def main():
    ap=argparse.ArgumentParser(description="Query the local project knowledge base")
    ap.add_argument("query"); ap.add_argument("--top-k",type=int,default=5)
    a=ap.parse_args(); kb=KnowledgeBase(); print(json.dumps(kb.query(a.query,a.top_k),indent=2))

if __name__=="__main__": main()
