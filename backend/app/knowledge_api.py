from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from .knowledge import MAX_QUERY_LENGTH, MAX_TOP_K, DuplicateDocument, LibraryFull

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class Document(BaseModel):
    document_id: str
    filename: str
    uploaded_at: str
    source: str
    chunk_count: int


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    position: int
    heading: str | None
    text: str


class DocumentDetail(Document):
    chunks: list[Chunk]


class SearchResult(Chunk):
    source: str
    score: float


@router.get("/documents", response_model=list[Document])
def list_documents(request: Request):
    return request.app.state.knowledge.list_documents()


@router.post("/documents", status_code=201, response_model=Document)
def upload_document(
    request: Request,
    file: Annotated[UploadFile, File()],
    source: Annotated[str, Form(max_length=200)] = "",
):
    filename = PurePosixPath((file.filename or "").replace("\\", "/")).name
    if not filename or len(filename) > 255 or not filename.isprintable():
        raise HTTPException(400, "Provide a printable filename of at most 255 characters.")
    limit = request.app.state.knowledge_upload_limit
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, f"The file exceeds the {limit:,}-byte upload limit.")
    try:
        return request.app.state.knowledge.upload(
            filename, content, source.strip() or "User upload"
        )
    except DuplicateDocument as exc:
        raise HTTPException(409, str(exc)) from exc
    except LibraryFull as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, request: Request):
    document = request.app.state.knowledge.get_document(document_id)
    if document is None:
        raise HTTPException(404, "Knowledge document not found.")
    return document


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, request: Request):
    if not request.app.state.knowledge.delete(document_id):
        raise HTTPException(404, "Knowledge document not found.")


@router.get("/search", response_model=list[SearchResult])
def search(
    request: Request,
    q: Annotated[str, Query(min_length=1, max_length=MAX_QUERY_LENGTH)],
    top_k: Annotated[int, Query(ge=1, le=MAX_TOP_K)] = 5,
):
    try:
        return request.app.state.knowledge.search(q, top_k)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
