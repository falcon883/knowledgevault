"""
Search-quality test for a running KnowledgeVault API.

The Project Charter's success criteria ask for a curated set of at least 20
documents and 15 plain-language queries, with a relevant source in the top 5
for at least 80% of the queries, judged against a predefined expected-source
key. This script runs exactly that against a live server and writes the result
to docs/qa/search-quality.md.

    python eval/search_quality.py https://3-13-43-176.sslip.io

Run it from the repository root with the backend's virtual environment active
(it needs httpx, which is in backend/requirements.txt).

What it does:
  1. signs up a throwaway account (qa-search-...@example.test), so the library
     holds only the test documents and nothing else can outrank them;
  2. uploads the 24 test documents: the 18 PDFs in pilot/sample_docs/ plus the 6
     text notes in eval/search_quality/notes/;
  3. runs every query in eval/search_quality/queries.json through POST /search
     (the same call the app makes, default settings) and checks where the
     expected document came out;
  4. runs the "negative" queries, which have no answer in the library, and
     records whether search correctly returns nothing;
  5. deletes the documents it uploaded (use --keep to leave them) and writes the
     results file.

The key (queries.json) was written before the first run against the real
model and should not be edited to make a query pass. If a query is plainly
wrong, say so in the results file instead of quietly changing it.

Exit code: 0 if at least 80% of the queries have a relevant document in the
top 5, otherwise 1.
"""

import argparse
import json
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PILOT_DOCS = ROOT / "pilot" / "sample_docs"
NOTES = ROOT / "eval" / "search_quality" / "notes"
KEY = ROOT / "eval" / "search_quality" / "queries.json"
DEFAULT_RESULTS = ROOT / "docs" / "qa" / "search-quality.md"

TOP_N = 5
TARGET = 0.80
CONTENT_TYPES = {".pdf": "application/pdf", ".txt": "text/plain"}


def corpus() -> list[Path]:
    files = sorted((PILOT_DOCS / "targets").glob("*.pdf")) + sorted((PILOT_DOCS / "background").glob("*.pdf")) + sorted(NOTES.glob("*.txt"))
    return files


def sign_up(client: httpx.Client) -> str | None:
    email = f"qa-search-{int(time.time())}-{secrets.token_hex(3)}@example.test"
    r = client.post("/auth/signup", json={"email": email, "password": secrets.token_urlsafe(16)})
    if r.status_code != 201:
        print(f"Could not create the test account: HTTP {r.status_code} {r.text[:200]}")
        return None
    return r.json()["access_token"]


def search(client: httpx.Client, query: str, **extra) -> list[dict]:
    r = client.post("/search", json={"query": query, "limit": 10, **extra})
    r.raise_for_status()
    return r.json()["results"]


def first_rank(results: list[dict], wanted_ids: set[int]) -> int | None:
    for position, hit in enumerate(results, start=1):
        if hit["document_id"] in wanted_ids:
            return position
    return None


