"""
KnowledgeVault backend - KV-6: Upload endpoint and text extraction.

Builds on the KV-5 scaffold. Accepts an uploaded document (PDF or plain
text), extracts its raw text, and returns it. Nothing is persisted yet -
that's KV-7 (data model) and later ingestion-pipeline work.
"""

import io
from datetime import datetime, timezone

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader

app = FastAPI(
    title="KnowledgeVault API",
    description="Backend service for the KnowledgeVault capstone project.",
    version="0.2.0",
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
async def upload_document(file: UploadFile = File(...)):
    """
    Accept a document (PDF or plain text), extract its raw text, and
    return it. This proves the upload -> extraction path end-to-end.
    Chunking, embeddings, and storage are built in upcoming sprints.
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

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(contents),
        "extracted_text": extracted_text,
        "extracted_length": len(extracted_text),
        "status": "extracted (not yet persisted - see KV-7)",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="localhost", port=8000, reload=True)
