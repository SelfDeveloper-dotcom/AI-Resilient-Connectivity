from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from knowledge_base import KnowledgeBase

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="AI Resilient Connectivity", version="1.1.0")
kb = KnowledgeBase()


def data_path(mode: str, filename: str) -> Path:
    if mode not in {"real", "sandbox"}:
        mode = "real"
    return ROOT / ("data/master" if mode == "real" else "data/sandbox") / filename


def load_csv(mode: str, filename: str) -> pd.DataFrame:
    p = data_path(mode, filename)
    return pd.read_csv(p) if p.exists() and p.stat().st_size else pd.DataFrame()


def records(mode: str, filename: str, limit: int = 200):
    df = load_csv(mode, filename)
    if df.empty:
        return []
    return df.tail(limit).where(pd.notna(df), None).to_dict(orient="records")


def active_model(mode: str):
    p = ROOT / (
        "models/registry/active.json"
        if mode == "real"
        else "models/sandbox_registry/active.json"
    )
    return json.loads(p.read_text()).get("version") if p.exists() else None


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/dashboard?mode=real")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "real_active_model": active_model("real"),
        "sandbox_active_model": active_model("sandbox"),
        "knowledge_base": kb.stats(),
    }


@app.get("/latest")
def latest(mode: str = Query("real", pattern="^(real|sandbox)$")):
    return records(mode, "latest_status.csv", 50)


@app.get("/alerts")
def alerts(
    mode: str = Query("real", pattern="^(real|sandbox)$"),
    limit: int = Query(100, ge=1, le=1000),
):
    return records(mode, "alerts.csv", limit)


@app.get("/validation")
def validation(limit: int = Query(100, ge=1, le=1000)):
    return records("real", "validation_report.csv", limit)


@app.get("/knowledge")
def knowledge(q: str, top_k: int = Query(5, ge=1, le=20)):
    return kb.query(q, top_k)


@app.get("/knowledge/stats")
def knowledge_stats():
    return kb.stats()