def run(base: str, out: Path, keep: bool) -> int:
    key = json.loads(KEY.read_text())
    files = corpus()
    if len(files) < 20:
        print(f"Only {len(files)} test documents found; the charter asks for at least 20.")
        return 2

    uploaded: dict[str, int] = {}  # file name -> document id
    with httpx.Client(base_url=base, timeout=180) as client:
        try:
            health = client.get("/health").json()
        except httpx.HTTPError as exc:
            print(f"Can't reach {base}: {exc}")
            return 1
        if not health.get("model_loaded"):
            print("Note: the embedding model is not loaded yet, so the first request will be slow.")
        token = sign_up(client)
        if not token:
            return 1
        client.headers["Authorization"] = f"Bearer {token}"

        try:
            print(f"Uploading {len(files)} documents...")
            for path in files:
                with path.open("rb") as f:
                    r = client.post("/upload", files={"file": (path.name, f, CONTENT_TYPES[path.suffix])})
                if r.status_code != 200:
                    print(f"  FAILED {path.name}: HTTP {r.status_code} {r.text[:200]}")
                    return 1
                uploaded[path.name] = r.json()["id"]
            print("Done. Running the queries.\n")

            rows = []
            for q in key["queries"]:
                wanted = {uploaded[name] for name in q["expected"]}
                results = search(client, q["query"])
                rank = first_rank(results, wanted)
                row = {**q, "rank": rank, "top": [(h["filename"], h["score"]) for h in results[:3]], "count": len(results)}
                if rank is None or rank > TOP_N:
                    # Why did it miss: below the minimum score, or outranked?
                    everything = search(client, q["query"], limit=20, min_score=0)
                    position = first_rank(everything, wanted)
                    if position is None:
                        row["why"] = "not in the top 20 even with the minimum score off"
                    else:
                        hit = everything[position - 1]
                        if rank is None:
                            row["why"] = f"hidden by the minimum score: it is #{position} with the cutoff off, scoring {hit['score']:.3f}"
                        else:
                            row["why"] = f"outranked: #{position}, scoring {hit['score']:.3f}"
                rows.append(row)
                shown = f"#{rank}" if rank else "not found"
                print(f"{q['id']}  {shown:>9}  {q['query']}")

            negatives = []
            for n in key["negatives"]:
                results = search(client, n["query"])
                negatives.append({**n, "count": len(results), "top": [(h["filename"], h["score"]) for h in results[:3]]})
                print(f"{n['id']:>3}  {len(results)} result(s)  {n['query']}")
        finally:
            if not keep:
                for doc_id in uploaded.values():
                    client.delete(f"/documents/{doc_id}")

    hits = [r for r in rows if r["rank"] and r["rank"] <= TOP_N]
    rate = len(hits) / len(rows)
    print(f"\nRelevant source in the top {TOP_N}: {len(hits)} of {len(rows)} ({rate:.0%}). Target {TARGET:.0%}.")
    write_results(out, base, health, files, rows, negatives)
    print(f"Results written to {out}")
    return 0 if rate >= TARGET else 1


def pct(n: int, d: int) -> str:
    return f"{n} of {d} ({n / d:.0%})" if d else "n/a"


