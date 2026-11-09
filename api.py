from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from knowledge_base import KnowledgeBase

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="AI Resilient Connectivity", version="1.3.1")
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


@app.get("/knowledge/answer")
def knowledge_answer(q: str, top_k: int = Query(5, ge=1, le=20)):
    return kb.answer(q, top_k)


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
    policy_df = load_csv(mode, "policy_decisions.csv")
    model = active_model(mode) or "No active model"
    kb_stats = kb.stats()

    def safe_num(v, default=None):
        try:
            if pd.isna(v):
                return default
            return float(v)
        except Exception:
            return default

    def decision_class(level: str) -> str:
        return {"HIGH_REVIEW":"danger","REVIEW":"review","WATCH":"watch","MONITOR":"good","NO_DECISION":"muted"}.get(str(level or "").upper(),"muted")

    def operator_cards() -> str:
        if latest_df.empty:
            return "<div class='empty-state'><div class='empty-icon'>◌</div><b>No operator predictions yet</b><span>Run the pipeline to populate the latest status.</span></div>"
        cards=[]
        sort_col="operator" if "operator" in latest_df.columns else latest_df.columns[0]
        for _,r in latest_df.sort_values(sort_col).iterrows():
            op=html.escape(str(r.get("operator","Operator"))); raw=safe_num(r.get("degradation_probability"))
            risk=(raw*100 if raw is not None and raw<=1 else raw) if raw is not None else None
            risk_txt="—" if risk is None else f"{risk:.0f}%"; risk_deg=0 if risk is None else max(0,min(100,risk))*3.6
            dec=html.escape(str(r.get("policy_decision","NO_DECISION"))); cls=decision_class(dec)
            date=html.escape(str(r.get("date",""))); quality=html.escape(str(r.get("quality_status","—"))); stress=html.escape(str(r.get("concurrent_deterioration_count","—")))
            cards.append(f"<button class='operator-card' data-operator='{op}' onclick='selectOperator(this.dataset.operator)'><div class='operator-card-top'><div><div class='operator-name'>{op}</div><div class='operator-date'>{date}</div></div><span class='badge {cls}'>{dec.replace('_',' ')}</span></div><div class='risk-row'><div class='risk-ring' style='--risk:{risk_deg}deg'><div><strong>{risk_txt}</strong><span>risk</span></div></div><div class='mini-metrics'><div><span>Quality</span><b>{quality}</b></div><div><span>Stress KPIs</span><b>{stress}</b></div></div></div></button>")
        return "".join(cards)

    def alert_rows() -> str:
        if alerts_df.empty:
            return "<tr><td colspan='5'><div class='empty-inline'>No WATCH / REVIEW alerts in this mode.</div></td></tr>"
        rows=[]
        for _,r in alerts_df.tail(12).iloc[::-1].iterrows():
            level=str(r.get("policy_decision","")); cls=decision_class(level); raw=safe_num(r.get("degradation_probability")); risk=(raw*100 if raw is not None and raw<=1 else raw) if raw is not None else None; risk_txt="—" if risk is None else f"{risk:.1f}%"
            rows.append("<tr>"+f"<td>{html.escape(str(r.get('date','')))}</td>"+f"<td><b>{html.escape(str(r.get('operator','')))}</b></td>"+f"<td><span class='badge {cls}'>{html.escape(level.replace('_',' '))}</span></td>"+f"<td>{risk_txt}</td>"+f"<td>{html.escape(str(r.get('recommended_action','')))}</td></tr>")
        return "".join(rows)

    latest_records=[] if latest_df.empty else latest_df.where(pd.notna(latest_df),None).to_dict(orient="records")
    history_records=[]
    if not policy_df.empty and "date" in policy_df.columns:
        cols=[c for c in ["date","operator","degradation_probability","policy_decision","availability_mean","cssr_mean","dcr_mean","hosr_mean","sd_congestion_mean","tch_congestion_mean","total_traffic_erlang","concurrent_deterioration_count"] if c in policy_df.columns]
        hist=policy_df[cols].copy(); hist["__date"]=pd.to_datetime(hist["date"],errors="coerce"); hist=hist.sort_values([c for c in ["operator","__date"] if c in hist.columns]).drop(columns="__date",errors="ignore"); history_records=hist.tail(1000).where(pd.notna(hist),None).to_dict(orient="records")
    operators=int(latest_df["operator"].nunique()) if not latest_df.empty and "operator" in latest_df.columns else 0
    alerts_count=int(len(alerts_df)); high_count=int((alerts_df.get("policy_decision",pd.Series(dtype=str)).astype(str)=="HIGH_REVIEW").sum()) if not alerts_df.empty else 0
    docs=int(kb_stats.get("documents",0)); chunks=int(kb_stats.get("chunks",0)); categories=", ".join(f"{k}: {v}" for k,v in kb_stats.get("categories",{}).items()) or "No documents indexed"
    page=(ROOT/"templates/dashboard.html").read_text(encoding="utf-8")
    replacements={"__MODE__":html.escape(mode.upper()),"__MODEL__":html.escape(model),"__REAL_ACTIVE__":"active" if mode=="real" else "","__SANDBOX_ACTIVE__":"active" if mode=="sandbox" else "","__OPERATORS__":str(operators),"__ALERTS__":str(alerts_count),"__HIGH__":str(high_count),"__DOCS__":str(docs),"__CHUNKS__":str(chunks),"__OPERATOR_CARDS__":operator_cards(),"__ALERT_ROWS__":alert_rows(),"__CATEGORIES__":html.escape(categories),"__LATEST_JSON__":json.dumps(latest_records,default=str),"__HISTORY_JSON__":json.dumps(history_records,default=str)}
    for key,val in replacements.items(): page=page.replace(key,val)
    return page
