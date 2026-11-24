import { useEffect, useState, type FormEvent } from "react";
import { api } from "./services/api";
import type {
  KnowledgeDetail,
  KnowledgeDocument,
  KnowledgeMatch,
} from "./types";
import "./knowledge.css";

export default function KnowledgeBase() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [detail, setDetail] = useState<KnowledgeDetail>();
  const [matches, setMatches] = useState<KnowledgeMatch[]>();
  const [confirmation, setConfirmation] = useState<KnowledgeDocument>();
  const [pending, setPending] = useState("Loading documents…");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    api
      .knowledgeDocuments()
      .then((items) => {
        if (active) setDocuments(items);
      })
      .catch((cause: Error) => {
        if (active) setError(cause.message);
      })
      .finally(() => {
        if (active) setPending("");
      });
    return () => {
      active = false;
    };
  }, []);

  async function run(message: string, action: () => Promise<void>) {
    setPending(message);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Knowledge base request failed.",
      );
    } finally {
      setPending("");
    }
  }

  function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    void run("Uploading document…", async () => {
      const document = await api.uploadKnowledge(data);
      setDocuments((items) => [
        document,
        ...items.filter((item) => item.document_id !== document.document_id),
      ]);
      setMatches(undefined);
      form.reset();
      setNotice(`Uploaded ${document.filename}.`);
    });
  }

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setMatches(undefined);
    void run("Searching documents…", async () => {
      setMatches(
        await api.searchKnowledge(
          String(form.get("query")),
          Number(form.get("top_k")),
        ),
      );
    });
  }

  function remove(document: KnowledgeDocument) {
    void run("Deleting document…", async () => {
      await api.deleteKnowledge(document.document_id);
      setDocuments((items) =>
        items.filter((item) => item.document_id !== document.document_id),
      );
      if (detail?.document_id === document.document_id) setDetail(undefined);
      setMatches(undefined);
      setConfirmation(undefined);
      setNotice(`Deleted ${document.filename}.`);
    });
  }

  return (
    <div className="page knowledge-page">
      <div className="page-intro">
        <h2>Knowledge Base</h2>
        <p>
          Manage maintenance references and search their excerpts by TF-IDF
          keyword relevance.
        </p>
      </div>
      <div aria-live="polite">{pending || notice}</div>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      <div className="knowledge-grid">
        <section className="panel">
          <h3>Upload a document</h3>
          <form onSubmit={upload}>
            <label>
              UTF-8 TXT or Markdown file
              <input
                name="file"
                type="file"
                accept=".txt,.md,.markdown"
                required
              />
            </label>
            <label>
              Source description (optional)
              <input name="source" maxLength={200} />
            </label>
            <button type="submit" className="primary" disabled={!!pending}>
              Upload document
            </button>
          </form>
        </section>
        <section className="panel">
          <h3>Search documents</h3>
          <form onSubmit={search}>
            <label>
              Search query
              <input
                name="query"
                maxLength={300}
                placeholder="e.g. low system pressure"
                required
              />
            </label>
            <label>
              Maximum results
              <input
                name="top_k"
                type="number"
                min={1}
                max={20}
                defaultValue={5}
                required
              />
            </label>
            <button type="submit" className="primary" disabled={!!pending}>
              Search documents
            </button>
          </form>
        </section>
      </div>
      {matches && (
        <section className="panel">
          <h3>Search results</h3>
          {matches.length === 0 && (
            <p>No sufficiently relevant excerpts found.</p>
          )}
          {matches.map((match) => (
            <article className="knowledge-item" key={match.chunk_id}>
              <h4>
                {match.filename} · Chunk {match.position}
              </h4>
              <small>
                {match.source} · Relevance {match.score.toFixed(3)}
              </small>
              {match.heading && (
                <p>
                  <strong>{match.heading}</strong>
                </p>
              )}
              <div className="knowledge-excerpt">{match.text}</div>
            </article>
          ))}
        </section>
      )}
      <section className="panel">
        <h3>Documents</h3>
        {!pending && !error && documents.length === 0 && (
          <p>No documents uploaded.</p>
        )}
        {documents.map((document) => (
          <article className="knowledge-item" key={document.document_id}>
            <h4>{document.filename}</h4>
            <small>
              {document.source} · {document.chunk_count} chunks ·{" "}
              <time dateTime={document.uploaded_at}>
                {new Date(document.uploaded_at).toLocaleString()}
              </time>
            </small>
            <div className="knowledge-actions">
              <button
                className="secondary"
                type="button"
                disabled={!!pending}
                aria-label={`View ${document.filename}`}
                onClick={() =>
                  void run("Loading document…", async () => {
                    setDetail(await api.knowledgeDetail(document.document_id));
                  })
                }
              >
                View document
              </button>
              <button
                className="secondary"
                type="button"
                disabled={!!pending || !!confirmation}
                aria-label={`Delete ${document.filename}`}
                onClick={() => setConfirmation(document)}
              >
                Delete
              </button>
            </div>
            {confirmation?.document_id === document.document_id && (
              <div
                role="group"
                aria-label="Confirm document deletion"
                className="knowledge-confirm"
              >
                <p>Delete {document.filename} and all its excerpts?</p>
                <div className="knowledge-actions">
                  <button
                    className="primary"
                    type="button"
                    disabled={!!pending}
                    onClick={() => remove(document)}
                  >
                    Confirm deletion
                  </button>
                  <button
                    className="secondary"
                    type="button"
                    disabled={!!pending}
                    onClick={() => setConfirmation(undefined)}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </article>
        ))}
      </section>
      {detail && (
        <section className="panel" aria-label="Document details">
          <h3>{detail.filename}</h3>
          <p>
            {detail.source} · {detail.chunk_count} chunks
          </p>
          {detail.chunks.map((chunk) => (
            <article className="knowledge-item" key={chunk.chunk_id}>
              <h4>
                Chunk {chunk.position}
                {chunk.heading && ` · ${chunk.heading}`}
              </h4>
              <div className="knowledge-excerpt">{chunk.text}</div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
