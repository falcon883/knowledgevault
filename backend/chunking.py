"""
KnowledgeVault backend - KV-14: chunking strategy.

Fixed-size chunking with overlap: simple, predictable, and good enough
for the demo-scale corpus this project targets (see Project Charter
Section 2.3, "large-scale performance tuning" is explicitly out of
scope). Overlap keeps a sentence that straddles a chunk boundary
findable from either side.
"""

CHUNK_SIZE = 800  # characters per chunk
CHUNK_OVERLAP = 150  # characters shared between consecutive chunks


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping fixed-size chunks.

    Returns an empty list for empty/whitespace-only input rather than a
    single empty chunk.
    """
    text = text.strip()
    if not text:
        return []

    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_length:
            break
        start = end - overlap

    return chunks
