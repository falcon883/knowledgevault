"""
KnowledgeVault backend - Sprint 2.

Builds on Sprint 1 (KV-5/6/7). This wires the upload endpoint to actually
persist a document (KV-13), splits its text into chunks (KV-14), and
embeds each chunk with a local sentence-transformers model, stored in a
pgvector column (KV-15).

Auto-tagging/summarization (KV-21) and the semantic search endpoint
(KV-16) are separate Sprint 2 tickets, not yet wired in here.
"""

import io
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
from sqlalchemy.orm import Session

from chunking import chunk_text
from database import get_db
from embeddings import embed_texts
from models import Chunk, Document

app = FastAPI(
    title="KnowledgeVault API",
    description="Backend service for the KnowledgeVault capstone project.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_TYPES = {"application/pdf", "text/plain"}


@app.get("/health")
def health_check():
    """Basic status endpoint used to confirm the service is running."""
    return {
        "status": "ok",
        "service": "knowledgevault-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def extract_text_from_pdf(contents: bytes) -> str:
    reader = PdfReader(io.BytesIO(contents))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text).strip()


def extract_text_from_plain(contents: bytes) -> str:
    return contents.decode("utf-8", errors="replace").strip()


@app.post("/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Accept a document (PDF or plain text), extract its text, persist it
    as a Document, split it into Chunks, embed each chunk, and return the
    saved document. This is the full Sprint 2 ingestion path: upload ->
    extract -> persist -> chunk -> embed.
    """
    if file.content_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. "
            f"Supported types: {', '.join(sorted(SUPPORTED_TYPES))}.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        if file.content_type == "application/pdf":
            extracted_text = extract_text_from_pdf(contents)
        else:
            extracted_text = extract_text_from_plain(contents)
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Could not extract text from file: {exc}"
        )

    document = Document(
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=len(contents),
        extracted_text=extracted_text,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    chunk_texts = chunk_text(extracted_text)
    if chunk_texts:
        chunk_vectors = embed_texts(chunk_texts)
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

    return {
        "id": document.id,
        "filename": document.filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "uploaded_at": document.uploaded_at.isoformat(),
        "chunk_count": len(chunk_texts),
        "status": "stored and embedded",
    }


@app.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    """
    List uploaded documents (most recent first). Backs the browse screen
    (KV-17) - deliberately minimal for now: no pagination/filtering yet,
    since the corpus this sprint targets is small (Project Charter 2.3).
    """
    documents = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "content_type": doc.content_type,
            "size_bytes": doc.size_bytes,
            "uploaded_at": doc.uploaded_at.isoformat(),
            "tags": doc.tags,
            "summary": doc.summary,
            "chunk_count": len(doc.chunks),
        }
        for doc in documents
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
