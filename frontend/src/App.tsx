import { useEffect, useRef, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Download,
  Factory,
  FileUp,
  Gauge,
  Info,
  Menu,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import Papa from "papaparse";
import { api } from "./services/api";
import type {
  AssetListItem,
  FleetSummary,
  MachineInput,
  MachineLookupResult,
  ModelInfo,
  PredictionResult,
} from "./types";
import "./lookup.css";

const EXAMPLES: Record<string, MachineInput> = {
  Healthy: {
    machine_id: "HYD-0001",
    pressure_bar: 160.6735,
    oil_temperature_c: 35.622,
    motor_power_w: 2538.9294,
    volume_flow_lpm: 6.7098,
    vibration_mms: 0.577,
  },
  "High risk": {
    machine_id: "HYD-0211",
    pressure_bar: 156.3915,
    oil_temperature_c: 54.2676,
    motor_power_w: 2427.4004,
    volume_flow_lpm: 6.3054,
    vibration_mms: 0.6483,
  },
};
type MachineForm = Record<keyof MachineInput, string>;
const BLANK_FORM: MachineForm = {
  machine_id: "",
  pressure_bar: "",
  oil_temperature_c: "",
  motor_power_w: "",
  volume_flow_lpm: "",
  vibration_mms: "",
};
const COLORS = { healthy: "#15865d", warning: "#d28b18", high: "#d2474d" };
const percent = (value: number) => `${Math.round(value * 100)}%`;
const titleCase = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());

