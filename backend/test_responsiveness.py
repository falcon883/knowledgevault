"""
Manual check for KV-33: the API stays responsive during an upload, and the
embedding model is loaded at startup.

    python test_responsiveness.py

Starts the real server on a spare local port, with the embedding model
replaced by a stand-in that takes 0.1 s per batch (so a large upload takes a
few seconds on any machine). Then uploads a large file and, while it is still
processing, sends searches. Before KV-33 those searches waited for the whole
upload; now each should come back in well under a second.

It does not need the embedding model, so it never downloads it. For real
timings with the real model, run bench_responsiveness.py against the running
server. Cleans up after itself. Requires Postgres with pgvector running.
"""

import random
import socket
import threading
import time
import uuid

import httpx
import uvicorn

import embeddings
import main
from database import Base, engine
from init_db import upgrade_schema

Base.metadata.create_all(bind=engine)
upgrade_schema()

BATCH_SECONDS = 0.1
MAX_SEARCH_SECONDS = 0.8  # one batch plus a generous margin

# ---- Stand-in for the model: slow like real compute, and it releases the GIL
def slow_encode(texts):
    time.sleep(BATCH_SECONDS)
    return [[1.0] + [0.0] * 383 for _ in texts]


embeddings._encode = slow_encode

loaded_at_startup = []
real_load_model = embeddings.load_model


def tracked_load_model():
    loaded_at_startup.append(True)
    return real_load_model()


embeddings.load_model = tracked_load_model

# ---- Start the real server in a background thread
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
base = f"http://127.0.0.1:{port}"

server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="warning"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
deadline = time.time() + 20
while not server.started:
    assert time.time() < deadline, "server did not start"
    time.sleep(0.05)

doc_id = None
try:
    # ---- The model is loaded before any request arrives -------------------
    assert loaded_at_startup == [True], "load_model was not called at startup"
    print("Embedding model is loaded at startup, before the first request")

    # ---- A large upload ----------------------------------------------------
    rng = random.Random(33)
    vocab = [f"word{n}" for n in range(400)]
    sentences = [
        " ".join(rng.choice(vocab) for _ in range(12)).capitalize() + "."
        for _ in range(900)
    ]
    text = f"Responsiveness check {uuid.uuid4()}.\n" + " ".join(sentences)
    print(f"Uploading {len(text) // 1000} KB of text (about {len(text) // 650} chunks)")

    result = {}

    def do_upload():
        started = time.perf_counter()
        r = httpx.post(
            f"{base}/upload",
            files={"file": ("kv33_big.txt", text.encode(), "text/plain")},
            timeout=120,
        )
        result["status"] = r.status_code
        result["body"] = r.json()
        result["seconds"] = time.perf_counter() - started

    uploader = threading.Thread(target=do_upload)
    uploader.start()
    time.sleep(0.5)  # let the upload get going

    latencies = []
    while uploader.is_alive():
        started = time.perf_counter()
        r = httpx.post(f"{base}/search", json={"query": "word12 word99", "min_score": 0}, timeout=60)
        took = time.perf_counter() - started
        assert r.status_code == 200, r.text
        if uploader.is_alive():  # only count searches that really overlapped the upload
            latencies.append(took)
        time.sleep(0.05)
    uploader.join()

    assert result["status"] == 200, result
    doc_id = result["body"]["id"]
    print(f"Upload took {result['seconds']:.1f}s")
    assert result["seconds"] > 2.0, "upload too quick for this check to mean anything"
    assert len(latencies) >= 3, f"only {len(latencies)} searches overlapped the upload"
    worst = max(latencies)
    print(
        f"{len(latencies)} searches during the upload: "
        f"median {sorted(latencies)[len(latencies) // 2]:.2f}s, slowest {worst:.2f}s"
    )
    assert worst < MAX_SEARCH_SECONDS, f"a search waited {worst:.2f}s behind the upload"
    print("Searches stay responsive while a large upload is processing")

    # Other endpoints answer during the upload too (the event loop is free).
    uploader = threading.Thread(target=do_upload)
    result.clear()
    text2 = text.replace("Responsiveness check", "Second responsiveness check")
    text = text2
    uploader.start()
    time.sleep(0.5)
    started = time.perf_counter()
    assert httpx.get(f"{base}/health", timeout=30).status_code == 200
    assert httpx.get(f"{base}/documents", timeout=30).status_code == 200
    quick = time.perf_counter() - started
    uploader.join()
    second_id = result["body"]["id"]
    httpx.delete(f"{base}/documents/{second_id}", timeout=30)
    assert quick < MAX_SEARCH_SECONDS, f"/health and /documents took {quick:.2f}s during an upload"
    print(f"/health and /documents answered in {quick:.2f}s during an upload")
finally:
    if doc_id is not None:
        httpx.delete(f"{base}/documents/{doc_id}", timeout=30)
    server.should_exit = True
    thread.join(timeout=10)

print("KV-33 responsiveness passed.")
