import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.diagnostic_schemas import Diagnosis
from backend.app.main import app

URL = "/api/v1/work-orders"


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    path = tmp_path / "orders.db"
    monkeypatch.setattr(settings, "database_path", path)
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "openlux_api_key", None)
    return path


def diagnostic_record(client):
    result = client.post("/api/v1/diagnostics", json={
        "device_id": "HYD-0001", "question": "What are possible low system pressure checks?",
    })
    assert result.status_code == 201
    return result.json()


def payload(diagnosis_id):
    return {
        "diagnosis_id": diagnosis_id, "title": "Review pressure readings",
        "issue_description": "Verify this hypothesis against the recorded pressure.",
        "priority": "medium", "maintenance_notes": "Arrange a qualified review.", "confirmed": True,
    }


def test_creation_preserves_snapshot_and_concurrent_clicks_create_once(isolated_database):
    with TestClient(app) as client:
        source = diagnostic_record(client)
        body = payload(source["diagnosis_id"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(lambda _: client.post(URL, json=body), range(2)))
        assert sorted(reply.status_code for reply in replies) == [201, 409]
        result = next(reply.json() for reply in replies if reply.status_code == 201)
        assert result["status"] == "open"
        assert result["device_id"] == source["device_id"]
        assert result["diagnostic_mode"] == "retrieval_only"
        assert result["diagnostic_snapshot"] == source
        assert result["created_at"] == result["updated_at"]
        assert source["evidence_references"]
        document_id = source["evidence_references"][0]["document_id"]
        assert client.delete(f"/api/v1/knowledge/documents/{document_id}").status_code == 204

    with TestClient(app) as client:
        assert client.get(f"{URL}/{result['work_order_id']}").json() == result
        assert client.get(URL).json()["counts"] == {"open": 1, "in_progress": 0, "resolved": 0}
    with sqlite3.connect(isolated_database) as db:
        assert db.execute("SELECT COUNT(*) FROM maintenance_work_orders").fetchone() == (1,)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_status_transitions_and_global_counts_with_filters():
    with TestClient(app) as client:
        source = diagnostic_record(client)
        result = client.post(URL, json=payload(source["diagnosis_id"])).json()
        details = f"{URL}/{result['work_order_id']}"
        assert client.patch(details, json={"status": "resolved",
                                          "maintenance_notes": "Checked."}).status_code == 409
        started = client.patch(details, json={"status": "in_progress"})
        assert started.json()["status"] == "in_progress"
        assert client.patch(details, json={"status": "open"}).status_code == 409
        assert client.patch(details, json={"status": "resolved"}).status_code == 422
        assert client.patch(details, json={"status": "resolved",
                                          "maintenance_notes": "  "}).status_code == 422
        resolved = client.patch(details, json={
            "status": "resolved", "maintenance_notes": "Verified the maintenance record.",
        }).json()
        assert resolved["status"] == "resolved"
        assert resolved["maintenance_notes"] == "Verified the maintenance record."
        assert resolved["created_at"] == result["created_at"]
        assert resolved["updated_at"] >= result["updated_at"]
        assert resolved["diagnostic_snapshot"] == source
        assert client.patch(details, json={"status": "in_progress"}).status_code == 409
        assert client.patch(details, json={"maintenance_notes": ""}).status_code == 422
        amended = client.patch(details, json={"maintenance_notes": "Review documented."}).json()
        assert amended["maintenance_notes"] == "Review documented."
        listing = client.get(URL, params={"status": "open", "limit": 1}).json()
        assert listing == {"items": [], "counts": {"open": 0, "in_progress": 0, "resolved": 1},
                           "total": 0}
        page = client.get(URL, params={"status": "resolved", "offset": 1}).json()
        assert page["total"] == 1 and page["items"] == []


def test_cloud_provenance_and_latest_first_list():
    with TestClient(app) as client:
        fallback = diagnostic_record(client)
        # Synthetic provider response metadata for this unit test only. No LLM request.
        synthetic = Diagnosis.model_validate({
            **fallback, "diagnosis_id": "synthetic-cloud-test", "mode": "openai",
            "llm_provider": "openlux", "openai_model": "synthetic-test-model",
        })
        app.state.diagnostic_history.save(synthetic)
        original = client.post(URL, json=payload(fallback["diagnosis_id"])).json()
        cloud = client.post(URL, json=payload(synthetic.diagnosis_id)).json()
        assert cloud["diagnostic_snapshot"] == synthetic.model_dump()
        assert cloud["diagnostic_mode"] == "openai"
        page = client.get(URL, params={"limit": 1}).json()
        assert page["total"] == 2
        assert page["items"][0]["work_order_id"] == cloud["work_order_id"]
        page = client.get(URL, params={"limit": 1, "offset": 1}).json()
        assert page["items"][0]["work_order_id"] == original["work_order_id"]


def test_work_order_validation_and_missing_records():
    with TestClient(app) as client:
        assert client.post(URL, json=payload("missing")).status_code == 404
        assert client.get(f"{URL}/missing").status_code == 404
        assert client.patch(f"{URL}/missing", json={"status": "resolved"}).status_code == 404
        assert client.get(URL, params={"status": "unknown"}).status_code == 422
        assert client.get(URL, params={"limit": 51}).status_code == 422
        source = diagnostic_record(client)
        body = payload(source["diagnosis_id"])
        for invalid in (
            {"confirmed": False}, {"confirmed": 1}, {"priority": "urgent"}, {"title": " "},
            {"issue_description": " "}, {"device_id": "spoofed"},
            {"diagnostic_snapshot": {"spoofed": True}},
        ):
            assert client.post(URL, json={**body, **invalid}).status_code == 422
        missing_confirmation = {key: value for key, value in body.items() if key != "confirmed"}
        assert client.post(URL, json=missing_confirmation).status_code == 422
        order = client.post(URL, json=body).json()
        url = f"{URL}/{order['work_order_id']}"
        for invalid in ({}, {"status": "closed"}, {"priority": "high"}):
            assert client.patch(url, json=invalid).status_code == 422
