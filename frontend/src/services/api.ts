import type {
  AssetListResponse,
  CreateWorkOrder,
  Diagnosis,
  DiagnosticSummary,
  FleetSummary,
  KnowledgeDetail,
  KnowledgeDocument,
  KnowledgeMatch,
  MachineInput,
  MachineLookupResult,
  ModelInfo,
  PredictionResult,
  WorkOrder,
  WorkOrderPage,
  WorkOrderStatus,
} from "../types";
const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

async function request<T>(
  path: string,
  options?: RequestInit,
  timeoutMs = 15000,
  decode?: (response: Response) => Promise<T>,
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
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
    if (response.status === 204) return undefined as T;
    if (decode) return await decode(response);
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

async function decodeReport(
  response: Response,
): Promise<{ blob: Blob; filename: string }> {
  const filename = /filename="(factorylens-[a-z0-9_-]+\.md)"/i.exec(
    response.headers.get("Content-Disposition") ?? "",
  )?.[1];
  if (
    !filename ||
    !response.headers.get("Content-Type")?.startsWith("text/markdown")
  ) {
    throw new Error("The server did not return a valid Markdown attachment.");
  }
  return { filename, blob: await response.blob() };
}

export const api = {
  maintenanceReport: (kind: "diagnostics" | "work-orders", id: string) =>
    request(
      `/${kind}/${encodeURIComponent(id)}/report`,
      undefined,
      15000,
      decodeReport,
    ),
  createWorkOrder: (order: CreateWorkOrder) =>
    request<WorkOrder>("/work-orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(order),
    }),
  workOrders: (status: WorkOrderStatus | "", limit: number, offset: number) => {
    const query = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (status) query.set("status", status);
    return request<WorkOrderPage>(`/work-orders?${query}`);
  },
  workOrder: (id: string) =>
    request<WorkOrder>(`/work-orders/${encodeURIComponent(id)}`),
  updateWorkOrder: (
    id: string,
    update: { status?: WorkOrderStatus; maintenance_notes: string },
  ) =>
    request<WorkOrder>(`/work-orders/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    }),
  diagnose: (
    deviceId: string,
    question: string,
    useOpenAI: boolean,
    expectedProvider?: DiagnosticSummary["llm_provider"],
  ) =>
    request<Diagnosis>(
      "/diagnostics",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: deviceId,
          question,
          use_openai: useOpenAI,
          expected_provider: expectedProvider,
        }),
      },
      105000,
    ),
  diagnosticHistory: () => request<DiagnosticSummary[]>("/diagnostics"),
  diagnosticConfig: () =>
    request<{ provider: DiagnosticSummary["llm_provider"] }>(
      "/diagnostics/config",
    ),
  diagnosisDetail: (id: string) =>
    request<Diagnosis>(`/diagnostics/${encodeURIComponent(id)}`),
  knowledgeDocuments: () =>
    request<KnowledgeDocument[]>("/knowledge/documents"),
  knowledgeDetail: (id: string) =>
    request<KnowledgeDetail>(`/knowledge/documents/${encodeURIComponent(id)}`),
  uploadKnowledge: (form: FormData) =>
    request<KnowledgeDocument>("/knowledge/documents", {
      method: "POST",
      body: form,
    }),
  deleteKnowledge: (id: string) =>
    request<void>(`/knowledge/documents/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  searchKnowledge: (query: string, topK: number) =>
    request<KnowledgeMatch[]>(
      `/knowledge/search?${new URLSearchParams({ q: query, top_k: String(topK) })}`,
    ),
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
