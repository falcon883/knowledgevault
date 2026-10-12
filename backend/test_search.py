"""
Manual check for KV-16: upload a few documents, search them by meaning,
and confirm the right one comes back first.

    python test_search.py

Requires Postgres with pgvector running (see README.md). Uses the real
embedding model, so the first run downloads it from huggingface.co.
Cleans up the documents it creates.
"""

from fastapi.testclient import TestClient

from database import Base, SessionLocal, engine
from main import app
from models import Document

Base.metadata.create_all(bind=engine)
client = TestClient(app)

DOCS = {
    "check_cooking.txt": (
        "A simple tomato pasta recipe. Boil the spaghetti, simmer garlic and "
        "tomatoes in olive oil, then toss everything together with fresh basil. "
        "Season with salt and finish with grated parmesan cheese."
    ),
    "check_space.txt": (
        "The telescope observed a distant galaxy and measured how fast it is "
        "moving away from Earth. Astronomers use the redshift of starlight to "
        "estimate the age and expansion of the universe."
    ),
    "check_finance.txt": (
        "Quarterly budget review: monthly expenses were lower than forecast, "
        "so the team moved the surplus into savings and updated the revenue "
        "projections for the next fiscal year."
    ),
}

created = []
try:
    for name, text in DOCS.items():
        r = client.post("/upload", files={"file": (name, text.encode(), "text/plain")})
        assert r.status_code == 200, r.text
        created.append(r.json()["id"])
    print(f"Uploaded {len(created)} test documents")

    cases = [
        ("how do I make dinner with pasta", "check_cooking.txt"),
        ("how old is the universe", "check_space.txt"),
        ("did we stay under budget this quarter", "check_finance.txt"),
    ]
    for query, expected in cases:
        r = client.post("/search", json={"query": query, "limit": 3, "min_score": 0})
        assert r.status_code == 200, r.text
        body = r.json()
        ours = [x for x in body["results"] if x["document_id"] in created]
        top = ours[0]
        print(f"{query!r} -> {top['filename']} (score {top['score']})")
        assert top["filename"] == expected, f"expected {expected}, got {top['filename']}"
        assert ours == sorted(ours, key=lambda x: -x["score"]), "results not ranked"
        ids = [x["document_id"] for x in body["results"]]
        assert len(ids) == len(set(ids)), "same document returned twice"

    # Low-scoring noise is hidden by default and shown when min_score is 0.
    junk = "quantum chromodynamics and medieval falconry"
    everything = client.post("/search", json={"query": junk, "min_score": 0}).json()
    filtered = client.post("/search", json={"query": junk}).json()
    assert filtered["count"] <= everything["count"]
    assert all(x["score"] >= 0.25 for x in filtered["results"]), "default cutoff not applied"
    print(f"Junk query: {everything['count']} results with min_score 0, {filtered['count']} by default")

    # Validation
    assert client.post("/search", json={"query": "   "}).status_code == 400
    assert client.post("/search", json={"query": "x", "limit": 0}).status_code == 422
    assert client.post("/search", json={}).status_code == 422
    print("Validation checks passed")

    print("KV-16 search check passed.")
finally:
    db = SessionLocal()
    for doc_id in created:
        doc = db.get(Document, doc_id)
        if doc:
            db.delete(doc)
    db.commit()
    db.close()
