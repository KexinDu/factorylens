import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app

VALID = {
    "machine_id": "MANUAL-TEST-2048",
    "pressure_bar": 160.6735,
    "oil_temperature_c": 35.622,
    "motor_power_w": 2538.9294,
    "volume_flow_lpm": 6.7098,
    "vibration_mms": 0.577,
}


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", tmp_path / "machineguard-test.db")


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["models_loaded"] is True


def test_valid_prediction_schema():
    with TestClient(app) as client:
        response = client.post("/api/v1/predict", json=VALID)
        assert response.status_code == 200
        assert 0 <= response.json()["failure_probability"] <= 1
        assert response.json()["risk_level"] in {"healthy", "warning", "high"}
        assert response.json()["top_factors"]


def test_invalid_prediction_rejected():
    with TestClient(app) as client:
        response = client.post("/api/v1/predict", json={**VALID, "pressure_bar": -1})
        assert response.status_code == 422


def test_machine_lookup_returns_details_and_assessment():
    with TestClient(app) as client:
        response = client.get("/api/v1/machines/HYD-0001")
        assert response.status_code == 200
        body = response.json()
        assert body["machine"]["machine_id"] == "HYD-0001"
        assert 0 <= body["assessment"]["failure_probability"] <= 1


def test_unknown_machine_lookup_returns_404():
    with TestClient(app) as client:
        response = client.get("/api/v1/machines/UNKNOWN")
        assert response.status_code == 404


def test_batch_csv():
    csv = (
        "machine_id,pressure_bar,oil_temperature_c,motor_power_w,volume_flow_lpm,vibration_mms\n"
        "M-1,160.67,35.62,2538.93,6.71,0.577\n"
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/predict/batch", files={"file": ("machines.csv", csv, "text/csv")}
        )
        assert response.status_code == 200
        assert response.json()["count"] == 1


def test_manual_asset_is_saved_and_autofilled_by_lookup():
    with TestClient(app) as client:
        saved = client.post("/api/v1/assets", json=VALID)
        assert saved.status_code == 200
        assert saved.json()["source"] == "Manual entry"
        lookup = client.get(f"/api/v1/machines/{VALID['machine_id']}")
        assert lookup.status_code == 200
        assert lookup.json()["machine"]["pressure_bar"] == VALID["pressure_bar"]


def test_dashboard_summary_and_category_list():
    with TestClient(app) as client:
        summary = client.get("/api/v1/assets/summary")
        assets = client.get("/api/v1/assets?category=high&limit=5")
        assert summary.status_code == 200
        assert summary.json()["total"] >= 2205
        assert assets.status_code == 200
        assert all(item["risk_level"] == "high" for item in assets.json()["results"])
