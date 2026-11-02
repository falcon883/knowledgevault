"""
Re-chunk and re-embed the documents already stored (KV-38).

    python rechunk_documents.py --dry-run    # show what would change, change nothing
    python rechunk_documents.py              # re-chunk every document
    python rechunk_documents.py --document 12 15

Documents uploaded before KV-38 were cut every 800 characters wherever that
landed. This cuts them again at sentence boundaries (see chunking.py) from the
text already saved, so the original files are not needed. For each document it
embeds the new chunks first and only then swaps them in, in one transaction, so
a failure leaves that document exactly as it was. Documents whose chunks would
not change are skipped, so it is safe to run again. Tags and summaries are left
alone (run backfill_enrichment.py --all if you want them redone).

It covers every user's documents; it is a maintenance script, not an API call.
The first real run loads the embedding model, which takes a few seconds.
"""

import argparse
import sys

from sqlalchemy import select

import embeddings
from chunking import boundary_quality, chunk_text
from database import SessionLocal
from models import Chunk, Document


def rechunk(db, document_ids=None, dry_run=False, embed=None) -> list[dict]:
    """
    Re-chunk documents (all of them, or just `document_ids`). Returns one dict
    per document: id, filename, status ("changed", "would change", "unchanged",
    "no text" or "failed"), the chunk counts before and after, the old and new
    chunk texts, and an error message when it failed.
    """
    embed = embed or embeddings.embed_texts
    query = select(Document.id).order_by(Document.id)
    if document_ids:
        query = query.where(Document.id.in_(document_ids))

    results = []
    for document_id in db.scalars(query).all():
        document = db.get(Document, document_id)
        old_texts = [c.text for c in sorted(document.chunks, key=lambda c: c.chunk_index)]
        new_texts = chunk_text(document.extracted_text or "")
        result = {
            "id": document.id,
            "filename": document.filename,
            "before": len(old_texts),
            "after": len(new_texts),
            "old_texts": old_texts,
            "new_texts": new_texts,
            "error": None,
        }

        if not new_texts:
            result["status"] = "no text"
        elif new_texts == old_texts:
            result["status"] = "unchanged"
        elif dry_run:
            result["status"] = "would change"
        else:
            try:
                vectors = embed(new_texts)  # before touching anything stored
                document.chunks = [
                    Chunk(chunk_index=index, text=text, embedding=vector)
                    for index, (text, vector) in enumerate(zip(new_texts, vectors))
                ]
                db.commit()
                result["status"] = "changed"
            except Exception as exc:  # leave this document as it was and carry on with the rest
                db.rollback()
                result["status"] = "failed"
                result["error"] = f"{type(exc).__name__}: {exc}"
        results.append(result)
    return results


def _percent(part: int, whole: int) -> str:
    return f"{100 * part // whole}%" if whole else "-"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Re-chunk and re-embed stored documents (KV-38).")
    parser.add_argument("--dry-run", action="store_true", help="show what would change, change nothing")
    parser.add_argument("--document", type=int, nargs="+", metavar="ID", help="only these document ids")
    args = parser.parse_args(argv)

    if not args.dry_run:
        print("Loading the embedding model...")
        embeddings.load_model()

    with SessionLocal() as db:
        results = rechunk(db, args.document, args.dry_run)

    for r in results:
        line = f"[{r['id']}] {r['filename']}: {r['status']}"
        if r["status"] in ("changed", "would change"):
            line += f" ({r['before']} -> {r['after']} chunks)"
        if r["error"]:
            line += f" - {r['error']}"
        print(line)

    touched = [r for r in results if r["status"] in ("changed", "would change")]
    old = boundary_quality([t for r in touched for t in r["old_texts"]])
    new = boundary_quality([t for r in touched for t in r["new_texts"]])
    verb = "would change" if args.dry_run else "changed"
    print(f"\n{len(results)} document(s): {len(touched)} {verb}, {sum(r['status'] == 'unchanged' for r in results)} unchanged, "
          f"{sum(r['status'] == 'failed' for r in results)} failed.")
    if touched:
        print(
            f"Chunks that start like a sentence: {_percent(old['clean_start'], old['chunks'])} -> "
            f"{_percent(new['clean_start'], new['chunks'])}; end like one: "
            f"{_percent(old['clean_end'], old['chunks'])} -> {_percent(new['clean_end'], new['chunks'])}."
        )
    return 1 if any(r["status"] == "failed" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
