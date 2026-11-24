import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.knowledge import parse_document, split_document
from backend.app.main import app

BASE = "/api/v1/knowledge"


@pytest.fixture
def database(tmp_path, monkeypatch):
    path = tmp_path / "knowledge.db"
    monkeypatch.setattr(settings, "database_path", path)
    return path


def test_parse_utf8_bom_and_normalize_whitespace():
    content = b"\xef\xbb\xbf  First line  \r\nSecond line\r\n"
    assert parse_document("guide.TXT", content) == "First line\nSecond line"


def test_chunks_keep_sections_order_overlap_and_limit():
    text = "# Pressure\n" + "abcdefghijklmnopqrstuvwxyz" * 3 + "\n## Flow\nCheck flow."
    chunks = split_document(text, 35, 6, markdown=True)
    assert [heading for heading, _ in chunks] == ["Pressure", "Pressure", "Pressure", "Flow"]
    assert all(len(excerpt) <= 35 for _, excerpt in chunks)
    assert chunks[0][1][-6:] == chunks[1][1][:6]
    assert chunks[-1][1] == "## Flow\nCheck flow."


def test_document_lifecycle_and_search_across_restart(database):
    content = b"# Calibration\r\nInspect the zephyr calibration reference."
    with TestClient(app) as client:
        response = client.post(
            f"{BASE}/documents",
            files={"file": ("reference.md", content)},
            data={"source": "Test workshop notes"},
        )
        assert response.status_code == 201
        document = response.json()
        document_id = document["document_id"]
        assert document["uploaded_at"]
        assert document["chunk_count"] == 1
        duplicate = client.post(
            f"{BASE}/documents", files={"file": ("renamed.txt", content.replace(b"\r", b""))}
        )
        assert duplicate.status_code == 409

    with TestClient(app) as client:
        assert document in client.get(f"{BASE}/documents").json()
        url = f"{BASE}/documents/{document_id}"
        detail = client.get(url).json()
        chunk, = detail["chunks"]
        assert chunk["filename"] == "reference.md"
        assert chunk["heading"] == "Calibration"
        assert chunk["position"] == 1
        query = {"q": "zephyr calibration", "top_k": 1}
        match, = client.get(f"{BASE}/search", params=query).json()
        assert match["chunk_id"] == chunk["chunk_id"]
        assert match["source"] == "Test workshop notes"
        assert 0 < match["score"] <= 1
        assert client.delete(url).status_code == 204
        assert client.get(url).status_code == 404
        assert client.delete(url).status_code == 404
        assert client.get(f"{BASE}/search", params={"q": "zephyr"}).json() == []
        with sqlite3.connect(database) as db:
            assert db.execute(
                "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ?", (document_id,)
            ).fetchone()[0] == 0


def test_search_examples_and_no_match(database):
    with TestClient(app) as client:
        first, = client.get(
            f"{BASE}/search", params={"q": "low system pressure abnormalities", "top_k": 1}
        ).json()
        assert first["heading"] == "Pressure abnormalities"
        assert "educational demonstration" in first["source"]
        assert client.get(f"{BASE}/search", params={"q": "galaxy cryptocurrency"}).json() == []
        assert client.get(f"{BASE}/search", params={"q": "the or"}).json() == []
        invalid_top_k = client.get(f"{BASE}/search", params={"q": "pressure", "top_k": 21})
        assert invalid_top_k.status_code == 422
        assert client.get(f"{BASE}/search", params={"q": " "}).status_code == 400
        assert client.get(f"{BASE}/search", params={"q": "x" * 301}).status_code == 422


@pytest.mark.parametrize(
    ("filename", "content", "status", "message"),
    [
        ("guide.exe", b"text", 400, "Only .txt"),
        ("guide.txt", b"", 400, "empty"),
        ("guide.txt", b"\xff", 400, "UTF-8"),
        ("guide.txt", b"bad\x00text", 400, "binary"),
        ("guide.md", b"x" * 131_073, 413, "upload limit"),
    ],
    ids=["extension", "empty", "encoding", "binary", "size"],
)
def test_invalid_uploads(database, filename, content, status, message):
    with TestClient(app) as client:
        response = client.post(f"{BASE}/documents", files={"file": (filename, content)})
        assert response.status_code == status
        assert message in response.json()["detail"]


def test_upload_txt_and_example_deletion_persists(database):
    with TestClient(app) as client:
        example = client.get(f"{BASE}/documents").json()[0]
        url = f"{BASE}/documents/{example['document_id']}"
        assert client.delete(url).status_code == 204
        response = client.post(
            f"{BASE}/documents", files={"file": ("plain.txt", b"Check reference records.")}
        )
        assert response.status_code == 201
        assert response.json()["source"] == "User upload"
    with TestClient(app) as client:
        assert client.get(url).status_code == 404
        assert len(client.get(f"{BASE}/documents").json()) == 3
