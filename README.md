# KnowledgeVault

[![CI](https://github.com/falcon883/knowledgevault/actions/workflows/ci.yml/badge.svg)](https://github.com/falcon883/knowledgevault/actions/workflows/ci.yml)

A personal knowledge base that finds your own notes, PDFs, and articles by
meaning rather than by exact keyword. Built as the MSCS 3999 capstone project
at Clark University, Fall 2026.

**Team:** Durvank Deorukhkar (backend), Percival Tapera (frontend)
**Jira:** [KnowledgeVault board](https://clarkcapstone.atlassian.net/jira/software/projects/KV/boards/2)
**Docs:** the Project Charter, Vision/Roadmap/Release Plan and sprint feedback are in [`/docs`](./docs).

## What it does

- **Capture:** upload a PDF or plain text file. The text is extracted,
  split into chunks and embedded locally, and the document gets automatic
  tags and a short summary. Bad files are rejected with a clear message, and
  a file that was already uploaded is flagged as a duplicate.
- **Browse:** list your documents and delete the ones you no longer want.
  The API can already filter by tag and date and return a full-text preview;
  the screen picks these up in Sprint 3.
- **Search:** ask in plain language ("how old is the universe") and get the
  best-matching documents back, ranked by meaning.

Everything runs on your own machine: FastAPI, Postgres with pgvector, and a
local sentence-transformers model, so there are no API keys or per-call costs.

## Repository structure

| Path | Contents |
|---|---|
| [`/backend`](./backend) | FastAPI service, database models, embedding and search code, and the pytest suite. See its [README](./backend/README.md) for details. |
| [`/frontend`](./frontend) | React app built with Vite: Search, Browse and Capture screens. |
| [`/docs`](./docs) | Project Charter, Vision/Roadmap/Release Plan, sprint feedback. |
| [`/.github/workflows`](./.github/workflows) | CI: runs the backend tests on every push and pull request. |

## Getting started

You need Python 3.11+, Node 20+, and Postgres 16 with the pgvector extension.

**Backend** (full steps, including installing Postgres, are in the [backend README](./backend/README.md#setup))
```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # only needed if your database settings differ
python init_db.py                  # creates the tables
python main.py
```
Runs at `http://localhost:8000` (interactive API docs at `/docs`). The first
start downloads the embedding model (about 90 MB).

**Frontend**
```bash
cd frontend
npm install
npm run dev
```
Runs at `http://localhost:5173` and talks to the backend at
`http://localhost:8000`. To point it somewhere else, set `VITE_API_URL`.

**Tests**
```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Status check (also reports the upload limit and whether the model is loaded) |
| `POST /upload` | Upload a PDF or text file |
| `GET /documents` | List documents; optional `tag`, `since` and `sort` filters |
| `GET /documents/{id}` | One document with its full text, for previews |
| `GET /tags` | Every tag in use with its document count |
| `POST /search` | Search by meaning |
| `DELETE /documents/{id}` | Delete a document |

Request and response details are in the [backend README](./backend/README.md#endpoints).

## Status

Release 2 (Sprint 3 of the roadmap) is in progress: upload validation,
duplicate detection, browse filters and previews, and automated tests and CI
are done, and the UX refinements and the pilot session are next. AWS
deployment and user accounts are planned for Sprint 4. See the roadmap in
[`/docs`](./docs) for the full plan.
