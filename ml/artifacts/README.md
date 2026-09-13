# Persisted artifacts

The classifier and anomaly detector are serialized scikit-learn pipelines and loaded once during FastAPI startup. `model_metadata.json` contains the held-out metrics and chart data shown by the frontend. `reports/` contains generated evaluation figures.

Only load these joblib files from this trusted repository. Recreate all artifacts with `python scripts/train.py` after dependency or feature-pipeline changes.

