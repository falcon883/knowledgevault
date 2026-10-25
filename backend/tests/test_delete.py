"""DELETE /documents/{id} removes the document everywhere."""

from models import Chunk

TEXT = "Zebras are striped African animals that live in herds on the open grassland. " * 5


def test_delete_removes_document_chunks_and_search_hits(client, upload, db):
    r = upload("check_delete.txt", TEXT.encode())
    assert r.status_code == 200, r.text
    doc_id = r.json()["id"]
    assert db.query(Chunk).filter(Chunk.document_id == doc_id).count() > 0

    r = client.delete(f"/documents/{doc_id}")
    assert r.status_code == 200 and r.json()["status"] == "deleted"

    assert doc_id not in [d["id"] for d in client.get("/documents").json()]
    found = client.post("/search", json={"query": "zebras in the grassland", "limit": 20}).json()
    assert doc_id not in [x["document_id"] for x in found["results"]]
    db.expire_all()
    assert db.query(Chunk).filter(Chunk.document_id == doc_id).count() == 0


def test_deleting_twice_or_an_unknown_id_is_404(client, upload):
    doc_id = upload("check_delete2.txt", TEXT.encode()).json()["id"]
    assert client.delete(f"/documents/{doc_id}").status_code == 200
    assert client.delete(f"/documents/{doc_id}").status_code == 404
    assert client.delete("/documents/999999999").status_code == 404
