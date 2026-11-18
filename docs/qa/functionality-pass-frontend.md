# Frontend functionality pass (KV-51)

Site: https://d33bsamq53gtgw.cloudfront.net  
Run: 2026-11-17 22:52–23:01 EST, desktop width, as a brand-new user  
Account: kv51-qa-7f3a9c@example.test (throwaway; 2 documents uploaded)  
Checks: 25. Passed 23, failed 1, warnings 0, skipped 1.  
Phone width: not yet run — see below.

Every check was made on the deployed site, over HTTPS, as a brand-new account. PASS means the app did what the ticket asks. FAIL means it did not, and the failure has a Jira bug (see Open findings). SKIPPED means it could not be checked from here, with the reason given.

## Auth: sign up, log in, log out

| Check | Result | Detail |
|---|---|---|
| sign up with a new account | PASS | Signed straight in to Capture ("backend connected", "Sign out" shown). No email-verification step. |
| a bad email address is refused | PASS | "not-an-email" refused with "Enter a valid email address." Field outlined red, no account created. |
| a too-short password is refused | PASS | "abc" refused with "Use a password of at least 8 characters." |
| log out | PASS | "Sign out" returned to the "Welcome back" sign-in form with Sign up / Sign in tabs. |
| log back in with the new account | PASS | Returned to the app; Browse still listed both uploaded documents. |
| session expiry | SKIPPED | Could not read the stored token: developer tools are unavailable in the browser used. Tokens last 24 hours by default (ACCESS_TOKEN_HOURS). The backend returns 401 token_expired ("Your session has expired. Sign in again."); the frontend behaviour on expiry was not observed live. |

## Capture: upload, validation, feedback

| Check | Result | Detail |
|---|---|---|
| upload a PDF (T2_how_vaccines_work.pdf) | PASS | "Saved. "T2_how_vaccines_work.pdf" is indexed (2 chunks)." plus summary and tags. Document appeared in Browse ("1 saved item"). |
| upload feedback during upload | PASS | Button changed to disabled "Uploading…" with a spinner; status line "Uploading → processing your document…". Note: no percentage progress bar, only spinner and status text. That gap is KV-49 (upload progress), not filed here. |
| a non-PDF file is refused | PASS | Selecting not-a-pdf.txt showed "That file is not a PDF. Choose a PDF file, or switch to Note or Article to save text instead." Drop zone red dashed border, "Save to vault" disabled, file not uploaded. |
| upload a second PDF (T5_why_sourdough_rises.pdf) | PASS | "Saved. "T5_why_sourdough_rises.pdf" is indexed (2 chunks)." Browse showed "2 saved items". Vault overview: 2 PDFs, 0 text files, 4 chunks indexed. |

## Browse: list, filters, opening a document

| Check | Result | Detail |
|---|---|---|
| list shows both documents with titles and dates | PASS | "2 saved items". T5 (17 Nov 2026, 22:54), T2 (17 Nov 2026, 22:53). |
| tag filter (vaccines) | PASS | Only T2 shown while the tag is pressed; clicking again restores both. Note: the header still reads "2 saved items" while filtered — that is the total count, not the filtered count. |
| recency filter | PASS | There is no date-range recency filter; recency is the Sort dropdown ("Newest first" / "Oldest first" / "Name (A–Z)"). "Oldest first" reordered to T2 then T5. Restored to "Newest first". |
| opening a document | PASS | Clicking the T2 card expands an inline detail panel (title, TYPE PDF, UPLOADED 17 Nov 2026, 22:53, SIZE 2.2 KB, CHUNKS 2, tags, summary, Source excerpt). The URL stays at #/browse — it is not a separate page. |

## Search: results, previews, empty state

| Check | Result | Detail |
|---|---|---|
| search ranks the right document first | PASS | "how does getting a shot protect me from disease" returned 1 result, T2 first with "Relevance 100 out of 100, relative to the top result". T5 did not appear. |
| matched terms highlighted in previews | PASS | Positive control: "how do vaccines work" highlights "vaccines" and "vaccine" bold on yellow in the snippet. The earlier query ("how does getting a shot protect me from disease") showed no highlight because no non-stopword of the query occurs in the snippet, so the backend correctly returns no matched terms and the highlighter leaves the text unchanged (KV-48/KV-57 design). |
| empty state for a gibberish query | PASS | "No matches for “qzxv wkpj vvbn mmzq xxqz”." plus the "Try searching for:" suggestion chips. |

## Keyboard use and screen reader basics

| Check | Result | Detail |
|---|---|---|
| Tab reaches the search box, with visible focus | PASS | One Tab from the Search nav button; clear blue focus ring and text cursor. The query was typed entirely by keyboard. |
| Tab reaches Search and Enter submits | PASS | Focus ring on "Search →"; Enter returned 1 result. |
| Tab reaches a result and Enter opens it | PASS | Result card showed a blue outline; Enter expanded it and the state changed to expanded. |
| Tab through the Browse list | PASS | Order ran through Filter and Sort, all 11 tag buttons, the T5 card, its Delete button, and the T2 card — all with visible focus. Enter on T5 expanded it and T2 collapsed. |
| nothing unreachable, no focus trap | PASS | Every tested control is reachable by Tab with a visible focus indicator. Tabbing past the last element moved focus to the browser chrome and back to "Sign out" — normal wrap-around. |
| landmarks, labels, names, expanded state | PASS | Main landmark, "Primary" navigation landmark, "Your documents" region. Search input labelled "Describe what you want to find". Buttons carry accessible names ("Sign out", "Delete T2_how_vaccines_work.pdf", "vaccines 1"). Items expose expanded state in the accessibility tree. Semantics only, not a full screen-reader test. |

## Page refresh and direct links (hash routes)

| Check | Result | Detail |
|---|---|---|
| refresh keeps the session and the list | PASS | After a full reload the session persisted and both documents were still listed. The sort reset to its default "Newest first". |
| direct link to a document | FAIL | No per-document direct link exists. The detail panel has no Copy link control, and opening a document does not change the URL (stays at #/browse). Three candidate hash routes tried in a fresh tab all failed: #/browse/T2_how_vaccines_work.pdf redirected to #/capture; #/document/T2_how_vaccines_work.pdf and #/documents/T2_how_vaccines_work.pdf both rendered the Capture page. The plain #/browse link does work. See Open findings. |

## Open findings

### No direct link to a document — Jira bug to file

Opening a document in Browse expands an inline panel and the URL stays at #/browse. There is no way to share or bookmark a link to a specific document, and guessed hash routes do not land on it. Expected: opening a document updates the URL to a per-document hash route that loads that document when opened directly.

### Not checked yet

- Phone width: the ticket requires the same pass on phone width. Not run yet.
- Session expiry behaviour on the frontend: skipped (see above).
