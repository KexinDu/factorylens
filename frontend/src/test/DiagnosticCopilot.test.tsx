import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import App from "../App";
import type { Diagnosis, WorkOrder } from "../types";

const fixture: Diagnosis = {
  diagnosis_id: "diagnosis-demo",
  device_id: "HYD-0001",
  source: "UCI hydraulic test rig",
  question: "What explains low pressure?",
  mode: "retrieval_only",
  llm_provider: "openai",
  openai_model: null,
  created_at: "2026-11-24T00:00:00Z",
  summary: "Generative diagnosis was not executed successfully.",
  observed_signals: {
    machine_id: "HYD-0001",
    pressure_bar: 160.6735,
    oil_temperature_c: 35.622,
    motor_power_w: 2538.9294,
    volume_flow_lpm: 6.7098,
    vibration_mms: 0.577,
  },
  model_findings: {
    machine_id: "HYD-0001",
    failure_prediction: false,
    failure_probability: 0.079939,
    risk_level: "healthy",
    anomaly: false,
    anomaly_score: 0.297729,
    top_factors: [],
    interpretation: "No elevated risk.",
  },
  possible_causes: [],
  recommended_checks: [],
  evidence_references: [
    {
      chunk_id: "guide:1",
      document_id: "guide",
      filename: "pressure.md",
      position: 1,
      heading: "Pressure evidence",
      source: "Educational example",
      text: "Review pressure alongside flow.",
      score: 0.331,
      reference_id: "KB-guide:1",
    },
  ],
  uncertainty: "Review the evidence.",
  limitations: ["Use qualified personnel."],
  trace: [
    {
      tool: "search_knowledge",
      order: 1,
      status: "ok",
      origin: "backend",
      elapsed_ms: 4,
      arguments: { top_k: 4 },
      result_summary: "Retrieved one relevant excerpt.",
    },
  ],
};

afterEach(() => vi.restoreAllMocks());

const orderFixture: WorkOrder = {
  work_order_id: "order-demo",
  diagnosis_id: fixture.diagnosis_id,
  device_id: fixture.device_id,
  title: "Inspect educational fixture",
  issue_description: "Verify the pressure observation.",
  priority: "medium",
  status: "open",
  maintenance_notes: "",
  created_at: fixture.created_at,
  updated_at: fixture.created_at,
  diagnostic_mode: fixture.mode,
  diagnostic_snapshot: fixture,
};

function openCopilot(url = "/diagnostics") {
  render(
    <MemoryRouter initialEntries={[url]}>
      <App />
    </MemoryRouter>,
  );
}

it("submits an opted-in question and renders retrieval fallback, evidence, trace and history", async () => {
  const mocked = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json([]))
    .mockResolvedValueOnce(Response.json({ provider: "openai" }))
    .mockResolvedValueOnce(Response.json(fixture, { status: 201 }))
    .mockResolvedValueOnce(Response.json(fixture));
  openCopilot("/diagnostics?device_id=HYD-0001");
  expect(screen.getByLabelText("Equipment ID")).toHaveValue("HYD-0001");
  await screen.findByText("No diagnostics recorded yet.");
  fireEvent.change(screen.getByLabelText("Diagnostic question"), {
    target: { value: fixture.question },
  });
  fireEvent.click(
    await screen.findByLabelText(
      "Use OpenAI direct for a public test-rig diagnosis",
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: "Run diagnosis" }));
  expect(
    await screen.findByText("Retrieval-only fallback", { exact: true }),
  ).toBeVisible();
  expect(screen.getByText("160.6735 bar")).toBeVisible();
  expect(screen.getByText("7.9939%")).toBeVisible();
  expect(screen.getByText("Review pressure alongside flow.")).toBeVisible();
  fireEvent.click(screen.getByText("Tool Execution Trace (1)"));
  expect(screen.getByText("search_knowledge")).toBeVisible();
  expect(JSON.parse(String(mocked.mock.calls[2][1]?.body))).toEqual({
    device_id: "HYD-0001",
    question: fixture.question,
    use_openai: true,
    expected_provider: "openai",
  });
  fireEvent.click(screen.getByRole("button", { name: "View diagnosis" }));
  expect(
    await screen.findByRole("heading", { name: "Diagnosis for HYD-0001" }),
  ).toBeVisible();
  expect(mocked.mock.calls[3][0]).toContain("/diagnostics/diagnosis-demo");
});

