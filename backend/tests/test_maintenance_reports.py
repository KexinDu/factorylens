from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.diagnostic_schemas import Diagnosis
from backend.app.main import app
from backend.app.maintenance_reports import render_report, report_download


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", tmp_path / "reports.db")
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "openlux_api_key", None)
    with TestClient(app) as client:
        yield client


def stored_diagnosis(client) -> Diagnosis:
    result = client.post("/api/v1/diagnostics", json={
        "device_id": "HYD-0001", "question": "What might unusually low system pressure indicate?",
    })
    assert result.status_code == 201
    return Diagnosis.model_validate(result.json())


def test_report_escapes_markdown_and_preserves_literal_evidence(client):
    diagnosis = stored_diagnosis(client)
    text = "油温\n````\n# Not a heading\n<script>example</script>"
    item = diagnosis.evidence_references[0].model_copy(update={
        "text": text, "filename": "[unsafe](test)<script>|.md",
    })
    diagnosis = diagnosis.model_copy(update={
        "question": text, "evidence_references": [item], "diagnosis_id": "../../evil\r\n",
    })
    when = datetime(2026, 11, 24, tzinfo=timezone.utc)
    report = render_report(diagnosis, generated_at=when)
    assert report == render_report(diagnosis, generated_at=when)
    assert f"`````text\n{text}\n`````" in report
    assert r"\[unsafe\](test)&lt;script&gt;\|.md" in report
    assert "## Recorded sensor measurements" in report
    header = report_download(diagnosis).headers["content-disposition"]
    assert "../" not in header and "\r" not in header and "\n" not in header


def test_fallback_report_and_missing_records(client):
    diagnosis = stored_diagnosis(client).model_copy(update={
        "evidence_references": [], "openai_model": None, "diagnosis_id": "no-evidence",
    })
    app.state.diagnostic_history.save(diagnosis)
    reply = client.get(
        "/api/v1/diagnostics/no-evidence/report", headers={"Origin": "http://127.0.0.1:5173"},
    )
    assert reply.status_code == 200
    assert reply.headers["content-type"] == "text/markdown; charset=utf-8"
    assert reply.headers["content-disposition"] == (
        'attachment; filename="factorylens-diagnosis-no-evidence.md"'
    )
    assert reply.headers["access-control-expose-headers"] == "Content-Disposition"
    assert "Retrieval-only fallback" in reply.text
    assert "Generative AI diagnosis did not complete" in reply.text
    assert "No relevant evidence was recorded." in reply.text
    assert "°C" in reply.text and "7.9939%" in reply.text
    assert client.get("/api/v1/diagnostics/absent/report").status_code == 404
    assert client.get("/api/v1/work-orders/absent/report").status_code == 404


@pytest.mark.parametrize(
    ("provider", "label"), [("openlux", "OpenLux"), ("openai", "OpenAI direct")],
)
def test_cloud_and_order_reports_use_saved_evidence(client, provider, label):
    # Test fixture only. The provider and model are labels on a local snapshot.
    cloud = stored_diagnosis(client).model_copy(update={
        "diagnosis_id": "mock-cloud", "mode": "openai", "llm_provider": provider,
        "openai_model": "example-test-model", "summary": "Compare comparable operating conditions.",
    })
    app.state.diagnostic_history.save(cloud)
    cloud_report = client.get("/api/v1/diagnostics/mock-cloud/report")
    assert f"Provider: {label}" in cloud_report.text
    assert "Model: example-test-model" in cloud_report.text
    order = client.post("/api/v1/work-orders", json={
        "diagnosis_id": cloud.diagnosis_id, "title": "Inspect test rig",
        "issue_description": "Study pressure deviations", "priority": "medium", "confirmed": True,
    }).json()
    url = f"/api/v1/work-orders/{order['work_order_id']}"
    assert client.patch(url, json={"status": "in_progress"}).status_code == 200
    assert client.patch(url, json={
        "status": "resolved", "maintenance_notes": "验收完成。\n```\nDetails remain literal.",
    }).status_code == 200
    evidence = cloud.evidence_references[0]
    assert client.delete(f"/api/v1/knowledge/documents/{evidence.document_id}").status_code == 204
    reply = client.get(f"{url}/report")
    assert reply.headers["content-disposition"].startswith('attachment; filename="factorylens-work')
    assert "Status: Resolved" in reply.text
    assert "Priority: medium" in reply.text
    assert "验收完成。" in reply.content.decode("utf-8")
    assert evidence.text in reply.text
    assert evidence.reference_id in reply.text
    assert "Compare comparable operating conditions." in reply.text
