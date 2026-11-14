# Search-quality test (KV-61)

Checks the Project Charter's search criterion on a live server: for a curated
set of at least 20 documents and 15 plain-language queries, at least 80% of
the queries should return a relevant source in the top 5 results, judged
against an expected-source key written in advance.

| Path | What it is |
|---|---|
| `search_quality.py` | The runner. Uploads the documents to a throwaway account, runs the queries, deletes the documents, writes the results. |
| `search_quality/queries.json` | The expected-source key: 29 queries (24 paraphrases, 1 broad, 4 short keyword searches) with the document or documents that count as relevant, plus 3 queries that have no answer in the library. |
| `search_quality/notes/` | 6 text notes (coffee, machine learning, interviews, photography, cats, a Lisbon trip). They are added to the 18 PDFs in `pilot/sample_docs/` to make a library of 24 documents. |

## Run it

From the repository root, with the backend's virtual environment active (it
needs `httpx`):

```bash
python eval/search_quality.py https://3-13-43-176.sslip.io
```

It takes a minute or two (24 uploads, each embedded and tagged). The results
go to [`docs/qa/search-quality.md`](../docs/qa/search-quality.md): the overall
rate, top-1 and top-3 rates, a row per query with where the expected document
ranked, and for every miss whether it was outranked or hidden by the minimum
score. The exit code is 0 when the 80% target is met, 1 otherwise. Add
`--keep` to leave the uploaded documents in the test account.

Run it against the real server, not a local one using the stand-in embedder
from some tests: that embedder ranks differently.

## Rules for the key

- The queries were written before the first run against the real model.
  Do not edit a query to make it pass. If one is plainly wrong, say so in the
  results file.
- To add a query, add it to `queries.json` with its expected document and note
  that it was added after the first run.
- After changing the embedding model, the chunking or the minimum score, rerun
  and compare with the committed results.
