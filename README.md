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
- **Browse:** list your documents, filter them by type or tag, sort them, read
  a preview of the text, and delete the ones you no longer want.
- **Search:** ask in plain language ("how old is the universe") and get the
  best-matching documents back, ranked by meaning.
- **Accounts:** sign up and sign in. Each person sees only their own documents.

Everything runs on your own machine or on one small server: FastAPI, Postgres
with pgvector, and a local sentence-transformers model, so there are no API
keys or per-call costs.

**Live demo** (Sprint 4 deployment): the app is at
https://d33bsamq53gtgw.cloudfront.net and the API, with its interactive docs,
at https://3-13-43-176.sslip.io/docs.

## Repository structure

| Path | Contents |
|---|---|
| [`/backend`](./backend) | FastAPI service, database models, embedding and search code, and the pytest suite. See its [README](./backend/README.md) for details. |
| [`/frontend`](./frontend) | React app built with Vite: Search, Browse and Capture screens. |
| [`/e2e`](./e2e) | End-to-end browser tests (Playwright): sign up, add, browse, search, delete, through the real screens. See its [README](./e2e/README.md). |
| [`/docs`](./docs) | Project Charter, Vision/Roadmap/Release Plan, architecture, sprint feedback. |
| [`docker-compose.yml`](./docker-compose.yml) | Starts Postgres with pgvector and the backend with one command (see Getting started). |
| [`/deploy`](./deploy) | AWS deployment: step-by-step guide, HTTPS config and an end-to-end check script. Used with [`docker-compose.prod.yml`](./docker-compose.prod.yml). |
| [`/.github/workflows`](./.github/workflows) | CI: runs the backend, frontend and end-to-end tests and builds and checks the Docker stack, on every push and pull request. |

## Getting started

You need [Docker](https://docs.docker.com/get-docker/) (Docker Desktop on
Windows and macOS) and Node 20+ for the frontend.

**Backend and database** (one command, from the repo root)
```bash
docker compose up --build
```
The first run builds the backend image and downloads the embedding model
(a few minutes). After that it starts in seconds. The API runs at
`http://localhost:8000` (interactive docs at `/docs`) and the tables are
created for you. Your documents are kept in a Docker volume, so
`docker compose down` stops everything without losing them; use
`docker compose down -v` to wipe the database too. Postgres is reachable from
your machine on port 5433, so it does not clash with a Postgres you may
already have on 5432. Settings you can override are listed at the top of
`docker-compose.yml`.

Prefer to run the backend without Docker? Install Python 3.11+ and Postgres 16
with pgvector, then follow the
[backend README](./backend/README.md#setup-without-docker).

**Frontend**
```bash
cd frontend
npm install
npm run dev
```
Runs at `http://localhost:5173` and talks to the backend at
`http://localhost:8000`. To point it somewhere else, set `VITE_API_URL`.

**Tests** (need Python 3.11+ and the database from `docker compose up -d db`)
```bash
cd backend
pip install -r requirements-dev.txt
DATABASE_URL=postgresql+psycopg2://knowledgevault:knowledgevault@localhost:5433/knowledgevault pytest
```
More on running the tests is in the [backend README](./backend/README.md#running-the-tests).

**End-to-end tests** (a real browser against the real screens and API; same database as above, set in `DATABASE_URL` or `backend/.env`)
```bash
cd e2e
npm install && npm run setup   # once
npm test
```
Details, and what each test covers, are in the [e2e README](./e2e/README.md).

## Deployment

The backend and database run on one small AWS server (EC2) with HTTPS from
Caddy, using `docker-compose.prod.yml`. Settings and secrets live in a `.env`
file on the server, never in the repo (`.env.example` lists them). The full
step-by-step guide, from creating the AWS account to checking the deployed API,
is in [`deploy/README.md`](./deploy/README.md). To check any running API end
to end (health, upload, search):

```bash
python deploy/smoke_test.py https://your-api-address     # or http://localhost:8000
```

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Status check: is the database reachable (503 if not), is the model loaded, upload limit |
| `POST /auth/signup`, `POST /auth/login` | Create an account or sign in; returns a token |
| `GET /auth/me` | The signed-in user |
| `POST /upload` | Upload a PDF or text file |
| `GET /documents` | List your documents; optional `tag`, `since` and `sort` filters |
| `GET /documents/{id}` | One of your documents with its full text, for previews |
| `GET /tags` | Every tag in your documents with its document count |
| `POST /search` | Search your documents by meaning |
| `DELETE /documents/{id}` | Delete one of your documents |

Everything except `/health`, signup and login needs `Authorization: Bearer <token>`,
and each person sees only their own documents. Details are in the
[backend README](./backend/README.md#accounts).

Request and response details are in the [backend README](./backend/README.md#endpoints).

## Status

Release 2 (Pilot Beta) is done: upload validation, duplicate detection,
browse filters and previews, automated tests and CI, and a pilot session with
six volunteers, five of whom (83%) added a document and found it again without
help, against a target of 80%. Sprint 4 added the Docker setup, the AWS
deployment, user accounts and sign-in screens, URL routing, accessibility
fixes, the architecture document ([`docs/architecture.md`](./docs/architecture.md))
and end-to-end tests. The pilot findings, mainly search ranking for natural
phrasing, are the first items in the next backlog. See the roadmap in
[`/docs`](./docs) for the full plan.
