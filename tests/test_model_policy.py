import json, tempfile, unittest
from pathlib import Path
import pandas as pd
from sandbox_generator import generate
from feature_engineer import FeatureEngineer
from target_engineer import TargetEngineer
from model_trainer import ModelTrainer
from predictor import Predictor
from policy_engine import PolicyEngine

ROOT=Path(__file__).resolve().parents[1]

class ModelPolicyTests(unittest.TestCase):
    def test_sandbox_train_predict_policy(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            # Use project sandbox output because registry is intentionally project-scoped.
            raw=ROOT/"data/sandbox/test_operator_day_features.csv"
            feat=ROOT/"data/sandbox/test_model_features.csv"
            target=ROOT/"data/sandbox/test_training_dataset.csv"
            pred=ROOT/"data/sandbox/test_predictions.csv"
            pol=ROOT/"data/sandbox/test_policy.csv"
            generate(ROOT/"config/sandbox_config.json",raw)
            FeatureEngineer(ROOT/"config/feature_config.json").transform_file(raw,feat)
            TargetEngineer(ROOT/"config/target_config.json").transform_file(feat,target)
            meta=ModelTrainer(ROOT/"config/model_config.json",ROOT,"models/sandbox_registry").train(target)
            self.assertIn(meta["model_name"],{"logistic_regression","random_forest"})
            df=Predictor("models/sandbox_registry").predict_file(feat,pred)
            self.assertGreater((df["prediction_status"]=="PREDICTED").sum(),0)
            out=PolicyEngine(ROOT/"config/policy_config.json").apply_file(pred,pol)
            self.assertIn("policy_decision",out.columns)

if __name__=="__main__": unittest.main()
