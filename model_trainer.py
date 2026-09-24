from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    average_precision_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_bool_series(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def json_dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


class ModelTrainer:
    """Train, compare and register next-day QoS degradation classifiers.

    The training label is a sandbox proxy until the project owner approves a
    formal operational/regulatory degradation definition.
    """

    def __init__(self, config_path: str | Path, project_root: str | Path | None = None, registry_dir: str | Path = "models/registry"):
        cfg_path = Path(config_path).resolve()
        self.cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        self.root = Path(project_root).resolve() if project_root else cfg_path.parent.parent
        reg = Path(registry_dir)
        self.registry = reg if reg.is_absolute() else self.root / reg
        self.registry.mkdir(parents=True, exist_ok=True)

    def _prepare(self, csv_path: str | Path):
        df = pd.read_csv(csv_path)
        target = self.cfg["target_column"]
        if target not in df.columns:
            raise ValueError(f"Target column missing: {target}")

        mask = df[target].notna()
        if self.cfg.get("target_available_column") in df.columns:
            mask &= parse_bool_series(df[self.cfg["target_available_column"]])
        if self.cfg.get("model_eligible_column") in df.columns:
            mask &= parse_bool_series(df[self.cfg["model_eligible_column"]])
        ready_col = self.cfg.get("feature_ready_column")
        if ready_col and ready_col in df.columns:
            mask &= parse_bool_series(df[ready_col])

        df = df.loc[mask].copy()
        if df.empty:
            raise ValueError("No labelled, model-eligible, feature-ready rows are available for training.")
        df[target] = pd.to_numeric(df[target], errors="coerce")
        df = df[df[target].isin([0, 1])].copy()

        min_rows = int(self.cfg.get("minimum_training_rows", 100))
        min_pos = int(self.cfg.get("minimum_positive_rows", 10))
        positives = int(df[target].sum())
        negatives = int((df[target] == 0).sum())
        if len(df) < min_rows:
            raise ValueError(f"Insufficient training rows: {len(df)} < configured minimum {min_rows}.")
        if positives < min_pos:
            raise ValueError(f"Insufficient positive target rows: {positives} < configured minimum {min_pos}.")
        if negatives < min_pos:
            raise ValueError(f"Insufficient negative target rows: {negatives} < configured minimum {min_pos}.")

        excluded = set(self.cfg.get("exclude_columns", []))
        prefixes = tuple(self.cfg.get("exclude_prefixes", ["target_"]))
        candidates = [c for c in df.columns if c not in excluded and not c.startswith(prefixes)]
        features: list[str] = []
        converted = {}
        for c in candidates:
            x = pd.to_numeric(df[c], errors="coerce")
            if x.notna().sum() > 0:
                features.append(c)
                converted[c] = x
        if not features:
            raise ValueError("No usable numeric model features were found.")
        X = pd.DataFrame(converted, index=df.index)
        y = df[target].astype(int)
        dates = pd.to_datetime(df[self.cfg["date_column"]], errors="coerce")
        return df, X, y, dates, features

    def _split(self, X, y, dates):
        order = np.argsort(dates.to_numpy())
        X = X.iloc[order].reset_index(drop=True)
        y = y.iloc[order].reset_index(drop=True)
        dates = dates.iloc[order].reset_index(drop=True)
        frac = float(self.cfg.get("test_fraction", 0.25))
        split = max(1, min(len(X) - 1, int(round(len(X) * (1 - frac)))))
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y.iloc[:split], y.iloc[split:]
        d_train, d_test = dates.iloc[:split], dates.iloc[split:]
        if y_train.nunique() < 2:
            raise ValueError("Chronological training partition contains only one target class. Add more history.")
        return X_train, X_test, y_train, y_test, d_train, d_test

    def _candidates(self):
        rs = int(self.cfg.get("random_state", 42))
        candidates = {}
        if "logistic_regression" in self.cfg.get("models", []):
            candidates["logistic_regression"] = Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=rs)),
            ])
        if "random_forest" in self.cfg.get("models", []):
            candidates["random_forest"] = Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("classifier", RandomForestClassifier(
                    n_estimators=120,
                    min_samples_leaf=3,
                    class_weight="balanced_subsample",
                    random_state=rs,
                    n_jobs=-1,
                )),
            ])
        if not candidates:
            raise ValueError("No models enabled in model_config.json")
        return candidates

    @staticmethod
    def _metrics(y_true, probs, threshold: float):
        pred = (probs >= threshold).astype(int)
        out = {
            "accuracy": float(accuracy_score(y_true, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
            "precision": float(precision_score(y_true, pred, zero_division=0)),
            "recall": float(recall_score(y_true, pred, zero_division=0)),
            "f1": float(f1_score(y_true, pred, zero_division=0)),
        }
        if len(np.unique(y_true)) == 2:
            out["roc_auc"] = float(roc_auc_score(y_true, probs))
            out["average_precision"] = float(average_precision_score(y_true, probs))
        else:
            out["roc_auc"] = None
            out["average_precision"] = None
        return out

    def train(self, training_csv: str | Path, activate: bool = True) -> dict[str, Any]:
        df, X, y, dates, features = self._prepare(training_csv)
        Xtr, Xte, ytr, yte, dtr, dte = self._split(X, y, dates)
        threshold = float(self.cfg.get("prediction_threshold", 0.5))
        primary = self.cfg.get("primary_metric", "f1")
        metrics: dict[str, Any] = {}
        fitted = {}

        for name, model in self._candidates().items():
            model.fit(Xtr, ytr)
            probs = model.predict_proba(Xte)[:, 1]
            metrics[name] = self._metrics(yte.to_numpy(), probs, threshold)
            fitted[name] = model

        def score(name: str):
            v = metrics[name].get(primary)
            return -1 if v is None else float(v)

        selected_name = max(fitted, key=score)
        selected = fitted[selected_name]
        version = datetime.now(timezone.utc).strftime("model_%Y%m%dT%H%M%SZ")
        model_dir = self.registry / version
        model_dir.mkdir(parents=True, exist_ok=True)

        medians = {c: (None if pd.isna(v) else float(v)) for c, v in Xtr.median(numeric_only=True).items()}

        # Global feature importance is also used to bound local explanation work.
        imp = []
        clf = selected.named_steps["classifier"]
        if hasattr(clf, "coef_"):
            coef = np.asarray(clf.coef_)[0]
            for f, v in zip(features, coef):
                imp.append({"feature": f, "importance": float(abs(v)), "signed_effect": float(v)})
        elif hasattr(clf, "feature_importances_"):
            for f, v in zip(features, clf.feature_importances_):
                imp.append({"feature": f, "importance": float(v), "signed_effect": None})
        imp = sorted(imp, key=lambda r: r["importance"], reverse=True)
        explain_features = [r["feature"] for r in imp[:12]]

        bundle = {
            "model": selected,
            "model_name": selected_name,
            "features": features,
            "explain_features": explain_features,
            "feature_medians": medians,
            "threshold": threshold,
            "target_column": self.cfg["target_column"],
            "trained_at_utc": utcnow(),
            "version": version,
        }
        joblib.dump(bundle, model_dir / "model.joblib")

        metadata = {
            "version": version,
            "model_name": selected_name,
            "target_definition": "SANDBOX_PROXY_NEXT_DAY_MULTI_KPI_STRESS",
            "trained_at_utc": bundle["trained_at_utc"],
            "training_rows": int(len(Xtr)),
            "test_rows": int(len(Xte)),
            "positive_training_rows": int(ytr.sum()),
            "positive_test_rows": int(yte.sum()),
            "training_date_min": str(dtr.min().date()) if len(dtr) else None,
            "training_date_max": str(dtr.max().date()) if len(dtr) else None,
            "test_date_min": str(dte.min().date()) if len(dte) else None,
            "test_date_max": str(dte.max().date()) if len(dte) else None,
            "feature_count": len(features),
            "features": features,
            "prediction_threshold": threshold,
            "primary_metric": primary,
            "candidate_metrics": metrics,
            "selected_metrics": metrics[selected_name],
            "limitations": [
                "Training target is a sandbox proxy, not a formal regulatory degradation label.",
                "Model outputs support analyst review and must not trigger autonomous regulatory action.",
                "Performance metrics are meaningful only when sufficient representative historical data is used."
            ],
        }
        json_dump(model_dir / "metadata.json", metadata)

        # Global feature importance for audit/explainability.
        pd.DataFrame(imp).to_csv(model_dir / "feature_importance.csv", index=False)

        if activate:
            json_dump(self.registry / "active.json", {"version": version, "model_path": str((model_dir / "model.joblib").relative_to(self.root)), "activated_at_utc": utcnow()})
        return metadata


def main():
    ap = argparse.ArgumentParser(description="Train and register QoS degradation prediction models")
    ap.add_argument("--input", default="data/master/training_dataset.csv")
    ap.add_argument("--config", default="config/model_config.json")
    ap.add_argument("--no-activate", action="store_true")
    args = ap.parse_args()
    meta = ModelTrainer(args.config).train(args.input, activate=not args.no_activate)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
