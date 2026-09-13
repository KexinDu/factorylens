import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";

afterEach(() => vi.restoreAllMocks());
const renderAnalysis = () =>
  render(
    <MemoryRouter initialEntries={["/analysis"]}>
      <App />
    </MemoryRouter>,
  );

describe("machine analysis", () => {
  it("reset clears all form values and the previous result", () => {
    renderAnalysis();
    fireEvent.click(screen.getByRole("button", { name: /load healthy/i }));
    expect(screen.getByLabelText(/machine id/i)).toHaveValue("HYD-0001");
    fireEvent.click(screen.getByRole("button", { name: /^reset$/i }));
    expect(screen.getByLabelText(/machine id/i)).toHaveValue("");
    expect(screen.getByLabelText(/system pressure/i)).toHaveValue(null);
  });

  it("loads an existing ID and auto-fills its sensor fields", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          source: "UCI hydraulic test rig",
          machine: {
            machine_id: "HYD-0001",
            pressure_bar: 160.67,
            oil_temperature_c: 35.62,
            motor_power_w: 2538.93,
            volume_flow_lpm: 6.71,
            vibration_mms: 0.577,
          },
          assessment: {
            machine_id: "HYD-0001",
            failure_prediction: false,
            failure_probability: 0.02,
            risk_level: "healthy",
            anomaly: false,
            anomaly_score: 0.1,
            top_factors: [],
            interpretation: "No elevated risk.",
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    renderAnalysis();
    const id = screen.getByLabelText(/machine id/i);
    fireEvent.change(id, { target: { value: "HYD-0001" } });
    fireEvent.blur(id);
    await waitFor(() =>
      expect(screen.getByLabelText(/system pressure/i)).toHaveValue(160.67),
    );
  });

  it("renders the prediction form and validates required values", () => {
    const request = vi.spyOn(globalThis, "fetch");
    renderAnalysis();
    const pressure = screen.getByLabelText(/system pressure/i);
    fireEvent.change(pressure, { target: { value: "-1" } });
    expect(pressure).toBeInvalid();
    fireEvent.click(
      screen.getByRole("button", { name: /analyze & save machine/i }),
    );
    expect(request).not.toHaveBeenCalled();
  });
  it("renders a successful API response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          source: "Manual entry",
          machine: {
            machine_id: "M-1",
            pressure_bar: 160.67,
            oil_temperature_c: 35.62,
            motor_power_w: 2538.93,
            volume_flow_lpm: 6.71,
            vibration_mms: 0.577,
          },
          assessment: {
            machine_id: "M-1",
            failure_prediction: false,
            failure_probability: 0.18,
            risk_level: "healthy",
            anomaly: false,
            anomaly_score: 0.14,
            top_factors: [{ feature: "Pressure", impact: 0.12 }],
            interpretation: "No elevated risk.",
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    renderAnalysis();
    fireEvent.click(screen.getByRole("button", { name: /load healthy/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /analyze & save machine/i }),
    );
    await waitFor(() => expect(screen.getByText("18%")).toBeInTheDocument());
  });
  it("shows an API error state", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("offline"));
    renderAnalysis();
    fireEvent.click(screen.getByRole("button", { name: /load healthy/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /analyze & save machine/i }),
    );
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/unavailable/i),
    );
  });
});