@app.get("/knowledge/sources")
def knowledge_sources():
    return kb.documents()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(mode: str = Query("real", pattern="^(real|sandbox)$")):
    latest_df = load_csv(mode, "latest_status.csv")
    alerts_df = load_csv(mode, "alerts.csv")
    model = active_model(mode) or "No active model"
    kb_stats = kb.stats()

    def table(df: pd.DataFrame, cols: list[str]) -> str:
        if df.empty:
            return "<p>No data yet.</p>"
        cols = [c for c in cols if c in df.columns]
        d = df[cols].tail(20)
        th = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
        body = "".join(
            "<tr>"
            + "".join(f"<td>{html.escape(str(v))}</td>" for v in row)
            + "</tr>"
            for row in d.astype(str).itertuples(index=False, name=None)
        )
        return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"

    cards = ""
    if not latest_df.empty:
        for _, r in latest_df.iterrows():
            op = html.escape(str(r.get("operator", "Operator")))
            prob = r.get("degradation_probability", "")
            dec = html.escape(str(r.get("policy_decision", "")))
            date = html.escape(str(r.get("date", "")))
            cards += (
                f"<div class='card'><h3>{op}</h3><p>{date}</p>"
                f"<b>Risk: {prob}</b><p>{dec}</p></div>"
            )

    categories = ", ".join(
        f"{html.escape(str(k))}: {v}" for k, v in kb_stats.get("categories", {}).items()
    ) or "No documents indexed"

    return f"""<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>AI Resilient Connectivity</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:28px;background:#f6f7f9;color:#17202a;max-width:1400px}}
h1{{margin-bottom:4px}} .sub{{color:#5d6d7e}} .cards{{display:flex;gap:14px;flex-wrap:wrap;margin:20px 0}}
.card{{background:white;border:1px solid #ddd;border-radius:10px;padding:16px;min-width:210px;box-shadow:0 1px 3px #ddd}}
table{{border-collapse:collapse;width:100%;background:white}} th,td{{border:1px solid #ddd;padding:7px;font-size:13px;vertical-align:top}} th{{background:#eef2f6;text-align:left}}
.note{{background:#fff6df;border-left:4px solid #d6a100;padding:12px;margin:15px 0}}
.kb{{background:white;border:1px solid #ddd;border-radius:10px;padding:18px;margin:22px 0;box-shadow:0 1px 3px #ddd}}
.searchrow{{display:flex;gap:8px;flex-wrap:wrap}} input[type=text]{{flex:1;min-width:280px;padding:10px;border:1px solid #bbb;border-radius:6px;font-size:14px}}
button{{padding:10px 16px;border:0;border-radius:6px;background:#1f5f99;color:white;cursor:pointer}} button:hover{{background:#174b79}}
.result{{border-top:1px solid #e2e2e2;padding:12px 0}} .meta{{font-size:12px;color:#667788}} .score{{font-weight:600}}
.small{{font-size:12px;color:#667788}} code{{background:#f1f3f5;padding:2px 4px;border-radius:3px}}
</style>
</head>
<body>
<h1>AI Resilient Connectivity</h1>
<div class='sub'>Mode: {html.escape(mode.upper())} · Y.3172-aligned QoS early-warning prototype · Active model: {html.escape(model)}</div>
<div class='note'>Model outputs are decision-support signals. Human validation is required before operational or regulatory action. Sandbox and real-data registries are strictly separate.</div>
<div class='cards'>{cards or '<div class="card">No latest predictions yet.</div>'}</div>

<h2>Recent alerts</h2>
{table(alerts_df,['date','operator','degradation_probability','policy_decision','recommended_action','explanation'])}
<h2>Latest operator status</h2>
{table(latest_df,['date','operator','quality_status','concurrent_deterioration_count','degradation_probability','policy_decision'])}

<section class='kb'>
<h2>Knowledge Base Search</h2>
<p>Search the project requirements, architecture and authorised local standards/regulatory references. Results are retrieved evidence, not model predictions or autonomous regulatory decisions.</p>
<div class='searchrow'>
<input id='kbq' type='text' placeholder='e.g. Why is human review required before regulatory action?'>
<button onclick='searchKB()'>Search</button>
</div>
<p class='small'>Indexed: {kb_stats.get('documents',0)} documents · {kb_stats.get('chunks',0)} chunks · {categories}</p>
<div id='kbstatus' class='small'></div>
<div id='kbresults'></div>
</section>

<script>
function esc(s){{
  return String(s ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
}}
async function searchKB(){{
  const q=document.getElementById('kbq').value.trim();
  const status=document.getElementById('kbstatus');
  const out=document.getElementById('kbresults');
  if(!q){{status.textContent='Enter a question first.'; out.innerHTML=''; return;}}
  status.textContent='Searching local knowledge sources...'; out.innerHTML='';
  try{{
    const r=await fetch('/knowledge?q='+encodeURIComponent(q)+'&top_k=5');
    if(!r.ok) throw new Error('HTTP '+r.status);
    const data=await r.json();
    if(!data.length){{status.textContent='No relevant evidence found.'; return;}}
    status.textContent='Retrieved '+data.length+' evidence chunk(s).';
    out.innerHTML=data.map((x,i)=>`<div class="result"><div class="meta">${{i+1}}. <b>${{esc(x.title)}}</b> · ${{esc(x.category)}} · <code>${{esc(x.source)}}</code> · chunk ${{esc(x.chunk)}} · <span class="score">score ${{esc(x.score)}}</span></div><p>${{esc(x.text)}}</p></div>`).join('');
  }}catch(e){{status.textContent='Knowledge search failed: '+e.message;}}
}}
document.getElementById('kbq').addEventListener('keydown',e=>{{if(e.key==='Enter') searchKB();}});
</script>
</body>
</html>"""
