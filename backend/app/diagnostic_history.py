import sqlite3
from contextlib import closing
from pathlib import Path

from .diagnostic_schemas import Diagnosis, DiagnosticSummary


class DiagnosticHistory:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS diagnostic_history (
                    diagnosis_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    mode TEXT NOT NULL CHECK(mode IN ('openai', 'retrieval_only')),
                    openai_model TEXT,
                    snapshot_json TEXT NOT NULL
                )
                """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS diagnostic_history_newest
                ON diagnostic_history (created_at DESC, diagnosis_id DESC)
                """)

    def save(self, diagnosis: Diagnosis) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT INTO diagnostic_history VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    diagnosis.diagnosis_id, diagnosis.created_at, diagnosis.device_id,
                    diagnosis.question, diagnosis.mode, diagnosis.openai_model,
                    diagnosis.model_dump_json(),
                ),
            )

    def list(self, limit: int, offset: int) -> list[DiagnosticSummary]:
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            return [DiagnosticSummary.model_validate(dict(row)) for row in db.execute("""
                SELECT diagnosis_id, created_at, device_id, question, mode, openai_model,
                       COALESCE(json_extract(snapshot_json, '$.llm_provider'), 'openai')
                           AS llm_provider
                FROM diagnostic_history ORDER BY created_at DESC, diagnosis_id DESC
                LIMIT ? OFFSET ?
                """, (limit, offset))]

    def get(self, diagnosis_id: str) -> Diagnosis | None:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute(
                "SELECT snapshot_json FROM diagnostic_history WHERE diagnosis_id = ?",
                (diagnosis_id,),
            ).fetchone()
        return Diagnosis.model_validate_json(row[0]) if row else None
