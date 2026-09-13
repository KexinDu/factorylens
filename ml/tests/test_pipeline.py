import pandas as pd

from ml.src.machineguard.features import RAW_FEATURES, HydraulicFeatures


def test_real_hydraulic_dataset_shape_and_target():
    frame = pd.read_csv("data/processed/hydraulic_cycles.csv")
    assert len(frame) == 2205
    assert set(RAW_FEATURES).issubset(frame.columns)
    assert 0.20 < frame["severe_degradation"].mean() < 0.25


def test_feature_engineering_has_no_nan():
    sample = pd.read_csv("data/processed/hydraulic_cycles.csv").head(1)
    transformed = HydraulicFeatures().transform(sample)
    assert transformed.shape[1] == 7
    assert not transformed.isna().any().any()
    assert transformed["hydraulic_power_proxy"].iloc[0] > 0