def write_results(out: Path, base: str, health: dict, files: list[Path], rows: list[dict], negatives: list[dict]) -> None:
    total = len(rows)
    top1 = sum(1 for r in rows if r["rank"] == 1)
    top3 = sum(1 for r in rows if r["rank"] and r["rank"] <= 3)
    top5 = sum(1 for r in rows if r["rank"] and r["rank"] <= TOP_N)
    mrr = sum(1 / r["rank"] for r in rows if r["rank"]) / total
    passed = top5 / total >= TARGET
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Search-quality test",
        "",
        f"Run on {when} against `{base}` with the real embedding model "
        f"(model loaded: {health.get('model_loaded')}).",
        "",
        "The Project Charter's success criteria ask for a curated set of at least 20 documents and 15 "
        "plain-language queries, with a relevant source in the top 5 results for at least 80% of the queries, "
        "judged against an expected-source key written in advance.",
        "",
        f"**Result: {pct(top5, total)} of queries had a relevant source in the top {TOP_N}, "
        f"against a target of {TARGET:.0%}. {'The criterion is met.' if passed else 'The criterion is not met.'}**",
        "",
        "## How the test was set up",
        "",
        f"- **Library:** {len(files)} documents in a fresh account, so nothing else could outrank them: "
        f"{sum(1 for f in files if f.suffix == '.pdf')} one-page PDFs (the 8 pilot targets and 10 background "
        f"documents from `pilot/sample_docs/`) and {sum(1 for f in files if f.suffix == '.txt')} text notes "
        "(`eval/search_quality/notes/`). Topics range from cooking and health to Python, a meeting, and a travel plan.",
        f"- **Queries:** {total} plain-language queries, written before the first run and not changed afterwards "
        "(`eval/search_quality/queries.json`). 24 are paraphrases that avoid the document's own wording, 1 is a broad "
        "question where two documents count, and 4 are short keyword searches.",
        "- **Pass rule:** a query passes if any expected document is among the first 5 results of the same "
        "`POST /search` call the app makes, with default settings (including the minimum score).",
        "- **Negative queries:** 3 questions with no answer anywhere in the library. Search should return nothing.",
        "- **Rerun:** `python eval/search_quality.py https://3-13-43-176.sslip.io` (see `eval/README.md`).",
        "",
        "## Summary",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Relevant source in the top 5 (the charter's measure) | {pct(top5, total)} |",
        f"| Relevant source in the top 3 | {pct(top3, total)} |",
        f"| Relevant source first | {pct(top1, total)} |",
        f"| Mean reciprocal rank (1.0 = always first) | {mrr:.2f} |",
        f"| Negative queries that correctly returned nothing | {pct(sum(1 for n in negatives if n['count'] == 0), len(negatives))} |",
        "",
        "| Query type | Queries | Top 5 | First |",
        "|---|---|---|---|",
    ]
    for kind in ("paraphrase", "broad", "short"):
        group = [r for r in rows if r["type"] == kind]
        if group:
            lines.append(
                f"| {kind} | {len(group)} | {pct(sum(1 for r in group if r['rank'] and r['rank'] <= TOP_N), len(group))} "
                f"| {pct(sum(1 for r in group if r['rank'] == 1), len(group))} |"
            )

    lines += ["", "## Every query", "", "| # | Type | Query | Expected | Rank | Best result (score) |", "|---|---|---|---|---|---|"]
    for r in rows:
        rank = f"{r['rank']}" if r["rank"] else "not found"
        mark = "" if r["rank"] and r["rank"] <= TOP_N else " **MISS**"
        best = f"{r['top'][0][0]} ({r['top'][0][1]:.2f})" if r["top"] else "no results"
        expected = " or ".join(f"`{e}`" for e in r["expected"])
        lines.append(f"| {r['id']} | {r['type']} | {r['query']} | {expected} | {rank}{mark} | {best} |")

    misses = [r for r in rows if not (r["rank"] and r["rank"] <= TOP_N)]
    lines += ["", "## Misses", ""]
    if not misses:
        lines.append("None. Every query had a relevant source in the top 5.")
    else:
        for r in misses:
            lines.append(f"- **{r['id']}** \"{r['query']}\": {r.get('why', 'unknown')}.")

    lines += ["", "## Negative queries (nothing in the library should match)", "", "| # | Query | Results returned | Best result (score) |", "|---|---|---|---|"]
    for n in negatives:
        best = f"{n['top'][0][0]} ({n['top'][0][1]:.2f})" if n["top"] else "-"
        lines.append(f"| {n['id']} | {n['query']} | {n['count']} | {best} |")

    lines += [
        "",
        "## Limits",
        "",
        "- The library is small (24 short documents), so every query has few rivals. The result shows that meaning-based "
        "search works on this set; it does not predict performance on thousands of documents.",
        "- The queries were written by the team, who know what the documents say. The pilot volunteers' own wording "
        "(`pilot/results/`) is the more independent evidence for how real users search.",
        "- Scores depend on the embedding model and the minimum-score setting, so a rerun after changing either "
        "should be compared with this file.",
        "",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="address of the API, e.g. https://3-13-43-176.sslip.io")
    parser.add_argument("--out", type=Path, default=DEFAULT_RESULTS, help="where to write the results (default: docs/qa/search-quality.md)")
    parser.add_argument("--keep", action="store_true", help="leave the uploaded documents in the test account")
    args = parser.parse_args()
    return run(args.url.rstrip("/"), args.out, args.keep)


if __name__ == "__main__":
    sys.exit(main())
