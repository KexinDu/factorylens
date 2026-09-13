import type {
  AssetListResponse,
  FleetSummary,
  MachineInput,
  MachineLookupResult,
  ModelInfo,
  PredictionResult,
} from "../types";
const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${BASE}${path}`, {
      ...options,
      signal: controller.signal,
    });
    if (!response.ok) {
      const body = (await response
        .json()
        .catch(() => ({ detail: "Request failed" }))) as {
        detail?: string | unknown[];
      };
      throw new Error(
        typeof body.detail === "string"
          ? body.detail
          : "Please check the submitted values and try again.",
      );
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw new Error("The service timed out. Please try again.");
    if (error instanceof TypeError)
      throw new Error(
        "The analysis service is unavailable. Confirm the backend is running.",
      );
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export const api = {
  predict: (input: MachineInput) =>
    request<PredictionResult>("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  modelInfo: () => request<ModelInfo>("/model/info"),
  lookupMachine: (machineId: string) =>
    request<MachineLookupResult>(`/machines/${encodeURIComponent(machineId)}`),
  saveAsset: (input: MachineInput) =>
    request<MachineLookupResult>("/assets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  fleetSummary: () => request<FleetSummary>("/assets/summary"),
  listAssets: (category: string) =>
    request<AssetListResponse>(
      `/assets?category=${encodeURIComponent(category)}&limit=12`,
    ),
  batch: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ count: number; results: PredictionResult[] }>(
      "/predict/batch",
      { method: "POST", body: form },
    );
  },
};
