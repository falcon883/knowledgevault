"""
KnowledgeVault backend - KV-15: embedding generation.

Uses sentence-transformers locally (all-MiniLM-L6-v2) rather than a
hosted embedding API. This keeps the pipeline free to run and removes
the "third-party API/service dependency" risk the Project Charter flags
(Section 3.5) - there's no API key, no rate limit, and no per-call cost.
384-dimensional output, matching models.EMBEDDING_DIM.

The model is loaded once (lazily, on first use) and reused across
requests rather than reloaded per call.
"""

from functools import lru_cache

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model():
    # Imported lazily so `uvicorn main:app` startup and simple unit tests
    # that don't touch embeddings don't pay the model-load cost.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of strings, returning one vector per input string."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return vectors.tolist()


def embed_text(text: str) -> list[float]:
    """Embed a single string (e.g. an incoming search query)."""
    return embed_texts([text])[0]
