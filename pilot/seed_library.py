"""
Load the pilot test library, and check that the target documents can be found.

    python pilot/seed_library.py            # upload the 10 background documents
    python pilot/seed_library.py --check    # dry run: can each target be found?

Needs the backend running (python main.py in backend/). Both steps use the
real API, so what you see here is what a volunteer will get.

Documents belong to an account (KV-42), so both steps sign in first, creating
the account the first time. Give it with --email and --password (or the
PILOT_EMAIL and PILOT_PASSWORD environment variables); the volunteers sign in
with the same account to see the library this script loads.

--check uploads each of the 8 target documents, runs the plain-language
searches listed below for each (worded differently from the document),
reports where the target came out in the results, and then deletes the
targets it uploaded. A target passes if it is in the top 3 for the prepared
searches and in the top 2 for the wording a pilot volunteer actually typed
(T1 to T6, KV-47 and KV-48). The prepared searches were written with the
document in mind; the volunteers' were not, so they are the more honest test.

Add --verbose to see, for every search, the five best results with their
scores, so you can tell what is outranking the target.
"""

import argparse
import os
import sys
from pathlib import Path

import httpx

DOCS = Path(__file__).parent / "sample_docs"

# Two searches per target, written the way a volunteer might describe it.
QUERIES = {
    "T1_composting_at_home": ["what can I do with leftover vegetable scraps in the garden", "how to turn food waste into soil"],
    "T2_how_vaccines_work": ["how does getting a shot protect me from disease", "why do booster shots work"],
    "T3_index_funds_for_beginners": ["low cost way to invest in the whole stock market", "what is an index fund"],
    "T4_first_marathon_training": ["how should I prepare to run 26 miles", "beginner running plan for a long race"],
    "T5_why_sourdough_rises": ["why does bread dough puff up", "what makes homemade bread with wild yeast taste tangy"],
    "T6_sleep_and_memory": ["does getting enough rest help me remember things", "what happens in the brain at night"],
    "T7_bike_commuting": ["tips for riding my bike to work", "how to stay safe cycling in traffic"],
    "T8_how_solar_panels_work": ["how do rooftop panels make electricity", "turn sunlight into power for my house"],
}
TOP_N = 3

# What pilot volunteers P1 to P6 actually typed for their own document (from
# pilot/results/observation-log.csv). These are the real test of search: they
# were not written with the document in mind. P2, P5 and P6 found theirs at
# rank 2 or 3 and P4 did not find it (KV-47, KV-48), so they must now be in the
# top 2.
VOLUNTEER_QUERIES = {
    "T1_composting_at_home": "How do I turn kitchen scraps and yard waste into compost at home?",
    "T2_how_vaccines_work": "Explain how vaccines teach the body to recognize germs and build protection.",
    "T3_index_funds_for_beginners": "Beginner-friendly guide to investing in a fund that tracks a market index.",
    "T4_first_marathon_training": "A gradual weekly running plan for someone preparing for their first 26.2-mile race.",
    "T5_why_sourdough_rises": "What makes sourdough bread dough expand and form bubbles during fermentation?",
    "T6_sleep_and_memory": "How does getting enough sleep help the brain store and remember information?",
}
VOLUNTEER_TOP_N = 2


def sign_in(client: httpx.Client, email: str, password: str) -> bool:
    """Log in, or create the account the first time. Sets the token on the client."""
    r = client.post("/auth/login", json={"email": email, "password": password})
    if r.status_code == 401:
        r = client.post("/auth/signup", json={"email": email, "password": password})
        if r.status_code == 201:
            print(f"Created the account {email}.")
    if r.status_code not in (200, 201):
        print(f"Could not sign in as {email}: {r.status_code} {r.text}")
        return False
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return True


def upload(client: httpx.Client, path: Path) -> httpx.Response:
    with path.open("rb") as f:
        return client.post("/upload", files={"file": (path.name, f, "application/pdf")})


def seed(client: httpx.Client) -> int:
    files = sorted((DOCS / "background").glob("*.pdf"))
    for path in files:
        r = upload(client, path)
        if r.status_code == 200:
            print(f"uploaded   {path.name}")
        elif r.status_code == 409:
            print(f"already in {path.name}")
        else:
            print(f"FAILED     {path.name}: {r.status_code} {r.text}")
            return 1
    print(f"\nThe library has the {len(files)} background documents.")
    return 0


