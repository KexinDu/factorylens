# FactoryLens industrial knowledge base

A UTF-8 file goes through the Knowledge Base page to FastAPI. The backend
normalizes line endings, trims whitespace, validates the text, and hashes the
cleaned content. It splits Markdown at basic headings and clips longer sections
into overlapping excerpts, preferring nearby word boundaries. The overlap
preserves context around a split. The filename and source appear with each
search result. The browser displays uploaded text as plain text.

## SQLite storage

The library uses the same `DATABASE_PATH` as the existing asset store.

| Table | Purpose |
| --- | --- |
| `knowledge_documents` | Document ID, original filename, UTC upload timestamp, source, and unique SHA-256 of the cleaned text. |
| `knowledge_chunks` | Chunk ID, parent document ID, one-based position, optional heading, and excerpt text. The filename is resolved from the parent. |
| `knowledge_metadata` | Records initial example import. A deleted example stays deleted after restart. |

An upload writes the document and all excerpts in one transaction. SQLite
deletes associated chunks when their document is deleted. The list calculates
each chunk count from the stored rows. The same cleaned text uploaded under a
different name receives HTTP 409.

## API and limits

All paths below are relative to `/api/v1/knowledge`.

| Method and route | Result |
| --- | --- |
| `GET /documents` | Document summaries. |
| `POST /documents` | Multipart `file` and optional `source` of up to 200 characters. Returns 201 and a summary. |
| `GET /documents/{document_id}` | Summary and ordered chunks, or 404 for an unknown ID. |
| `DELETE /documents/{document_id}` | Deletes the document and chunks. Returns 204, or 404 for an unknown ID. |
| `GET /search?q=low+system+pressure&top_k=5` | Excerpts with citation fields and cosine scores. An empty array indicates no sufficiently relevant excerpt. |

The default upload limit is 128 KiB per file and the library holds up to 100
documents, including examples. Accepted extensions are `.txt`, `.md`, and
`.markdown`. The default chunk length and overlap are 800 and 100 characters.
Set `KNOWLEDGE_MAX_UPLOAD_BYTES`, `KNOWLEDGE_CHUNK_LENGTH`, and
`KNOWLEDGE_CHUNK_OVERLAP` in the backend environment to change these defaults.
Chunk settings apply to new uploads. Queries accept up to 300 characters and
return at most 20 matches. The initial cutoff is 0.08.

## Search and extension point

`KnowledgeLibrary.search(query, top_k)` in `backend/app/knowledge.py` can be
called directly from other backend modules. TF-IDF gives weight to matching
words and two-word phrases, with more weight for terms that occur in fewer
excerpts. Cosine similarity ranks how closely each excerpt's weighted terms
match the query. A score measures lexical similarity. It does not express
diagnostic confidence or establish that a fault is present.

This version favors English maintenance references. Default tokenization and
English stop words limit Chinese search. Translations and synonyms often
require a query that uses wording from the document. The implementation
recomputes corpus weights on each search, a trade-off for keeping uploads and
deletions immediately visible at this scale. Later work can reuse the returned
citation fields with a different retrieval method or for diagnosis. This phase
uses lexical TF-IDF and does not require a model API or vector database.

The seeded documents are educational prose. The five channels they discuss are
measurements from the UCI hydraulic test rig. The examples contain no fabricated
device readings or manufacturer-specific maintenance thresholds.

## Verification

From the project root on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check backend ml scripts
Set-Location frontend
pnpm lint
pnpm test
pnpm build
```

Open `/knowledge`, upload disposable TXT and Markdown files, view the excerpts,
and search for `low system pressure abnormalities`. Verify the citation and
score, then search for `galaxy cryptocurrency` to see the empty state. Restart
the backend with the same SQLite path and verify the uploads still appear.
Confirm deletion of a disposable upload and verify it leaves the list and
search results. Use a separate database path for this workflow.
