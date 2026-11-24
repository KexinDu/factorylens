import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "./services/api";
import type { Diagnosis, WorkOrder, WorkOrderPriority } from "./types";
import "./work-orders.css";

export const maintenanceNotice =
  "Industrial education prototype. Treat diagnostic causes as hypotheses. Qualified personnel must verify findings and decide on maintenance.";

export default function WorkOrderForm({ diagnosis }: { diagnosis: Diagnosis }) {
  const [expanded, setExpanded] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<WorkOrder>();
  const submitting = useRef(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (submitting.current || created || !form.has("confirmed")) return;
    submitting.current = true;
    setPending(true);
    setError("");
    try {
      setCreated(
        await api.createWorkOrder({
          diagnosis_id: diagnosis.diagnosis_id,
          title: String(form.get("title")),
          issue_description: String(form.get("issue_description")),
          priority: String(form.get("priority")) as WorkOrderPriority,
          maintenance_notes: String(form.get("maintenance_notes")),
          confirmed: true,
        }),
      );
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not create work order.",
      );
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  return (
    <section className="panel work-order-panel">
      {created ? (
        <p role="status">
          Work order created.{" "}
          <Link
            to={`/work-orders?order=${encodeURIComponent(created.work_order_id)}`}
          >
            View work order
          </Link>
        </p>
      ) : !expanded ? (
        <button
          type="button"
          className="secondary"
          onClick={() => setExpanded(true)}
        >
          Create Work Order
        </button>
      ) : (
        <>
          <h3>Create work order for {diagnosis.device_id}</h3>
          {diagnosis.mode === "retrieval_only" && (
            <p>Source diagnosis: Retrieval-only fallback.</p>
          )}
          <p>{maintenanceNotice}</p>
          <p>
            Choose the priority after reviewing the evidence and maintenance
            needs.
          </p>
          <form onSubmit={submit}>
            <fieldset disabled={pending}>
              <label>
                Title
                <input
                  name="title"
                  required
                  maxLength={120}
                  defaultValue={`Inspect ${diagnosis.device_id}`}
                />
              </label>
              <label>
                Issue description
                <textarea
                  name="issue_description"
                  required
                  maxLength={4000}
                  rows={3}
                  defaultValue={diagnosis.question}
                />
              </label>
              <label>
                Priority
                <select name="priority" defaultValue="" required>
                  <option value="" disabled>
                    Select a priority
                  </option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </label>
              <label>
                Maintenance notes
                <textarea name="maintenance_notes" maxLength={4000} rows={3} />
              </label>
              <label className="work-order-confirm">
                <input type="checkbox" name="confirmed" required />I reviewed
                the diagnosis and confirm creation of this work order.
              </label>
              <div className="knowledge-actions">
                <button type="submit" className="primary">
                  {pending ? "Creating…" : "Confirm and create"}
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setExpanded(false);
                    setError("");
                  }}
                >
                  Cancel
                </button>
              </div>
            </fieldset>
          </form>
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
