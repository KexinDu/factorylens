import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import mlflow
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from .constants import RANDOM_SEED, RAW_FEATURES
from .data import load_dataset, model_frame
from .evaluation import curves, metrics, save_evaluation_plots, select_threshold
from .preprocessing import FeatureEngineer, build_preprocessor, transformed_names


def classifier_pipeline(model) -> Pipeline:
    return Pipeline(
        [("features", FeatureEngineer()), ("preprocess", build_preprocessor()), ("model", model)]
    )


def train(data_path: str | Path, artifact_dir: str | Path) -> dict[str, object]:
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("machineguard-ai4i")
    frame = load_dataset(data_path)
    X, y = model_frame(frame)
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.4, stratify=y, random_state=RANDOM_SEED
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=RANDOM_SEED
    )
    positive_weight = float((y_train == 0).sum() / (y_train == 1).sum())
    candidates = {
        "Logistic Regression": LogisticRegression(
            max_iter=1500, class_weight="balanced", random_state=RANDOM_SEED
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=350,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=RANDOM_SEED,
        ),
        "XGBoost": XGBClassifier(
            n_estimators=300,
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
    comparison, fitted, thresholds = {}, {}, {}
    for name, model in candidates.items():
        pipeline = classifier_pipeline(model).fit(X_train, y_train)
        probability = pipeline.predict_proba(X_val)[:, 1]
        threshold = select_threshold(y_val, probability)
        fitted[name], thresholds[name] = pipeline, threshold
        comparison[name] = metrics(y_val, probability, threshold)
        with mlflow.start_run(run_name=name):
            mlflow.log_param("model_name", name)
            mlflow.log_param("random_seed", RANDOM_SEED)
            mlflow.log_param("threshold", threshold)
            mlflow.log_param("preprocessing", "median+standard-scale+one-hot")
            mlflow.log_metrics(
                {key: value for key, value in comparison[name].items() if isinstance(value, float)}
            )
    selected_name = max(
        comparison, key=lambda name: (comparison[name]["pr_auc"], comparison[name]["recall"])
    )
    selected, threshold = fitted[selected_name], thresholds[selected_name]
    test_probability = selected.predict_proba(X_test)[:, 1]
    test_metrics = metrics(y_test, test_probability, threshold)
    anomaly = Pipeline(
        [
            ("features", FeatureEngineer()),
            ("preprocess", build_preprocessor()),
            (
                "model",
                IsolationForest(
                    n_estimators=300, contamination=0.04, random_state=RANDOM_SEED, n_jobs=-1
                ),
            ),
        ]
    ).fit(X_train[y_train == 0])
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected, artifact_dir / "classifier.joblib")
    joblib.dump(anomaly, artifact_dir / "anomaly_model.joblib")
    names = transformed_names(selected)
    model = selected.named_steps["model"]
    importance = getattr(
        model, "feature_importances_", np.abs(getattr(model, "coef_", [np.zeros(len(names))])[0])
    )
    feature_importance = sorted(
        [
            {"feature": name, "importance": float(value)}
            for name, value in zip(names, importance, strict=True)
        ],
        key=lambda item: item["importance"],
        reverse=True,
    )
    metadata = {
        "model_name": selected_name,
        "model_version": "1.0.0",
        "target": "machine_failure",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "UCI AI4I 2020",
        "dataset_rows": len(frame),
        "failure_rate": float(y.mean()),
        "threshold": threshold,
        "metrics": test_metrics,
        "validation_comparison": comparison,
        "curves": curves(y_test, test_probability),
        "features": RAW_FEATURES,
        "transformed_features": names,
        "feature_importance": feature_importance,
        "split": {
            "train": len(X_train),
            "validation": len(X_val),
            "test": len(X_test),
            "seed": RANDOM_SEED,
        },
        "leakage_columns_excluded": ["TWF", "HDF", "PWF", "OSF", "RNF"],
    }
    (artifact_dir / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
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
