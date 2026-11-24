import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import ReportDownload from "../ReportDownload";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it.each([
  ["diagnostics", "diagnosis"],
  ["work-orders", "work-order"],
] as const)(
  "downloads the named Markdown attachment for %s",
  async (kind, prefix) => {
    const filename = `factorylens-${prefix}-sample.md`;
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("# Report", {
        headers: {
          "Content-Type": "text/markdown; charset=utf-8",
          "Content-Disposition": `attachment; filename="${filename}"`,
        },
      }),
    );
    const objectURL = vi.fn(() => "blob:report");
    vi.stubGlobal(
      "URL",
      Object.assign(class extends URL {}, {
        createObjectURL: objectURL,
        revokeObjectURL: vi.fn(),
      }),
    );
    let downloaded = "";
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      downloaded = this.download;
    });
    render(<ReportDownload kind={kind} recordId="sample" />);
    fireEvent.click(
      screen.getByRole("button", { name: "Download Markdown Report" }),
    );
    expect(
      screen.getByRole("button", { name: "Downloading report…" }),
    ).toBeDisabled();
    expect(await screen.findByRole("status")).toHaveTextContent(filename);
    expect(downloaded).toBe(filename);
    expect(objectURL).toHaveBeenCalledOnce();
    expect(fetch.mock.calls[0][0]).toContain(`/${kind}/sample/report`);
  },
);

it("shows an error if the report record is missing", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    Response.json({ detail: "Work order not found." }, { status: 404 }),
  );
  render(<ReportDownload kind="work-orders" recordId="missing" />);
  fireEvent.click(
    screen.getByRole("button", { name: "Download Markdown Report" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Work order not found.",
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Download Markdown Report" }),
    ).toBeEnabled(),
  );
});
