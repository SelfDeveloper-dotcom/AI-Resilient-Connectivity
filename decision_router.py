from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

ALERT_LEVELS={"WATCH","REVIEW","HIGH_REVIEW"}

def route(input_csv="data/master/policy_decisions.csv", alerts_csv="data/master/alerts.csv", latest_csv="data/master/latest_status.csv"):
    df=pd.read_csv(input_csv)
    if "date" in df: df["__date"]=pd.to_datetime(df["date"],errors="coerce")
    alerts=df[df.get("policy_decision",pd.Series(index=df.index,dtype=str)).isin(ALERT_LEVELS)].copy()
    if "__date" in alerts: alerts=alerts.sort_values([c for c in ["operator","__date"] if c in alerts]).drop(columns="__date")
    Path(alerts_csv).parent.mkdir(parents=True,exist_ok=True); alerts.to_csv(alerts_csv,index=False)
    if "operator" in df and "__date" in df:
        latest=df.sort_values("__date").groupby("operator",as_index=False).tail(1).drop(columns="__date")
    else: latest=df.tail(20).drop(columns=["__date"],errors="ignore")
    latest.to_csv(latest_csv,index=False)
    return alerts,latest

def main():
    ap=argparse.ArgumentParser(description="Y.3172 D: route policy decisions to alert/SINK datasets")
    ap.add_argument("--input",default="data/master/policy_decisions.csv")
    ap.add_argument("--alerts",default="data/master/alerts.csv")
    ap.add_argument("--latest",default="data/master/latest_status.csv")
    a=ap.parse_args(); alerts,latest=route(a.input,a.alerts,a.latest)
    print(f"Alerts: {len(alerts)}; latest operator rows: {len(latest)}")

if __name__=="__main__": main()
