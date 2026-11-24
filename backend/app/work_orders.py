import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, StrictBool, StringConstraints, field_validator

from .diagnostic_schemas import Diagnosis

Status = Literal["open", "in_progress", "resolved"]
Priority = Literal["low", "medium", "high"]
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
NEXT_STATUS = {"open": "in_progress", "in_progress": "resolved"}


class WorkOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    diagnosis_id: Identifier
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    issue_description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]
    priority: Priority
    maintenance_notes: Notes = ""
    confirmed: StrictBool

    @field_validator("confirmed")
    @classmethod
    def require_confirmation(cls, confirmed: bool) -> bool:
        if not confirmed:
            raise ValueError("Confirm that you reviewed the diagnosis before creating the order.")
        return confirmed


class WorkOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status | None = None
    maintenance_notes: Notes | None = None


class WorkOrderSummary(BaseModel):
    work_order_id: str
    diagnosis_id: str
    device_id: str
    title: str
    priority: Priority
    status: Status
    created_at: str
    updated_at: str
    diagnostic_mode: Literal["openai", "retrieval_only"]


class WorkOrder(WorkOrderSummary):
    issue_description: str
    maintenance_notes: str
    diagnostic_snapshot: Diagnosis


class WorkOrderPage(BaseModel):
    items: list[WorkOrderSummary]
    counts: dict[Status, int]
    total: int


class WorkOrderConflict(ValueError):
    pass


class WorkOrderStore:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def initialize(self) -> None:
        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS maintenance_work_orders (
                    work_order_id TEXT PRIMARY KEY,
                    diagnosis_id TEXT NOT NULL UNIQUE
                        REFERENCES diagnostic_history(diagnosis_id),
                    device_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    issue_description TEXT NOT NULL,
                    priority TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high')),
                    status TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'resolved')),
                    maintenance_notes TEXT NOT NULL,
                    diagnostic_snapshot TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS maintenance_work_orders_newest
                ON maintenance_work_orders (created_at DESC, work_order_id DESC)
                """)

    @staticmethod
    def _detail(row: sqlite3.Row) -> WorkOrder:
        fields = dict(row)
        snapshot = Diagnosis.model_validate_json(fields.pop("diagnostic_snapshot"))
        return WorkOrder(**fields, diagnostic_mode=snapshot.mode, diagnostic_snapshot=snapshot)

    def create(self, payload: WorkOrderCreate) -> WorkOrder:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            diagnosis = db.execute(
                "SELECT snapshot_json FROM diagnostic_history WHERE diagnosis_id = ?",
                (payload.diagnosis_id,),
            ).fetchone()
            if diagnosis is None:
                raise KeyError("Diagnosis not found.")
            if db.execute(
                "SELECT 1 FROM maintenance_work_orders WHERE diagnosis_id = ?",
                (payload.diagnosis_id,),
            ).fetchone():
                raise WorkOrderConflict("A work order already exists for this diagnosis.")
            snapshot = Diagnosis.model_validate_json(diagnosis["snapshot_json"])
            work_order_id = uuid4().hex
            now = datetime.now(timezone.utc).isoformat()
            row = db.execute("""
                INSERT INTO maintenance_work_orders (
                    work_order_id, diagnosis_id, device_id, title, issue_description,
                    priority, status, maintenance_notes, diagnostic_snapshot, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?) RETURNING *
                """, (
                work_order_id, payload.diagnosis_id, snapshot.device_id, payload.title,
                payload.issue_description, payload.priority, payload.maintenance_notes,
                snapshot.model_dump_json(), now, now,
            )).fetchone()
            return self._detail(row)

    def get(self, work_order_id: str) -> WorkOrder | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM maintenance_work_orders WHERE work_order_id = ?", (work_order_id,),
            ).fetchone()
            return self._detail(row) if row else None

    def list(self, status: Status | None, limit: int, offset: int) -> WorkOrderPage:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN")
            counts = dict.fromkeys(("open", "in_progress", "resolved"), 0)
            counts.update(db.execute("""
                SELECT status, COUNT(*) FROM maintenance_work_orders GROUP BY status
                """).fetchall())
            rows = db.execute("""
                SELECT work_order_id, diagnosis_id, device_id, title, priority, status,
                       created_at, updated_at,
                       json_extract(diagnostic_snapshot, '$.mode') AS diagnostic_mode
                FROM maintenance_work_orders WHERE (? IS NULL OR status = ?)
                ORDER BY created_at DESC, work_order_id DESC LIMIT ? OFFSET ?
                """, (status, status, limit, offset)).fetchall()
            return WorkOrderPage(
                items=[WorkOrderSummary.model_validate(dict(row)) for row in rows],
                counts=counts, total=counts[status] if status else sum(counts.values()),
            )

    def update(self, work_order_id: str, payload: WorkOrderUpdate) -> WorkOrder:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM maintenance_work_orders WHERE work_order_id = ?", (work_order_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Work order not found.")
            current = row["status"]
            status = payload.status or current
            notes = payload.maintenance_notes
            if status != current and NEXT_STATUS.get(current) != status:
                raise WorkOrderConflict("Allowed transitions are Open → In Progress → Resolved.")
            if status == "resolved" and (notes == "" or (status != current and not notes)):
                raise ValueError("Enter maintenance results before resolving a work order.")
            row = db.execute("""
                UPDATE maintenance_work_orders SET status = ?,
                    maintenance_notes = COALESCE(?, maintenance_notes), updated_at = ?
                WHERE work_order_id = ? RETURNING *
                """, (status, notes, datetime.now(timezone.utc).isoformat(), work_order_id)
            ).fetchone()
            return self._detail(row)
