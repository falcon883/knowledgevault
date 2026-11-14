# KnowledgeVault Backend

FastAPI service for KnowledgeVault: ingestion, semantic search, tags and
summaries, and the browse API used by the React frontend (see the
[root README](../README.md) for the whole project).

## Sprint 4: configuration

- **KV-37**: settings come from environment variables, so the same code runs
  on a laptop, in Docker and on AWS (`settings.py`). `DATABASE_URL` is now
  required (no default credentials in the code), the allowed browser origins
  are set with `CORS_ORIGINS`, and `GET /health` checks the database. See
  [Configuration](#configuration).
- **KV-35**: the backend has a `Dockerfile`, and `docker-compose.yml` in the
  repo root starts Postgres with pgvector and the backend with one command, so
  nobody has to install Postgres or pgvector by hand. See [Setup](#setup).

- **KV-42**: user accounts. People sign up and sign in, and every document
  belongs to one account: upload, list, view, tags, search and delete only
  touch the signed-in user's own documents. See [Accounts](#accounts).

- **KV-36**: the database schema is now changed with Alembic migrations
  instead of code that patches tables at start-up, so a model change comes
  with a versioned, testable migration. Existing databases keep all their data.
  See [Database migrations](#database-migrations).

- **KV-38**: documents are split into chunks at sentence boundaries instead of
  every 800 characters, so snippets start and end at natural points. A script
  re-chunks documents already stored. See [Chunking](#chunking).

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
- **KV-14**: document text is split into overlapping chunks (`chunking.py`; sentence-aware since KV-38).
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

### With Docker (recommended)

From the repo root:

```bash
docker compose up --build
```

This starts Postgres 16 with pgvector and the backend, creates the tables,
and serves the API at `http://localhost:8000`. What happens, in order:

1. `db` starts (the `pgvector/pgvector:pg16` image) and waits until it accepts
   connections.
2. `backend` starts, runs `python init_db.py` (applies the database
   migrations: enables pgvector, creates or upgrades the tables; safe to
   re-run), then starts uvicorn.
3. Compose marks `backend` healthy once `GET /health` answers 200.

The embedding model is downloaded when the image is built (about 90 MB), so the
container itself does not need internet access to start.

| Command | What it does |
|---|---|
| `docker compose up --build` | Build if needed and start (add `-d` to run in the background) |
| `docker compose logs -f backend` | Follow the backend log |
| `docker compose down` | Stop; documents are kept in the `pgdata` volume |
| `docker compose down -v` | Stop and delete the database |
| `docker compose up -d db` | Start only Postgres, to run the backend or the tests on your machine |

Postgres is published on `localhost:5433` (not 5432, which a locally installed
Postgres usually uses). To run the tests or `python main.py` against it, point
`DATABASE_URL` at that port:

```
DATABASE_URL=postgresql+psycopg2://knowledgevault:knowledgevault@localhost:5433/knowledgevault
```

Changed code? Run `docker compose up --build` again to rebuild the image. The
Docker setup passes the settings from [Configuration](#configuration) as
environment variables (`CORS_ORIGINS`, `MAX_UPLOAD_MB`; see the top of
`docker-compose.yml`), and the database credentials in it are for local
development only.

### Setup without Docker

Use this if you would rather run the backend directly on your machine.

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

(The first migration runs `CREATE EXTENSION IF NOT EXISTS vector` for you, no
need to do it by hand.)

### 3. Python environment

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, check that `DATABASE_URL` matches your
Postgres (the example matches the user, password and database from step 2),
and fill in `SECRET_KEY` with a random value, which signs the sign-in tokens
(`python -c "import secrets; print(secrets.token_hex(32))"` prints one). The
server will not start without both:

```bash
cp .env.example .env               # Windows: copy .env.example .env
```

Or export the variables instead of using a file:

```bash
export DATABASE_URL="postgresql+psycopg2://knowledgevault:knowledgevault@localhost:5432/knowledgevault"
export SECRET_KEY="<the random value>"
```

### 4. Create or upgrade the tables

```bash
python init_db.py
```

This applies the database migrations (see
[Database migrations](#database-migrations)). Run it again after pulling a
change that touches the database; it is safe to re-run.

### 5. Run the server

```bash
python main.py
```

Runs at `http://localhost:8000` (interactive docs at `/docs`).

On start the server loads the embedding model (a few seconds; the very first
run also downloads it, about 90 MB), so it is ready before the first request.
The log line `Embedding model loaded in X.Xs` shows when it is. `GET /health`
reports `"model_loaded": true` once it is.

## Database migrations

The schema is managed with [Alembic](https://alembic.sqlalchemy.org). Each
migration is a small file in `migrations/versions/` that changes the database
one step, and the database remembers which ones have run (in a table called
`alembic_version`). Run these from the `backend/` folder; they read
`DATABASE_URL` and `SECRET_KEY` from `.env` like the app does.

| Task | Command |
|---|---|
| Bring the database up to date | `python init_db.py` (same as `alembic upgrade head`) |
| See which migration it is at | `alembic current` |
| List all migrations | `alembic history` |
| Check the models and migrations agree | `alembic check` |
| Undo the latest migration | `alembic downgrade -1` |

Normally you do nothing: Docker runs `init_db.py` before the API starts, and
the API applies pending migrations itself when it starts. All pending
migrations run in one transaction, so if one fails the database is left as it
was.

**When you change a model** (add a column, say):

1. Edit `models.py`.
2. `alembic revision --autogenerate -m "add notes to documents"` writes a new
   file in `migrations/versions/`.
3. Read it and fix what it got wrong. Autogenerate cannot tell a rename from a
   drop plus an add, and it does not move data.
4. `python init_db.py`, then `pytest`. A test fails if the models and the
   migrations disagree, so a forgotten migration is caught before CI.
5. Commit the migration together with the model change.

**Databases that already exist** (made before Alembic, by the old `init_db.py`)
need nothing special. Migrations `0001` and `0002` check what is already there,
so the first run keeps every document, chunk and account, and records the
database as up to date. Newer migrations are ordinary and do not need those
checks. Never import app code into a migration: it has to keep meaning what it
meant on the day it was written.

`alembic downgrade` is for throwaway databases: undoing `0001` deletes every
document and chunk, and undoing `0002` forgets who owned what.

## Configuration

All settings are environment variables. For local work put them in
`backend/.env` (copy `.env.example`); a real environment variable overrides the
file. `.env` is in `.gitignore`, so your passwords stay out of the repo.

| Setting | Required | Default | What it does |
|---|---|---|---|
| `DATABASE_URL` | yes | none | Postgres connection URL, `postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DATABASE`. The database needs the pgvector extension. |
| `CORS_ORIGINS` | no | `http://localhost:5173` | Browser origins allowed to call the API, comma-separated, no trailing slash. Add the deployed frontend's URL here, e.g. `http://localhost:5173,https://app.example.com`. |
| `SECRET_KEY` | yes | none | Signs the sign-in tokens. At least 32 characters and kept secret; generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. Changing it signs everyone out. |
| `ACCESS_TOKEN_HOURS` | no | `24` | How long a sign-in lasts. |
| `LOGIN_MAX_FAILURES_PER_EMAIL` | no | `5` | Wrong passwords allowed for one email before sign-in is refused for a while. See [Sign-in limits](#sign-in-limits). |
| `LOGIN_MAX_FAILURES_PER_IP` | no | `20` | The same, per client address (higher, because people share one). |
| `LOGIN_WINDOW_MINUTES` | no | `10` | Failures are forgotten after this long, which is also the longest a lockout lasts. |
| `FRONTEND_URL` | no | first `CORS_ORIGINS` entry | Where the app is served. Password reset links point here. |
| `RESET_TOKEN_MINUTES` | no | `30` | How long a password reset link works (5 to 1440). |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` | no | none (port `587`) | An outgoing mail server for reset emails. Without `SMTP_HOST` nothing is sent and the link is written to the server log. See [Password reset](#password-reset). |
| `MAX_UPLOAD_MB` | no | `10` | Largest upload accepted. See [Upload errors](#upload-errors). |

Only for tests: `TEST_DATABASE_URL` (use a separate database),
`KV_FAKE_EMBEDDINGS=1` (skip the model download) and `BCRYPT_ROUNDS` (faster
password hashing; the tests set it for you). See
[Running the tests](#running-the-tests).

If `DATABASE_URL` or `SECRET_KEY` is missing the server stops at startup with
a message that says how to set it, rather than falling back to made-up
credentials. **After pulling KV-42, add a `SECRET_KEY` to your `backend/.env`.**

### Health check

`GET /health` runs a trivial query against the database:

```json
{
  "status": "ok",
  "service": "knowledgevault-backend",
  "timestamp": "2026-11-01T14:03:11+00:00",
  "database": "ok",
  "model_loaded": true,
  "max_upload_mb": 10.0
}
```

If the database cannot be reached the response is `503` with
`"status": "error"` and `"database": "unavailable"`, so a load balancer stops
sending traffic to that server. `model_loaded` is informational only: the model
loads at startup and retries on first use, so it does not fail the check.

## Running the tests

```bash
pip install -r requirements-dev.txt    # once: adds pytest
pytest                                 # all backend tests
pytest tests/test_search.py            # one file
pytest -k duplicate                    # tests with "duplicate" in the name
```

Run it from the `backend/` folder, with Postgres and pgvector running (for
example `docker compose up -d db` from the repo root, with `DATABASE_URL` set
to the port 5433 URL shown in [Setup](#with-docker-recommended)). The
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
| `test_chunking.py` | chunks cut at sentence boundaries, stay within 800 characters, overlap, and lose nothing, including tables and text with no punctuation (KV-38) |
| `test_rechunk.py` | re-chunking stored documents safely, and the before-and-after comparison (KV-38) |
| `test_search.py` | semantic search ranking and validation (KV-16) |
| `test_enrichment.py` | tags and summaries (KV-21) |
| `test_delete.py` | `DELETE /documents/{id}` |
| `test_upload_validation.py` | upload error cases (KV-24) |
| `test_duplicate_upload.py` | duplicate detection (KV-25) |
| `test_browse_api.py` | filters, `/tags`, document detail (KV-26) |
| `test_responsiveness.py` | searches during an upload, model loaded at startup (KV-33) |
| `test_settings.py` | required settings, CORS origins, `/health` with the database up and down (KV-37) |
| `test_auth.py` | signup, login, tokens, 401 errors, one user not seeing another's documents (KV-42) |
| `test_password_reset.py` | reset links: emailed, single use, expiry, no account enumeration; sending mail (KV-53) |
| `test_login_limits.py` | failed sign-ins per email and per address: the 429, the wait ending, normal logins untouched (KV-54) |
| `test_migrations.py` | migrations build the schema the models describe; databases from before Alembic or before accounts keep their documents and chunks; a failed upgrade changes nothing (KV-36) |

## Accounts

Each person has their own account, and each document belongs to one account.
This is what the frontend needs to know (code in `auth.py`).

**Sign up or sign in**, both with a JSON body `{"email": "...", "password": "..."}`:

```
POST /auth/signup   ->  201
POST /auth/login    ->  200
```
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": { "id": 7, "email": "you@example.com" }
}
```

**Send the token with every other request:**

```
Authorization: Bearer eyJhbGciOi...
```

`GET /auth/me` returns the user for a token, which is a cheap way to check that
a token saved in the browser still works. A token lasts `ACCESS_TOKEN_HOURS`
(24 by default); after that the user signs in again.

Emails are stored in lowercase, so `You@Example.com` and `you@example.com` are
one account. Passwords need 8 to 72 characters and are stored only as bcrypt
hashes.

**Errors** use the same shape as upload errors, `{"detail": <message>, "code": <code>}`.
The frontend can branch on `code`:

| Status | `code` | When |
|---|---|---|
| 401 | `not_authenticated` | No token was sent |
| 401 | `invalid_token` | The token is damaged, signed with another key, or its user no longer exists |
| 401 | `token_expired` | The token is old. Sign in again |
| 401 | `invalid_credentials` | Wrong email or password (the same answer for both, so it does not reveal which emails have accounts) |
| 409 | `email_taken` | Signup with an email that already has an account |
| 429 | `too_many_attempts` | Too many wrong passwords for this email or from this address. Wait; see [Sign-in limits](#sign-in-limits) |
| 422 | `invalid_email`, `weak_password`, `password_too_long` | Signup (or password reset) input that is not acceptable |
| 400 | `invalid_reset_token`, `reset_token_expired`, `reset_token_used` | A password reset link that cannot be used (see [Password reset](#password-reset)) |

All 401 responses also carry `WWW-Authenticate: Bearer`, and the 429 carries
`Retry-After` (seconds).

**One user cannot see another's documents.** Every document query is filtered
by the signed-in user. Asking for someone else's document returns the same 404
as one that does not exist, so ids reveal nothing, and search only looks at
your own documents. "Already uploaded" (see [Duplicate uploads](#duplicate-uploads))
means already uploaded by you.

**Upgrading an existing database.** Migration `0002` (applied by
`python init_db.py` and by the server at start-up) creates the `users` table, adds `documents.user_id`, and gives every
document that had no owner to a placeholder user, `default@knowledgevault.local`,
that nobody can sign in as. To keep those documents, sign up and then move
them to your account:

```bash
python claim_documents.py you@example.com
```

**Not included yet:** email confirmation, and deleting an account.

### Sign-in limits

`POST /auth/login` counts wrong passwords (KV-54). After 5 for one email, or 20
from one client address, within 10 minutes, further attempts get
`429 too_many_attempts` with a message like "Too many failed sign-in attempts.
Try again in 8 minutes." and a `Retry-After` header. The frontend should show
`detail`.

- The wait ends by itself: it lasts until the oldest counted failure is 10
  minutes old, so at most 10 minutes.
- Only failures count. A correct password is never slowed down, and a
  successful sign-in forgets that email's failures.
- During a lockout the password is not checked, so even the right one is
  refused, and refused attempts do not extend the wait.
- Emails without an account are limited the same way, so the limit does not
  reveal which emails exist. Requests the server rejects as malformed (422) are
  not counted.
- One locked email does not affect other emails. Password reset and signup are
  not blocked by a lockout.
- The client address comes from `X-Forwarded-For`: Caddy sets it to the address
  it saw, and the last entry is used. Without a proxy (local development) the
  connection's own address is used.

The numbers are `LOGIN_MAX_FAILURES_PER_EMAIL`, `LOGIN_MAX_FAILURES_PER_IP` and
`LOGIN_WINDOW_MINUTES` (see [Configuration](#configuration)). Counts are kept in
memory by the one server process (code in `ratelimit.py`), so a restart clears
them.

**Known limit:** someone who knows an email can lock that email out for up to 10
minutes by failing on purpose. The owner can still use password reset, which is
not blocked.

### Password reset

Two calls, both with a JSON body, neither needing a token (KV-53):

```
POST /auth/forgot-password   {"email": "you@example.com"}
POST /auth/reset-password    {"token": "...", "password": "a new password"}
```

1. **Ask for a link.** `forgot-password` always answers `202` with
   `{"message": "If an account exists for that email, we have sent a link ..."}`,
   whether or not the address has an account, so it cannot be used to find out
   who has one. The frontend shows that message. A badly formed address gets
   `422 invalid_email`.
2. **The email** has a link to the app with the token in the address:
   `<FRONTEND_URL>/?reset_token=<token>`. The app's home page reads
   `reset_token` from the address when it loads and shows a "choose a new
   password" form.
3. **Set the password.** `reset-password` sends the token and the new password
   (8 to 72 characters). On success it answers `200` with the same body as
   login (`access_token`, `user`), so the user is signed in straight away.

| Status | `code` | When |
|---|---|---|
| 400 | `invalid_reset_token` | The token was never issued, or was changed |
| 400 | `reset_token_expired` | The link is older than `RESET_TOKEN_MINUTES` (30 by default) |
| 400 | `reset_token_used` | The link was already used, or a newer link replaced it |
| 422 | `weak_password`, `password_too_long` | The new password is not acceptable. The link is not used up, so the user can try again |

How it is kept safe: the token is 256 random bits and only its SHA-256 is
stored, so a copy of the database cannot reset anyone's password. A link works
once. Asking for a new link cancels the older one, and using a link cancels any
others for the account. Asking again within a minute sends nothing new, so the
form cannot fill someone's inbox. The email is sent after the answer, so it
takes the same time whether or not the account exists.

**Sending the email.** Set `SMTP_HOST`, `SMTP_PORT` (default 587, which uses
STARTTLS; 465 uses SSL), `SMTP_USER`, `SMTP_PASSWORD` and `MAIL_FROM`, for
example for Gmail with an [app password](https://myaccount.google.com/apppasswords):

```
SMTP_HOST=smtp.gmail.com
SMTP_USER=you@gmail.com
SMTP_PASSWORD=<16-character app password>
FRONTEND_URL=https://<your frontend address>
```

With no `SMTP_HOST` nothing is sent. The whole message, including the link, is
written to the server log instead, which is enough to try it locally. On the
server:

```bash
docker compose -f docker-compose.prod.yml logs backend | grep -A8 "Email is not set up"
```

A mail server that is down is logged and does not change the answer to the user.

**Known limit:** changing a password does not sign out sessions that are
already open; they end when their token expires (`ACCESS_TOKEN_HOURS`).

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
| `text_too_long` | 422 | more text than one document may hold (500,000 characters, about 160 pages) |
| `duplicate_document` | 409 | same content as a document already stored (adds `existing`) |
| `processing_failed` | 500 | text was fine, but saving or embedding failed; nothing is kept |

A file sent with a generic type (`application/octet-stream` or none) is
judged by its extension. `GET /health` reports the active limit as
`max_upload_mb`.

A file under the size limit can still hold far more text than a small server
can embed in a reasonable time (a 10 MB text file is millions of characters),
so a document is also refused when its text passes `MAX_TEXT_CHARS` in
`uploads.py` (500,000 characters, about 160 pages). A PDF is checked page by
page and reading stops as soon as it is over, so a huge one fails quickly.

### Search and server errors (KV-52)

Every error from the API has the same two fields, `detail` (a message the
screen can show as it is) and `code` (stable, for the screen to branch on).
Upload errors are above; these are the rest:

| code | status | when |
|---|---|---|
| `empty_query` | 400 | `/search` with a blank query |
| `query_too_long` | 400 | `/search` query over 500 characters |
| `search_unavailable` | 503 | the embedding model failed while searching |
| `service_unavailable` | 503 | the database cannot be reached; the response has `Retry-After: 5` |
| `not_found` | 404 | no such document (someone else's document gives the same answer), or no such address |
| `method_not_allowed` | 405 | wrong HTTP method for an address |
| `bad_request`, `unauthorized`, `forbidden`, `too_many_requests` | 400, 401, 403, 429 | used when a plain HTTP error carries no more specific code |
| auth codes | 400, 401, 409 | sign-in problems, see [Accounts](#accounts) |

Not changed: a request that does not match the expected shape (a missing
field, `limit` of 0) still returns FastAPI's own 422 with a `detail` list, and
a crash nobody anticipated still returns a plain 500. The screens only send
valid requests, so the first does not come up in normal use.

Searches of any other kind (one letter, a number such as `26.2`, only
punctuation, an emoji, SQL or HTML typed into the box) are ordinary text: they
are embedded and answered with a normal results list, possibly empty.

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

Databases from before this existed are upgraded by migration `0001`, which
adds the `content_hash` column and fills it in for documents uploaded earlier,
so they count as duplicates too.

## Chunking

Each document is cut into chunks of at most 800 characters, and every chunk is
embedded and searched on its own (`chunking.py`). Chunks are cut at natural
breaks, so a search snippet reads cleanly and a match is not lost across a cut:

- Text is split into paragraphs and sentences. A period after `Dr.`, `e.g.`, an
  initial or a decimal point does not end a sentence.
- Sentences are packed into a chunk until the next one would not fit. If a
  paragraph break falls in the second half of a chunk, the chunk ends there.
- The next chunk starts with the last sentence or two of the previous one (up
  to 150 characters), so an idea that straddles a cut is whole in at least one
  chunk.
- Text with no sentence breaks, such as a table or a schedule, is cut between
  lines, then between words. Only a single "word" longer than 800 characters
  (a long base64 string, say) is cut by length.

**Documents stored before KV-38** still have the old fixed-size chunks until you
re-chunk them. This rebuilds the chunks and embeddings from the text already
saved (no files needed), one document at a time, so a failure leaves that
document as it was. It is safe to run again, and it covers every user's
documents:

```bash
python rechunk_documents.py --dry-run     # show what would change, change nothing
python rechunk_documents.py               # do it
python rechunk_documents.py --document 12 15   # only these documents
```

On the server: `docker compose -f docker-compose.prod.yml exec backend python rechunk_documents.py`.
Tags and summaries are left as they are.

**Seeing the difference.** With the real model (not `KV_FAKE_EMBEDDINGS`), this
chunks every stored document both ways in memory, searches each way, and prints
the best snippet per document side by side, plus how many chunks start and end
like a sentence. It changes nothing in the database:

```bash
python compare_chunking.py "how do I feed a sourdough starter" "what did we decide about the budget"
```

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
      "snippet": "The telescope observed a distant galaxy and measured how fast it is moving away from Earth.",
      "matched_terms": ["universe"],
      "chunk_index": 0,
      "tags": null,
      "summary": null
    }
  ]
}
```

- One result per document: its best-matching chunk, closest first.
- `snippet` is the part of that chunk that matches the query (KV-48): the
  sentence sharing the most words with the query, plus the sentences after it
  while they fit in 300 characters. If no word matches (the chunk matched by
  meaning alone), it is the start of the chunk. `matched_terms` lists the query
  words found in the snippet, lowercase, so a screen can highlight them; it is
  empty in that case. The picking is in `passage.py` and uses words only.
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
| `GET /health` | Status check: database reachable (503 if not), model loaded, upload limit. Public |
| `POST /auth/signup` | Create an account; returns a token. Public |
| `POST /auth/login` | Sign in; returns a token. Public |
| `GET /auth/me` | The signed-in user |
| `POST /upload` | Upload a PDF or text file; persists it, chunks it, embeds each chunk, adds tags and a summary |
| `POST /search` | Semantic search over your documents: returns the best-matching ones for a query |
| `GET /documents` | List your documents (backs the browse screen). Optional filters below |
| `GET /documents/{id}` | One of your documents with its full extracted text, for previews |
| `GET /tags` | Every tag in your documents with its document count, for the tag filter |
| `DELETE /documents/{id}` | Delete one of your documents and its chunks |

Everything except `/health`, `/auth/signup`, `/auth/login` and the `/docs` page
needs a token (see [Accounts](#accounts)).

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

From the pilot session (KV-28) and the Sprint 4 work:

- **Search quality (KV-47, KV-48):** one volunteer could not find a document
  with their own wording, and the right result was first for only 2 of 6.
  Candidates: hybrid keyword and meaning matching, re-ranking by the best
  passage, and returning the matching passage with each result.
- **Password reset:** not built. It needs email sending (for example AWS SES) and
  reset-token endpoints.
- **Login attempts are not rate limited.** Worth adding before real users.
- Possible later improvement: swap the extractive summary for an LLM-written one if the team decides the API dependency is worth it.