it("shows a missing equipment error while keeping cloud opt-in unchecked", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json([]))
    .mockResolvedValueOnce(Response.json({ provider: "openlux" }))
    .mockResolvedValueOnce(
      Response.json(
        { detail: "The selected equipment was not found." },
        {
          status: 404,
        },
      ),
    );
  openCopilot();
  await screen.findByText("No diagnostics recorded yet.");
  expect(
    await screen.findByLabelText("Use OpenLux for a public test-rig diagnosis"),
  ).not.toBeChecked();
  fireEvent.change(screen.getByLabelText("Diagnostic question"), {
    target: { value: "check" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Run diagnosis" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The selected equipment was not found.",
  );
});

it("shows the OpenLux provider and actual model in history and detail", async () => {
  const relay = {
    ...fixture,
    mode: "openai",
    llm_provider: "openlux",
    openai_model: "relay-model",
  };
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json([relay]))
    .mockResolvedValueOnce(Response.json({ provider: "openlux" }))
    .mockResolvedValueOnce(Response.json(relay));
  openCopilot();
  expect(await screen.findByText(/OpenLux API · relay-model/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "View diagnosis" }));
  expect(await screen.findByText("OpenLux API", { exact: true })).toBeVisible();
});

it("creates a work order only after reviewing the fallback and confirming", async () => {
  const mocked = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json([fixture]))
    .mockResolvedValueOnce(Response.json({ provider: "openai" }))
    .mockResolvedValueOnce(Response.json(fixture))
    .mockResolvedValueOnce(Response.json(orderFixture, { status: 201 }));
  openCopilot();
  fireEvent.click(
    await screen.findByRole("button", { name: "View diagnosis" }),
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "Create Work Order" }),
  );
  expect(
    screen.getByText("Source diagnosis: Retrieval-only fallback."),
  ).toBeVisible();
  const create = screen.getByRole("button", { name: "Confirm and create" });
  fireEvent.submit(create.closest("form")!);
  expect(mocked).toHaveBeenCalledTimes(3);
  fireEvent.change(screen.getByLabelText("Issue description"), {
    target: { value: orderFixture.issue_description },
  });
  fireEvent.change(screen.getByLabelText("Priority"), {
    target: { value: "medium" },
  });
  fireEvent.click(screen.getByLabelText(/I reviewed the diagnosis/));
  fireEvent.click(create);
  expect(
    await screen.findByRole("link", { name: "View work order" }),
  ).toHaveAttribute("href", "/work-orders?order=order-demo");
  expect(JSON.parse(String(mocked.mock.calls[3][1]?.body))).toMatchObject({
    confirmed: true,
    diagnosis_id: fixture.diagnosis_id,
    priority: "medium",
    issue_description: orderFixture.issue_description,
  });
});

it("filters work orders, resolves one with notes and refreshes global counts", async () => {
  const inProgress = { ...orderFixture, status: "in_progress" };
  const resolved = {
    ...inProgress,
    status: "resolved",
    maintenance_notes: "Verified the test fixture.",
    updated_at: "2026-11-24T00:10:00Z",
  };
  const activeList = {
    items: [inProgress],
    counts: { open: 0, in_progress: 1, resolved: 0 },
    total: 1,
  };
  const mock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json(activeList))
    .mockResolvedValueOnce(Response.json(activeList))
    .mockResolvedValueOnce(Response.json(inProgress))
    .mockResolvedValueOnce(Response.json(resolved))
    .mockResolvedValueOnce(
      Response.json({
        items: [],
        counts: { open: 0, in_progress: 0, resolved: 1 },
        total: 0,
      }),
    );
  openCopilot("/work-orders");
  await screen.findByRole("link", { name: orderFixture.title });
  fireEvent.change(screen.getByLabelText("Status filter"), {
    target: { value: "in_progress" },
  });
  fireEvent.click(
    await screen.findByRole("link", { name: orderFixture.title }),
  );
  const status = await screen.findByLabelText("Work order status");
  fireEvent.change(status, { target: { value: "resolved" } });
  expect(screen.getByLabelText("Maintenance notes")).toBeRequired();
  fireEvent.change(screen.getByLabelText("Maintenance notes"), {
    target: { value: resolved.maintenance_notes },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(
    await screen.findByText("No work orders match this filter."),
  ).toBeVisible();
  expect(screen.getByLabelText("Resolved count")).toHaveTextContent("1");
  expect(screen.getByLabelText("Maintenance notes")).toHaveValue(
    resolved.maintenance_notes,
  );
  expect(mock.mock.calls[1][0]).toContain("status=in_progress");
  expect(mock.mock.calls[3][1]?.method).toBe("PATCH");
});
