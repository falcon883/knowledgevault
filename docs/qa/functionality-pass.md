# Backend functionality pass (KV-50)

Server: https://3-13-43-176.sslip.io  
Run: 2026-11-14 17:58 UTC, with `deploy/functionality_pass.py`  
Checks: 104. Passed 102, failed 0, warnings 0, skipped 2.  
Restart check: done

Every check was made as a brand new account on the deployed server, over HTTPS, with the real embedding model. PASS means the answer was what the API documentation says. WARN is worth a look but is not necessarily a bug. SKIPPED means it cannot be checked from this script (reason given).


## Health

| Check | Result | Detail |
|---|---|---|
| GET /health reports the database | PASS |  |
| the embedding model is loaded | PASS |  |
| the upload limit is reported | PASS |  |

## Accounts: sign up and log in

| Check | Result | Detail |
|---|---|---|
| sign up returns 201 and a token | PASS |  |
| the email is stored in lowercase | PASS |  |
| the same email again (any case) is refused | PASS |  |
| a too-short password is refused | PASS |  |
| a bad email address is refused | PASS |  |
| log in with the right password | PASS |  |
| a wrong password gives 401 invalid_credentials | PASS |  |
| an unknown email gets the identical answer | PASS |  |

## Accounts: /auth/me and tokens

| Check | Result | Detail |
|---|---|---|
| GET /auth/me with a valid token | PASS |  |
| no token gives 401 not_authenticated | PASS |  |
| a garbage token gives 401 invalid_token | PASS |  |
| a token with a changed signature gives 401 invalid_token | PASS |  |
| an expired token gives 401 token_expired | SKIPPED | set KV_SECRET_KEY (and have PyJWT) to forge one; covered by tests/test_auth.py |
| a token for a user that does not exist gives 401 invalid_token | SKIPPED | same as above |
| GET /documents without a token is refused | PASS |  |
| GET /tags without a token is refused | PASS |  |
| GET /documents/1 without a token is refused | PASS |  |
| POST /search without a token is refused | PASS |  |
| POST /upload without a token is refused | PASS |  |

## A new account with no documents

| Check | Result | Detail |
|---|---|---|
| the document list is empty | PASS |  |
| the tag list is empty | PASS |  |
| a search finds nothing and is not an error | PASS |  |

## Upload: each supported file type

| Check | Result | Detail |
|---|---|---|
| upload a PDF (T4_first_marathon_training.pdf) | PASS |  |
| upload a PDF (T2_how_vaccines_work.pdf) | PASS |  |
| upload a plain text file (.txt) | PASS |  |
| each upload reports its type, size and chunks | PASS |  |
| the text file is stored as text/plain | PASS |  |
| the PDFs are stored as application/pdf | PASS |  |

## Upload: files that must be refused

| Check | Result | Detail |
|---|---|---|
| a Word file gives 415 unsupported_type | PASS |  |
| an empty file gives 400 empty_file | PASS |  |
| no file gives 400 no_file | PASS |  |
| a PDF with no text (a scan) gives 422 no_text | PASS |  |
| a document with too much text gives 422 text_too_long | PASS |  |
| a file over 10 MB gives 413 file_too_large | PASS |  |
| the same PDF again gives 409 duplicate_document | PASS |  |
| allow_duplicate=true stores it anyway | PASS |  |

## Browse: list, sort, filters, one document

