# Pilot test materials (KV-28)

Everything needed to run the pilot sessions. The plan, task script, observation
log and feedback form are in the **KnowledgeVault Pilot Test Plan** document;
this folder holds the sample documents and the script that prepares the app.

| Path | What it is |
|---|---|
| `sample_docs/targets/` | 8 one-page PDFs, one per volunteer (T1 to T8). Copy them into a folder called `Pilot` on the Desktop. |
| `sample_docs/background/` | 10 PDFs on other topics, loaded into the library so search has something to rank against. |
| `seed_library.py` | Loads the background documents, and checks that every target can be found. |
| `results/` | The pilot results: summary, feedback forms, observation log and facilitator pack. |

## Before the sessions

The sessions use the live site (the API on AWS, the app on CloudFront). Add
`--url https://3-13-43-176.sslip.io` to point the script at the AWS API; without
it the script uses a backend on your own machine (`python main.py` in `backend/`).

```bash
python pilot/seed_library.py --url https://3-13-43-176.sslip.io --password <pilot password>            # load the 10 background documents
python pilot/seed_library.py --url https://3-13-43-176.sslip.io --password <pilot password> --check    # dry run for the 8 target documents
```

Documents belong to an account (KV-42). The script signs in as the pilot account
(`pilot@example.com` unless you pass `--email`), creating it the first time, so
choose a password for it and have the volunteers sign in with that account.
You can also set `PILOT_EMAIL` and `PILOT_PASSWORD` instead of the flags.

`--check` uploads each target, runs the plain-language searches for it (two
prepared ones, plus a volunteer's own wording for T4 from the pilot, KV-47),
prints where it ranked, and deletes the targets again. A target passes if it is
in the top 3 for every search. Add `--verbose` to see the five best results and
their scores for each search, and, when the target is missing, whether it was
outranked or scored below the minimum. Run it with the real model, since the
stand-in embedder used in some tests ranks differently.

## Between volunteers

Delete the document the previous volunteer uploaded (Browse, then Delete) so the
library is back to the 10 background documents.
