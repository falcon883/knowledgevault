"""
Compare search before and after KV-38 (the fixed 800-character chunks against
the sentence-aware ones), without changing the database.

    python compare_chunking.py "how do I feed a sourdough starter" "what is the budget for Q3"

Reads the text of every stored document, chunks it both ways in memory, embeds
the chunks with the real model, and for each question prints the best matching
snippet per document under each method, followed by how many chunks start and
end like a sentence. Run it with the real model (not KV_FAKE_EMBEDDINGS) when
you want results worth showing; paste the output into the Jira ticket or the
sprint notes.
"""

import argparse
import sys

import numpy as np
from sqlalchemy import select

import embeddings
from chunking import boundary_quality, chunk_text, chunk_text_fixed
from database import SessionLocal
from models import Document

SNIPPET = 160


def build_index(texts: dict[str, str], chunker, embed=None) -> list[tuple[str, str, np.ndarray]]:
    """(document name, chunk text, unit-length vector) for every chunk of every document."""
    embed = embed or embeddings.embed_texts
    rows = [(name, chunk) for name, text in texts.items() for chunk in chunker(text)]
    if not rows:
        return []
    vectors = np.array(embed([chunk for _, chunk in rows]), dtype=float)
    vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
    return [(name, chunk, vector) for (name, chunk), vector in zip(rows, vectors)]


def search(index, query_vector, top: int = 3) -> list[tuple[float, str, str]]:
    """Best chunk per document as (score, document name, chunk text), best first."""
    query = np.asarray(query_vector, dtype=float)
    query = query / max(np.linalg.norm(query), 1e-12)
    best: dict[str, tuple[float, str]] = {}
    for name, chunk, vector in index:
        score = float(vector @ query)
        if name not in best or score > best[name][0]:
            best[name] = (score, chunk)
    ranked = sorted(((score, name, chunk) for name, (score, chunk) in best.items()), reverse=True)
    return ranked[:top]


def show(snippet: str) -> str:
    flat = " ".join(snippet.split())
    return flat if len(flat) <= SNIPPET else flat[:SNIPPET] + "..."


def compare(texts: dict[str, str], queries: list[str], embed=None, top: int = 3) -> str:
    embed = embed or embeddings.embed_texts
    methods = {"BEFORE (fixed 800)": chunk_text_fixed, "AFTER (sentence-aware)": chunk_text}
    indexes = {label: build_index(texts, chunker, embed) for label, chunker in methods.items()}

    out = []
    for query in queries:
        out.append(f'\nQuery: "{query}"')
        query_vector = embed([query])[0]
        for label, index in indexes.items():
            out.append(f"  {label}")
            for score, name, chunk in search(index, query_vector, top):
                out.append(f"    {score:.3f}  {name}: {show(chunk)}")

    out.append("\nChunk boundaries")
    for label, chunker in methods.items():
        quality = boundary_quality([c for text in texts.values() for c in chunker(text)])
        n = max(quality["chunks"], 1)
        out.append(
            f"  {label}: {quality['chunks']} chunks, {100 * quality['clean_start'] // n}% start like a sentence, "
            f"{100 * quality['clean_end'] // n}% end like one"
        )
    return "\n".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Compare search before and after sentence-aware chunking.")
    parser.add_argument("queries", nargs="+", help="questions to search for, in quotes")
    parser.add_argument("--top", type=int, default=3, help="documents to show per query (default 3)")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        texts = {
            f"[{d.id}] {d.filename}": d.extracted_text
            for d in db.scalars(select(Document).order_by(Document.id))
            if (d.extracted_text or "").strip()
        }
    if not texts:
        print("There are no documents with text to compare. Upload some first.")
        return 1
    embeddings.load_model()
    print(compare(texts, args.queries, top=args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
