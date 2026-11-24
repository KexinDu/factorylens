import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.src.machineguard.features import RAW_FEATURES

from .config import Settings
from .schemas import MachineInput

LABELS = {
    "pressure_bar": "System pressure",
    "oil_temperature_c": "Oil temperature",
    "motor_power_w": "Motor power",
    "volume_flow_lpm": "Volume flow",
    "vibration_mms": "Vibration",
    "hydraulic_power_proxy": "Hydraulic power proxy",
    "load_vibration_interaction": "Load × vibration",
}


class PredictionService:
    def __init__(self, config: Settings):
        self.config = config
        self.classifier = joblib.load(config.model_path)
        self.anomaly_model = joblib.load(config.anomaly_model_path)
        self.metadata = json.loads(Path(config.metadata_path).read_text(encoding="utf-8"))
        self.threshold = config.prediction_threshold or float(self.metadata["threshold"])
        self.feature_names = self.metadata["transformed_features"]
        self.inventory = pd.read_csv(config.data_path)
        self.database_path = Path(config.database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._explainer = None
        try:
            import shap

            self._explainer = shap.LinearExplainer(
                self.classifier.named_steps["model"], np.zeros((1, 7))
            )
        except Exception:
            self._explainer = None
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS assets (
                machine_id TEXT PRIMARY KEY, pressure_bar REAL NOT NULL,
                oil_temperature_c REAL NOT NULL, motor_power_w REAL NOT NULL,
                volume_flow_lpm REAL NOT NULL, vibration_mms REAL NOT NULL,
                failure_probability REAL NOT NULL, risk_level TEXT NOT NULL,
                anomaly INTEGER NOT NULL, anomaly_score REAL NOT NULL,
                source TEXT NOT NULL, component_condition TEXT,
                updated_at TEXT NOT NULL)"""
            )
            existing = connection.execute(
                "SELECT COUNT(*) FROM assets WHERE source = ?", ("UCI hydraulic test rig",)
            ).fetchone()[0]
            if existing == len(self.inventory):
                return
            frame = self.inventory[RAW_FEATURES]
            probabilities, anomalies, scores, risks = self._signals(frame)
            records = []
            for index, row in self.inventory.iterrows():
                condition = {
                    "cooler_efficiency_pct": int(row["cooler_condition_pct"]),
                    "valve_condition_pct": int(row["valve_condition_pct"]),
                    "pump_leakage_class": int(row["pump_leakage_class"]),
                    "accumulator_pressure_bar": int(row["accumulator_pressure_bar"]),
                    "stable_flag": int(row["stable_flag"]),
                }
                records.append(
                    (
                        row["machine_id"],
                        *[float(row[feature]) for feature in RAW_FEATURES],
                        float(probabilities[index]),
                        risks[index],
                        int(anomalies[index]),
                        float(scores[index]),
                        "UCI hydraulic test rig",
                        json.dumps(condition),
                        datetime.now(timezone.utc).isoformat(),
                    )
                )
            connection.execute("DELETE FROM assets WHERE source = ?", ("UCI hydraulic test rig",))
            connection.executemany(
                """INSERT OR REPLACE INTO assets VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                records,
            )

    @staticmethod
    def frame(items: list[MachineInput]) -> pd.DataFrame:
        return pd.DataFrame(
            [{feature: getattr(item, feature) for feature in RAW_FEATURES} for item in items]
        )

    def _signals(self, frame: pd.DataFrame):
        probabilities = self.classifier.predict_proba(frame)[:, 1]
        anomalies = self.anomaly_model.predict(frame) == -1
        decision = self.anomaly_model.decision_function(frame)
        scores = 1 / (1 + np.exp(np.clip(decision * 12, -40, 40)))
        risks = np.where(
            probabilities >= self.config.high_risk_threshold,
            "high",
            np.where(
                (probabilities >= self.config.warning_threshold) | anomalies,
                "warning",
                "healthy",
            ),
        )
        return probabilities, anomalies, scores, risks

    def _factors(self, frame: pd.DataFrame, index: int) -> list[dict[str, float | str]]:
        transformed = self.classifier[:-1].transform(frame)
        values = None
        if self._explainer is not None:
            values = np.asarray(self._explainer.shap_values(transformed))
        if values is None:
            coefficients = np.asarray(self.classifier.named_steps["model"].coef_[0])
            values = transformed * coefficients
        ranked = np.argsort(np.abs(values[index]))[::-1][:5]
        return [
            {
                "feature": LABELS.get(self.feature_names[i], self.feature_names[i]),
                "impact": round(float(values[index, i]), 4),
            }
            for i in ranked
        ]

    def predict_many(self, items: list[MachineInput]) -> list[dict]:
        frame = self.frame(items)
        probabilities, anomalies, scores, risks = self._signals(frame)
        results = []
        for index, item in enumerate(items):
            risk = str(risks[index])
            interpretation = (
                "Sensor behavior indicates high risk of severe internal pump leakage."
                if risk == "high"
                else (
                    "The hydraulic cycle warrants monitoring or qualified inspection."
                    if risk == "warning"
                    else "No elevated pump-leakage risk is indicated by this cycle."
                )
            )
            results.append(
                {
                    "machine_id": item.machine_id,
                    "failure_prediction": bool(probabilities[index] >= self.threshold),
                    "failure_probability": round(float(probabilities[index]), 6),
                    "risk_level": risk,
                    "anomaly": bool(anomalies[index]),
                    "anomaly_score": round(float(scores[index]), 6),
                    "top_factors": self._factors(frame, index),
                    "interpretation": interpretation,
                }
            )
        return results

    def predict(self, item: MachineInput) -> dict:
        return self.predict_many([item])[0]

    def save(self, item: MachineInput) -> dict:
        if not item.machine_id:
            raise ValueError("Machine ID is required when saving an asset")
        assessment = self.predict(item)
        with self._connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO assets VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item.machine_id,
                    *[getattr(item, feature) for feature in RAW_FEATURES],
                    assessment["failure_probability"],
                    assessment["risk_level"],
                    int(assessment["anomaly"]),
                    assessment["anomaly_score"],
                    "Manual entry",
                    None,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return {"machine": item.model_dump(), "assessment": assessment, "source": "Manual entry"}

    def equipment_record(self, machine_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM assets WHERE machine_id = ?", (machine_id.strip().upper(),)
            ).fetchone()
        if row is None:
            raise KeyError(machine_id)
        machine = MachineInput(
            **{feature: row[feature] for feature in RAW_FEATURES},
            machine_id=row["machine_id"],
        )
        return {
            "machine": machine.model_dump(),
            "source": row["source"],
            "component_condition": json.loads(row["component_condition"])
            if row["component_condition"]
            else None,
        }

    def lookup(self, machine_id: str) -> dict:
        record = self.equipment_record(machine_id)
        assessment = self.predict(MachineInput.model_validate(record["machine"]))
        return {**record, "assessment": assessment}

    def list_assets(self, category: str, limit: int, offset: int) -> dict:
        clauses, parameters = [], []
        if category in {"healthy", "warning", "high"}:
            clauses.append("risk_level = ?")
            parameters.append(category)
        elif category == "anomaly":
            clauses.append("anomaly = 1")
        elif category != "all":
            raise ValueError("Unsupported category")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            count = connection.execute(
                f"SELECT COUNT(*) FROM assets {where}", parameters
            ).fetchone()[0]
            rows = connection.execute(
                f"""SELECT machine_id, failure_probability, risk_level, anomaly,
                anomaly_score, source FROM assets {where}
                ORDER BY failure_probability DESC LIMIT ? OFFSET ?""",
                [*parameters, limit, offset],
            ).fetchall()
        return {"category": category, "count": count, "results": [dict(row) for row in rows]}

    def fleet_summary(self) -> dict:
        with self._connect() as connection:
            rows = dict(
                connection.execute("SELECT risk_level, COUNT(*) FROM assets GROUP BY risk_level")
            )
            total = connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            anomalies = connection.execute(
                "SELECT COUNT(*) FROM assets WHERE anomaly = 1"
            ).fetchone()[0]
        return {
            "total": total,
            "healthy": rows.get("healthy", 0),
            "warning": rows.get("warning", 0),
            "high": rows.get("high", 0),
            "anomalies": anomalies,
        }
