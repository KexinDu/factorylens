import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { DiagnosticResult } from "./DiagnosticCopilot";
import ReportDownload from "./ReportDownload";
import { api } from "./services/api";
import type { WorkOrder, WorkOrderPage, WorkOrderStatus } from "./types";
import { maintenanceNotice } from "./WorkOrderForm";

const labels = {
  open: "Open",
  in_progress: "In Progress",
  resolved: "Resolved",
} as const;
const statuses = Object.keys(labels) as WorkOrderStatus[];
const nextStatus = {
  open: "in_progress",
  in_progress: "resolved",
  resolved: null,
} as const;
const pageSize = 20;
const message = (error: unknown) =>
  error instanceof Error ? error.message : "Work order request failed.";

function WorkOrderDetail({
  order,
  onSave,
}: {
  order: WorkOrder;
  onSave: (order: WorkOrder) => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [status, setStatus] = useState(order.status);
  const next = nextStatus[order.status];

  async function update(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    setSaved(false);
    try {
      const updated = await api.updateWorkOrder(order.work_order_id, {
        status,
        maintenance_notes: String(form.get("maintenance_notes")),
      });
      onSave(updated);
      setSaved(true);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="panel" aria-label="Work order details">
      <h3>{order.title}</h3>
      <p>
        {order.device_id} · {labels[order.status]} · {order.priority} priority
      </p>
      <p>Work order {order.work_order_id}</p>
      <p>Diagnosis {order.diagnosis_id}</p>
      <h4>Issue description</h4>
      <div className="knowledge-excerpt">{order.issue_description}</div>
      <form key={order.updated_at} onSubmit={update}>
        <fieldset disabled={pending}>
          <label>
            Work order status
            <select
              value={status}
              onChange={(event) =>
                setStatus(event.target.value as WorkOrderStatus)
              }
            >
              <option value={order.status}>{labels[order.status]}</option>
              {next && <option value={next}>{labels[next]}</option>}
            </select>
          </label>
          <label>
            Maintenance notes
            <textarea
              name="maintenance_notes"
              rows={4}
              maxLength={4000}
              defaultValue={order.maintenance_notes}
              required={status === "resolved"}
            />
          </label>
          {status === "resolved" && (
            <small>Enter the maintenance result or handling notes.</small>
          )}
          <button type="submit" className="primary">
            {pending ? "Saving…" : "Save changes"}
          </button>
        </fieldset>
      </form>
      {saved && <p role="status">Work order updated.</p>}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <p>{maintenanceNotice}</p>
      <ReportDownload kind="work-orders" recordId={order.work_order_id} />
      <details>
        <summary>Original diagnostic snapshot</summary>
        <DiagnosticResult result={order.diagnostic_snapshot} />
      </details>
    </section>
  );
}

export default function WorkOrders() {
  const [params] = useSearchParams();
  const id = params.get("order");
  const [filter, setFilter] = useState<WorkOrderStatus | "">("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<WorkOrderPage>();
  const [order, setOrder] = useState<WorkOrder>();
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    setPage(undefined);
    setListError("");
    api
      .workOrders(filter, pageSize, offset)
      .then((data) => {
        if (active) setPage(data);
      })
      .catch((cause: unknown) => {
        if (active) setListError(message(cause));
      });
    return () => {
      active = false;
    };
  }, [filter, offset, revision]);

  useEffect(() => {
    let active = true;
    setOrder(undefined);
    setDetailError("");
    if (id) {
      api
        .workOrder(id)
        .then((data) => {
          if (active) setOrder(data);
        })
        .catch((cause: unknown) => {
          if (active) setDetailError(message(cause));
        });
    }
    return () => {
      active = false;
    };
  }, [id]);

  return (
    <div className="page knowledge-page work-order-page">
      <div className="page-intro">
        <h2>Maintenance Work Orders</h2>
        <p>{maintenanceNotice}</p>
      </div>
      <div className="knowledge-grid">
        {statuses.map((status) => (
          <section className="panel" key={status}>
            <h3>{labels[status]}</h3>
            <strong aria-label={`${labels[status]} count`}>
              {page?.counts[status] ?? "—"}
            </strong>
          </section>
        ))}
      </div>
      <section className="panel">
        <h3>Work orders</h3>
        <label>
          Status filter
          <select
            value={filter}
            onChange={(event) => {
              setFilter(event.target.value as WorkOrderStatus | "");
              setOffset(0);
            }}
          >
            <option value="">All statuses</option>
            {statuses.map((status) => (
              <option key={status} value={status}>
                {labels[status]}
              </option>
            ))}
          </select>
        </label>
        {listError && (
          <p className="error" role="alert">
            {listError}
          </p>
        )}
        {!page && !listError && <p role="status">Loading work orders…</p>}
        {page?.items.length === 0 && <p>No work orders match this filter.</p>}
        {page?.items.map((item) => (
          <article className="knowledge-item" key={item.work_order_id}>
            <h4>
              <Link
                to={`/work-orders?order=${encodeURIComponent(item.work_order_id)}`}
              >
                {item.title}
              </Link>
            </h4>
            <p>
              {item.device_id} · {labels[item.status]} · {item.priority}{" "}
              priority
            </p>
            <small>
              {item.work_order_id} ·{" "}
              {new Date(item.created_at).toLocaleString()} ·{" "}
              {item.diagnostic_mode === "openai"
                ? "Cloud diagnosis"
                : "Retrieval-only fallback"}
            </small>
          </article>
        ))}
        {page && (offset > 0 || page.total > pageSize) && (
          <div className="knowledge-actions">
            <button
              className="secondary"
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - pageSize))}
            >
              Previous
            </button>
            <button
              className="secondary"
              type="button"
              disabled={offset + pageSize >= page.total}
              onClick={() => setOffset(offset + pageSize)}
            >
              Next
            </button>
          </div>
        )}
      </section>
      {detailError && (
        <p className="error" role="alert">
          {detailError}
        </p>
      )}
      {id && !order && !detailError && (
        <p role="status">Loading work order details…</p>
      )}
      {order && order.work_order_id === id && (
        <WorkOrderDetail
          key={order.work_order_id}
          order={order}
          onSave={(updated) => {
            setOrder((current) =>
              current?.work_order_id === updated.work_order_id
                ? updated
                : current,
            );
            setOffset(0);
            setRevision((value) => value + 1);
          }}
        />
      )}
    </div>
  );
}
