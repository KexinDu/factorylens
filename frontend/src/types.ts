export interface MachineInput {
  machine_id?: string;
  pressure_bar: number;
  oil_temperature_c: number;
  motor_power_w: number;
  volume_flow_lpm: number;
  vibration_mms: number;
}
export interface RiskFactor {
  feature: string;
  impact: number;
}
export interface PredictionResult {
  machine_id?: string;
  failure_prediction: boolean;
  failure_probability: number;
  risk_level: "healthy" | "warning" | "high";
  anomaly: boolean;
  anomaly_score: number;
  top_factors: RiskFactor[];
  interpretation: string;
}
export interface MetricSet {
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number;
  pr_auc: number;
  confusion_matrix: number[][];
}
export interface ModelInfo {
  model_name: string;
  model_version: string;
  trained_at: string;
  dataset: string;
  dataset_rows: number;
  failure_rate: number;
  threshold: number;
  metrics: MetricSet;
  features: string[];
  leakage_columns_excluded: string[];
  validation_comparison: Record<string, MetricSet>;
  feature_importance: { feature: string; importance: number }[];
  curves: {
    roc: { x: number; y: number }[];
    precision_recall: { x: number; y: number }[];
  };
}

export interface MachineLookupResult {
  machine: MachineInput;
  assessment: PredictionResult;
  source: string;
  component_condition?: {
    cooler_efficiency_pct: number;
    valve_condition_pct: number;
    pump_leakage_class: number;
    accumulator_pressure_bar: number;
    stable_flag: number;
  } | null;
}

export interface AssetListItem {
  machine_id: string;
  failure_probability: number;
  risk_level: "healthy" | "warning" | "high";
  anomaly: boolean;
  anomaly_score: number;
  source: string;
}

export interface AssetListResponse {
  category: string;
  count: number;
  results: AssetListItem[];
}

export interface FleetSummary {
  total: number;
  healthy: number;
  warning: number;
  high: number;
  anomalies: number;
}
export interface KnowledgeDocument {
  document_id: string;
  filename: string;
  source: string;
  uploaded_at: string;
  chunk_count: number;
}

export interface KnowledgeChunk {
  chunk_id: string;
  document_id: string;
  filename: string;
  position: number;
  heading: string | null;
  text: string;
}

export interface KnowledgeDetail extends KnowledgeDocument {
  chunks: KnowledgeChunk[];
}

export interface KnowledgeMatch extends KnowledgeChunk {
  source: string;
  score: number;
}
export interface DiagnosticSummary {
  diagnosis_id: string;
  device_id: string;
  question: string;
  mode: "openai" | "retrieval_only";
  llm_provider: "openai" | "openlux";
  openai_model: string | null;
  created_at: string;
}

export interface Diagnosis extends DiagnosticSummary {
  source: string;
  observed_signals: MachineInput;
  model_findings: PredictionResult;
  summary: string;
  possible_causes: { text: string; references: string[] }[];
  recommended_checks: { text: string; references: string[] }[];
  evidence_references: (KnowledgeMatch & { reference_id: string })[];
  uncertainty: string;
  limitations: string[];
  trace: {
    tool: string;
    order: number;
    status: "ok" | "no_match" | "rejected" | "error";
    origin: "backend" | "model";
    elapsed_ms: number;
    arguments: Record<string, string | number>;
    result_summary: string;
  }[];
}
export type WorkOrderStatus = "open" | "in_progress" | "resolved";
export type WorkOrderPriority = "low" | "medium" | "high";

export interface WorkOrderSummary {
  work_order_id: string;
  diagnosis_id: string;
  device_id: string;
  title: string;
  priority: WorkOrderPriority;
  status: WorkOrderStatus;
  created_at: string;
  updated_at: string;
  diagnostic_mode: Diagnosis["mode"];
}

export interface WorkOrder extends WorkOrderSummary {
  issue_description: string;
  maintenance_notes: string;
  diagnostic_snapshot: Diagnosis;
}

export interface WorkOrderPage {
  items: WorkOrderSummary[];
  counts: Record<WorkOrderStatus, number>;
  total: number;
}

export type CreateWorkOrder = Pick<WorkOrder,
  "diagnosis_id" | "title" | "issue_description" | "priority" | "maintenance_notes"
> & { confirmed: true };