def search(client: httpx.Client, query: str, **extra) -> list[dict]:
    # Same defaults the app uses, so the result matches what a volunteer sees.
    r = client.post("/search", json={"query": query, "limit": 10, **extra})
    r.raise_for_status()
    return r.json()["results"]


def rank_of(results: list[dict], doc_id: int) -> int | None:
    ids = [hit["document_id"] for hit in results]
    return ids.index(doc_id) + 1 if doc_id in ids else None


def show_top(results: list[dict], doc_id: int, n: int = 5) -> None:
    """Print the best results with their scores; mark the target with an arrow."""
    if not results:
        print("      (no results above the minimum score)")
    for position, hit in enumerate(results[:n], start=1):
        marker = "->" if hit["document_id"] == doc_id else "  "
        print(f"    {marker} {position}. {hit['score']:.3f}  {hit['filename']}")


def check(client: httpx.Client, verbose: bool = False) -> int:
    ours: list[int] = []  # documents this run uploaded, deleted again at the end
    failures = 0
    try:
        print(f"{'target':32} position in results per search (last one = volunteer's wording)")
        for path in sorted((DOCS / "targets").glob("*.pdf")):
            r = upload(client, path)
            if r.status_code == 200:
                doc_id = r.json()["id"]
                ours.append(doc_id)
            elif r.status_code == 409:
                doc_id = r.json()["existing"]["id"]  # already in the library; leave it there
            else:
                print(f"FAILED upload {path.name}: {r.status_code} {r.text}")
                return 1

            wanted = [(q, TOP_N) for q in QUERIES[path.stem]]
            if path.stem in VOLUNTEER_QUERIES:
                wanted.append((VOLUNTEER_QUERIES[path.stem], VOLUNTEER_TOP_N))
            queries = [q for q, _ in wanted]
            found = [search(client, q) for q in queries]
            ranks = [rank_of(results, doc_id) for results in found]
            ok = all(rank is not None and rank <= limit for rank, (_, limit) in zip(ranks, wanted))
            failures += not ok
            shown = [str(rank) if rank else "not found" for rank in ranks]
            print(f"{path.stem:32} {'  '.join(f'{x:>9}' for x in shown)}   {'ok' if ok else 'FIX THIS ONE'}")
            if verbose:
                for query, results in zip(queries, found):
                    print(f'    "{query}"')
                    show_top(results, doc_id)
                    if rank_of(results, doc_id) is None:
                        # Missing from the normal results: is it below the minimum score, or outranked?
                        everything = search(client, query, limit=20, min_score=0)
                        position = rank_of(everything, doc_id)
                        if position is None:
                            print("    target is not in the top 20 even with no minimum score")
                        else:
                            score = everything[position - 1]["score"]
                            print(f"    target is #{position} with the minimum score off, scoring {score:.3f}")
    finally:
        for doc_id in ours:
            client.delete(f"/documents/{doc_id}")

    print("\nAll targets can be found." if not failures else f"\n{failures} target(s) need a closer look.")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="dry run: find each target document by search")
    parser.add_argument("--verbose", action="store_true", help="with --check: show the top 5 results and scores for every search")
    parser.add_argument("--url", default="http://localhost:8000", help="backend address (default %(default)s)")
    parser.add_argument("--email", default=os.getenv("PILOT_EMAIL", "pilot@example.com"), help="pilot account (default %(default)s)")
    parser.add_argument("--password", default=os.getenv("PILOT_PASSWORD"), help="pilot account password (or set PILOT_PASSWORD)")
    args = parser.parse_args()
    if not args.password:
        print("Give the pilot account's password with --password or the PILOT_PASSWORD environment variable.")
        return 2

    with httpx.Client(base_url=args.url, timeout=180) as client:
        try:
            health = client.get("/health").json()
        except httpx.HTTPError:
            print(f"Can't reach the backend at {args.url}. Start it with: python main.py (in backend/)")
            return 1
        if not health.get("model_loaded"):
            print("Note: the embedding model is not loaded yet, so the first request will be slow.\n")
        if not sign_in(client, args.email, args.password):
            return 1
        return check(client, args.verbose) if args.check else seed(client)


if __name__ == "__main__":
    sys.exit(main())
