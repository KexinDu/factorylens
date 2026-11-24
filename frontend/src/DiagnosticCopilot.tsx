import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "./services/api";
import WorkOrderForm from "./WorkOrderForm";
import ReportDownload from "./ReportDownload";
import type { Diagnosis, DiagnosticSummary } from "./types";
import "./diagnostic.css";

const providerLabel = (provider: DiagnosticSummary["llm_provider"]) =>
  provider === "openlux" ? "OpenLux" : "OpenAI direct";

const modeLabel = (entry: DiagnosticSummary) =>
  entry.mode === "openai"
    ? `${providerLabel(entry.llm_provider)} API`
    : "Retrieval-only fallback";

function Findings({
  title,
  items,
  diagnosis,
}: {
  title: string;
  items: Diagnosis["possible_causes"];
  diagnosis: Diagnosis;
}) {
  if (items.length === 0) return null;
  return (
    <section>
      <h4>{title}</h4>
      <ul>
        {items.map((item, index) => (
          <li key={index}>
            {item.text}{" "}
            {Array.from(new Set(item.references)).map((reference) => (
              <a key={reference} href={`#${reference}`}>
                [
                {diagnosis.evidence_references.findIndex(
                  (evidence) => evidence.reference_id === reference,
                ) + 1}
                ]
              </a>
            ))}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function DiagnosticResult({ result }: { result: Diagnosis }) {
  const data = result.observed_signals;
  const model = result.model_findings;
  return (
    <div className="diagnostic-result">
      <section className="panel">
        <h3>Diagnosis for {result.device_id}</h3>
        <p>
          <strong>{modeLabel(result)}</strong>
          {result.openai_model && ` · ${result.openai_model}`}
        </p>
        <p>{result.question}</p>
        <p>{result.summary}</p>
        <Findings
          title="Possible causes to verify"
          items={result.possible_causes}
          diagnosis={result}
        />
        <Findings
          title="Recommended checks for qualified personnel"
          items={result.recommended_checks}
          diagnosis={result}
        />
        <h4>Uncertainty</h4>
        <p>{result.uncertainty}</p>
        <h4>Limitations</h4>
        <ul>
          {result.limitations.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      </section>
      <div className="knowledge-grid">
        <section className="panel">
          <h3>Recorded measurements</h3>
          <p>Source: {result.source}</p>
          <dl>
            <dt>Pressure</dt>
            <dd>{data.pressure_bar} bar</dd>
            <dt>Oil temperature</dt>
            <dd>{data.oil_temperature_c} °C</dd>
            <dt>Motor power</dt>
            <dd>{data.motor_power_w} W</dd>
            <dt>Volume flow</dt>
            <dd>{data.volume_flow_lpm} L/min</dd>
            <dt>Vibration</dt>
            <dd>{data.vibration_mms} mm/s</dd>
          </dl>
        </section>
        <section className="panel">
          <h3>Machine learning findings</h3>
          <dl>
            <dt>Risk level</dt>
            <dd>{model.risk_level}</dd>
            <dt>Failure probability</dt>
            <dd>{(model.failure_probability * 100).toFixed(4)}%</dd>
            <dt>Isolation Forest</dt>
            <dd>
              {model.anomaly ? "Anomaly detected" : "No anomaly detected"}
            </dd>
            <dt>Anomaly score</dt>
            <dd>{model.anomaly_score}</dd>
          </dl>
          <p>{model.interpretation}</p>
        </section>
      </div>
      <section className="panel">
        <h3>Knowledge evidence</h3>
        {!result.evidence_references.length && (
          <p>No sufficiently relevant excerpts found.</p>
        )}
        {result.evidence_references.map((item, index) => (
          <article
            className="knowledge-item"
            key={item.reference_id}
            id={item.reference_id}
          >
            <h4>
              [{index + 1}] {item.filename} · Chunk {item.position}
            </h4>
            <small>
              {item.source} · Relevance {item.score.toFixed(3)}
            </small>
            {item.heading && (
              <p>
                <strong>{item.heading}</strong>
              </p>
            )}
            <div className="knowledge-excerpt">{item.text}</div>
          </article>
        ))}
      </section>
      <details className="panel">
        <summary>Tool Execution Trace ({result.trace.length})</summary>
        <ol>
          {result.trace.map((entry) => (
            <li key={entry.order}>
              <strong>{entry.tool}</strong> · {entry.origin} · {entry.status} ·{" "}
              {entry.elapsed_ms} ms
              <div>{entry.result_summary}</div>
              {Object.entries(entry.arguments).map(([key, value]) => (
                <small key={key}>
                  {key}: {value}{" "}
                </small>
              ))}
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}

export default function DiagnosticCopilot() {
  const [params] = useSearchParams();
  const [history, setHistory] = useState<DiagnosticSummary[]>();
  const [result, setResult] = useState<Diagnosis>();
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [provider, setProvider] = useState<DiagnosticSummary["llm_provider"]>();

  useEffect(() => {
    let active = true;
    api
      .diagnosticHistory()
      .then((items) => {
        if (active) setHistory(items);
      })
      .catch((cause: Error) => {
        if (active) setHistoryError(cause.message);
      });
    api
      .diagnosticConfig()
      .then((config) => {
        if (active) setProvider(config.provider);
      })
      .catch(() => {
        if (active) setProvider(undefined);
      });
    return () => {
      active = false;
    };
  }, []);

  async function run(
    message: string,
    action: () => Promise<Diagnosis>,
    save = false,
  ) {
    setError("");
    setPending(message);
    try {
      const diagnosis = await action();
      setResult(diagnosis);
      if (save) {
        setHistory((items) => [diagnosis, ...(items ?? [])].slice(0, 20));
        setHistoryError("");
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Diagnostic request failed.",
      );
    } finally {
      setPending("");
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    void run(
      "Running diagnosis…",
      () =>
        api.diagnose(
          String(form.get("device_id")),
          String(form.get("question")),
          form.has("use_openai"),
          provider,
        ),
      true,
    );
  }

  return (
    <div className="page knowledge-page diagnostic-page">
      <div className="page-intro">
        <h2>AI Diagnostic Copilot</h2>
        <p>
          Review recorded measurements, model findings and maintenance evidence
          for a selected equipment ID.
        </p>
      </div>
      <section className="panel">
        <form onSubmit={submit}>
          <label>
            Equipment ID
            <input
              name="device_id"
              defaultValue={params.get("device_id") || "HYD-0001"}
              required
              maxLength={64}
            />
          </label>
          <label>
            Diagnostic question
            <textarea
              name="question"
              required
              maxLength={500}
              rows={3}
              placeholder="What should I check if system pressure is unusually low?"
            />
          </label>
          <label className="diagnostic-consent">
            <input type="checkbox" name="use_openai" disabled={!provider} />
            {provider
              ? `Use ${providerLabel(provider)} for a public test-rig diagnosis`
              : "Cloud provider unavailable"}
          </label>
          <small>
            Cloud mode sends your question, public UCI cycle data and matching
            educational excerpts. Leave personal information out of the
            question. Uploads and manually entered equipment stay local.
          </small>
          <button
            type="submit"
            className="primary"
            disabled={!!pending || (!history && !historyError)}
          >
            Run diagnosis
          </button>
        </form>
      </section>
      <div role="status">{pending}</div>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {result && (
        <>
          <DiagnosticResult result={result} />
          <ReportDownload key={`report-${result.diagnosis_id}`} kind="diagnostics"
            recordId={result.diagnosis_id} />
          <WorkOrderForm key={result.diagnosis_id} diagnosis={result} />
        </>
      )}
      <section className="panel">
        <h3>Diagnostic history</h3>
        {historyError && <p role="alert">{historyError}</p>}
        {!history && !historyError && <p>Loading diagnostic history…</p>}
        {history?.length === 0 && <p>No diagnostics recorded yet.</p>}
        {history?.map((entry) => (
          <article className="knowledge-item" key={entry.diagnosis_id}>
            <h4>{entry.device_id}</h4>
            <p>{entry.question}</p>
            <small>
              {modeLabel(entry)}
              {entry.openai_model && ` · ${entry.openai_model}`} ·{" "}
              {new Date(entry.created_at).toLocaleString()}
            </small>
            <div className="knowledge-actions">
              <button
                type="button"
                className="secondary"
                disabled={!!pending}
                onClick={() =>
                  void run("Loading diagnosis…", () =>
                    api.diagnosisDetail(entry.diagnosis_id),
                  )
                }
              >
                View diagnosis
              </button>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
