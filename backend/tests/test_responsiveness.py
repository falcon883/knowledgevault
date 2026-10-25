"""
KV-33: the API stays responsive during an upload, and the model is loaded at startup.

Runs the real server on a spare local port with the embedding model replaced
by a stand-in that takes 0.1 s per batch, so a large upload takes a few
seconds on any machine. Before KV-33 a search sent during an upload waited
for the whole upload; now it should wait for at most one batch.

For timings with the real model, run bench_responsiveness.py instead.
"""

import random
import socket
import threading
import time
import uuid

import httpx
import pytest
import uvicorn

import embeddings
import main

BATCH_SECONDS = 0.1
MAX_WAIT_SECONDS = 0.8  # one batch plus a generous margin


@pytest.fixture(scope="module")
def live_server():
    loaded_at_startup = []
    real_load_model = embeddings.load_model

    def slow_encode(texts):
        time.sleep(BATCH_SECONDS)  # sleeping releases the GIL, like real model compute
        return [[1.0] + [0.0] * 383 for _ in texts]

    def tracked_load_model():
        loaded_at_startup.append(True)
        return real_load_model()

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(embeddings, "_encode", slow_encode)
        patch.setattr(embeddings, "load_model", tracked_load_model)

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.time() + 20
        while not server.started:
            assert time.time() < deadline, "server did not start"
            time.sleep(0.05)

        yield f"http://127.0.0.1:{port}", loaded_at_startup

        server.should_exit = True
        thread.join(timeout=10)


def test_model_is_loaded_at_startup(live_server):
    _, loaded_at_startup = live_server
    assert loaded_at_startup == [True]


def test_requests_are_served_during_a_large_upload(live_server):
    base, _ = live_server
    rng = random.Random(33)
    vocab = [f"word{n}" for n in range(400)]
    sentences = [" ".join(rng.choice(vocab) for _ in range(12)).capitalize() + "." for _ in range(900)]
    text = f"Responsiveness check {uuid.uuid4()}.\n" + " ".join(sentences)

    result = {}

    def do_upload():
        started = time.perf_counter()
        r = httpx.post(f"{base}/upload", files={"file": ("kv33_big.txt", text.encode(), "text/plain")}, timeout=120)
        result["status"] = r.status_code
        result["seconds"] = time.perf_counter() - started

    uploader = threading.Thread(target=do_upload)
    uploader.start()
    time.sleep(0.5)  # let the upload get going

    # Other endpoints answer straight away while the upload runs.
    started = time.perf_counter()
    assert httpx.get(f"{base}/health", timeout=30).status_code == 200
    assert httpx.get(f"{base}/documents", timeout=30).status_code == 200
    quick = time.perf_counter() - started
    assert uploader.is_alive(), "upload finished too soon for this check"

    search_times = []
    while uploader.is_alive():
        started = time.perf_counter()
        r = httpx.post(f"{base}/search", json={"query": "word12 word99", "min_score": 0}, timeout=60)
        took = time.perf_counter() - started
        assert r.status_code == 200, r.text
        if uploader.is_alive():  # only count searches that really overlapped the upload
            search_times.append(took)
        time.sleep(0.05)

    uploader.join()

    assert result["status"] == 200
    assert result["seconds"] > 2.0, "upload too quick for this check to mean anything"
    assert len(search_times) >= 3, f"only {len(search_times)} searches overlapped the upload"
    assert max(search_times) < MAX_WAIT_SECONDS, f"a search waited {max(search_times):.2f}s behind the upload"
    assert quick < MAX_WAIT_SECONDS, f"/health and /documents took {quick:.2f}s during an upload"
