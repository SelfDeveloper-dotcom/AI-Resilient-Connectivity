from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
import joblib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent

def parse_bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().isin({"true","1","yes","y"})

class Predictor:
    def __init__(self, registry_dir: str|Path = "models/registry"):
        self.registry=(ROOT/registry_dir).resolve() if not Path(registry_dir).is_absolute() else Path(registry_dir)
        active=json.loads((self.registry/"active.json").read_text(encoding="utf-8"))
        self.version=active["version"]
        self.bundle=joblib.load(ROOT/active["model_path"])
        self.model=self.bundle["model"]
        self.features=self.bundle["features"]
        self.explain_features=self.bundle.get("explain_features", self.features[:12])
        self.threshold=float(self.bundle.get("threshold",0.5))
        self.medians=self.bundle.get("feature_medians",{})

    def _explain(self, row: pd.DataFrame, probability: float, top_n: int=5) -> str:
        impacts=[]
        # Model-agnostic local sensitivity: replace one feature at a time by its training median.
        for f in self.explain_features:
            median=self.medians.get(f)
            if median is None: continue
            alt=row.copy()
            alt.loc[:,f]=median
            p=float(self.model.predict_proba(alt[self.features])[:,1][0])
            impacts.append((f, probability-p, row.iloc[0].get(f)))
        impacts.sort(key=lambda x: abs(x[1]), reverse=True)
        parts=[]
        for f,impact,val in impacts[:top_n]:
            direction="increased" if impact>0 else "reduced"
            parts.append(f"{f}={val}: {direction} risk by ~{abs(impact):.3f}")
        return "; ".join(parts)

    def predict_file(self, features_csv: str|Path, output_csv: str|Path, explain_threshold: float=0.35):
        df=pd.read_csv(features_csv)
        out=df.copy()
        out["model_version"]=self.version
        out["prediction_status"]="NOT_READY"
        out["degradation_probability"]=np.nan
        out["predicted_degradation"]=np.nan
        out["explanation"]=""
        ready=pd.Series(True,index=df.index)
        if "model_eligible" in df: ready &= parse_bool(df["model_eligible"])
        if "feature_ready_7d" in df: ready &= parse_bool(df["feature_ready_7d"])
        X=pd.DataFrame({f: (pd.to_numeric(df[f],errors="coerce") if f in df else pd.Series(np.nan,index=df.index)) for f in self.features}, index=df.index).astype(float)
        idx=df.index[ready]
        if len(idx):
            probs=self.model.predict_proba(X.loc[idx,self.features])[:,1]
            out.loc[idx,"degradation_probability"]=probs
            out.loc[idx,"predicted_degradation"]=(probs>=self.threshold).astype(int)
            out.loc[idx,"prediction_status"]="PREDICTED"
            # Explain rows with material risk plus the latest row for each operator.
            explain_idx=set(idx[np.asarray(probs)>=max(explain_threshold, 0.80)].tolist())
            if "operator" in df and "date" in df:
                temp=df.loc[idx,["operator","date"]].copy(); temp["__i"]=temp.index
                temp["date"]=pd.to_datetime(temp["date"],errors="coerce")
                for _,g in temp.groupby("operator"):
                    explain_idx.add(int(g.sort_values("date").iloc[-1]["__i"]))
            # Bound explanation work for laptop performance.
            explain_idx = set(sorted(explain_idx)[:8])
            for i in sorted(explain_idx):
                p=float(out.at[i,"degradation_probability"])
                out.at[i,"explanation"]=self._explain(X.loc[[i],self.features],p)
        Path(output_csv).parent.mkdir(parents=True,exist_ok=True)
        out.to_csv(output_csv,index=False)
        return out

def main():
    ap=argparse.ArgumentParser(description="Run next-day QoS degradation inference")
    ap.add_argument("--input",default="data/master/model_features.csv")
    ap.add_argument("--out",default="data/master/predictions.csv")
    args=ap.parse_args()
    df=Predictor().predict_file(args.input,args.out)
    print(f"Predictions written: {args.out}; predicted rows={(df['prediction_status']=='PREDICTED').sum()}")

if __name__=="__main__": main()
