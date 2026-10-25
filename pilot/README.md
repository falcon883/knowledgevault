# Pilot test materials (KV-28)

Everything needed to run the pilot sessions. The plan, task script, observation
log and feedback form are in the **KnowledgeVault Pilot Test Plan** document;
this folder holds the sample documents and the script that prepares the app.

| Path | What it is |
|---|---|
| `sample_docs/targets/` | 8 one-page PDFs, one per volunteer (T1 to T8). Copy them into a folder called `Pilot` on the Desktop. |
| `sample_docs/background/` | 10 PDFs on other topics, loaded into the library so search has something to rank against. |
| `seed_library.py` | Loads the background documents, and checks that every target can be found. |

## Before the sessions

With the backend running (`python main.py` in `backend/`):

```bash
python pilot/seed_library.py            # load the 10 background documents
python pilot/seed_library.py --check    # dry run for the 8 target documents
```

`--check` uploads each target, runs two plain-language searches for it, prints
where it ranked, and deletes the targets again. A target passes if it is in the
top 3 for both searches. Run it with the real model, since the stand-in
embedder used in some tests ranks differently.

## Between volunteers

Delete the document the previous volunteer uploaded (Browse, then Delete) so the
library is back to the 10 background documents.
