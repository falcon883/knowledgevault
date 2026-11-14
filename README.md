# KnowledgeVault

[![CI](https://github.com/falcon883/knowledgevault/actions/workflows/ci.yml/badge.svg)](https://github.com/falcon883/knowledgevault/actions/workflows/ci.yml)

A personal knowledge base that finds your own notes, PDFs, and articles by
meaning rather than by exact keyword. Built as the MSCS 3999 capstone project
at Clark University, Fall 2026.

**Team:** Durvank Deorukhkar (backend, deployment), Percival Tapera (frontend)
**Jira:** [KnowledgeVault board](https://clarkcapstone.atlassian.net/jira/software/projects/KV/boards/2)
**Live app:** https://d33bsamq53gtgw.cloudfront.net, with the API and its
interactive docs at https://3-13-43-176.sslip.io/docs

## What it does

- **Capture:** upload a PDF, or type or paste a note or article. The text is
  extracted, split into chunks and embedded locally, and the document gets
  automatic tags and a short summary. Bad files are rejected with a clear
  message, and a file that was already uploaded is flagged as a duplicate.
- **Browse:** list your documents, filter them by type or tag, sort them, read a
  preview of the text, and delete the ones you no longer want.
- **Search:** ask in plain language ("how old is the universe") and get the
  best-matching documents back, one per document, ranked by meaning, each with the
  passage that matched.
- **Accounts:** sign up and sign in. Each person sees only their own documents.
  Repeated wrong passwords are rate limited, and a forgotten password can be reset
  through a link sent by email (the API is done; the app screens are in progress).

Everything runs on your own machine or on one small server: FastAPI, Postgres
with pgvector, and a local sentence-transformers model, so there are no AI API
keys or per-call costs.

## Documentation

| Read this | For |
|---|---|
| [User guide](./docs/user-guide.md) | How to use the app: sign up, add, browse, search |
| [Architecture](./docs/architecture.md) | The three tiers, components, data flows and deployment, with a diagram |
| [Testing and pilot summary](./docs/testing-and-pilot.md) | What was tested and the results: automated tests, live checks, search quality, the pilot |
| [Backend README](./backend/README.md) | The API in detail: endpoints, error codes, configuration, database migrations |
| [Deployment guide](./deploy/README.md) | Setting up the AWS server and updating it |
| [Project documents](./docs/README.md) | Charter, roadmap and release plan, sprint feedback, QA results |

## Run it on your own machine

You need [Docker](https://docs.docker.com/get-docker/) (Docker Desktop on
Windows and macOS) and Node 20 or newer for the frontend.

**1. Backend and database** (one command, from the repository root)

```bash
docker compose up --build
```

The first run builds the backend image and downloads the embedding model (a few
minutes); after that it starts in seconds. The API is at `http://localhost:8000`
(interactive docs at `/docs`) and the tables are created for you. Documents are
kept in a Docker volume, so `docker compose down` stops everything without losing
them; `docker compose down -v` wipes the database too. Postgres is reachable from
your machine on port 5433, so it does not clash with one you already run on 5432.
Settings you can override are listed at the top of `docker-compose.yml`.

Prefer to run the backend without Docker? Install Python 3.11+ and Postgres 16
with pgvector, then follow the
[backend README](./backend/README.md#setup-without-docker).

**2. Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The app talks to the backend at
`http://localhost:8000`; set `VITE_API_URL` to point it somewhere else.

**3. Use it**

Choose **Sign up**, create an account, and add a document on the Capture tab. The
[user guide](./docs/user-guide.md) walks through every screen. To fill the app
with sample documents, run `python pilot/seed_library.py --password <choose one>`
(it creates a `pilot@example.com` account and loads ten PDFs).

Password reset emails need an outgoing mail server. Without one, the reset link
is written to the backend's log instead (`docker compose logs backend`), which is
enough for local work.

## Run the tests

Backend (needs Python 3.11+ and the database from `docker compose up -d db`):

```bash
cd backend
pip install -r requirements-dev.txt
DATABASE_URL=postgresql+psycopg2://knowledgevault:knowledgevault@localhost:5433/knowledgevault pytest
```

Frontend: `cd frontend && npm test`. End-to-end, with a real browser against the
real screens and API (same database as above, set in `DATABASE_URL` or
`backend/.env`):

```bash
cd e2e
npm install && npm run setup   # once
npm test
```

More on each suite is in the [backend README](./backend/README.md#running-the-tests)
and the [e2e README](./e2e/README.md). The three suites run in GitHub Actions on
every push and pull request, and the results of every kind of test are collected in
the [testing summary](./docs/testing-and-pilot.md).

## Deploy

The backend and database run on one small AWS server (EC2) with HTTPS from Caddy,
using `docker-compose.prod.yml`; the built frontend is served from S3 and
CloudFront. Settings and secrets live in a `.env` file on the server, never in the
repository (`.env.example` lists them). The step-by-step guide, from creating the
AWS account to checking the deployed API, is in
[`deploy/README.md`](./deploy/README.md). Once the server exists, updating it is
one command, run on the server:

```bash
bash deploy/deploy.sh
```

It pulls the latest code, rebuilds, waits until the backend is healthy and checks
the public address. To check any running API from your own machine:

```bash
python deploy/smoke_test.py https://your-api-address     # or http://localhost:8000
python eval/search_quality.py https://your-api-address   # the search-quality test
```

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Status check: database reachable (503 if not), model loaded, upload limit |
| `POST /auth/signup`, `POST /auth/login` | Create an account or sign in; returns a token |
| `POST /auth/forgot-password`, `POST /auth/reset-password` | Ask for a reset link by email; set a new password with the token from it |
| `GET /auth/me` | The signed-in user |
| `POST /upload` | Upload a PDF or text file |
| `GET /documents` | List your documents; optional `tag`, `since` and `sort` filters |
| `GET /documents/{id}` | One of your documents with its full text, for previews |
| `GET /tags` | Every tag in your documents with its document count |
| `POST /search` | Search your documents by meaning |
| `DELETE /documents/{id}` | Delete one of your documents |

Everything except `/health` and the sign-in, sign-up and reset routes needs
`Authorization: Bearer <token>`, and each person sees only their own documents.
Every error has the same shape, `{"detail": "<message>", "code": "<code>"}`. Request
and response details, and the list of error codes, are in the
[backend README](./backend/README.md#endpoints).

## Repository structure

| Path | Contents |
|---|---|
| [`/backend`](./backend) | FastAPI service, database models and migrations, embedding and search code, and the pytest suite |
| [`/frontend`](./frontend) | React app built with Vite: sign-in, Capture, Browse and Search screens |
| [`/e2e`](./e2e) | End-to-end browser tests (Playwright) |
| [`/deploy`](./deploy) | AWS deployment guide, HTTPS config, `deploy.sh`, and the scripts that check a live server |
| [`/eval`](./eval) | The search-quality test: documents, queries and expected sources |
| [`/pilot`](./pilot) | Sample documents, seed script and results of the pilot with volunteers |
| [`/docs`](./docs) | Project documents, architecture, user guide, testing summary and QA results |
| [`/.github/workflows`](./.github/workflows) | CI: backend, frontend and end-to-end tests, plus a Docker build and smoke test |
| [`docker-compose.yml`](./docker-compose.yml), [`docker-compose.prod.yml`](./docker-compose.prod.yml) | Local development stack and the production server stack |

## Status

Release 3 (final) is in progress; the final presentation and submission are on
December 10, 2026. Release 2 (Pilot Beta) is done: six volunteers took part in the
pilot and five (83%) added a document and found it again without help, against a
target of 80%. Since then the app has been deployed to AWS, gained accounts, sign-in
screens, password reset (API), sign-in rate limiting and a single error format, and
search now shows the passage that matched. A live check of the whole backend passed
104 checks with none failed, and a 29-query search-quality test found a relevant
document in the top 5 every time (charter target: 80%). Results and how they were
produced are in the [testing summary](./docs/testing-and-pilot.md).

**Still to do:** the password reset screens, upload progress, and clearer error
messages in the app (KV-59, KV-49, KV-58), highlighting the matched words in
results (KV-57), and the frontend check of the live site (KV-51).

**Known limitations:** a password change does not sign out sessions that are
already open (they last up to 24 hours); reset emails go through Amazon SES in
sandbox mode, so they only reach verified addresses and may land in spam; and the
sign-in counters reset when the server restarts.
