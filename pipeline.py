from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
from collector import Collector
from feature_engineer import FeatureEngineer
from target_engineer import TargetEngineer
from model_trainer import ModelTrainer
from predictor import Predictor
from policy_engine import PolicyEngine
from decision_router import route
from sandbox_generator import generate

ROOT=Path(__file__).resolve().parent

def exists(rel):
    p=ROOT/rel; return p.exists() and p.stat().st_size>0

def feature_stage(input_rel="data/master/operator_day_features.csv", output_rel="data/master/model_features.csv"):
    return FeatureEngineer(ROOT/"config/feature_config.json").transform_file(ROOT/input_rel,ROOT/output_rel)

def target_stage(input_rel="data/master/model_features.csv", output_rel="data/master/training_dataset.csv"):
    return TargetEngineer(ROOT/"config/target_config.json").transform_file(ROOT/input_rel,ROOT/output_rel)

def train_stage(input_rel="data/master/training_dataset.csv"):
    return ModelTrainer(ROOT/"config/model_config.json",ROOT).train(ROOT/input_rel)

def predict_stage(input_rel="data/master/model_features.csv"):
    return Predictor().predict_file(ROOT/input_rel,ROOT/"data/master/predictions.csv")

def policy_stage():
    df=PolicyEngine(ROOT/"config/policy_config.json").apply_file(ROOT/"data/master/predictions.csv",ROOT/"data/master/policy_decisions.csv")
    route(ROOT/"data/master/policy_decisions.csv",ROOT/"data/master/alerts.csv",ROOT/"data/master/latest_status.csv")
    return df

def collect_stage():
    Collector(ROOT/"config/collector_config.json").scan()

def sandbox_demo():
    df,p=generate(ROOT/"config/sandbox_config.json",ROOT/"data/sandbox/operator_day_features.csv")
    FeatureEngineer(ROOT/"config/feature_config.json").transform_file(p,ROOT/"data/sandbox/model_features.csv")
    TargetEngineer(ROOT/"config/target_config.json").transform_file(ROOT/"data/sandbox/model_features.csv",ROOT/"data/sandbox/training_dataset.csv")
    meta=ModelTrainer(ROOT/"config/model_config.json",ROOT,"models/sandbox_registry").train(ROOT/"data/sandbox/training_dataset.csv")
    Predictor("models/sandbox_registry").predict_file(ROOT/"data/sandbox/model_features.csv",ROOT/"data/sandbox/predictions.csv")
    PolicyEngine(ROOT/"config/policy_config.json").apply_file(ROOT/"data/sandbox/predictions.csv",ROOT/"data/sandbox/policy_decisions.csv")
    route(ROOT/"data/sandbox/policy_decisions.csv",ROOT/"data/sandbox/alerts.csv",ROOT/"data/sandbox/latest_status.csv")
    return meta

def all_real(train_if_possible=False):
    collect_stage()
    if not exists("data/master/operator_day_features.csv"):
        print("No collected data yet."); return
    feature_stage(); target_stage()
    if train_if_possible:
        try: train_stage()
        except Exception as e: print(f"Training skipped: {e}")
    if exists("models/registry/active.json"):
        predict_stage(); policy_stage()
    else:
        print("No active model. Run 'train' after sufficient historical data or run 'sandbox-demo' for a system demonstration.")

def main():
    ap=argparse.ArgumentParser(description="AI Resilient Connectivity end-to-end pipeline")
    sub=ap.add_subparsers(dest="cmd",required=True)
    for c in ["collect","features","targets","train","predict","policy","all","sandbox-demo","serve"]: sub.add_parser(c)
    args=ap.parse_args()
    if args.cmd=="collect": collect_stage()
    elif args.cmd=="features": feature_stage()
    elif args.cmd=="targets": target_stage()
    elif args.cmd=="train": print(json.dumps(train_stage(),indent=2))
    elif args.cmd=="predict": predict_stage()
    elif args.cmd=="policy": policy_stage()
    elif args.cmd=="all": all_real(train_if_possible=True)
    elif args.cmd=="sandbox-demo": print(json.dumps(sandbox_demo(),indent=2))
    elif args.cmd=="serve": subprocess.run([sys.executable,"-m","uvicorn","api:app","--host","127.0.0.1","--port","8000"],cwd=ROOT,check=False)

if __name__=="__main__": main()
