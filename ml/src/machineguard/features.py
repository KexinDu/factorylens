from __future__ import annotations

import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

RAW_FEATURES = [
    "pressure_bar",
    "oil_temperature_c",
    "motor_power_w",
    "volume_flow_lpm",
    "vibration_mms",
]


class HydraulicFeatures(BaseEstimator, TransformerMixin):
    """Deployment-safe feature engineering used inside persisted pipelines."""

    def fit(self, X: pd.DataFrame, y=None):
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        result = X[RAW_FEATURES].copy()
        result["hydraulic_power_proxy"] = result["pressure_bar"] * result["volume_flow_lpm"]
        result["load_vibration_interaction"] = result["motor_power_w"] * result["vibration_mms"]
        return result
