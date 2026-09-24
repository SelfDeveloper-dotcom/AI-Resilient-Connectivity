from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "models" / "registry"


def list_models():
    rows=[]
    active=None
    ap=REGISTRY/"active.json"
    if ap.exists(): active=json.loads(ap.read_text()).get("version")
    for p in sorted(REGISTRY.glob("model_*"), reverse=True):
        meta=p/"metadata.json"
        if meta.exists():
            d=json.loads(meta.read_text())
            rows.append({"version":d.get("version",p.name),"model_name":d.get("model_name"),"trained_at_utc":d.get("trained_at_utc"),"active":p.name==active,"metrics":d.get("selected_metrics",{})})
    return rows


def activate(version: str):
    p=REGISTRY/version/"model.joblib"
    if not p.exists(): raise FileNotFoundError(p)
    payload={"version":version,"model_path":str(p.relative_to(ROOT)),"activated_at_utc":datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (REGISTRY/"active.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
    return payload


def main():
    ap=argparse.ArgumentParser(description="Minimal MLFO model registry manager")
    sub=ap.add_subparsers(dest="cmd",required=True)
    sub.add_parser("list")
    a=sub.add_parser("activate"); a.add_argument("version")
    args=ap.parse_args()
    print(json.dumps(list_models() if args.cmd=="list" else activate(args.version),indent=2))

if __name__=="__main__": main()
