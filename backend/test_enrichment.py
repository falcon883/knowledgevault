"""
Manual check for KV-21: tags and summaries on upload.

    python test_enrichment.py

Requires Postgres with pgvector running. Uses the real embedding model.
Cleans up the document it creates.
"""

from fastapi.testclient import TestClient

from database import Base, SessionLocal, engine
from enrichment import extract_tags, summarize, document_vector
import embeddings
from main import app
from models import Document

Base.metadata.create_all(bind=engine)

TEXT = (
    "The new telescope observed a distant galaxy and measured how fast it is "
    "moving away from Earth. Astronomers use the redshift of starlight to "
    "estimate how quickly the universe is expanding. Careful measurements of "
    "the galaxy showed that its light had been stretched by the expansion of "
    "space. The telescope team also compared the galaxy with others nearby. "
    "Over many nights, the astronomers recorded the redshift again and again. "
    "Their results suggest the universe is expanding slightly faster than "
    "earlier estimates predicted. The team plans to publish the galaxy data "
    "so other astronomers can check the redshift measurements themselves."
)
TOPIC_WORDS = {"galaxy", "galaxies", "telescope", "universe", "redshift", "astronomers", "starlight", "expansion", "expanding"}

# 1. The functions on their own.
vec = document_vector(embeddings.embed_texts([TEXT]))
tags = extract_tags(TEXT, vec)
summary = summarize(TEXT, vec)
print("tags:", tags)
print("summary:", summary)
assert 1 <= len(tags) <= 5, "expected 1 to 5 tags"
assert all(t == t.lower() for t in tags), "tags should be lowercase"
assert any(w in TOPIC_WORDS for t in tags for w in t.split()), "no tag is about the topic"
assert summary and len(summary) < len(TEXT), "summary should be shorter than the text"
for sentence in summary.rstrip(".").split(". "):
    assert sentence.strip(". ") in TEXT, "summary should only reuse sentences from the text"

# 2. Through the API.
client = TestClient(app)
r = client.post("/upload", files={"file": ("check_enrich.txt", TEXT.encode(), "text/plain")})
assert r.status_code == 200, r.text
doc_id = r.json()["id"]
try:
    body = r.json()
    assert body["tags"] and body["summary"], "upload should return tags and summary"
    listed = next(d for d in client.get("/documents").json() if d["id"] == doc_id)
    assert listed["tags"] == body["tags"] and listed["summary"] == body["summary"]
    found = client.post("/search", json={"query": "how fast is the universe expanding"}).json()
    hit = next(x for x in found["results"] if x["document_id"] == doc_id)
    assert hit["tags"] == body["tags"], "search results should carry the tags"
    print("API checks passed: upload, /documents and /search all show tags and summary")

    # 3. A document with no real sentences (like a schedule) still gets a summary.
    table = "Time | Team | Project\n6:30 PM | Team 1 | Alpha\n6:45 PM | Team 2 | Beta\n7:00 PM | Team 3 | Gamma"
    r2 = client.post("/upload", files={"file": ("check_table.txt", table.encode(), "text/plain")})
    assert r2.status_code == 200 and r2.json()["summary"], r2.text
    print("Fallback summary for table-style text:", r2.json()["summary"][:60])
    other_id = r2.json()["id"]
finally:
    db = SessionLocal()
    for i in (doc_id, locals().get("other_id")):
        d = db.get(Document, i) if i else None
        if d:
            db.delete(d)
    db.commit()
    db.close()

print("KV-21 tagging and summarization check passed.")
