# End-to-end tests (KV-32)

These tests open KnowledgeVault in a real browser (Chromium, driven by
[Playwright](https://playwright.dev)) and use it the way a person does: sign
up, add a note or a PDF, find it by asking a question, read it, delete it. They
check the whole chain at once: the React screens, the API, the database and
search. If a screen and the API ever disagree, this is where it shows.

## What is covered

| File | What it checks |
|---|---|
| `tests/journey.spec.js` | The pilot path in one go: add two notes, browse, search by a plain question, open the result, delete, reload |
| `tests/auth.spec.js` | Sign up, stay signed in after a refresh, sign out, sign in, wrong password, email already taken, short password, links to a tab |
| `tests/upload.spec.js` | Note and PDF uploads, title taken from the first line, duplicate content, a PDF with no text, a file that is not a PDF, an empty file |
| `tests/browse.spec.js` | Empty vault, details and excerpt, type filter, sort, cancel and confirm delete, deleted documents leave search |
| `tests/search.spec.js` | Idle screen and empty vault, the right document ranked first for a question, previews open and close, the query survives a tab change, category cards open Browse filtered |
| `tests/privacy.spec.js` | A second account cannot see or search the first account's documents |

## Running them

One-time setup, from the repository root:

```bash
cd backend && python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt                                     # skip if you already did
cd ../e2e
npm install
npm run setup          # installs the frontend's packages and the Chromium browser
```

Then, any time (Postgres with pgvector must be running, as for the backend):

```bash
cd e2e
npm test
```

That one command builds the frontend, starts the API and the site, runs all the
tests and shuts everything down. It takes under a minute.

Handy variations:

```bash
npm run test:headed                 # watch the browser do it
npm run test:ui                     # Playwright's interactive runner
npx playwright test upload          # only the files whose name contains "upload"
npm run report                      # open the HTML report of the last run
```

Use the same terminal where the backend virtual environment is active. If your
Python is not called `python`, set `E2E_PYTHON` (for example `E2E_PYTHON=python3 npm test`).

The tests find your database the way the backend does: `DATABASE_URL` from the
environment or from `backend/.env`. (With `docker compose up -d db` that is the
Postgres on port 5433.)

## What it does not touch

- **Your data.** The API for these tests works in its own `kv_e2e` schema inside
  your usual database and wipes that schema at every start. Your documents and
  accounts live in the default schema and are not read or changed.
- **Your dev servers.** The tests use ports 8100 (API) and 4173 (site), not 8000
  and 5173. Override with `E2E_API_PORT` and `E2E_WEB_PORT` if those are taken.
- **The embedding model.** `start_backend.py` swaps in a quick stand-in that
  matches shared words, so there is no 90 MB model to download and uploads take
  milliseconds. It also means the search questions in the tests reuse some of
  each note's own words (the backend ignores anything scoring under 0.25).
  To try the real model, run with `E2E_REAL_EMBEDDINGS=1` (needs
  `sentence-transformers` installed; CI does not do this).

To use a different database, set `E2E_DATABASE_URL`.

## Writing a new test

Every test gets a brand-new account, so tests never share data and can run side
by side. In `tests/helpers.js`:

- `test` is Playwright's `test` plus an `app` fixture: a page already signed in
  and showing the Capture tab.
- `saveNote`, `savePdf`, `openTab`, `search`, `browseRow` and friends do the
  common things on screen.
- `SOURDOUGH`, `TOMATOES` and the two PDFs in `fixtures/` are ready-made content
  with a question that finds each one.

```js
import { test, expect, saveNote, expectSaved, openTab, SOURDOUGH } from './helpers.js';

test('my new check', async ({ app: page }) => {
  await saveNote(page, SOURDOUGH);
  await expectSaved(page, SOURDOUGH.filename);
  await openTab(page, 'Browse');
  // ...
});
```

The PDFs in `fixtures/` can be rebuilt with `python fixtures/make_fixtures.py`.

## In CI

`.github/workflows/e2e.yml` runs the same `npm test` on every pull request and
every push to `main`, with a throwaway pgvector Postgres. If it fails, the
HTML report and traces (screenshots, a step-by-step recording of the page) are
attached to the run under "Artifacts".

## When a test fails

1. Run it again on its own: `npx playwright test <part of the file name> --headed`.
2. Open the trace: `npx playwright show-trace test-results/<test folder>/trace.zip`.
   It shows every step with a screenshot of the page before and after.
3. Decide whether the app or the test is wrong. The first run of this suite found
   a real bug (the Browse tab showed a stale list after an upload until the page
   was reloaded), so do not assume it is the test.
