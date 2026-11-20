# Testing and pilot summary

What was tested on KnowledgeVault, how, and what came out. Written for KV-55 on
November 14, 2026. The numbers below are the results of real runs; each row
says where the evidence is kept.

## At a glance

| What | Result | Evidence |
|---|---|---|
| Backend automated tests | 317 tests, all passing | [`backend/tests/`](../backend/tests), run in CI on every pull request |
| Frontend automated tests | 31 tests, all passing, plus lint and a production build | [`frontend/src/`](../frontend/src), run in CI |
| End-to-end browser tests | 28 tests, all passing | [`e2e/`](../e2e), run in CI |
| Live backend functionality pass | 104 checks, 0 failed, 2 skipped (reason recorded) | [`docs/qa/functionality-pass.md`](qa/functionality-pass.md) |
| Search quality (charter criterion: 80% of queries with a relevant source in the top 5) | 29 of 29 queries (100%), the right document first every time | [`docs/qa/search-quality.md`](qa/search-quality.md) |
| Pilot with volunteers (charter criterion: 80% finish both tasks without help) | 5 of 6 (83%) | [`pilot/results/`](../pilot/results) |

That is 376 automated tests in all (317 + 31 + 28).

## Automated tests

All three suites run in GitHub Actions on every push and pull request
(`.github/workflows/`): `ci.yml` runs the backend tests against a throwaway
Postgres with pgvector, then builds the Docker stack and smoke-tests it;
`frontend-ci.yml` runs lint, the frontend tests and a production build;
`e2e.yml` runs the browser tests.

**Backend (317 tests).** Each file covers one feature:

| Area | What is checked |
|---|---|
| Ingestion | chunking at sentence boundaries, embeddings stored in pgvector, re-chunking existing documents, tags and summaries |
| Upload | every rejection (wrong type, too large, empty, damaged or password-protected PDF, no text, too much text) with its error code, duplicates, the API staying responsive during an upload |
| Search | ranking on small known sets, the matching passage and matched words, blank and over-long queries, odd input (punctuation, emoji, SQL and HTML typed into the box) treated as plain text |
| Browse | tag, date and sort filters, document detail, tag counts, delete with everything derived from it |
| Accounts | sign up, sign in, tokens (expired, forged, for a deleted user), one user never seeing another's documents |
| Password reset | single-use links, expiry, newer link cancelling older, no way to tell which emails exist, mail sending |
| Change password | wrong current password is a 400 (never a 401), weak or unchanged passwords, wrong guesses limited like sign-in, unused reset links cancelled |
| Sign-in limits | the 429 after repeated failures, the wait ending, normal sign-ins unaffected |
| Configuration and database | required settings, CORS, `/health` with the database up and down, migrations producing the schema the models describe, old databases keeping their data |

**Frontend (31 tests, Vitest and React Testing Library).** The session and token
handling, the API client and its error handling, the excerpt helper, the
sign-in screen and the app shell's routing.

**End-to-end (28 tests, Playwright).** A real browser against the real screens
and API on a throwaway database: sign up and sign in, a refresh keeping the
session, wrong passwords, adding a typed note and a PDF, duplicates and
rejected files, browse filters and sorting, delete, search ranking, and one
user not seeing another's documents.

## Live checks

These run against the deployed server (`https://3-13-43-176.sslip.io`) with the
real embedding model and the real database, which the automated tests cannot
do.

- **Functionality pass** ([`deploy/functionality_pass.py`](../deploy/functionality_pass.py),
  KV-50): goes through every backend feature as a brand new user, then restarts
  the containers and checks the account, the documents and search all survived.
  104 checks passed, none failed. The two skipped checks and the reason for
  each are in the results file. Features that cannot be run safely from a script
  (the 429 lockout, the reset email) were checked by hand on the same day and
  recorded on KV-53 and KV-54.
- **Smoke test** ([`deploy/smoke_test.py`](../deploy/smoke_test.py)): health,
  sign up, upload, search, per-user isolation and delete; also run in CI against
  the Docker stack.
- **Search-quality test** ([`eval/`](../eval), KV-61): see below.

## Search quality

The charter asks for a curated set of at least 20 documents and 15 queries, with
a relevant source in the top 5 for at least 80% of them.

- **Set:** 24 documents (18 one-page PDFs plus 6 text notes) and 29 queries
  written before the first run and not changed afterwards: 24 paraphrases that
  avoid the document's own words ("why do I feel worn out and sore the day after
  getting an injection" for the vaccines document), 1 broad question where two
  documents count, and 4 short keyword searches. Three more queries have no
  answer in the library.
- **Result:** a relevant source was in the top 5 for 29 of 29 queries and first
  for all 29. The 3 no-answer queries returned nothing.
- **Limit:** every document is on a different topic, so each query has few
  rivals. The result shows that meaning-based search works on a varied library; it
  does not say how it behaves on thousands of similar documents.

## Pilot (KV-28)

Six volunteers each added one document and then tried to find it again by
describing what it was about, on the live site, with no help and four minutes per
task. Percival facilitated and Durvank observed.

| Measure | Result |
|---|---|
| Both tasks completed | 5 of 6 (83.3%), target 80% |
| Adding a document | 6 of 6 |
| Finding it again | 5 of 6 |
| Ease of adding / finding (1 to 5) | 4.5 / 3.8 |
| Would use it | 4 yes, 2 maybe, 0 no |
| Target document ranked first | 2 of 6 |

It was a narrow pass: one more failure would have meant 66.7%. The main weakness
was ranking for natural phrasing (one volunteer never found the document, one had
to reword the query), and some volunteers were unsure an upload had finished.
Those findings became KV-47 and KV-48 (search) and KV-49 (upload progress).
KV-48 also made each result show the passage that matched. The volunteers' own
queries are now a standing check
([`pilot/seed_library.py --check`](../pilot/README.md)) that requires each
target in the top 2. Details, the observation log and the feedback forms are in
[`pilot/results/`](../pilot/results).

## Security and accessibility

- **Isolation:** every document query is scoped to the signed-in user, and
  someone else's document id gets the same 404 as one that does not exist. Checked
  in the backend tests, the end-to-end tests and the live pass.
- **Accounts:** passwords are bcrypt-hashed, tokens expire after 24 hours,
  password reset links are single-use and stored only as hashes, and repeated
  wrong passwords are rate limited.
- **Accessibility (KV-44):** labelled controls, visible focus outlines, grouped
  filters and reduced-motion support, built in by Percival and covered by the
  component tests.

## Known limitations

- A password change does not sign out sessions that are already open; they last
  until their token expires (up to 24 hours).
- Reset emails go through Amazon SES in sandbox mode, so they only reach
  verified addresses, and they can land in spam.
- The sign-in counters are kept in memory and reset when the server restarts.
- The frontend functionality pass on the live site (KV-51) is still to be added
  here.
