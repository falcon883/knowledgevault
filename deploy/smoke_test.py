"""
End-to-end check of a running KnowledgeVault API (KV-41): health, upload,
search, then delete what it uploaded, so it is safe to run against live data.

    python deploy/smoke_test.py https://3-91-12-45.sslip.io
    python deploy/smoke_test.py http://localhost:8000

Uses httpx, which is already in backend/requirements.txt (run it with the
backend virtual environment active). Exits with 0 if every step passed.
"""

import sys
import time

import httpx


def main(base_url: str) -> int:
    base = base_url.rstrip("/")
    stamp = int(time.time())
    filename = f"smoke-test-{stamp}.txt"
    # The timestamp makes the content unique, so duplicate detection never
    # rejects it, even if an earlier run was interrupted.
    text = (
        f"Smoke test {stamp}. Astronomers estimate that the universe is about "
        "13.8 billion years old, measured from the cosmic microwave background "
        "left over from the Big Bang."
    )

    failures = 0

    def step(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"[{'ok' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
        if not ok:
            failures += 1

    with httpx.Client(base_url=base, timeout=60) as client:
        health = client.get("/health")
        body = health.json() if health.headers.get("content-type", "").startswith("application/json") else {}
        step(
            "GET /health",
            health.status_code == 200 and body.get("database") == "ok",
            f"HTTP {health.status_code}, database={body.get('database')}, model_loaded={body.get('model_loaded')}",
        )
        if failures:
            return 1

        upload = client.post("/upload", files={"file": (filename, text.encode(), "text/plain")})
        document_id = upload.json().get("id") if upload.status_code == 200 else None
        step("POST /upload", upload.status_code == 200 and document_id is not None, f"HTTP {upload.status_code}")
        if document_id is None:
            print(upload.text[:300])
            return 1

        try:
            search = client.post("/search", json={"query": "how old is the universe"})
            results = search.json().get("results", []) if search.status_code == 200 else []
            found = any(r.get("document_id") == document_id for r in results)
            step("POST /search finds the upload", found, f"HTTP {search.status_code}, {len(results)} result(s)")
        finally:
            delete = client.delete(f"/documents/{document_id}")
            step("DELETE /documents/{id} (cleanup)", delete.status_code == 200, f"HTTP {delete.status_code}")

    print("\nAll checks passed." if not failures else f"\n{failures} check(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    try:
        sys.exit(main(sys.argv[1]))
    except httpx.TransportError as error:
        # Server not reachable, certificate not ready yet, timeout, and so on.
        print(f"[FAIL] could not reach {sys.argv[1]} - {error}")
        sys.exit(1)
