from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import mlflow
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from .constants import RANDOM_SEED
from .evaluation import curves, metrics, save_evaluation_plots, select_threshold
from .features import RAW_FEATURES, HydraulicFeatures

TARGET = "severe_degradation"
CONDITION_COLUMNS = [
    "cooler_condition_pct",
    "valve_condition_pct",
    "pump_leakage_class",
    "accumulator_pressure_bar",
    "stable_flag",
]


def pipeline(model) -> Pipeline:
    return Pipeline(
        [
            ("features", HydraulicFeatures()),
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", model),
        ]
    )


def train_hydraulic(data_path: str | Path, artifact_dir: str | Path) -> dict[str, object]:
    frame = pd.read_csv(data_path)
    if frame[RAW_FEATURES + [TARGET]].isna().any().any():
        raise ValueError("Hydraulic model columns contain missing values")
    X, y = frame[RAW_FEATURES], frame[TARGET].astype(int)
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.4, stratify=y, random_state=RANDOM_SEED
    )
    X_validation, X_test, y_validation, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=RANDOM_SEED
    )
    positive_weight = float((y_train == 0).sum() / (y_train == 1).sum())
    candidates = {
        "Logistic Regression": LogisticRegression(
            max_iter=1500, class_weight="balanced", random_state=RANDOM_SEED
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=400,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=RANDOM_SEED,
        ),
        "XGBoost": XGBClassifier(
            n_estimators=350,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            scale_pos_weight=positive_weight,
            eval_metric="logloss",
            n_jobs=-1,
            random_state=RANDOM_SEED,
        ),
    }
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("machineguard-hydraulic-real-data")
    comparison, fitted, thresholds = {}, {}, {}
    for name, model in candidates.items():
        fitted_model = pipeline(model).fit(X_train, y_train)
        probability = fitted_model.predict_proba(X_validation)[:, 1]
        threshold = select_threshold(y_validation, probability)
        fitted[name], thresholds[name] = fitted_model, threshold
        comparison[name] = metrics(y_validation, probability, threshold)
        with mlflow.start_run(run_name=name):
            mlflow.log_params(
                {
                    "model_name": name,
                    "random_seed": RANDOM_SEED,
                    "threshold": threshold,
                    "dataset": "UCI hydraulic condition monitoring",
                }
            )
            mlflow.log_metrics(
                {key: value for key, value in comparison[name].items() if isinstance(value, float)}
            )
    selected_name = max(
        comparison, key=lambda name: (comparison[name]["pr_auc"], comparison[name]["recall"])
    )
    selected, threshold = fitted[selected_name], thresholds[selected_name]
    test_probability = selected.predict_proba(X_test)[:, 1]
    test_metrics = metrics(y_test, test_probability, threshold)
    anomaly = pipeline(
        IsolationForest(n_estimators=350, contamination=0.06, random_state=RANDOM_SEED, n_jobs=-1)
    ).fit(X_train[y_train == 0])

    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected, artifact_dir / "classifier.joblib")
    joblib.dump(anomaly, artifact_dir / "anomaly_model.joblib")
    feature_names = RAW_FEATURES + ["hydraulic_power_proxy", "load_vibration_interaction"]
    model = selected.named_steps["model"]
    importance = getattr(
        model,
        "feature_importances_",
        np.abs(getattr(model, "coef_", [np.zeros(len(feature_names))])[0]),
    )
    feature_importance = sorted(
        [
            {"feature": feature, "importance": float(value)}
            for feature, value in zip(feature_names, importance, strict=True)
        ],
        key=lambda item: item["importance"],
        reverse=True,
    )
    metadata = {
        "model_name": selected_name,
        "model_version": "2.0.0",
        "target": "severe_internal_pump_leakage",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "UCI Condition Monitoring of Hydraulic Systems",
        "dataset_doi": "10.24432/C5CW21",
        "dataset_type": "Real industrial hydraulic test-rig measurements",
        "dataset_rows": len(frame),
        "failure_rate": float(y.mean()),
        "threshold": threshold,
        "metrics": test_metrics,
        "validation_comparison": comparison,
        "curves": curves(y_test, test_probability),
        "features": RAW_FEATURES,
        "transformed_features": feature_names,
        "feature_importance": feature_importance,
        "split": {
            "train": len(X_train),
            "validation": len(X_validation),
            "test": len(X_test),
            "seed": RANDOM_SEED,
        },
        "leakage_columns_excluded": CONDITION_COLUMNS,
    }
    metadata_path = artifact_dir / "model_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    save_evaluation_plots(metadata, artifact_dir / "reports", feature_importance)
    with mlflow.start_run(run_name=f"selected-{selected_name}"):
        mlflow.set_tag("stage", "held-out-test")
        mlflow.log_param("selected_model", selected_name)
        mlflow.log_param("classification_threshold", threshold)
        mlflow.log_metrics(
            {
                f"test_{key}": value
                for key, value in test_metrics.items()
                if isinstance(value, float)
            }
        )
        mlflow.log_artifacts(str(artifact_dir), artifact_path="model-artifacts")
    return metadata
