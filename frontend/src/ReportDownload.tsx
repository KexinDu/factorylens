import { useState } from "react";
import { api } from "./services/api";

export default function ReportDownload({
  kind,
  recordId,
}: {
  kind: "diagnostics" | "work-orders";
  recordId: string;
}) {
  const [pending, setPending] = useState(false);
  const [filename, setFilename] = useState("");
  const [error, setError] = useState("");

  async function download() {
    setPending(true);
    setFilename("");
    setError("");
    try {
      const report = await api.maintenanceReport(kind, recordId);
      const objectURLs = URL;
      const url = objectURLs.createObjectURL(report.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = report.filename;
      document.body.append(link);
      try {
        link.click();
        setFilename(report.filename);
      } finally {
        link.remove();
        window.setTimeout(() => objectURLs.revokeObjectURL(url), 1000);
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Report download failed.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="knowledge-actions">
      <button
        type="button"
        className="secondary"
        disabled={pending}
        onClick={() => void download()}
      >
        {pending ? "Downloading report…" : "Download Markdown Report"}
      </button>
      {filename && (
        <span role="status">Report download started. {filename}</span>
      )}
      {error && (
        <span className="error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
