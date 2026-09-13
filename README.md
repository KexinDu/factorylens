# MachineGuard AI

A portfolio-grade predictive-maintenance and anomaly-detection platform built on real hydraulic test-rig measurements. It includes a React operations dashboard, FastAPI service, SQLite asset store, reproducible ML training, explainability, batch scoring, tests, and container configuration.

## What the website does

- Shows live fleet counts from 2,205 UCI operating cycles.
- Makes All, Healthy, Warning, High Risk, and Anomaly cards clickable.
- Displays a prioritized machine list with probability and a **View details** action.
- Looks up a machine/cycle ID and auto-fills its sensor measurements.
- Accepts a new or edited sensor snapshot, analyzes it, and stores it in SQLite.
- Runs CSV batch analysis and exports prioritized results.
- Separates supervised pump-leakage risk from unsupervised unusual behavior.

## Real dataset

The active dataset is UCI's **Condition Monitoring of Hydraulic Systems** (`10.24432/C5CW21`, CC BY 4.0): 2,205 real 60-second cycles from a hydraulic test rig, collected from 17 sensors. The preparation pipeline aggregates pressure, oil temperature, motor power, flow, and vibration. The label is severe internal pump leakage; condition labels are excluded from the predictors.

`HYD-####` is an operating-cycle identifier supplied by this application, not a claim that the benchmark contains 2,205 different physical machines. This distinction matters in a technical interview.

## Model and achieved metrics

The training pipeline compares Logistic Regression, Random Forest, and XGBoost on stratified 60/20/20 train/validation/test splits with seed 42. Logistic Regression was selected by validation PR-AUC. Isolation Forest is trained separately on healthy cycles for anomaly detection.

Held-out test results (441 cycles):

| Metric | Result |
|---|---:|
| Precision | 98.0% |
| Recall | 100.0% |
| F1 | 98.99% |
| ROC-AUC | 100.0% |
| PR-AUC | 100.0% |
| Confusion matrix | TN 341, FP 2, FN 0, TP 98 |

These near-perfect results reflect a controlled hydraulic test-rig benchmark with strongly separated operating states. They must not be presented as expected real-factory performance without external/site-specific validation, temporal testing, drift monitoring, and calibration.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python scripts/train.py
uvicorn backend.app.main:app --reload --port 8123
```

In a second terminal:

```powershell
cd frontend
npm install
$env:VITE_API_BASE_URL="http://127.0.0.1:8123/api/v1"
npm run dev -- --host 127.0.0.1 --port 5174
```

Open http://127.0.0.1:5174/. API documentation is at http://127.0.0.1:8123/docs.

## Batch analysis

Open **Batch Analysis** and upload a CSV (maximum 2 MB / 5,000 rows) with:

```text
machine_id,pressure_bar,oil_temperature_c,motor_power_w,volume_flow_lpm,vibration_mms
```

Use `data/sample_batch.csv` as a template. The API validates each row and returns failure probability, Healthy/Warning/High risk, anomaly status/score, and local top drivers. The page can filter by category and download all results. Batch scoring does not automatically persist rows; manual **Analyze & save machine** does.

## Main API routes

- `GET /api/v1/assets/summary` — dashboard counts
- `GET /api/v1/assets?category=high` — filtered asset queue
- `GET /api/v1/machines/{machine_id}` — lookup and auto-fill data
- `POST /api/v1/assets` — analyze and store a manual snapshot
- `POST /api/v1/predict` — analyze without storing
- `POST /api/v1/predict/batch` — validate and score a CSV
- `GET /api/v1/model/info` — versioned model metadata

## Verification

```powershell
pytest
ruff check backend ml scripts
cd frontend
npm run lint
npm test
npm run build
```

MachineGuard is decision-support software, not a certified safety system. Qualified personnel remain responsible for inspection and maintenance decisions.
