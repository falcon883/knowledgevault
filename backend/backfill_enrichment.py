"""
Fill in tags and summaries for documents uploaded before KV-21 existed.

    python backfill_enrichment.py          # only documents with no summary yet
    python backfill_enrichment.py --all    # redo every document

Reuses the chunk embeddings already stored in Postgres, so it only has to
embed the candidate phrases and sentences, not re-read any files.
"""

import sys

from database import SessionLocal
from enrichment import enrich
from models import Document

redo_all = "--all" in sys.argv
db = SessionLocal()

query = db.query(Document).order_by(Document.id)
if not redo_all:
    query = query.filter(Document.summary.is_(None))

updated = 0
for doc in query.all():
    vectors = [c.embedding for c in sorted(doc.chunks, key=lambda c: c.chunk_index) if c.embedding is not None]
    tags, summary = enrich(doc.extracted_text or "", vectors)
    doc.tags, doc.summary = tags, summary
    db.commit()
    updated += 1
    print(f"[{doc.id}] {doc.filename}\n    tags: {tags}\n    summary: {(summary or '')[:120]}")

db.close()
print(f"Done. Updated {updated} document(s).")
