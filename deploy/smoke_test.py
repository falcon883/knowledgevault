"""
End-to-end check of a running KnowledgeVault API (KV-41, accounts KV-42):
health, sign-up, upload, search, a second user who must not see the first
user's document, and a request with no token, then it deletes what it uploaded.

    python deploy/smoke_test.py https://3-91-12-45.sslip.io
    python deploy/smoke_test.py http://localhost:8000

Uses httpx, which is already in backend/requirements.txt (run it with the
backend virtual environment active). Exits with 0 if every step passed.

Each run signs up two throwaway accounts (smoke-...@example.test) with random
passwords. They own nothing once the run is over; the two small user rows stay.
"""

import secrets
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

    def new_user(client: httpx.Client, label: str) -> tuple[dict, int]:
        email = f"smoke-{label}-{stamp}-{secrets.token_hex(3)}@example.test"
        r = client.post("/auth/signup", json={"email": email, "password": secrets.token_urlsafe(16)})
        token = r.json().get("access_token") if r.status_code == 201 else None
        return ({"Authorization": f"Bearer {token}"} if token else {}), r.status_code

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

        alice, status = new_user(client, "a")
        step("POST /auth/signup", bool(alice), f"HTTP {status}")
        if not alice:
            return 1

        step(
            "GET /documents without a token is refused",
            client.get("/documents").status_code == 401,
        )

        upload = client.post("/upload", files={"file": (filename, text.encode(), "text/plain")}, headers=alice)
        document_id = upload.json().get("id") if upload.status_code == 200 else None
        step("POST /upload", upload.status_code == 200 and document_id is not None, f"HTTP {upload.status_code}")
        if document_id is None:
            print(upload.text[:300])
            return 1

        try:
            search = client.post("/search", json={"query": "how old is the universe"}, headers=alice)
            results = search.json().get("results", []) if search.status_code == 200 else []
            found = any(r.get("document_id") == document_id for r in results)
            step("POST /search finds the upload", found, f"HTTP {search.status_code}, {len(results)} result(s)")

            bob, status = new_user(client, "b")
            step("a second user signs up", bool(bob), f"HTTP {status}")
            if bob:
                seen = client.get(f"/documents/{document_id}", headers=bob).status_code
                listed = client.get("/documents", headers=bob).json()
                step(
                    "the second user cannot see the first user's document",
                    seen == 404 and all(d["id"] != document_id for d in listed),
                    f"GET /documents/{{id}} gave HTTP {seen}",
                )
        finally:
            delete = client.delete(f"/documents/{document_id}", headers=alice)
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
