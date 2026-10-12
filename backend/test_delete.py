"""
Manual check for the delete endpoint.

    python test_delete.py

Uploads a document, deletes it, and confirms it is gone from /documents and
/search and that its chunks were removed. Uses the real embedding model.
"""

from fastapi.testclient import TestClient

from database import Base, SessionLocal, engine
from main import app
from models import Chunk

Base.metadata.create_all(bind=engine)
client = TestClient(app)

text = "Zebras are striped African animals that live in herds on the open grassland. " * 5
r = client.post("/upload", files={"file": ("check_delete.txt", text.encode(), "text/plain")})
assert r.status_code == 200, r.text
doc_id = r.json()["id"]

db = SessionLocal()
assert db.query(Chunk).filter(Chunk.document_id == doc_id).count() > 0
print(f"Uploaded document {doc_id} with chunks")

r = client.delete(f"/documents/{doc_id}")
assert r.status_code == 200 and r.json()["status"] == "deleted", r.text
print("Delete returned:", r.json())

assert doc_id not in [d["id"] for d in client.get("/documents").json()], "still in /documents"
found = client.post("/search", json={"query": "zebras in the grassland", "limit": 20}).json()
assert doc_id not in [x["document_id"] for x in found["results"]], "still in /search"
db.expire_all()
assert db.query(Chunk).filter(Chunk.document_id == doc_id).count() == 0, "chunks left behind"
db.close()

assert client.delete(f"/documents/{doc_id}").status_code == 404, "second delete should be 404"
assert client.delete("/documents/999999").status_code == 404
print("Delete check passed.")
