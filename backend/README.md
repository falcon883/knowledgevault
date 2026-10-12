# KnowledgeVault Backend

## Sprint 2: ingestion pipeline + semantic search foundation

Builds on Sprint 1 (KV-5/6/7). This sprint:

- **KV-13**: `POST /upload` now actually persists a `Document` row instead
  of just returning extracted text.
- **KV-14**: document text is split into overlapping chunks (`chunking.py`).
- **KV-15**: each chunk is embedded locally (`embeddings.py`) and stored in
  a **pgvector** column for semantic similarity search.

- **KV-16**: `POST /search` embeds a plain-language query and returns the
  closest documents by meaning (pgvector cosine distance).

- **KV-21**: every upload now gets automatic tags and a short summary
  (`enrichment.py`), stored on the document and returned by `/upload`,
  `/documents`, and `/search`.

Not yet wired in (separate Sprint 2 tickets): the frontend screens
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

## Tags and summaries

Both run locally on the same embedding model as search, so there is no API
key, cost, or extra service.

- **Tags** (up to 5): candidate words and two-word phrases are pulled from
  the text and ranked by how close they are in meaning to the whole
  document, with a penalty so the list isn't five near-duplicates.
- **Summary** (up to 3 sentences): the sentences closest in meaning to the
  whole document, kept in their original order. It only reuses sentences
  from the document, so it can't make anything up. Text with no real
  sentences (schedules, tables) falls back to the first 300 characters.
- If tagging ever fails, the upload still succeeds and the fields stay null.

```bash
python test_enrichment.py          # check it works
python backfill_enrichment.py      # fill in documents uploaded before KV-21
python backfill_enrichment.py --all  # redo every document
```

## Search

```bash
python test_search.py
```

Uploads three small documents on different topics, searches them, and
checks the right one ranks first. Cleans up after itself.

Example request (also available in `/docs`):

```json
POST /search
{ "query": "how old is the universe", "limit": 5, "min_score": 0.25 }
```

Response:

```json
{
  "query": "how old is the universe",
  "count": 1,
  "results": [
    {
      "document_id": 3,
      "filename": "notes.pdf",
      "score": 0.6123,
      "snippet": "The telescope observed a distant galaxy...",
      "chunk_index": 0,
      "tags": null,
      "summary": null
    }
  ]
}
```

- One result per document: its best-matching chunk, closest first.
- `score` is cosine similarity (1.0 = same meaning, near 0 = unrelated).
  Scores are relative, so use them for ordering rather than as a pass/fail
  cutoff.
- `limit` is 1 to 20 (default 5). A blank query returns 400.
- `min_score` (default 0.25) hides weak matches so unrelated documents don't
  pad the list. Send `0` to see everything. To change the default, edit
  `MIN_SCORE` in `main.py`.
- `tags` (comma-separated) and `summary` come from KV-21. They are null
  for documents uploaded before it, until you run `backfill_enrichment.py`.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Status check |
| `POST /upload` | Upload a PDF or text file; persists it, chunks it, embeds each chunk, adds tags and a summary |
| `POST /search` | Semantic search: returns the best-matching documents for a query |
| `GET /documents` | List uploaded documents, most recent first (backs the KV-17 browse screen) |

## Next steps

- Possible later improvement: swap the extractive summary for an LLM-written one if the team decides the API dependency is worth it
