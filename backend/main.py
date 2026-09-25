"""
KnowledgeVault backend - KV-5: FastAPI project scaffold.

This is the foundation everything else in the backend builds on top of.
It proves the framework and project layout work, per Section 5.2 of the
Vision/Roadmap/Release Plan. The upload endpoint (KV-6) and data model
(KV-7) are built on top of this in the next tasks.
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="KnowledgeVault API",
    description="Backend service for the KnowledgeVault capstone project.",
    version="0.1.0",
)

# Allow the local frontend dev server (Vite default port) to call this API.
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="localhost", port=8000, reload=True)
