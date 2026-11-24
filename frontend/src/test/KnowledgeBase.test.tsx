import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import App from "../App";

const document = {
  document_id: "test-id",
  filename: "pressure.md",
  source: "Workshop notes",
  uploaded_at: "2026-11-24T00:00:00Z",
  chunk_count: 1,
};
const chunk = {
  chunk_id: "test-id:1",
  document_id: document.document_id,
  filename: document.filename,
  position: 1,
  heading: "Pressure abnormalities",
  text: "Compare low pressure against similar cycles.",
};

function openLibrary() {
  render(
    <MemoryRouter initialEntries={["/knowledge"]}>
      <App />
    </MemoryRouter>,
  );
}

afterEach(() => vi.restoreAllMocks());

it("renders search citations and the no-match state", async () => {
  const mock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json([document]))
    .mockResolvedValueOnce(
      Response.json([{ ...chunk, source: document.source, score: 0.62 }]),
    )
    .mockResolvedValueOnce(Response.json([]));
  openLibrary();
  await screen.findByRole("button", { name: "View pressure.md" });
  fireEvent.change(screen.getByLabelText("Search query"), {
    target: { value: "low pressure" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search documents" }));
  expect(
    await screen.findByText("Workshop notes · Relevance 0.620"),
  ).toBeVisible();
  expect(screen.getByText("pressure.md · Chunk 1")).toBeVisible();
  expect(mock.mock.calls[1][0]).toContain("q=low+pressure&top_k=5");
  fireEvent.change(screen.getByLabelText("Search query"), {
    target: { value: "unrelated" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search documents" }));
  expect(
    await screen.findByText("No sufficiently relevant excerpts found."),
  ).toBeVisible();
});

it("uploads, opens and confirms deletion of a document", async () => {
  const mock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json([]))
    .mockResolvedValueOnce(Response.json(document, { status: 201 }))
    .mockResolvedValueOnce(Response.json({ ...document, chunks: [chunk] }))
    .mockResolvedValueOnce(new Response(null, { status: 204 }));
  openLibrary();
  await screen.findByText("No documents uploaded.");
  const input = screen.getByLabelText("UTF-8 TXT or Markdown file");
  fireEvent.change(input, {
    target: { files: [new File(["Pressure"], "pressure.md")] },
  });
  fireEvent.submit(
    screen.getByRole("button", { name: "Upload document" }).closest("form")!,
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "View pressure.md" }),
  );
  expect(await screen.findByText(chunk.text)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Delete pressure.md" }));
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(mock).toHaveBeenCalledTimes(3);
  fireEvent.click(screen.getByRole("button", { name: "Delete pressure.md" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm deletion" }));
  await waitFor(() =>
    expect(screen.queryByText(chunk.text)).not.toBeInTheDocument(),
  );
  expect(await screen.findByText("Deleted pressure.md.")).toBeVisible();
  expect(mock.mock.calls[3][1]).toMatchObject({ method: "DELETE" });
});

it("shows the backend error for a rejected upload", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json([]))
    .mockResolvedValueOnce(
      Response.json(
        { detail: "This document already exists." },
        { status: 409 },
      ),
    );
  openLibrary();
  await screen.findByText("No documents uploaded.");
  fireEvent.submit(
    screen.getByRole("button", { name: "Upload document" }).closest("form")!,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This document already exists.",
  );
});
