from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent


def generate(config_path="config/sandbox_config.json", out="data/sandbox/operator_day_features.csv"):
    p=Path(config_path); p=p if p.is_absolute() else ROOT/p
    cfg=json.loads(p.read_text(encoding="utf-8"))
    rng=np.random.default_rng(int(cfg.get("seed",42)))
    days=int(cfg.get("days",240)); dates=pd.date_range(cfg.get("start_date","2026-01-01"),periods=days,freq="D")
    rows=[]
    for op_i,operator in enumerate(cfg["operators"]):
        stress=np.zeros(days)
        i=7
        while i<days-8:
            if rng.random()<float(cfg.get("stress_event_probability",0.08)):
                dur=int(rng.integers(int(cfg.get("stress_duration_min",2)),int(cfg.get("stress_duration_max",5))+1))
                for k in range(dur):
                    if i+k<days: stress[i+k]=min(3.0,1.0+k*0.75)
                i += dur+3
            else: i+=1
        # Ensure at least a few events in deterministic demos.
        for anchor in [40+op_i*2, 105+op_i*3, 175+op_i*2]:
            for k,level in enumerate([0.8,1.6,2.4]):
                if anchor+k<days: stress[anchor+k]=max(stress[anchor+k],level)
        traffic_base=6_600_000+op_i*350_000
        for j,d in enumerate(dates):
            weekly=1+0.05*math.sin(2*math.pi*j/7)
            s=stress[j]
            traffic=max(1000,traffic_base*weekly*(1+0.035*s)+rng.normal(0,90000))
            availability=np.clip(99.35-0.30*s+rng.normal(0,0.08),92,100)
            cssr=np.clip(99.60-0.18*s+rng.normal(0,0.04),90,100)
            hosr=np.clip(99.25-0.28*s+rng.normal(0,0.07),85,100)
            dcr=np.clip(0.16+0.12*s+rng.normal(0,0.025),0,10)
            sd=np.clip(0.02+0.055*s+rng.normal(0,0.008),0,10)
            tch=np.clip(0.004+0.035*s+rng.normal(0,0.006),0,10)
            cells=84000+op_i*1800+int(rng.normal(0,150))
            rows.append({
                "sheet":d.strftime("%d %B"),"date":d.date().isoformat(),"operator":operator,"technology":"2G",
                "total_rows":cells,"unique_cells":cells,"duplicate_cell_rows":0,"states":37,"lgas":774,
                "total_traffic_erlang":round(float(traffic),4),
                "availability_mean":round(float(availability),5),"availability_p10":round(float(max(0,availability-rng.uniform(0.1,0.5))),5),
                "cssr_mean":round(float(cssr),5),"cssr_p10":round(float(max(0,cssr-rng.uniform(0.1,0.6))),5),
                "sd_congestion_mean":round(float(sd),6),"sd_congestion_p95":round(float(sd+rng.uniform(0.01,0.15)),6),
                "tch_congestion_mean":round(float(tch),6),"tch_congestion_p95":round(float(tch+rng.uniform(0.01,0.12)),6),
                "dcr_mean":round(float(dcr),6),"dcr_p90":round(float(dcr+rng.uniform(0.05,0.35)),6),
                "hosr_mean":round(float(hosr),5),"hosr_p10":round(float(max(0,hosr-rng.uniform(0.1,0.8))),5),
                "quality_status":"PASS","model_eligible":True,"submission_id":f"SANDBOX_{operator.replace(' ','_')}_{d:%Y%m%d}",
                "source_filename":"SYNTHETIC_SANDBOX.csv","sha256":"SANDBOX"
            })
    df=pd.DataFrame(rows).sort_values(["operator","date"])
    outp=Path(out); outp=outp if outp.is_absolute() else ROOT/outp; outp.parent.mkdir(parents=True,exist_ok=True); df.to_csv(outp,index=False)
    return df,outp


def main():
    ap=argparse.ArgumentParser(description="Generate synthetic Operator x Day data for ML Sandbox validation")
    ap.add_argument("--config",default="config/sandbox_config.json"); ap.add_argument("--out",default="data/sandbox/operator_day_features.csv")
    a=ap.parse_args(); df,p=generate(a.config,a.out); print(f"Generated {len(df)} synthetic rows -> {p}")

if __name__=="__main__": main()
