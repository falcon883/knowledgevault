# KnowledgeVault Backend

FastAPI service for KnowledgeVault: ingestion, semantic search, tags and
summaries, and the browse API used by the React frontend (see the
[root README](../README.md) for the whole project).

## Sprint 3: upload validation, duplicate detection, browse and preview API

- **KV-24**: every bad upload is rejected with a clear message before
  anything is saved (`uploads.py`). See [Upload errors](#upload-errors).
- **KV-25**: uploading a file whose text is already stored is refused with
  `409 duplicate_document`, pointing at the existing document. See
  [Duplicate uploads](#duplicate-uploads).
- **KV-33**: the API stays responsive during uploads, and the embedding
  model is loaded when the server starts. See
  [Responsiveness and startup](#responsiveness-and-startup).
- **KV-26**: new endpoints for the refined Browse and Search screens:
  `GET /tags`, `tag` / `since` / `sort` filters on `GET /documents`, and
  `GET /documents/{id}` for previews. See [Endpoints](#endpoints).

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

The React frontend (`../frontend`) uses these endpoints for its Capture
(upload), Browse and Search screens.

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
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
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

On start the server loads the embedding model (a few seconds; the very first
run also downloads it, about 90 MB), so it is ready before the first request.
The log line `Embedding model loaded in X.Xs` shows when it is. `GET /health`
reports `"model_loaded": true` once it is.

## Running the tests

```bash
pip install -r requirements-dev.txt    # once: adds pytest
pytest                                 # all backend tests
pytest tests/test_search.py            # one file
pytest -k duplicate                    # tests with "duplicate" in the name
```

Run it from the `backend/` folder, with Postgres and pgvector running. The
tests use the real embedding model, so the first run downloads it (~90 MB,
cached after that). Every test deletes the documents it creates, so your own
documents are left alone. To keep the tests in a completely separate
database, create an empty one and set `TEST_DATABASE_URL` to its URL.

For a quick run with no model download, set `KV_FAKE_EMBEDDINGS=1` (search
ranking is rougher, but every test still passes). The same `pytest` command
runs in GitHub Actions on every push and pull request (`.github/workflows/ci.yml`),
against a throwaway Postgres with pgvector. The tests are in `tests/`:

| File | Covers |
|---|---|
| `test_models.py` | tables, chunk cascade |
| `test_pipeline.py` | chunking, embeddings, pgvector similarity (KV-13/14/15) |
| `test_search.py` | semantic search ranking and validation (KV-16) |
| `test_enrichment.py` | tags and summaries (KV-21) |
| `test_delete.py` | `DELETE /documents/{id}` |
| `test_upload_validation.py` | upload error cases (KV-24) |
| `test_duplicate_upload.py` | duplicate detection (KV-25) |
| `test_browse_api.py` | filters, `/tags`, document detail (KV-26) |
| `test_responsiveness.py` | searches during an upload, model loaded at startup (KV-33) |

## Upload errors

`POST /upload` accepts PDF and plain text (`.txt`) files up to
`MAX_UPLOAD_MB` (default 10; set it in `.env` or the environment). Anything
else is rejected before it is saved, always in the same shape. `detail` is a
plain-language message that can be shown to the user as is, and `code` is
stable for the frontend to branch on:

```json
{"detail": "This file is larger than the 10 MB limit. Try a smaller file, or split it into parts.", "code": "file_too_large"}
```

| code | status | when |
|---|---|---|
| `no_file` | 400 | request had no file |
| `unsupported_type` | 415 | not a PDF or plain text file |
| `file_too_large` | 413 | bigger than `MAX_UPLOAD_MB` |
| `empty_file` | 400 | zero bytes |
| `unreadable_pdf` | 422 | damaged, or not really a PDF |
| `password_protected_pdf` | 422 | PDF needs a password |
| `unreadable_text` | 422 | not plain text (binary data) |
| `no_text` | 422 | readable file, but no text in it (for example a scanned PDF) |
| `duplicate_document` | 409 | same content as a document already stored (adds `existing`) |
| `processing_failed` | 500 | text was fine, but saving or embedding failed; nothing is kept |

A file sent with a generic type (`application/octet-stream` or none) is
judged by its extension. `GET /health` reports the active limit as
`max_upload_mb`.

### Duplicate uploads

Each document is stored with a fingerprint of its text (`content_hash`,
SHA-256 of the extracted text with whitespace collapsed). If a new upload
has the same fingerprint as a stored document it is refused before it is
embedded or saved:

```json
{
  "detail": "This looks like a file you already uploaded: \"notes.txt\".",
  "code": "duplicate_document",
  "existing": {"id": 12, "filename": "notes.txt", "uploaded_at": "2026-10-12T14:03:11+00:00"}
}
```

So a renamed copy, or the same text with different spacing or line breaks,
is caught too. To store it anyway, send `POST /upload?allow_duplicate=true`.
Once every copy is deleted the content can be uploaded again.

**After pulling this change, run `python init_db.py` once** (the server also
does the same upgrade when it starts). It adds the `content_hash` column and
fills it in for documents uploaded earlier. It is safe to re-run.

## Responsiveness and startup

`POST /upload` does its slow work (reading the PDF, chunking, embedding,
saving, tagging) on a worker thread, so searches and browsing keep working
while a large file is processed. Embedding is done a few chunks at a time
(`BATCH_SIZE` in `embeddings.py`), so a search that arrives mid-upload waits
for one small batch rather than the whole file.

If the model can't be loaded at startup (for example, the first run is
offline), the server still starts, logs the error, and tries again on first
use.

```bash
python bench_responsiveness.py     # real timings, against a running server (python main.py)
```

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
python backfill_enrichment.py      # fill in documents uploaded before KV-21
python backfill_enrichment.py --all  # redo every document
```

## Search

The search tests upload three small documents on different topics, search them, and
check that the right one ranks first.

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
| `GET /documents` | List uploaded documents (backs the browse screen). Optional filters below |
| `GET /documents/{id}` | One document with its full extracted text, for previews |
| `GET /tags` | Every tag in use with its document count, for the tag filter |
| `DELETE /documents/{id}` | Delete a document and its chunks |

### Browsing: `GET /documents`, `GET /documents/{id}`, `GET /tags`

All parameters are optional and combine. With none, `GET /documents`
behaves as before: everything, newest first.

| Parameter | On | Meaning |
|---|---|---|
| `tag` | `/documents` | Only documents with this tag. Whole tag, ignoring case; blank is ignored |
| `since` | `/documents` | Only documents uploaded at or after this date or time, e.g. `2026-10-12` or `2026-10-12T09:30:00Z`. No zone means UTC |
| `sort` | `/documents` | `newest` (default), `oldest`, or `name` (A to Z, ignoring case) |
| `max_chars` | `/documents/{id}` | Cut `extracted_text` to this many characters (1 to 1,000,000) |
| `limit` | `/tags` | Return only the top N tags (1 to 500) |

Each item in `GET /documents` has `id`, `filename`, `content_type`,
`size_bytes`, `uploaded_at`, `tags`, `summary`, `chunk_count`.

`GET /documents/{id}` returns those same fields plus `extracted_text`,
`text_length` (always the full length) and `truncated` (true when
`max_chars` cut the text). An unknown id gives 404 with
`{"detail": "Document 7 not found."}`.

`GET /tags` returns `[{"tag": "recipes", "count": 4}, ...]`, most common
first (ties A to Z). "Recipes" and "recipes" count as one tag.

## Next steps

- Possible later improvement: swap the extractive summary for an LLM-written one if the team decides the API dependency is worth it
