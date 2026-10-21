"""
KnowledgeVault backend - KV-15: embedding generation.

Uses sentence-transformers locally (all-MiniLM-L6-v2) rather than a
hosted embedding API. This keeps the pipeline free to run and removes
the "third-party API/service dependency" risk the Project Charter flags
(Section 3.5) - there's no API key, no rate limit, and no per-call cost.
384-dimensional output, matching models.EMBEDDING_DIM.

The model is loaded once and reused across requests rather than reloaded
per call. KV-33: the server loads it at startup (load_model, called from
main.py) so the first request is not the slow one; if that fails it is
loaded on first use instead.

KV-33: uploads embed on a worker thread while searches embed on another, and
the model is not safe to call from two threads at once (its tokenizer can
raise "Already borrowed"). So calls take a lock, and long inputs are embedded
in small batches, releasing the lock between batches. A search that arrives
during a big upload waits for at most one small batch, not the whole file.
"""

import threading
import time
from functools import lru_cache

MODEL_NAME = "all-MiniLM-L6-v2"

# Texts embedded per lock hold. Small enough that a search arriving mid-upload
# waits well under a second on a laptop CPU, big enough to keep throughput.
BATCH_SIZE = 8



class _FairLock:
    """
    A lock that hands over in arrival order. A plain threading.Lock does not:
    a thread that releases it and immediately asks again usually wins, so a
    long upload could starve a search that is waiting for its turn.
    """

    def __init__(self):
        self._cond = threading.Condition()
        self._next_ticket = 0
        self._now_serving = 0

    def __enter__(self):
        with self._cond:
            ticket = self._next_ticket
            self._next_ticket += 1
            while ticket != self._now_serving:
                self._cond.wait()

    def __exit__(self, *exc):
        with self._cond:
            self._now_serving += 1
            self._cond.notify_all()


_model_lock = _FairLock()


@lru_cache(maxsize=1)
def _get_model():
    # Imported lazily so simple unit tests that don't touch embeddings
    # don't pay the model-load cost.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def load_model() -> float:
    """
    Load the model now and run one tiny embedding so the first real request
    is as fast as later ones. Returns how many seconds that took.
    """
    start = time.perf_counter()
    with _model_lock:
        _encode(["warm up"])
    return time.perf_counter() - start


def is_loaded() -> bool:
    return _get_model.cache_info().currsize > 0


def _encode(texts: list[str]) -> list[list[float]]:
    """Run the model on one batch. The caller must hold _model_lock."""
    model = _get_model()
    vectors = model.encode(
        texts, convert_to_numpy=True, show_progress_bar=False, batch_size=BATCH_SIZE
    )
    return vectors.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of strings, returning one vector per input string."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        with _model_lock:
            vectors.extend(_encode(texts[start : start + BATCH_SIZE]))
    return vectors


def embed_text(text: str) -> list[float]:
    """Embed a single string (e.g. an incoming search query)."""
    return embed_texts([text])[0]
