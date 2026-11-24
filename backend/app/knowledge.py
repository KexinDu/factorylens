import re
import sqlite3
import unicodedata
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MAX_QUERY_LENGTH = 300
MAX_TOP_K = 20
MAX_DOCUMENTS = 100
MIN_SCORE = 0.08
EXAMPLE_SOURCE = "FactoryLens educational demonstration content"
EXAMPLE_DIR = Path(__file__).with_name("knowledge_examples")
HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)


class DuplicateDocument(ValueError):
    pass


class LibraryFull(ValueError):
    pass


def content_digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def parse_document(filename: str, content: bytes) -> str:
    if Path(filename).suffix.lower() not in {".txt", ".md", ".markdown"}:
        raise ValueError("Only .txt, .md and .markdown files are accepted.")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("The file must use UTF-8 encoding.") from exc
    decoded = decoded.replace("\r\n", "\n").replace("\r", "\n")
    if any(
        unicodedata.category(char) == "Cc" and char not in "\t\n"
        for char in decoded
    ):
        raise ValueError("The file contains binary or unsupported control characters.")
    cleaned = "\n".join(line.rstrip() for line in decoded.split("\n")).strip()
    if not cleaned:
        raise ValueError("The file is empty or contains only whitespace.")
    return cleaned


def split_document(
    text: str, length: int, overlap: int, *, markdown: bool
) -> list[tuple[str | None, str]]:
    if length <= 0 or not 0 <= overlap < length:
        raise ValueError("Chunk overlap must be smaller than the chunk length.")
    sections = []
    start, heading = 0, None
    if markdown:
        for match in HEADING.finditer(text):
            sections.append((heading, text[start:match.start()]))
            start, heading = match.start(), match.group(1)
    sections.append((heading, text[start:]))

    chunks = []
    for heading, section in sections:
        section = section.strip()
        start = 0
        while start < len(section):
            end = min(start + length, len(section))
            if end < len(section):
                # Prefer a nearby word boundary if it leaves enough room to advance.
                boundary = max(section.rfind(char, start, end) for char in (" ", "\n", "\t"))
                if boundary >= start + max(overlap + 1, length * 3 // 4):
                    end = boundary
            excerpt = section[start:end].strip()
            if excerpt:
                chunks.append((heading, excerpt))
            if end == len(section):
                break
            start = end - overlap
    return chunks


class KnowledgeLibrary:
    def __init__(self, path: Path, chunk_length: int, chunk_overlap: int):
        self.path = path
        self.chunk_length = chunk_length
        self.chunk_overlap = chunk_overlap

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    document_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    content_hash TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES knowledge_documents(document_id)
                        ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    heading TEXT,
                    text TEXT NOT NULL,
                    UNIQUE(document_id, position)
                );
                CREATE TABLE IF NOT EXISTS knowledge_metadata (key TEXT PRIMARY KEY);
                """)
            db.execute("BEGIN IMMEDIATE")
            seeded = db.execute(
                "INSERT OR IGNORE INTO knowledge_metadata VALUES ('examples-v1')"
            ).rowcount
            if seeded:
                for example in sorted(EXAMPLE_DIR.glob("*.md")):
                    self._insert(db, example.name, example.read_bytes(), EXAMPLE_SOURCE)

    def _insert(self, db: sqlite3.Connection, filename: str, content: bytes, source: str) -> dict:
        text = parse_document(filename, content)
        digest = content_digest(text)
        if db.execute(
            "SELECT 1 FROM knowledge_documents WHERE content_hash = ?", (digest,)
        ).fetchone():
            raise DuplicateDocument("This document's text is already in the knowledge base.")
        count = db.execute("SELECT COUNT(*) FROM knowledge_documents").fetchone()[0]
        if count >= MAX_DOCUMENTS:
            raise LibraryFull(f"The knowledge base can contain at most {MAX_DOCUMENTS} documents.")
        chunks = split_document(
            text, self.chunk_length, self.chunk_overlap,
            markdown=Path(filename).suffix.lower() != ".txt",
        )
        document_id = uuid4().hex
        uploaded_at = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO knowledge_documents VALUES (?, ?, ?, ?, ?)",
            (document_id, filename, uploaded_at, source, digest),
        )
        db.executemany(
            "INSERT INTO knowledge_chunks VALUES (?, ?, ?, ?, ?)",
            (
                (f"{document_id}:{position}", document_id, position, heading, excerpt)
                for position, (heading, excerpt) in enumerate(chunks, 1)
            ),
        )
        return {
            "document_id": document_id,
            "filename": filename,
            "uploaded_at": uploaded_at,
            "source": source,
            "chunk_count": len(chunks),
        }

    def upload(self, filename: str, content: bytes, source: str) -> dict:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            return self._insert(db, filename, content, source)

    def list_documents(self) -> list[dict]:
        with closing(self._connect()) as db:
            return [dict(row) for row in db.execute("""
                SELECT d.document_id, d.filename, d.uploaded_at, d.source,
                       COUNT(c.chunk_id) AS chunk_count
                FROM knowledge_documents d JOIN knowledge_chunks c USING (document_id)
                GROUP BY d.document_id ORDER BY d.uploaded_at DESC, d.document_id
                """)]

    def get_document(self, document_id: str) -> dict | None:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN")
            document = db.execute("""
                SELECT document_id, filename, uploaded_at, source
                FROM knowledge_documents WHERE document_id = ?
                """, (document_id,)).fetchone()
            if document is None:
                return None
            chunks = [dict(row) for row in db.execute("""
                SELECT chunk_id, document_id, filename, position, heading, text
                FROM knowledge_chunks JOIN knowledge_documents USING (document_id)
                WHERE document_id = ? ORDER BY position
                """, (document_id,))]
            return {**dict(document), "chunk_count": len(chunks), "chunks": chunks}

    def delete(self, document_id: str) -> bool:
        with closing(self._connect()) as db, db:
            return bool(db.execute(
                "DELETE FROM knowledge_documents WHERE document_id = ?", (document_id,)
            ).rowcount)

    def search(self, query: str, top_k: int = 5, *, public_only: bool = False) -> list[dict]:
        """Rank current text excerpts for reuse by API and diagnostic workflows."""
        query = query.strip()
        if not 1 <= len(query) <= MAX_QUERY_LENGTH or not 1 <= top_k <= MAX_TOP_K:
            raise ValueError("Provide a query of 1–300 characters and a top_k of 1–20.")
        with closing(self._connect()) as db:
            chunks = db.execute("""
                SELECT chunk_id, document_id, filename, source, position, heading, text,
                       content_hash
                FROM knowledge_chunks JOIN knowledge_documents USING (document_id)
                WHERE (? = 0 OR source = ?)
                ORDER BY filename, document_id, position
                """, (public_only, EXAMPLE_SOURCE)).fetchall()
        if public_only:
            examples = {
                (path.name, content_digest(parse_document(path.name, path.read_bytes())))
                for path in EXAMPLE_DIR.glob("*.md")
            }
            chunks = [
                row for row in chunks
                if row["source"] == EXAMPLE_SOURCE
                and (row["filename"], row["content_hash"]) in examples
            ]
        # A single fitted vocabulary keeps query and document weights comparable.
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        analyze = vectorizer.build_analyzer()
        if not chunks or not analyze(query):
            return []
        corpus = [f"{row['heading'] or ''}\n{row['text']}" for row in chunks]
        try:
            matrix = vectorizer.fit_transform(corpus)
        except ValueError as exc:
            if "empty vocabulary" not in str(exc):
                raise
            return []
        vector = vectorizer.transform([query])
        scores = cosine_similarity(vector, matrix).ravel()
        ranked = sorted(range(len(chunks)), key=lambda index: -scores[index])
        matches = []
        for index in ranked[:top_k]:
            if scores[index] < MIN_SCORE:
                break
            match = dict(chunks[index])
            match.pop("content_hash")
            match["score"] = round(float(scores[index]), 6)
            matches.append(match)
        return matches
