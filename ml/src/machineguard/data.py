from pathlib import Path

import pandas as pd

from .constants import LEAKAGE_COLUMNS, RAW_FEATURES, TARGET

ALIASES = {
    "udi": "udi",
    "product id": "product_id",
    "type": "type",
    "air temperature [k]": "air_temperature",
    "process temperature [k]": "process_temperature",
    "rotational speed [rpm]": "rotational_speed",
    "torque [nm]": "torque",
    "tool wear [min]": "tool_wear",
    "machine failure": TARGET,
    "twf": "twf",
    "hdf": "hdf",
    "pwf": "pwf",
    "osf": "osf",
    "rnf": "rnf",
}


def load_dataset(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame.rename(columns={c: ALIASES.get(c.strip().lower(), c) for c in frame.columns})
    missing = sorted(set(RAW_FEATURES + [TARGET]) - set(frame.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")
    if frame[RAW_FEATURES + [TARGET]].isna().any().any():
        raise ValueError("Required model columns contain missing values")
    if not set(frame["type"].unique()).issubset({"L", "M", "H"}):
        raise ValueError("Product type must contain only L, M, or H")
    return frame


def model_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    safe = frame.drop(columns=[c for c in LEAKAGE_COLUMNS if c in frame], errors="ignore")
    return safe[RAW_FEATURES].copy(), safe[TARGET].astype(int).copy()
