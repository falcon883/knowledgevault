"""
Timings for KV-33, against a running server with the real embedding model.

    python main.py                      # in one terminal, then straight away:
    python bench_responsiveness.py      # in another (optionally pass the server URL)

Prints the numbers to paste on the Jira issue:
  1. how long the very first search takes (right after the server starts),
  2. how long searches take when nothing else is happening,
  3. how long searches take while a large file is being uploaded.

Run it once on the old code (before KV-33) and once on the new code, each
time starting the server fresh. Uploads a temporary document and deletes it
afterwards.
"""

import random
import sys
import threading
import time
import uuid

import httpx

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
QUERY = {"query": "how do I keep tomatoes healthy", "min_score": 0}


def search():
    started = time.perf_counter()
    r = httpx.post(f"{BASE}/search", json=QUERY, timeout=300)
    r.raise_for_status()
    return time.perf_counter() - started


def summary(values):
    if not values:
        return "none (the upload finished before a search could be sent)"
    values = sorted(values)
    return f"median {values[len(values) // 2]:.2f}s, slowest {values[-1]:.2f}s"


first = search()
print(f"First search after startup: {first:.2f}s")

idle = [search() for _ in range(5)]
print(f"Searches with nothing else running (5): {summary(idle)}")

rng = random.Random(33)
vocab = [f"{rng.choice('abcdefghij')}{n}{rng.choice(['ing', 'ed', 'er', 'ly', ''])}" for n in range(1500)]
text = f"Benchmark document {uuid.uuid4()}.\n" + " ".join(
    " ".join(rng.choice(vocab) for _ in range(12)).capitalize() + "." for _ in range(3000)
)
print(f"Uploading {len(text) // 1000} KB of text...")

result = {}


def upload():
    started = time.perf_counter()
    r = httpx.post(f"{BASE}/upload", files={"file": ("bench_big.txt", text.encode(), "text/plain")}, timeout=900)
    result["status"] = r.status_code
    result["seconds"] = time.perf_counter() - started
    if r.status_code == 200:
        result["id"] = r.json()["id"]
        result["chunks"] = r.json()["chunk_count"]


worker = threading.Thread(target=upload)
worker.start()
time.sleep(1.0)  # let the upload get going

during = []
while worker.is_alive():
    took = search()
    during.append(took)
    time.sleep(0.2)
worker.join()

if result.get("status") != 200:
    print(f"Upload failed: {result}")
else:
    print(f"Upload: {result['seconds']:.1f}s for {result['chunks']} chunks")
    print(f"Searches sent while it ran ({len(during)}): {summary(during)}")
    httpx.delete(f"{BASE}/documents/{result['id']}", timeout=60)
