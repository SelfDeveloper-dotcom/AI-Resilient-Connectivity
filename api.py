from __future__ import annotations
import html, json
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from knowledge_base import KnowledgeBase

ROOT=Path(__file__).resolve().parent
app=FastAPI(title="AI Resilient Connectivity",version="1.0.0")
kb=KnowledgeBase()

def data_path(mode: str, filename: str) -> Path:
    if mode not in {"real","sandbox"}: mode="real"
    return ROOT / ("data/master" if mode=="real" else "data/sandbox") / filename

def load_csv(mode: str, filename: str):
    p=data_path(mode,filename)
    return pd.read_csv(p) if p.exists() and p.stat().st_size else pd.DataFrame()

def records(mode: str, filename: str, limit=200):
    df=load_csv(mode,filename)
    if df.empty: return []
    return df.tail(limit).where(pd.notna(df),None).to_dict(orient="records")

def active_model(mode: str):
    p=ROOT/("models/registry/active.json" if mode=="real" else "models/sandbox_registry/active.json")
    return json.loads(p.read_text()).get("version") if p.exists() else None

@app.get("/health")
def health():
    return {"status":"ok","real_active_model":active_model("real"),"sandbox_active_model":active_model("sandbox")}

@app.get("/latest")
def latest(mode:str=Query("real",pattern="^(real|sandbox)$")): return records(mode,"latest_status.csv",50)

@app.get("/alerts")
def alerts(mode:str=Query("real",pattern="^(real|sandbox)$"),limit:int=Query(100,ge=1,le=1000)): return records(mode,"alerts.csv",limit)

@app.get("/validation")
def validation(limit:int=Query(100,ge=1,le=1000)): return records("real","validation_report.csv",limit)

@app.get("/knowledge")
def knowledge(q:str,top_k:int=5): return kb.query(q,top_k)

@app.get("/dashboard",response_class=HTMLResponse)
def dashboard(mode:str=Query("real",pattern="^(real|sandbox)$")):
    latest_df=load_csv(mode,"latest_status.csv")
    alerts_df=load_csv(mode,"alerts.csv")
    model=active_model(mode) or "No active model"
    def table(df,cols):
        if df.empty: return "<p>No data yet.</p>"
        cols=[c for c in cols if c in df.columns]; d=df[cols].tail(20)
        th="".join(f"<th>{html.escape(c)}</th>" for c in cols)
        body="".join("<tr>"+"".join(f"<td>{html.escape(str(v))}</td>" for v in row)+"</tr>" for row in d.astype(str).itertuples(index=False,name=None))
        return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"
    cards=""
    if not latest_df.empty:
        for _,r in latest_df.iterrows():
            op=html.escape(str(r.get("operator","Operator"))); prob=r.get("degradation_probability",""); dec=html.escape(str(r.get("policy_decision",""))); date=html.escape(str(r.get("date","")))
            cards += f"<div class='card'><h3>{op}</h3><p>{date}</p><b>Risk: {prob}</b><p>{dec}</p></div>"
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>AI Resilient Connectivity</title><style>
    body{{font-family:Segoe UI,Arial;margin:28px;background:#f6f7f9;color:#17202a}} h1{{margin-bottom:4px}} .sub{{color:#5d6d7e}} .cards{{display:flex;gap:14px;flex-wrap:wrap;margin:20px 0}} .card{{background:white;border:1px solid #ddd;border-radius:10px;padding:16px;min-width:210px;box-shadow:0 1px 3px #ddd}} table{{border-collapse:collapse;width:100%;background:white}} th,td{{border:1px solid #ddd;padding:7px;font-size:13px}} th{{background:#eef2f6;text-align:left}} .note{{background:#fff6df;border-left:4px solid #d6a100;padding:12px;margin:15px 0}}</style></head><body>
    <h1>AI Resilient Connectivity</h1><div class='sub'>Mode: {html.escape(mode.upper())} · Y.3172-aligned QoS early-warning prototype · Active model: {html.escape(model)}</div>
    <div class='note'>Model outputs are decision-support signals. Human validation is required before operational or regulatory action. Sandbox and real-data registries are strictly separate.</div>
    <div class='cards'>{cards or '<div class="card">No latest predictions yet.</div>'}</div>
    <h2>Recent alerts</h2>{table(alerts_df,['date','operator','degradation_probability','policy_decision','recommended_action','explanation'])}
    <h2>Latest operator status</h2>{table(latest_df,['date','operator','quality_status','concurrent_deterioration_count','degradation_probability','policy_decision'])}
    </body></html>"""
