# KnowledgeVault Backend

## Sprint 2: ingestion pipeline + semantic search foundation

Builds on Sprint 1 (KV-5/6/7). This sprint:

- **KV-13**: `POST /upload` now actually persists a `Document` row instead
  of just returning extracted text.
- **KV-14**: document text is split into overlapping chunks (`chunking.py`).
- **KV-15**: each chunk is embedded locally (`embeddings.py`) and stored in
  a **pgvector** column for semantic similarity search.

Not yet wired in (separate Sprint 2 tickets): auto-tagging/summarization
(KV-21), the `/search` endpoint (KV-16), and the frontend screens
(KV-17/18/19).

## Why pgvector + local embeddings

Decided at the Sprint 2 kickoff (KV-20), per the Project Charter's
instruction to finalize the vector database choice in Sprint 1-2
(Section 3.7):

- **pgvector** (a Postgres extension) instead of a separate managed
  vector database. The team already runs Postgres for document/chunk
  metadata, so this avoids standing up, paying for, and syncing data
  between two separate systems. It's free and integrates directly with
  the existing SQLAlchemy models.
- **sentence-transformers, run locally** (`all-MiniLM-L6-v2`, 384-dim)
  instead of a hosted embedding API. No API key, no rate limits, no
  per-call cost, and it removes the "third-party API/service dependency"
  risk called out in the Charter's risk table (Section 3.5).

## Setup

### 1. Install Postgres and the pgvector extension

```bash
# macOS (Homebrew)
brew install postgresql@16 pgvector

# Ubuntu/Debian
sudo apt-get install postgresql postgresql-16-pgvector
```

### 2. Create the database and enable the extension

```bash
sudo -u postgres psql -c "CREATE USER knowledgevault WITH PASSWORD 'knowledgevault';"
sudo -u postgres psql -c "CREATE DATABASE knowledgevault OWNER knowledgevault;"
```

(`init_db.py` below runs `CREATE EXTENSION IF NOT EXISTS vector` for you,
no need to do it by hand.)

### 3. Python environment

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` (or just export the variable) if your
Postgres isn't on `localhost:5432` with the default credentials above:

```bash
export DATABASE_URL="postgresql+psycopg2://knowledgevault:knowledgevault@localhost:5432/knowledgevault"
```

### 4. Create the tables

```bash
python init_db.py
```

### 5. Run the server

```bash
python main.py
```

Runs at `http://localhost:8000` (interactive docs at `/docs`).

## Verify the pipeline works

```bash
python test_pipeline.py
```

Inserts a document, chunks and embeds it, confirms a similarity search
against the stored vectors returns it, then cleans up. The first run
downloads the embedding model (~90MB, one-time, cached after that), so it
needs network access to huggingface.co.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Status check |
| `POST /upload` | Upload a PDF or text file; persists it, chunks it, embeds each chunk |
| `GET /documents` | List uploaded documents, most recent first (backs the KV-17 browse screen) |

## Next steps

- KV-16: `POST /search` - embed an incoming query, run `Chunk.embedding.cosine_distance(...)` against the stored vectors, return the top matches
- KV-21: generate tags/summary at upload time and fill in `Document.tags` / `Document.summary`
