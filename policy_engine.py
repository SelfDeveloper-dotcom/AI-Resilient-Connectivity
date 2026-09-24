from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent

def truth(v): return str(v).strip().lower() in {"true","1","yes","y"}

class PolicyEngine:
    """Y.3172 P: configurable human-review policy over model outputs."""
    def __init__(self, config_path="config/policy_config.json"):
        p=Path(config_path); p=p if p.is_absolute() else ROOT/p
        self.cfg=json.loads(p.read_text(encoding="utf-8"))

    def decide_row(self,row):
        if row.get("prediction_status") != "PREDICTED" or not truth(row.get(self.cfg["eligible_column"],False)):
            level="NO_DECISION"
        else:
            try: p=float(row.get(self.cfg["probability_column"]))
            except Exception: p=-1
            try: stress=int(float(row.get(self.cfg["stress_count_column"],0)))
            except Exception: stress=0
            quality=str(row.get(self.cfg["quality_column"],""))
            if p >= self.cfg["high_threshold"] and stress >= self.cfg["minimum_stress_count_for_high"]:
                level="HIGH_REVIEW"
            elif p >= self.cfg["review_threshold"]:
                level="REVIEW"
            elif p >= self.cfg["low_threshold"]:
                level="WATCH"
            else:
                level="MONITOR"
            if quality=="FAIL": level="NO_DECISION"
        return level, self.cfg["actions"][level]

    def apply_file(self,input_csv,output_csv):
        df=pd.read_csv(input_csv)
        decisions=[self.decide_row(r) for _,r in df.iterrows()]
        df["policy_decision"]=[x[0] for x in decisions]
        df["recommended_action"]=[x[1] for x in decisions]
        df["human_review_required"]=bool(self.cfg.get("human_review_required",True))
        Path(output_csv).parent.mkdir(parents=True,exist_ok=True)
        df.to_csv(output_csv,index=False)
        return df

def main():
    ap=argparse.ArgumentParser(description="Apply Y.3172 policy/human-review guardrails")
    ap.add_argument("--input",default="data/master/predictions.csv")
    ap.add_argument("--out",default="data/master/policy_decisions.csv")
    args=ap.parse_args(); df=PolicyEngine().apply_file(args.input,args.out)
    print(df["policy_decision"].value_counts(dropna=False).to_string())

if __name__=="__main__": main()
