"""
KnowledgeVault backend - Sprint 2.

Builds on Sprint 1 (KV-5/6/7). This wires the upload endpoint to actually
persist a document (KV-13), splits its text into chunks (KV-14), and
embeds each chunk with a local sentence-transformers model, stored in a
pgvector column (KV-15).

Sprint 2 also adds POST /search (KV-16): semantic search over the stored
chunk embeddings, and automatic tags plus a summary for each upload (KV-21,
see enrichment.py), and DELETE /documents/{id} to remove a document.

Sprint 3 starts with upload validation (KV-24, see uploads.py): every bad
upload is rejected with a clear message before anything is saved. KV-26 adds
what the refined Browse and Search screens need: GET /tags, tag/date/sort
filters on GET /documents, and GET /documents/{id}.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, defer

from chunking import chunk_text
from database import get_db
from embeddings import embed_text, embed_texts
from enrichment import enrich
from init_db import upgrade_schema
from models import Chunk, Document
from uploads import (
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    UploadError,
    check_size,
    content_hash,
    detect_kind,
    extract_text,
)

logger = logging.getLogger("knowledgevault")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Add any columns this version needs to an existing database (KV-25), so
    # pulling new code never leaves the API running against an old schema.
    try:
        filled = upgrade_schema()
        if filled:
            logger.info("Backfilled content_hash for %d document(s)", filled)
    except Exception:
        logger.exception("Could not update the database schema; run python init_db.py")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="KnowledgeVault API",
    description="Backend service for the KnowledgeVault capstone project.",
    version="0.9.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(UploadError)
async def upload_error_handler(request: Request, exc: UploadError):
    """
    All upload problems come back as {"detail": <message>, "code": <code>},
    plus extra fields for a few codes (duplicate_document adds `existing`).
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code, **exc.extra},
    )


@app.get("/health")
def health_check():
    """Basic status endpoint used to confirm the service is running."""
    return {
        "status": "ok",
        "service": "knowledgevault-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "max_upload_mb": MAX_UPLOAD_MB,
    }


