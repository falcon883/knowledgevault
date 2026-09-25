"""
KnowledgeVault backend - Sprint 1 scaffold.

This is a placeholder FastAPI service demonstrating the chosen framework
and project layout, per Section 5.2 of the Vision/Roadmap/Release Plan.
Real ingestion, embedding, and search logic will be built incrementally
starting in Sprint 1 (see Section 2 of the Vision doc).
"""

from datetime import datetime, timezone

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="KnowledgeVault API",
    description="Backend service for the KnowledgeVault capstone project.",
    version="0.1.0",
)

# Allow the local frontend dev server to call this API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Basic status endpoint used to confirm the service is running."""
    return {
        "status": "ok",
        "service": "knowledgevault-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Placeholder upload endpoint.

    Sprint 1 will replace this stub with real text extraction and
    chunking (see Roadmap Theme 1). For now it only confirms receipt
    of the file so the frontend team can build against a stable contract.
    """
    contents = await file.read()
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(contents),
        "status": "received (processing not yet implemented)",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
