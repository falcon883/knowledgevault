"""
Load the pilot test library, and check that the target documents can be found.

    python pilot/seed_library.py            # upload the 10 background documents
    python pilot/seed_library.py --check    # dry run: can each target be found?

Needs the backend running (python main.py in backend/). Both steps use the
real API, so what you see here is what a volunteer will get.

--check uploads each of the 8 target documents, runs two plain-language
searches for each (worded differently from the document), reports where the
target came out in the results, and then deletes the targets it uploaded. A
target passes if it is in the top 3 for both searches. If one fails, adjust
the wording of that document rather than the searches.
"""

import argparse
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


def rank_of(client: httpx.Client, query: str, doc_id: int) -> int | None:
    # Same defaults the app uses, so the result matches what a volunteer sees.
    r = client.post("/search", json={"query": query, "limit": 10})
    r.raise_for_status()
    ids = [hit["document_id"] for hit in r.json()["results"]]
    return ids.index(doc_id) + 1 if doc_id in ids else None


def check(client: httpx.Client) -> int:
    ours: list[int] = []  # documents this run uploaded, deleted again at the end
    failures = 0
    try:
        print(f"{'target':32} {'search 1':>9} {'search 2':>9}   (position in results; top {TOP_N} passes)")
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

            ranks = [rank_of(client, q, doc_id) for q in QUERIES[path.stem]]
            ok = all(rank is not None and rank <= TOP_N for rank in ranks)
            failures += not ok
            shown = [str(rank) if rank else "not found" for rank in ranks]
            print(f"{path.stem:32} {shown[0]:>9} {shown[1]:>9}   {'ok' if ok else 'FIX THIS ONE'}")
    finally:
        for doc_id in ours:
            client.delete(f"/documents/{doc_id}")

    print("\nAll targets can be found." if not failures else f"\n{failures} target(s) need a closer look.")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="dry run: find each target document by search")
    parser.add_argument("--url", default="http://localhost:8000", help="backend address (default %(default)s)")
    args = parser.parse_args()

    with httpx.Client(base_url=args.url, timeout=180) as client:
        try:
            health = client.get("/health").json()
        except httpx.HTTPError:
            print(f"Can't reach the backend at {args.url}. Start it with: python main.py (in backend/)")
            return 1
        if not health.get("model_loaded"):
            print("Note: the embedding model is not loaded yet, so the first request will be slow.\n")
        return check(client) if args.check else seed(client)


if __name__ == "__main__":
    sys.exit(main())
