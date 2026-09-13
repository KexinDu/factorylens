import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib"))

from ml.src.machineguard.hydraulic import train_hydraulic  # noqa: E402

if __name__ == "__main__":
    metadata = train_hydraulic(ROOT / "data/processed/hydraulic_cycles.csv", ROOT / "ml/artifacts")
    name = metadata["model_name"]
    recall = metadata["metrics"]["recall"]
    pr_auc = metadata["metrics"]["pr_auc"]
    print(f"Selected {name} | test recall={recall:.3f} | PR-AUC={pr_auc:.3f}")