| Check | Result | Detail |
|---|---|---|
| the list holds exactly the three documents | PASS |  |
| each entry has the documented fields | PASS |  |
| sort=newest puts the latest upload first | PASS |  |
| sort=oldest is the reverse | PASS |  |
| sort=name is A to Z, ignoring case | PASS |  |
| an unknown sort is refused (422) | PASS |  |
| since a date in the future lists nothing | PASS |  |
| since a date in the past lists everything | PASS |  |
| since the newest upload's time lists just that document (the time is included) | PASS |  |
| a date that cannot be read is refused (422) | PASS |  |
| tag filter ('sourdough starter') returns only documents with that tag | PASS |  |
| the tag filter ignores case | PASS |  |
| GET /tags lists the tags with counts | PASS |  |
| tags are ordered most common first | PASS |  |
| GET /tags?limit=1 returns one tag | PASS |  |
| an unknown tag lists nothing | PASS |  |
| GET /documents/{id} returns the extracted text | PASS |  |
| text_length is the full length | PASS |  |
| max_chars=50 cuts the text and says so | PASS |  |
| a document that does not exist gives 404 not_found | PASS |  |

## Search

| Check | Result | Detail |
|---|---|---|
| a question about the marathon PDF ranks it first | PASS |  |
| a question about the vaccines PDF ranks it first | PASS |  |
| a question about the text file ranks it first | PASS |  |
| each result has the documented fields | PASS |  |
| results are ordered best first, one per document | PASS |  |
| the matching passage is shown, with the matched words | PASS |  |
| limit=1 returns one result | PASS |  |
| min_score=0 shows every document | PASS |  |
| the default minimum score (0.25) hides weak matches | PASS |  |
| min_score=0.99 finds nothing | PASS |  |
| a nonsense search finds nothing (no results is not an error) | PASS |  |
| a blank search gives 400 empty_query | PASS |  |
| a search over 500 characters gives 400 query_too_long | PASS |  |
| limit=0 is refused (422) | PASS |  |
| an unusual search ('a') answers normally | PASS |  |
| an unusual search ('26.2') answers normally | PASS |  |
| an unusual search ('?!?!') answers normally | PASS |  |
| an unusual search ('😀') answers normally | PASS |  |
| an unusual search ('SELECT * FROM documents; --') answers normally | PASS |  |
| an unusual search ('<script>alert(1)</script>') answers normally | PASS |  |

## Each account sees only its own documents

| Check | Result | Detail |
|---|---|---|
| a second account signs up | PASS |  |
| the second account's list is empty | PASS |  |
| the second account has no tags | PASS |  |
| opening the first account's document gives 404 not_found | PASS |  |
| deleting it gives 404 too, and it is not deleted | PASS |  |
| searching finds none of the first account's documents | PASS |  |
| the same PDF is not a duplicate for the second account | PASS |  |
| its search finds only its own copy | PASS |  |
| the first account still has its three documents | PASS |  |

## Delete

| Check | Result | Detail |
|---|---|---|
| upload a document to delete | PASS |  |
| it can be found before deleting | PASS |  |
| DELETE returns status deleted | PASS |  |
| the deleted document is gone (404) | PASS |  |
| and no longer found by search | PASS |  |
| deleting it again gives 404 | PASS |  |
| the other three are untouched | PASS |  |

## After restarting the containers

| Check | Result | Detail |
|---|---|---|
| the server is back and healthy | PASS |  |
| the embedding model loaded again | PASS |  |
| the account still exists and its password works | PASS |  |
| all three documents are still there | PASS |  |
| each still has all its chunks | PASS |  |
| the extracted text is unchanged | PASS |  |
| search still finds the marathon PDF first | PASS |  |
| the tags are unchanged | PASS |  |
| clean-up: the test account's documents are deleted | PASS |  |

## Failures

None.

## Not covered by this script

| What | Why |
|---|---|
| The database being down | Needs the database stopped. Covered by `tests/test_settings.py` and `tests/test_edge_cases.py` (503 `service_unavailable`, and `/health` returning 503). |
| A password-protected PDF, a corrupt PDF, an unreadable text file | Needs fixture files that are not in the repository. Covered by `tests/test_upload_validation.py`. |
| Login rate limiting (429) | Would lock the address running this script out for 10 minutes. Checked live on 2026-11-14 for KV-54 (see the ticket). |
| Password reset by email | Needs a real inbox. Checked live on 2026-11-14 for KV-53 (see the ticket). |