function Shell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  const nav = [
    ["/", "Overview", Gauge],
    ["/analysis", "Machine Analysis", Search],
    ["/batch", "Batch Analysis", FileUp],
  ] as const;
  return (
    <div className="app-shell">
      <aside className={open ? "sidebar open" : "sidebar"}>
        <div className="brand">
          <span className="brand-mark">
            <ShieldCheck />
          </span>
          <span>
            <strong>MachineGuard</strong>
            <small>AI OPERATIONS</small>
          </span>
        </div>
        <nav aria-label="Primary navigation">
          {nav.map(([path, label, Icon]) => (
            <NavLink key={label} to={path} end={path === "/"}>
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">
          <span className="status-dot" /> Models operational
          <small>Portfolio demonstration</small>
        </div>
      </aside>
      {open && (
        <button
          className="backdrop"
          aria-label="Close menu"
          onClick={() => setOpen(false)}
        />
      )}
      <main>
        <header>
          <button
            className="menu"
            aria-label="Open navigation"
            onClick={() => setOpen(true)}
          >
            <Menu />
          </button>
          <div>
            <small>INDUSTRIAL INTELLIGENCE</small>
            <h1>
              {location.pathname === "/"
                ? "Fleet overview"
                : titleCase(location.pathname.slice(1))}
            </h1>
          </div>
          <div className="demo-pill">
            <span /> Demo environment
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}

function Stat({
  label,
  value,
  detail,
  icon: Icon,
  tone = "blue",
  onClick,
  active = false,
}: {
  label: string;
  value: string;
  detail: string;
  icon: typeof Activity;
  tone?: string;
  onClick?: () => void;
  active?: boolean;
}) {
  const content = (
    <>
      <div className="stat-icon">
        <Icon />
      </div>
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
        <span>{detail}</span>
      </div>
    </>
  );
  if (onClick)
    return (
      <button
        className={`stat ${tone} selectable ${active ? "selected" : ""}`}
        onClick={onClick}
      >
        {content}
      </button>
    );
  return <article className={`stat ${tone}`}>{content}</article>;
}

function Overview() {
  const [summary, setSummary] = useState<FleetSummary>();
  const [category, setCategory] = useState("high");
  const [assets, setAssets] = useState<AssetListItem[]>([]);
  const [assetCount, setAssetCount] = useState(0);
  const [lookupId, setLookupId] = useState("HYD-0001");
  const [lookup, setLookup] = useState<MachineLookupResult>();
  const [lookupError, setLookupError] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);
  const lookupRef = useRef<HTMLElement>(null);
  useEffect(() => {
    api
      .fleetSummary()
      .then(setSummary)
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    api
      .listAssets(category)
      .then((data) => {
        setAssets(data.results);
        setAssetCount(data.count);
      })
      .catch(() => {
        setAssets([]);
        setAssetCount(0);
      });
  }, [category]);
  const searchMachine = async (event: React.FormEvent) => {
    event.preventDefault();
    setLookupLoading(true);
    setLookupError("");
    try {
      setLookup(await api.lookupMachine(lookupId));
    } catch (error) {
      setLookup(undefined);
      setLookupError(
        error instanceof Error ? error.message : "Machine lookup failed.",
      );
    } finally {
      setLookupLoading(false);
    }
  };
  const risk = ["healthy", "warning", "high"].map((name) => ({
    name: titleCase(name),
    value: summary?.[name as "healthy" | "warning" | "high"] ?? 0,
    color: COLORS[name as keyof typeof COLORS],
  }));
  const showDetails = async (machineId: string) => {
    setLookupId(machineId);
    setLookupLoading(true);
    try {
      setLookup(await api.lookupMachine(machineId));
      window.setTimeout(
        () => lookupRef.current?.scrollIntoView?.({ behavior: "smooth" }),
        50,
      );
    } finally {
      setLookupLoading(false);
    }
  };
  return (
    <div className="page">
      <section className="hero">
        <div>
          <span className="eyebrow">PREDICTIVE MAINTENANCE PLATFORM</span>
          <h2>
            Know which machines need attention—before downtime decides for you.
          </h2>
          <p>
            Failure-risk classification, unsupervised anomaly detection, and
            explainable signals in one operational view.
          </p>
          <NavLink className="primary" to="/analysis">
            <Sparkles size={17} /> Analyze a machine
          </NavLink>
        </div>
        <div className="hero-signal">
          <span>Fleet signal</span>
          <strong>
            {summary?.total
              ? `${Math.round((summary.healthy / summary.total) * 100)}%`
              : "—"}
          </strong>
          <small>Machines within healthy range</small>
          <div className="signal-bars">
            {[55, 80, 68, 94, 76, 88, 62, 86, 78, 92, 72, 89].map((h, i) => (
              <i key={i} style={{ height: `${h}%` }} />
            ))}
          </div>
        </div>
      </section>
      <div className="stats category-stats">
        <Stat
          label="ALL ASSETS"
          value={summary?.total.toLocaleString() ?? "—"}
          detail="Real operating cycles"
          icon={Factory}
          onClick={() => setCategory("all")}
          active={category === "all"}
        />
        <Stat
          label="HEALTHY"
          value={summary?.healthy.toLocaleString() ?? "—"}
          detail="Within learned range"
          icon={CheckCircle2}
          tone="green"
          onClick={() => setCategory("healthy")}
          active={category === "healthy"}
        />
        <Stat
          label="WARNING"
          value={summary?.warning.toLocaleString() ?? "—"}
          detail="Monitor or inspect"
          icon={AlertTriangle}
          tone="amber"
          onClick={() => setCategory("warning")}
          active={category === "warning"}
        />
        <Stat
          label="HIGH RISK"
          value={summary?.high.toLocaleString() ?? "—"}
          detail="Qualified review needed"
          icon={AlertTriangle}
          tone="red"
          onClick={() => setCategory("high")}
          active={category === "high"}
        />
        <Stat
          label="ANOMALIES"
          value={summary?.anomalies.toLocaleString() ?? "—"}
          detail="Unusual sensor pattern"
          icon={Activity}
          tone="amber"
          onClick={() => setCategory("anomaly")}
          active={category === "anomaly"}
        />
      </div>
      <section className="panel asset-list">
        <div className="panel-head">
          <div>
            <small>CLICKABLE FLEET QUEUE</small>
            <h3>
              {titleCase(category)} assets ({assetCount})
            </h3>
          </div>
          <span className="chip">Top 12 by risk</span>
        </div>
        <div className="asset-table">
          <table>
            <thead>
              <tr>
                <th>Machine ID</th>
                <th>Probability</th>
                <th>Risk</th>
                <th>Anomaly</th>
                <th>Source</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => (
                <tr key={asset.machine_id}>
                  <td>
                    <strong>{asset.machine_id}</strong>
                  </td>
                  <td>{percent(asset.failure_probability)}</td>
                  <td>
                    <span className={`risk-tag ${asset.risk_level}`}>
                      {titleCase(asset.risk_level)}
                    </span>
                  </td>
                  <td>{asset.anomaly ? "Detected" : "No"}</td>
                  <td>{asset.source}</td>
                  <td>
                    <button
                      className="secondary compact"
                      onClick={() => showDetails(asset.machine_id)}
                    >
                      View details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="machine-lookup" ref={lookupRef}>
        <div className="lookup-copy">
          <span className="eyebrow">MACHINE INVENTORY LOOKUP</span>
          <h3>Find an asset by machine ID</h3>
          <p>
            Search the real UCI hydraulic operating-cycle inventory or a
            manually saved machine to retrieve its sensor snapshot and live
            assessment.
          </p>
          <form onSubmit={searchMachine}>
            <label htmlFor="machine-search">Machine ID</label>
            <div>
              <input
                id="machine-search"
                value={lookupId}
                onChange={(event) => setLookupId(event.target.value)}
                placeholder="Example: HYD-0001"
                maxLength={64}
                required
              />
              <button className="primary" disabled={lookupLoading}>
                <Search size={17} />
                {lookupLoading ? "Searching…" : "Search machine"}
              </button>
            </div>
          </form>
          <div className="lookup-examples">
            Try:
            {[
              ["HYD-0001", "Healthy cycle"],
              ["HYD-0211", "Severe pump leakage"],
            ].map(([id, label]) => (
              <button key={id} onClick={() => setLookupId(id)}>
                {id} · {label}
              </button>
            ))}
          </div>
          {lookupError && (
            <div className="error" role="alert">
              <AlertTriangle /> {lookupError}
            </div>
          )}
        </div>
        <div className="lookup-result" aria-live="polite">
          {lookup ? (
            <>
              <div className="lookup-result-head">
                <div>
                  <small>{lookup.source}</small>
                  <h3>{lookup.machine.machine_id}</h3>
                  <span className={`risk-tag ${lookup.assessment.risk_level}`}>
                    {titleCase(lookup.assessment.risk_level)} risk
                  </span>
                </div>
                <div className="lookup-probability">
                  <strong>
                    {percent(lookup.assessment.failure_probability)}
                  </strong>
                  <span>Failure probability</span>
                </div>
              </div>
              <div className="lookup-sensors">
                <span>
                  Pressure{" "}
                  <strong>{lookup.machine.pressure_bar.toFixed(2)} bar</strong>
                </span>
                <span>
                  Oil temperature{" "}
                  <strong>
                    {lookup.machine.oil_temperature_c.toFixed(2)} °C
                  </strong>
                </span>
                <span>
                  Motor power{" "}
                  <strong>{lookup.machine.motor_power_w.toFixed(1)} W</strong>
                </span>
                <span>
                  Volume flow{" "}
                  <strong>
                    {lookup.machine.volume_flow_lpm.toFixed(2)} L/min
                  </strong>
                </span>
                <span>
                  Vibration{" "}
                  <strong>
                    {lookup.machine.vibration_mms.toFixed(3)} mm/s
                  </strong>
                </span>
              </div>
              <p className="lookup-anomaly">
                <Activity size={16} />
                {lookup.assessment.anomaly
                  ? "Anomalous operating pattern detected"
                  : "Operating pattern within learned range"}
              </p>
            </>
          ) : (
            <div className="lookup-empty">
              <Factory />
              <strong>No machine selected</strong>
              <span>Search an inventory ID to view its model assessment.</span>
            </div>
          )}
        </div>
      </section>
      <div className="grid">
        <section className="panel">
          <div className="panel-head">
            <div>
              <small>UCI HYDRAULIC TEST-RIG DATA</small>
              <h3>Risk distribution</h3>
            </div>
            <span className="chip">Current view</span>
          </div>
          <div className="risk-chart">
            <ResponsiveContainer width="52%" height={240}>
              <PieChart>
                <Pie
                  data={risk}
                  dataKey="value"
                  innerRadius={67}
                  outerRadius={90}
                  paddingAngle={3}
                >
                  {risk.map((x) => (
                    <Cell key={x.name} fill={x.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="legend">
              {risk.map((x) => (
                <div key={x.name}>
                  <i style={{ background: x.color }} />
                  <span>{x.name}</span>
                  <strong>{x.value}</strong>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function Field({
  label,
  name,
  value,
  unit,
  onChange,
  min,
  max,
  onBlur,
}: {
  label: string;
  name: keyof MachineInput;
  value: string | number;
  unit?: string;
  onChange: (name: keyof MachineInput, value: string) => void;
  min?: number;
  max?: number;
  onBlur?: () => void;
}) {
  return (
    <label className="field">
      <span>
        {label}
        {unit && <em>{unit}</em>}
      </span>
      <input
        name={name}
        value={value}
        type={name === "machine_id" ? "text" : "number"}
        min={min}
        max={max}
        step="any"
        onChange={(e) => onChange(name, e.target.value)}
        onBlur={onBlur}
        required
      />
    </label>
  );
}

function Result({ result }: { result: PredictionResult }) {
  const color = COLORS[result.risk_level];
  const max = Math.max(
    ...result.top_factors.map((f) => Math.abs(f.impact)),
    0.001,
  );
  return (
    <section className="result" tabIndex={-1}>
      <div className="result-top">
        <div>
          <small>
            MACHINE ASSESSMENT · {result.machine_id || "UNSPECIFIED"}
          </small>
          <h2 style={{ color }}>{titleCase(result.risk_level)} risk</h2>
          <p>{result.interpretation}</p>
        </div>
        <div
          className="probability"
          style={
            {
              "--risk": color,
              "--p": result.failure_probability,
            } as React.CSSProperties
          }
        >
          <strong>{percent(result.failure_probability)}</strong>
          <span>Failure probability</span>
        </div>
      </div>
      <div className="result-grid">
        <article>
          <small>CLASSIFICATION</small>
          <strong>
            {result.failure_prediction
              ? "Failure threshold exceeded"
              : "Below failure threshold"}
          </strong>
          <span>Decision support signal</span>
        </article>
        <article>
          <small>ANOMALY DETECTION</small>
          <strong>
            {result.anomaly ? "Anomalous pattern" : "Within learned range"}
          </strong>
          <span>Anomaly score {result.anomaly_score.toFixed(2)}</span>
        </article>
      </div>
      <div className="drivers">
        <div className="panel-head">
          <div>
            <small>LOCAL SHAP EXPLANATION</small>
            <h3>Key prediction drivers</h3>
          </div>
          <span className="chip">Positive raises risk</span>
        </div>
        {result.top_factors.map((f) => (
          <div className="driver" key={f.feature}>
            <span>{f.feature}</span>
            <div>
              <i
                style={{
                  width: `${Math.max(8, (Math.abs(f.impact) / max) * 100)}%`,
                  background: f.impact >= 0 ? "#3274c5" : "#28a379",
                }}
              />
            </div>
            <strong>
              {f.impact > 0 ? "+" : ""}
              {f.impact.toFixed(3)}
            </strong>
          </div>
        ))}
      </div>
      <p className="disclaimer">
        Decision-support demonstration only. Not validated for safety-critical
        maintenance decisions.
      </p>
    </section>
  );
}

function MachineAnalysis() {
  const [form, setForm] = useState<MachineForm>({ ...BLANK_FORM });
  const [result, setResult] = useState<PredictionResult>();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [lookupLoading, setLookupLoading] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);
  const change = (name: keyof MachineInput, value: string) =>
    setForm((old) => ({ ...old, [name]: value }));
  const fill = (machine: MachineInput) =>
    setForm({
      machine_id: machine.machine_id ?? "",
      pressure_bar: String(machine.pressure_bar),
      oil_temperature_c: String(machine.oil_temperature_c),
      motor_power_w: String(machine.motor_power_w),
      volume_flow_lpm: String(machine.volume_flow_lpm),
      vibration_mms: String(machine.vibration_mms),
    });
  const loadMachine = async () => {
    const machineId = form.machine_id.trim();
    if (!machineId) return;
    setLookupLoading(true);
    setError("");
    setNotice("");
    try {
      const found = await api.lookupMachine(machineId);
      fill(found.machine);
      setResult(found.assessment);
      setNotice(
        `Loaded ${found.machine.machine_id} from ${found.source}. Sensor fields were filled automatically.`,
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Lookup failed.";
      if (message.includes("not found"))
        setNotice(
          "New machine ID. Enter its measurements, then analyze and save it.",
        );
      else setError(message);
    } finally {
      setLookupLoading(false);
    }
  };
  const loadExample = (data: MachineInput) => {
    fill(data);
    setResult(undefined);
    setError("");
    setNotice("Example loaded.");
  };
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.machine_id.trim()) {
      setError("Machine ID is required so this assessment can be saved.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload: MachineInput = {
        machine_id: form.machine_id.trim().toUpperCase(),
        pressure_bar: Number(form.pressure_bar),
        oil_temperature_c: Number(form.oil_temperature_c),
        motor_power_w: Number(form.motor_power_w),
        volume_flow_lpm: Number(form.volume_flow_lpm),
        vibration_mms: Number(form.vibration_mms),
      };
      const stored = await api.saveAsset(payload);
      const next = stored.assessment;
      setResult(next);
      setNotice(
        `${payload.machine_id} was analyzed and saved to the database.`,
      );
      const old = JSON.parse(
        localStorage.getItem("machineguard-history") ?? "[]",
      ) as PredictionResult[];
      localStorage.setItem(
        "machineguard-history",
        JSON.stringify([next, ...old].slice(0, 25)),
      );
      setTimeout(
        () => resultRef.current?.scrollIntoView?.({ behavior: "smooth" }),
        50,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Prediction failed.");
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className="page">
      <div className="page-intro">
        <span className="eyebrow">LIVE MODEL INFERENCE</span>
        <h2>Machine analysis</h2>
        <p>
          Enter a sensor snapshot or load a dataset-compatible example. Every
          result runs through the persisted classifier and anomaly model.
        </p>
      </div>
      <div className="analysis-layout">
        <form className="panel form-panel" onSubmit={submit}>
          <div className="form-head">
            <div>
              <small>SENSOR INPUT</small>
              <h3>Operating measurements</h3>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setForm({ ...BLANK_FORM });
                setResult(undefined);
                setError("");
                setNotice("");
              }}
            >
              <RotateCcw size={15} /> Reset
            </button>
          </div>
          <div className="example-row">
            {Object.entries(EXAMPLES).map(([name, data]) => (
              <button
                type="button"
                key={name}
                onClick={() => loadExample(data)}
              >
                Load {name}
              </button>
            ))}
          </div>
          <div className="form-grid">
            <Field
              label="Machine ID"
              name="machine_id"
              value={form.machine_id}
              onChange={change}
              onBlur={loadMachine}
            />
            <button
              type="button"
              className="secondary lookup-form-button"
              onClick={loadMachine}
              disabled={lookupLoading}
            >
              {lookupLoading ? "Loading…" : "Load ID & autofill"}
            </button>
            <Field
              label="System pressure"
              unit="bar"
              name="pressure_bar"
              value={form.pressure_bar}
              min={0}
              max={500}
              onChange={change}
            />
            <Field
              label="Oil temperature"
              unit="°C"
              name="oil_temperature_c"
              value={form.oil_temperature_c}
              min={-20}
              max={150}
              onChange={change}
            />
            <Field
              label="Motor power"
              unit="W"
              name="motor_power_w"
              value={form.motor_power_w}
              min={0}
              max={20000}
              onChange={change}
            />
            <Field
              label="Volume flow"
              unit="L/min"
              name="volume_flow_lpm"
              value={form.volume_flow_lpm}
              min={0}
              max={100}
              onChange={change}
            />
            <Field
              label="Vibration"
              unit="mm/s"
              name="vibration_mms"
              value={form.vibration_mms}
              min={0}
              max={20}
              onChange={change}
            />
          </div>
          {notice && (
            <div className="success-note" role="status">
              <CheckCircle2 /> {notice}
            </div>
          )}
          {error && (
            <div className="error" role="alert">
              <AlertTriangle /> {error}
            </div>
          )}
          <button className="primary wide" disabled={loading}>
            {loading ? (
              <>
                <span className="spinner" />
                Analyzing machine…
              </>
            ) : (
              <>
                <Activity size={18} />
                Analyze & save machine
              </>
            )}
          </button>
        </form>
        <aside className="panel sensor">
          <small>INPUT SIGNAL SNAPSHOT</small>
          <h3>Sensor overview</h3>
          {[
            ["Pressure", form.pressure_bar, 200],
            ["Oil temperature", form.oil_temperature_c, 100],
            ["Motor power", form.motor_power_w, 3500],
            ["Volume flow", form.volume_flow_lpm, 10],
            ["Vibration", form.vibration_mms, 2],
          ].map(([label, value, max]) => (
            <div className="sensor-row" key={label as string}>
              <span>{label}</span>
              <strong>{value}</strong>
              <div>
                <i
                  style={{
                    width: `${Math.min(100, (Number(value) / Number(max)) * 100)}%`,
                  }}
                />
              </div>
            </div>
          ))}
          <div className="note">
            <Info size={18} />
            <p>
              <strong>Anomaly ≠ failure</strong>An unusual operating pattern can
              be important even when predicted failure probability is low.
            </p>
          </div>
        </aside>
      </div>
      <div ref={resultRef}>{result && <Result result={result} />}</div>
    </div>
  );
}

function BatchAnalysis() {
  const [file, setFile] = useState<File>();
  const [preview, setPreview] = useState<Record<string, string>[]>([]);
  const [results, setResults] = useState<PredictionResult[]>([]);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const choose = (f?: File) => {
    if (!f) return;
    setFile(f);
    setResults([]);
    setError("");
    Papa.parse<Record<string, string>>(f, {
      header: true,
      preview: 5,
      complete: (r) => setPreview(r.data),
    });
  };
  const run = async () => {
    if (!file) return;
    setLoading(true);
    try {
      setResults((await api.batch(file)).results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Batch analysis failed.");
    } finally {
      setLoading(false);
    }
  };
  const shown = results
    .filter(
      (r) =>
        filter === "all" ||
        (filter === "anomalies" ? r.anomaly : r.risk_level === filter),
    )
    .sort((a, b) => b.failure_probability - a.failure_probability);
  const download = () => {
    const csv = Papa.unparse(results);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = "machineguard-results.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  };
  return (
    <div className="page">
      <div className="page-intro">
        <span className="eyebrow">FLEET ASSESSMENT</span>
        <h2>Batch analysis</h2>
        <p>
          Upload up to 5,000 machines in a CSV. Files are validated by the API
          and never executed.
        </p>
      </div>
      <section className="panel upload">
        <input
          id="csv"
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => choose(e.target.files?.[0])}
        />
        <label htmlFor="csv">
          <FileUp />
          <strong>{file ? file.name : "Choose a machine CSV"}</strong>
          <span>
            Required: machine_id, pressure_bar, oil_temperature_c,
            motor_power_w, volume_flow_lpm, vibration_mms · max 2 MB
          </span>
        </label>
        {preview.length > 0 && (
          <>
            <div className="preview">
              <table>
                <thead>
                  <tr>
                    {Object.keys(preview[0]).map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.map((row, i) => (
                    <tr key={i}>
                      {Object.values(row).map((v, j) => (
                        <td key={j}>{v}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button className="primary" onClick={run} disabled={loading}>
              {loading ? "Analyzing fleet…" : `Analyze ${file?.name}`}
            </button>
          </>
        )}
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
      </section>
      {results.length > 0 && (
        <section className="panel result-table">
          <div className="panel-head">
            <div>
              <small>{results.length} ASSESSMENTS</small>
              <h3>Prioritized results</h3>
            </div>
            <button className="secondary" onClick={download}>
              <Download size={16} /> Download results
            </button>
          </div>
          <div className="filters">
            {["all", "healthy", "warning", "high", "anomalies"].map((x) => (
              <button
                className={filter === x ? "active" : ""}
                onClick={() => setFilter(x)}
                key={x}
              >
                {titleCase(x)}
              </button>
            ))}
          </div>
          <table>
            <thead>
              <tr>
                <th>Machine</th>
                <th>Failure probability</th>
                <th>Risk level</th>
                <th>Anomaly</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r, i) => (
                <tr key={`${r.machine_id}-${i}`}>
                  <td>{r.machine_id || `Row ${i + 1}`}</td>
                  <td>
                    <strong>{percent(r.failure_probability)}</strong>
                  </td>
                  <td>
                    <span className={`risk-tag ${r.risk_level}`}>
                      {titleCase(r.risk_level)}
                    </span>
                  </td>
                  <td>{r.anomaly ? "Detected" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

function Performance() {
  const [info, setInfo] = useState<ModelInfo>();
  const [error, setError] = useState("");
  useEffect(() => {
    api
      .modelInfo()
      .then(setInfo)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Could not load metadata"),
      );
  }, []);
  if (error)
    return (
      <div className="page">
        <div className="error">{error}</div>
      </div>
    );
  if (!info)
    return <div className="page loading">Loading verified model metadata…</div>;
  const metricData: { name: string; value: number }[] = [
    { name: "Precision", value: info.metrics.precision },
    { name: "Recall", value: info.metrics.recall },
    { name: "F1", value: info.metrics.f1 },
    { name: "ROC-AUC", value: info.metrics.roc_auc },
    { name: "PR-AUC", value: info.metrics.pr_auc },
  ];
  return (
    <div className="page">
      <div className="page-intro">
        <span className="eyebrow">HELD-OUT EVALUATION</span>
        <h2>Model performance</h2>
        <p>
          Metrics below come directly from the saved test evaluation on the
          official UCI AI4I dataset.
        </p>
      </div>
      <div className="model-banner">
        <div>
          <small>SELECTED CLASSIFIER</small>
          <h3>{info.model_name}</h3>
          <p>
            Version {info.model_version} · threshold {info.threshold.toFixed(2)}
          </p>
        </div>
        <div>
          <small>TRAINED</small>
          <strong>{new Date(info.trained_at).toLocaleDateString()}</strong>
        </div>
        <div>
          <small>DATASET</small>
          <strong>{info.dataset_rows.toLocaleString()} rows</strong>
        </div>
      </div>
      <div className="stats metrics">
        {metricData.map(({ name, value }) => (
          <Stat
            key={name}
            label={name.toUpperCase()}
            value={percent(value)}
            detail={
              name === "Recall"
                ? "Primary operational metric"
                : "Held-out test set"
            }
            icon={name === "Recall" ? ShieldCheck : BarChart3}
            tone={name === "Recall" ? "green" : "blue"}
          />
        ))}
      </div>
      <div className="grid two">
        <section className="panel chart-panel">
          <div className="panel-head">
            <div>
              <small>DISCRIMINATION</small>
              <h3>ROC curve</h3>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={info.curves.roc}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="x" />
              <YAxis />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="y"
                stroke="#3274c5"
                strokeWidth={3}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </section>
        <section className="panel chart-panel">
          <div className="panel-head">
            <div>
              <small>CLASS IMBALANCE AWARE</small>
              <h3>Precision–recall curve</h3>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={info.curves.precision_recall}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="x" />
              <YAxis />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="y"
                stroke="#168661"
                strokeWidth={3}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </section>
      </div>
      <section className="panel chart-panel">
        <div className="panel-head">
          <div>
            <small>GLOBAL IMPORTANCE</small>
            <h3>Leading model features</h3>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            layout="vertical"
            data={info.feature_importance.slice(0, 8).reverse()}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis type="category" dataKey="feature" width={170} />
            <Tooltip />
            <Bar dataKey="importance" fill="#3274c5" radius={[0, 5, 5, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </section>
    </div>
  );
}

function About() {
  return (
    <div className="page">
      <div className="page-intro">
        <span className="eyebrow">MODEL CARD</span>
        <h2>Transparent by design</h2>
        <p>
          What the system knows, how it reaches a result, and where its limits
          begin.
        </p>
      </div>
      <div className="about-grid">
        {[
          [
            "What does it predict?",
            "The supervised classifier estimates machine-failure probability from a single operational sensor snapshot.",
          ],
          [
            "What data does it use?",
            "Product type, air/process temperature (K), rotational speed (rpm), torque (Nm), and tool wear (minutes), plus three defensible interactions.",
          ],
          [
            "Why does recall matter?",
            "Missing a real failure can be operationally costly. Threshold selection therefore emphasizes failure recall while making precision trade-offs visible.",
          ],
          [
            "What is anomaly detection?",
            "Isolation Forest learns normal operation and flags unusual combinations. Anomaly detection and failure prediction answer different questions.",
          ],
          [
            "How is leakage prevented?",
            "TWF, HDF, PWF, OSF, and RNF are direct failure-mode labels. They remain available for EDA but are excluded from all predictors.",
          ],
          [
            "What are the limitations?",
            "AI4I is synthetic industrial data; one-row predictions lack temporal context; thresholds require site-specific validation; drift is not monitored in this demo.",
          ],
        ].map(([h, p], i) => (
          <article key={h}>
            <span>0{i + 1}</span>
            <h3>{h}</h3>
            <p>{p}</p>
          </article>
        ))}
      </div>
      <div className="safety">
        <ShieldCheck />
        <div>
          <strong>
            Portfolio demonstration—not a certified safety system.
          </strong>
          <p>
            MachineGuard AI is not validated for real-world safety-critical
            maintenance decisions. Qualified personnel remain responsible for
            inspection and action.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/analysis" element={<MachineAnalysis />} />
        <Route path="/batch" element={<BatchAnalysis />} />
        <Route path="/performance" element={<Performance />} />
        <Route path="/about" element={<About />} />
      </Routes>
    </Shell>
  );
}