@app.post("/upload")
async def upload_document(
    file: UploadFile | None = File(None),
    allow_duplicate: bool = Query(
        False, description="Store the file even if the same content is already uploaded."
    ),
    db: Session = Depends(get_db),
):
    """
    Accept a document (PDF or plain text), extract its text, persist it
    as a Document, split it into Chunks, embed each chunk, and return the
    saved document. The full ingestion path: upload -> validate -> extract
    -> chunk -> embed -> persist.

    Validation (KV-24, see uploads.py) happens first and nothing is saved
    unless the file passes. A file whose text matches a document already
    stored is refused with 409 duplicate_document (KV-25) unless
    `allow_duplicate=true` is passed. The document and its chunks are written in one
    transaction, so a failure part way through leaves nothing behind.
    """
    if file is None or not (file.filename or "").strip():
        raise UploadError(400, "no_file", "No file was uploaded.")

    kind, content_type = detect_kind(file.filename, file.content_type)

    # Read one byte past the limit so an oversized file is caught without
    # loading all of it into memory.
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    check_size(contents)

    extracted_text = extract_text(kind, contents)

    # KV-25: refuse a re-upload before spending time embedding it.
    text_hash = content_hash(extracted_text)
    if not allow_duplicate:
        existing = db.execute(
            select(Document)
            .where(Document.content_hash == text_hash)
            .order_by(Document.id)
            .options(defer(Document.extracted_text))
            .limit(1)
        ).scalar_one_or_none()
        if existing is not None:
            raise UploadError(
                409,
                "duplicate_document",
                f"This looks like a file you already uploaded: \"{existing.filename}\".",
                extra={
                    "existing": {
                        "id": existing.id,
                        "filename": existing.filename,
                        "uploaded_at": existing.uploaded_at.isoformat(),
                    }
                },
            )

    chunk_texts = chunk_text(extracted_text)

    try:
        chunk_vectors = embed_texts(chunk_texts)
        document = Document(
            filename=file.filename,
            content_type=content_type,
            size_bytes=len(contents),
            extracted_text=extracted_text,
            content_hash=text_hash,
        )
        db.add(document)
        db.flush()  # assigns document.id without committing yet
        for index, (text, vector) in enumerate(zip(chunk_texts, chunk_vectors)):
            db.add(
                Chunk(
                    document_id=document.id,
                    chunk_index=index,
                    text=text,
                    embedding=vector,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not process upload %r", file.filename)
        raise UploadError(
            500,
            "processing_failed",
            "The file was read, but it could not be processed. Nothing was saved. Please try again.",
        )
    db.refresh(document)

    # KV-21: tags and summary. The upload is already saved and searchable
    # at this point, so a failure here is logged and skipped rather than
    # turned into an error for the user.
    try:
        document.tags, document.summary = enrich(extracted_text, chunk_vectors)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Tagging/summarization failed for document %s", document.id)

    return {
        "id": document.id,
        "filename": document.filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "uploaded_at": document.uploaded_at.isoformat(),
        "chunk_count": len(chunk_texts),
        "tags": document.tags,
        "summary": document.summary,
        "status": "stored and embedded",
    }


def parse_tags(tags: str | None) -> list[str]:
    """Document.tags is stored as one comma-separated string."""
    return [tag.strip() for tag in (tags or "").split(",") if tag.strip()]


def document_summary(doc: Document, chunk_count: int) -> dict:
    """The fields shown for a document in lists. Same shape as before KV-26."""
    return {
        "id": doc.id,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "size_bytes": doc.size_bytes,
        "uploaded_at": doc.uploaded_at.isoformat(),
        "tags": doc.tags,
        "summary": doc.summary,
        "chunk_count": chunk_count,
    }


@app.get("/documents")
def list_documents(
    tag: str | None = Query(
        None, description="Only documents with this tag (exact match, ignoring case)."
    ),
    since: datetime | None = Query(
        None,
        description="Only documents uploaded at or after this date or time, "
        "e.g. 2026-10-12 or 2026-10-12T09:30:00Z. A date or time with no "
        "zone is read as UTC.",
    ),
    sort: Literal["newest", "oldest", "name"] = Query(
        "newest", description="newest (default), oldest, or name (A to Z)."
    ),
    db: Session = Depends(get_db),
):
    """
    List uploaded documents. Backs the browse screen (KV-17). With no
    parameters it returns everything, newest first, as it always has.
    KV-26 adds optional filters: `tag`, `since`, and `sort`. They combine.
    No pagination yet, since the corpus this project targets is small
    (Project Charter 2.3).
    """
    query = (
        select(Document, func.count(Chunk.id))
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .group_by(Document.id)
        # The text can be large and the list never shows it.
        .options(defer(Document.extracted_text))
    )

    if since is not None:
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        query = query.where(Document.uploaded_at >= since)

    if sort == "oldest":
        query = query.order_by(Document.uploaded_at.asc(), Document.id.asc())
    elif sort == "name":
        query = query.order_by(func.lower(Document.filename).asc(), Document.id.asc())
    else:
        query = query.order_by(Document.uploaded_at.desc(), Document.id.desc())

    wanted = (tag or "").strip().lower()
    return [
        document_summary(doc, chunk_count)
        for doc, chunk_count in db.execute(query).all()
        if not wanted or wanted in (t.lower() for t in parse_tags(doc.tags))
    ]


@app.get("/documents/{document_id}")
def get_document(
    document_id: int,
    max_chars: int | None = Query(
        None,
        ge=1,
        le=1_000_000,
        description="Cut the returned text to this many characters (for previews).",
    ),
    db: Session = Depends(get_db),
):
    """
    One document in full (KV-26): the list fields plus its extracted text,
    for previews. `truncated` is true when `max_chars` cut the text short;
    `text_length` is always the full length.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")

    chunk_count = db.scalar(
        select(func.count(Chunk.id)).where(Chunk.document_id == document_id)
    )
    text = document.extracted_text or ""
    truncated = max_chars is not None and len(text) > max_chars
    return {
        **document_summary(document, chunk_count),
        "extracted_text": text[:max_chars] if truncated else text,
        "text_length": len(text),
        "truncated": truncated,
    }


@app.get("/tags")
def list_tags(
    limit: int | None = Query(None, ge=1, le=500, description="Return only the top N tags."),
    db: Session = Depends(get_db),
):
    """
    Every tag in use with the number of documents that have it, most common
    first (ties A to Z). Tags are matched ignoring case, so "Recipes" and
    "recipes" count as one. Backs the tag filter on the browse screen (KV-26).
    """
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for tags in db.execute(select(Document.tags).where(Document.tags.is_not(None))).scalars():
        for key in {tag.lower() for tag in parse_tags(tags)}:
            counts[key] = counts.get(key, 0) + 1
        for tag in parse_tags(tags):
            labels.setdefault(tag.lower(), tag)

    ordered = sorted(counts, key=lambda key: (-counts[key], key))
    if limit is not None:
        ordered = ordered[:limit]
    return [{"tag": labels[key], "count": counts[key]} for key in ordered]


# Results scoring below this are treated as noise and left out. Real matches
# scored roughly 0.4 to 0.7 in testing, unrelated documents 0.2 or lower.
MIN_SCORE = 0.25


class SearchRequest(BaseModel):
    query: str = Field(..., max_length=500, description="What to look for, in plain language.")
    limit: int = Field(5, ge=1, le=20, description="Maximum number of documents to return.")
    min_score: float = Field(
        MIN_SCORE,
        ge=0.0,
        le=1.0,
        description="Hide results less similar than this. Use 0 to see everything.",
    )


# How many of the closest chunks to pull before collapsing them to one
# result per document. Larger than the max `limit` so a document with many
# near-identical chunks can't crowd every other document out of the results.
CANDIDATE_CHUNKS = 100
SNIPPET_CHARS = 300


@app.post("/search")
def search_documents(request: SearchRequest, db: Session = Depends(get_db)):
    """
    Semantic search (KV-16). Embeds the query with the same model used at
    upload time, finds the closest chunks by cosine distance in pgvector,
    and returns one result per document: its best-matching chunk, a
    similarity score (1.0 = identical meaning, around 0 = unrelated), and
    the document's tags/summary. Results below `min_score` (default 0.25)
    are left out so unrelated documents don't pad the list. Backs the
    search screen (KV-18).
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    query_vector = embed_text(query)
    distance = Chunk.embedding.cosine_distance(query_vector)

    rows = db.execute(
        select(Chunk, distance.label("distance"))
        .where(Chunk.embedding.is_not(None))
        .order_by(distance)
        .limit(CANDIDATE_CHUNKS)
    ).all()

    # Rows arrive closest-first, so the first chunk seen for a document is
    # its best match. Keep that one and move on.
    results = []
    seen_documents = set()
    for chunk, dist in rows:
        if chunk.document_id in seen_documents:
            continue
        seen_documents.add(chunk.document_id)
        score = round(1 - float(dist), 4)
        if score < request.min_score:
            # Rows are closest-first, so everything after this is lower too.
            break
        doc = chunk.document
        results.append(
            {
                "document_id": doc.id,
                "filename": doc.filename,
                "score": score,
                "snippet": chunk.text[:SNIPPET_CHARS],
                "chunk_index": chunk.chunk_index,
                "tags": doc.tags,
                "summary": doc.summary,
            }
        )
        if len(results) == request.limit:
            break

    return {"query": query, "count": len(results), "results": results}


@app.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """
    Delete a document and everything derived from it (its chunks and their
    embeddings), so it no longer shows up in /documents or /search.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")

    filename = document.filename
    db.delete(document)  # chunks go with it (cascade on Document.chunks)
    db.commit()
    return {"id": document_id, "filename": filename, "status": "deleted"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
