# FactoryLens maintenance work orders

Start from a current diagnostic result or open one from **Diagnostic history**.
Choose **Create Work Order**, edit the title and issue, select a priority,
and confirm that you reviewed the diagnosis. Both cloud diagnoses and
retrieval-only results can be used. The page marks their sources. Users select
priority after reviewing the evidence and maintenance needs.

Possible causes are hypotheses for qualified personnel to verify. FactoryLens
is an industrial education prototype. An order tracks a review or maintenance
task. A person remains responsible for decisions and any physical work.

## SQLite

The `maintenance_work_orders` table is created at backend startup in the
configured `DATABASE_PATH`. It stores:

| Field | Meaning |
| --- | --- |
| `work_order_id` | Primary key for the task. |
| `diagnosis_id` | Unique foreign key to `diagnostic_history`. |
| `device_id` | Equipment identifier taken from the saved diagnosis. |
| `title`, `issue_description`, `priority` | Human-reviewed task fields. |
| `status`, `maintenance_notes` | Current workflow state and editable handling notes. |
| `diagnostic_snapshot` | Server-generated copy of the full diagnosis, including mode, provider, model, device measurements, ML findings and citation text. |
| `created_at`, `updated_at` | UTC timestamps. |

Creation reads the stored diagnosis and writes the order in a single SQLite
transaction. A unique diagnosis ID permits one work order per diagnosis and
prevents duplicate creation even if two requests arrive together. The new
order stores its own evidence text, so future edits and deletions in the
knowledge base do not change that snapshot.

## API

All paths are relative to `/api/v1/work-orders`.

| Method and path | Input and result |
| --- | --- |
| `POST /` | `diagnosis_id`, `title`, `issue_description`, `priority`, optional `maintenance_notes`, and `confirmed: true`. Returns 201 and the detail. |
| `GET /` | Optional `status`, `limit` from 1–50, and `offset` from 0. Returns `items`, filtered `total`, and global `counts`. |
| `GET /{work_order_id}` | Returns the detail, including the original snapshot. |
| `PATCH /{work_order_id}` | Updates `status`, `maintenance_notes`, or both. Returns the updated detail. |

Priorities are `low`, `medium`, and `high`. States are `open`,
`in_progress`, and `resolved`. A status update can retain the current state
or move one step forward, from Open to In Progress to Resolved. Include
nonblank handling notes when resolving the order. Resolved orders can retain
their status while the maintenance results are amended. Their notes must stay
nonblank. The backend returns 404 for unknown records, 409 for duplicates or
disallowed transitions, and 422 for invalid fields or missing required notes.

## Verify on a test database

1. Start the backend with a separate `DATABASE_PATH`. Use a copy containing a
   prior diagnosis or generate a local retrieval-only diagnosis.
2. Open the saved diagnosis and open the work order form. Check that creation
   requires review confirmation and explicit priority selection.
3. Create the work order, open its detail, and confirm the diagnostic snapshot
   carries the source mode and citations.
4. Move the order to In Progress. Enter handling notes and resolve it.
   Filter the list by state and verify that the global counts remain accurate.
5. Restart against the same test database and reopen the order.

Run pytest and Ruff at the repository root, and Vitest, ESLint and the
production build from `frontend`. Work order tests use temporary SQLite
databases and make zero live model requests.

The MVP stores the current status and notes. Assignments, per-user permissions,
approval flows, lifecycle audit logs, and report export are future work.
