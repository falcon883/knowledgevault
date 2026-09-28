# KnowledgeVault Backend

## KV-7: Initial data model

Defines the schema for documents and chunks using SQLAlchemy, so both of
you build against the same structure going forward.

## Schema

**documents**
| column | type | notes |
|---|---|---|
| id | integer, PK | |
| filename | string | |
| content_type | string | e.g. `application/pdf` |
| size_bytes | integer | |
| extracted_text | text | full text from KV-6's extraction |
| uploaded_at | datetime | defaults to now (UTC) |
| tags | text | comma-separated; filled in once auto-tagging exists (Theme 2) |
| summary | text | filled in once summarization exists (Theme 2) |

**chunks**
| column | type | notes |
|---|---|---|
| id | integer, PK | |
| document_id | integer, FK -> documents.id | |
| chunk_index | integer | position within the document |
| text | text | the chunk's text content |
| embedding | text | placeholder until the vector DB/embedding model is picked (Theme 2) |

No `user_id` / ownership column yet - auth and per-user data isolation
are Theme 4 work, so that column is added when that lands rather than
now.

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

By default this uses a local SQLite file (`knowledgevault.db`, gitignored)
so there's nothing to install to try it out. To point at real Postgres
later, set an environment variable before running:

```bash
export DATABASE_URL="postgresql://user:password@host:5432/knowledgevault"
```

## Create the tables

```bash
python init_db.py
```

## Verify the schema works

```bash
python test_models.py
```

Inserts a document and a chunk, confirms the relationship works, then
cleans up after itself. Should print "KV-7 schema check passed."

## Next steps

- Wire `POST /upload` (KV-6) to actually save a `Document` row instead of
  just returning the extracted text
- Roadmap Theme 2: chunking strategy, embedding generation, fill in the
  `embedding` column for real
