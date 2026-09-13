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
