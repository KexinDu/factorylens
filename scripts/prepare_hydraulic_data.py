"""Aggregate real 60-second hydraulic test-rig cycles into model-ready sensor snapshots."""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/hydraulic"
OUTPUT = ROOT / "data/processed/hydraulic_cycles.csv"
SENSORS = {
    "PS1.txt": "pressure_bar",
    "TS1.txt": "oil_temperature_c",
    "EPS1.txt": "motor_power_w",
    "FS1.txt": "volume_flow_lpm",
    "VS1.txt": "vibration_mms",
}


def row_means(path: Path) -> np.ndarray:
    values = np.loadtxt(path, dtype=np.float32)
    return values.mean(axis=1)


if __name__ == "__main__":
    profile = np.loadtxt(RAW / "profile.txt", dtype=np.float32)
    frame = pd.DataFrame(
        {
            "machine_id": [f"HYD-{index:04d}" for index in range(1, len(profile) + 1)],
            "cooler_condition_pct": profile[:, 0].astype(int),
            "valve_condition_pct": profile[:, 1].astype(int),
            "pump_leakage_class": profile[:, 2].astype(int),
            "accumulator_pressure_bar": profile[:, 3].astype(int),
            "stable_flag": profile[:, 4].astype(int),
        }
    )
    for filename, feature in SENSORS.items():
        frame[feature] = row_means(RAW / filename)
    # The supervised target is severe internal pump leakage (class 2).
    # Other component labels remain available for condition details, never as predictors.
    frame["severe_degradation"] = (frame["pump_leakage_class"] >= 2).astype(int)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT, index=False)
    print(
        f"Prepared {len(frame):,} real operating cycles; "
        f"severe-pump-leakage rate={frame['severe_degradation'].mean():.1%}"
    )
