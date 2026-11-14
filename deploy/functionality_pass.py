"""
Full functionality pass over a running KnowledgeVault API (KV-50).

Goes through every backend feature as a brand new user, records the result of
each check, and writes them to docs/qa/functionality-pass.md. It is the live
version of the backend test suite: same questions, asked of the deployed server
over HTTPS, with the real embedding model and the real database.

    python deploy/functionality_pass.py https://3-13-43-176.sslip.io
        ... then restart the containers on the server:
            docker compose -f docker-compose.prod.yml restart
    python deploy/functionality_pass.py https://3-13-43-176.sslip.io --after-restart

Run it from the repository root with the backend's virtual environment active
(it needs httpx, which is in backend/requirements.txt).

The first run signs up a throwaway account, runs every check, and keeps that
account's three documents. The second run, after the restart, checks that the
account, the documents and search all survived, deletes what it uploaded, and
writes the final results. The state between the two runs is kept in
.qa-state.json (not committed; it holds the throwaway account's password).

Optional: set KV_SECRET_KEY to the server's SECRET_KEY (in the environment, not
on the command line) to also check an expired token and a token for a deleted
user. Without it those two checks are marked SKIPPED. Needs PyJWT, which is in
backend/requirements.txt.

Results: PASS, FAIL (the program exits with 1 if any), WARN (worth a look, not
necessarily a bug) and SKIPPED (could not be checked from here, with the reason).
The accounts it creates (qa-...@example.test) stay in the users table, since
there is no way to delete an account yet; they own nothing once the run is over.
"""

import argparse
import json
import os
import secrets
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "pilot" / "sample_docs" / "targets"
BLANK_SCAN = ROOT / "e2e" / "fixtures" / "blank-scan.pdf"
STATE_FILE = ROOT / ".qa-state.json"
DEFAULT_RESULTS = ROOT / "docs" / "qa" / "functionality-pass.md"

MARATHON_PDF = DOCS / "T4_first_marathon_training.pdf"
VACCINES_PDF = DOCS / "T2_how_vaccines_work.pdf"

MARATHON_QUERY = "how should I prepare to run 26 miles"
VACCINES_QUERY = "how does getting a shot protect me from disease"
BREAD_QUERY = "why does bread dough puff up"
GIBBERISH_QUERY = "qzxv wkpj vvbn mmzq xxqz"

NOT_RUN = [
    ("The database being down", "Needs the database stopped. Covered by `tests/test_settings.py` and `tests/test_edge_cases.py` (503 `service_unavailable`, and `/health` returning 503)."),
    ("A password-protected PDF, a corrupt PDF, an unreadable text file", "Needs fixture files that are not in the repository. Covered by `tests/test_upload_validation.py`."),
    ("Login rate limiting (429)", "Would lock the address running this script out for 10 minutes. Checked live on 2026-11-14 for KV-54 (see the ticket)."),
    ("Password reset by email", "Needs a real inbox. Checked live on 2026-11-14 for KV-53 (see the ticket)."),
]


@dataclass
class Result:
    area: str
    name: str
    status: str  # PASS, FAIL, WARN, SKIPPED
    detail: str = ""


class Report:
    def __init__(self, results: list[Result] | None = None):
        self.results: list[Result] = results or []
        self.area = ""

    def section(self, title: str) -> None:
        self.area = title
        print(f"\n{title}")

    def add(self, name: str, ok: bool, detail: str = "", status: str | None = None) -> bool:
        status = status or ("PASS" if ok else "FAIL")
        self.results.append(Result(self.area, name, status, detail))
        shown = {"PASS": "ok  ", "FAIL": "FAIL", "WARN": "warn", "SKIPPED": "skip"}[status]
        print(f"  [{shown}] {name}" + (f" - {detail}" if detail and status != "PASS" else ""))
        return ok

    def count(self, status: str) -> int:
        return sum(1 for r in self.results if r.status == status)


def short(response: httpx.Response) -> str:
    return f"HTTP {response.status_code}: {response.text[:160]}"


def code_of(response: httpx.Response) -> str | None:
    try:
        return response.json().get("code")
    except (ValueError, AttributeError):
        return None


def tags_of(doc: dict) -> list[str]:
    return [t.strip() for t in (doc.get("tags") or "").split(",") if t.strip()]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def sign_up(client: httpx.Client, label: str, stamp: int) -> tuple[dict | None, httpx.Response]:
    email = f"qa-{label}-{stamp}-{secrets.token_hex(3)}@example.test"
    password = secrets.token_urlsafe(16)
    response = client.post("/auth/signup", json={"email": email, "password": password})
    if response.status_code != 201:
        return None, response
    body = response.json()
    return {"email": email, "password": password, "token": body["access_token"], "id": body["user"]["id"]}, response


def bread_text(stamp: int) -> bytes:
    # The timestamp keeps the text unique, so duplicate detection never refuses it.
    return (
        f"Notes on bread, run {stamp}. A sourdough starter is a mix of flour and water that wild yeast and "
        "bacteria live in. The yeast eats the sugars in the flour and gives off carbon dioxide, and the gas "
        "gets trapped in the stretchy gluten, so the dough puffs up and rises. The bacteria make acids, which "
        "is why the bread tastes tangy. A warm kitchen speeds the rise and a cold one slows it down."
    ).encode()


# ---------------------------------------------------------------------------------------------------------
# First run
# ---------------------------------------------------------------------------------------------------------


def first_run(base: str, out: Path) -> int:
    stamp = int(time.time())
    report = Report()
    state: dict = {"base": base, "stamp": stamp}

    with httpx.Client(base_url=base, timeout=180) as client:
        # ------------------------------------------------------------------ health
        report.section("Health")
        health = client.get("/health")
        body = health.json() if health.headers.get("content-type", "").startswith("application/json") else {}
        report.add("GET /health reports the database", health.status_code == 200 and body.get("database") == "ok" and body.get("status") == "ok", short(health))
        report.add("the embedding model is loaded", body.get("model_loaded") is True, f"model_loaded={body.get('model_loaded')}")
        report.add("the upload limit is reported", isinstance(body.get("max_upload_mb"), (int, float)), f"max_upload_mb={body.get('max_upload_mb')}")
        if health.status_code != 200:
            print("\nThe server is not healthy; stopping.")
            return 1
        max_upload_mb = body.get("max_upload_mb") or 10

        # ------------------------------------------------------------------ sign up
        report.section("Accounts: sign up and log in")
        alice, response = sign_up(client, "a", stamp)
        if not report.add("sign up returns 201 and a token", alice is not None, short(response)):
            return finish(report, out, state, base, partial=True)
        report.add("the email is stored in lowercase", response.json()["user"]["email"] == alice["email"].lower())
        dup = client.post("/auth/signup", json={"email": alice["email"].upper(), "password": "another-password-1"})
        report.add("the same email again (any case) is refused", dup.status_code == 409 and code_of(dup) == "email_taken", short(dup))
        weak = client.post("/auth/signup", json={"email": f"qa-weak-{stamp}@example.test", "password": "short"})
        report.add("a too-short password is refused", weak.status_code == 422 and code_of(weak) == "weak_password", short(weak))
        bad_email = client.post("/auth/signup", json={"email": "not-an-email", "password": "long-enough-1"})
        report.add("a bad email address is refused", bad_email.status_code == 422 and code_of(bad_email) == "invalid_email", short(bad_email))

        good = client.post("/auth/login", json={"email": alice["email"], "password": alice["password"]})
        report.add("log in with the right password", good.status_code == 200 and "access_token" in good.json(), short(good))
        wrong = client.post("/auth/login", json={"email": alice["email"], "password": "not-the-password"})
        unknown = client.post("/auth/login", json={"email": f"nobody-{stamp}@example.test", "password": "not-the-password"})
        report.add("a wrong password gives 401 invalid_credentials", wrong.status_code == 401 and code_of(wrong) == "invalid_credentials", short(wrong))
        report.add("an unknown email gets the identical answer", unknown.status_code == 401 and unknown.json() == wrong.json(), short(unknown))

        # ------------------------------------------------------------------ tokens
        report.section("Accounts: /auth/me and tokens")
        me = client.get("/auth/me", headers=auth(alice["token"]))
        report.add("GET /auth/me with a valid token", me.status_code == 200 and me.json().get("email") == alice["email"].lower(), short(me))
        none = client.get("/auth/me")
        report.add("no token gives 401 not_authenticated", none.status_code == 401 and code_of(none) == "not_authenticated", short(none))
        garbage = client.get("/auth/me", headers=auth("abc.def.ghi"))
        report.add("a garbage token gives 401 invalid_token", garbage.status_code == 401 and code_of(garbage) == "invalid_token", short(garbage))
        tampered = client.get("/auth/me", headers=auth(alice["token"][:-3] + ("AAA" if not alice["token"].endswith("AAA") else "BBB")))
        report.add("a token with a changed signature gives 401 invalid_token", tampered.status_code == 401 and code_of(tampered) == "invalid_token", short(tampered))
        secret = os.getenv("KV_SECRET_KEY", "")
        forged = None
        if secret:
            try:
                import jwt

                now = datetime.now(timezone.utc)
                expired = jwt.encode({"sub": str(alice["id"]), "iat": now.timestamp() - 7200, "exp": now.timestamp() - 3600}, secret, algorithm="HS256")
                gone = jwt.encode({"sub": "2000000000", "iat": now.timestamp(), "exp": now.timestamp() + 3600}, secret, algorithm="HS256")
                forged = (expired, gone)
            except ImportError:
                pass
        if forged:
            r1 = client.get("/auth/me", headers=auth(forged[0]))
            report.add("an expired token gives 401 token_expired", r1.status_code == 401 and code_of(r1) == "token_expired", short(r1))
            r2 = client.get("/auth/me", headers=auth(forged[1]))
            report.add("a token for a user that does not exist gives 401 invalid_token", r2.status_code == 401 and code_of(r2) == "invalid_token", short(r2))
        else:
            report.add("an expired token gives 401 token_expired", True, "set KV_SECRET_KEY (and have PyJWT) to forge one; covered by tests/test_auth.py", status="SKIPPED")
            report.add("a token for a user that does not exist gives 401 invalid_token", True, "same as above", status="SKIPPED")
        for path in ("/documents", "/tags", "/documents/1"):
            r = client.get(path)
            report.add(f"GET {path} without a token is refused", r.status_code == 401, short(r))
        r = client.post("/search", json={"query": "anything"})
        report.add("POST /search without a token is refused", r.status_code == 401, short(r))
        r = client.post("/upload", files={"file": ("x.txt", b"hello there", "text/plain")})
        report.add("POST /upload without a token is refused", r.status_code == 401, short(r))

        head = auth(alice["token"])

        # ------------------------------------------------------------------ empty library
        report.section("A new account with no documents")
        r = client.get("/documents", headers=head)
        report.add("the document list is empty", r.status_code == 200 and r.json() == [], short(r))
        r = client.get("/tags", headers=head)
        report.add("the tag list is empty", r.status_code == 200 and r.json() == [], short(r))
        r = client.post("/search", json={"query": MARATHON_QUERY}, headers=head)
        report.add("a search finds nothing and is not an error", r.status_code == 200 and r.json().get("count") == 0, short(r))

        # ------------------------------------------------------------------ uploads
        report.section("Upload: each supported file type")
        uploaded: dict[str, dict] = {}

        def upload(label: str, name: str, data: bytes, content_type: str, **params) -> httpx.Response:
            return client.post("/upload", files={"file": (name, data, content_type)}, params=params, headers=head)

        for label, path in (("marathon", MARATHON_PDF), ("vaccines", VACCINES_PDF)):
            if not path.exists():
                report.add(f"upload a PDF ({path.name})", False, f"{path} not found: run this from a full checkout of the repository")
                continue
            r = upload(label, path.name, path.read_bytes(), "application/pdf")
            ok = r.status_code == 200 and r.json().get("chunk_count", 0) >= 1
            report.add(f"upload a PDF ({path.name})", ok, short(r))
            if ok:
                uploaded[label] = r.json()
        bread_name = f"qa-bread-{stamp}.txt"
        r = upload("bread", bread_name, bread_text(stamp), "text/plain")
        report.add("upload a plain text file (.txt)", r.status_code == 200 and r.json().get("chunk_count", 0) >= 1, short(r))
        if r.status_code == 200:
            uploaded["bread"] = r.json()
        if len(uploaded) < 3:
            report.add("all three documents were stored", False, f"only {sorted(uploaded)} were; the checks that need them are skipped")
            return finish(report, out, state, base, partial=True)
        report.add("each upload reports its type, size and chunks", all(
            d["content_type"] and d["size_bytes"] > 0 and d["chunk_count"] > 0 for d in uploaded.values()
        ), json.dumps({k: (v["content_type"], v["size_bytes"], v["chunk_count"]) for k, v in uploaded.items()}))
        report.add("the text file is stored as text/plain", uploaded["bread"]["content_type"] == "text/plain", uploaded["bread"]["content_type"])
        report.add("the PDFs are stored as application/pdf", uploaded["marathon"]["content_type"] == "application/pdf")

        report.section("Upload: files that must be refused")
        r = upload("docx", "report.docx", b"PK\x03\x04 not really", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        report.add("a Word file gives 415 unsupported_type", r.status_code == 415 and code_of(r) == "unsupported_type", short(r))
        r = upload("empty", "empty.txt", b"", "text/plain")
        report.add("an empty file gives 400 empty_file", r.status_code == 400 and code_of(r) == "empty_file", short(r))
        r = client.post("/upload", headers=head)
        report.add("no file gives 400 no_file", r.status_code == 400 and code_of(r) == "no_file", short(r))
        if BLANK_SCAN.exists():
            r = upload("blank", "blank-scan.pdf", BLANK_SCAN.read_bytes(), "application/pdf")
            report.add("a PDF with no text (a scan) gives 422 no_text", r.status_code == 422 and code_of(r) == "no_text", short(r))
        r = upload("long", f"qa-too-long-{stamp}.txt", (b"word " * 130_000), "text/plain")
        report.add("a document with too much text gives 422 text_too_long", r.status_code == 422 and code_of(r) == "text_too_long", short(r))
        big = b"a" * int(max_upload_mb * 1024 * 1024 + 1)
        r = upload("big", "too-big.txt", big, "text/plain")
        report.add(f"a file over {max_upload_mb:g} MB gives 413 file_too_large", r.status_code == 413 and code_of(r) == "file_too_large", short(r))
        r = upload("dup", MARATHON_PDF.name, MARATHON_PDF.read_bytes(), "application/pdf")
        existing = (r.json() or {}).get("existing", {}) if r.headers.get("content-type", "").startswith("application/json") else {}
        report.add("the same PDF again gives 409 duplicate_document", r.status_code == 409 and code_of(r) == "duplicate_document" and existing.get("id") == uploaded["marathon"]["id"], short(r))
        r = upload("dup", MARATHON_PDF.name, MARATHON_PDF.read_bytes(), "application/pdf", allow_duplicate="true")
        ok = r.status_code == 200
        report.add("allow_duplicate=true stores it anyway", ok, short(r))
        if ok:
            client.delete(f"/documents/{r.json()['id']}", headers=head)

        # ------------------------------------------------------------------ browse
        report.section("Browse: list, sort, filters, one document")
        r = client.get("/documents", headers=head)
        docs = r.json() if r.status_code == 200 else []
        ids = {d["id"] for d in docs}
        report.add("the list holds exactly the three documents", r.status_code == 200 and ids == {d["id"] for d in uploaded.values()}, f"{len(docs)} listed")
        fields = {"id", "filename", "content_type", "size_bytes", "uploaded_at", "tags", "summary", "chunk_count"}
        report.add("each entry has the documented fields", all(fields <= set(d) for d in docs), "")
        newest = [d["id"] for d in client.get("/documents", params={"sort": "newest"}, headers=head).json()]
        oldest = [d["id"] for d in client.get("/documents", params={"sort": "oldest"}, headers=head).json()]
        by_time = [d["id"] for d in sorted(docs, key=lambda d: d["uploaded_at"], reverse=True)]
        report.add("sort=newest puts the latest upload first", newest == by_time and newest[0] == uploaded["bread"]["id"], str(newest))
        report.add("sort=oldest is the reverse", oldest == list(reversed(newest)), str(oldest))
        by_name = [d["filename"] for d in client.get("/documents", params={"sort": "name"}, headers=head).json()]
        report.add("sort=name is A to Z, ignoring case", by_name == sorted(by_name, key=str.lower), str(by_name))
        r = client.get("/documents", params={"sort": "sideways"}, headers=head)
        report.add("an unknown sort is refused (422)", r.status_code == 422, short(r))

        newest_doc = max(docs, key=lambda d: d["uploaded_at"])
        r = client.get("/documents", params={"since": "2099-01-01"}, headers=head)
        report.add("since a date in the future lists nothing", r.status_code == 200 and r.json() == [], short(r))
        r = client.get("/documents", params={"since": "2000-01-01"}, headers=head)
        report.add("since a date in the past lists everything", r.status_code == 200 and len(r.json()) == 3, short(r))
        r = client.get("/documents", params={"since": newest_doc["uploaded_at"]}, headers=head)
        report.add("since the newest upload's time lists just that document (the time is included)", r.status_code == 200 and [d["id"] for d in r.json()] == [newest_doc["id"]], short(r))
        r = client.get("/documents", params={"since": "last tuesday"}, headers=head)
        report.add("a date that cannot be read is refused (422)", r.status_code == 422, short(r))

        tagged = next((d for d in docs if tags_of(d)), None)
        if tagged is None:
            report.add("documents were given tags", False, "no document has any tags", status="WARN")
        else:
            tag = tags_of(tagged)[0]
            r = client.get("/documents", params={"tag": tag}, headers=head)
            listed = r.json() if r.status_code == 200 else []
            report.add(f"tag filter ({tag!r}) returns only documents with that tag", bool(listed) and all(tag.lower() in [t.lower() for t in tags_of(d)] for d in listed) and tagged["id"] in {d["id"] for d in listed}, short(r))
            r = client.get("/documents", params={"tag": tag.upper()}, headers=head)
            report.add("the tag filter ignores case", r.status_code == 200 and tagged["id"] in {d["id"] for d in r.json()}, short(r))
            r = client.get("/tags", headers=head)
            tag_list = r.json() if r.status_code == 200 else []
            report.add("GET /tags lists the tags with counts", any(t["tag"].lower() == tag.lower() and t["count"] >= 1 for t in tag_list), f"{len(tag_list)} tags")
            report.add("tags are ordered most common first", [t["count"] for t in tag_list] == sorted((t["count"] for t in tag_list), reverse=True))
            r = client.get("/tags", params={"limit": 1}, headers=head)
            report.add("GET /tags?limit=1 returns one tag", r.status_code == 200 and len(r.json()) == 1, short(r))
            state["tags"] = sorted(t["tag"] for t in tag_list)
        r = client.get("/documents", params={"tag": "no-such-tag-xyz"}, headers=head)
        report.add("an unknown tag lists nothing", r.status_code == 200 and r.json() == [], short(r))

        marathon = uploaded["marathon"]
        r = client.get(f"/documents/{marathon['id']}", headers=head)
        detail = r.json() if r.status_code == 200 else {}
        report.add("GET /documents/{id} returns the extracted text", r.status_code == 200 and "marathon" in detail.get("extracted_text", "").lower() and detail.get("truncated") is False, short(r))
        report.add("text_length is the full length", detail.get("text_length") == len(detail.get("extracted_text", "")) and detail.get("text_length", 0) > 100, str(detail.get("text_length")))
        r = client.get(f"/documents/{marathon['id']}", params={"max_chars": 50}, headers=head)
        cut = r.json() if r.status_code == 200 else {}
        report.add("max_chars=50 cuts the text and says so", len(cut.get("extracted_text", "x" * 99)) == 50 and cut.get("truncated") is True and cut.get("text_length") == detail.get("text_length"), short(r))
        r = client.get("/documents/2000000000", headers=head)
        report.add("a document that does not exist gives 404 not_found", r.status_code == 404 and code_of(r) == "not_found", short(r))
        state["documents"] = {
            label: {"id": d["id"], "filename": d["filename"], "chunk_count": d["chunk_count"]} for label, d in uploaded.items()
        }
        state["text_length"] = detail.get("text_length")

        # ------------------------------------------------------------------ search
        report.section("Search")

        def search(query: str, **extra) -> httpx.Response:
            return client.post("/search", json={"query": query, **extra}, headers=head)

        def ranks(response: httpx.Response, doc_id: int) -> int | None:
            found = [hit["document_id"] for hit in response.json().get("results", [])]
            return found.index(doc_id) + 1 if doc_id in found else None

        r = search(MARATHON_QUERY)
        top = r.json()["results"][0] if r.status_code == 200 and r.json().get("results") else {}
        report.add("a question about the marathon PDF ranks it first", ranks(r, marathon["id"]) == 1 if r.status_code == 200 else False, short(r) if r.status_code != 200 else str([(h['filename'], round(h['score'], 3)) for h in r.json()['results']]))
        r2 = search(VACCINES_QUERY)
        report.add("a question about the vaccines PDF ranks it first", r2.status_code == 200 and ranks(r2, uploaded["vaccines"]["id"]) == 1, short(r2) if r2.status_code != 200 else str([(h['filename'], round(h['score'], 3)) for h in r2.json()['results']]))
        r3 = search(BREAD_QUERY)
        report.add("a question about the text file ranks it first", r3.status_code == 200 and ranks(r3, uploaded["bread"]["id"]) == 1, short(r3) if r3.status_code != 200 else str([(h['filename'], round(h['score'], 3)) for h in r3.json()['results']]))
        hit_fields = {"document_id", "filename", "score", "snippet", "matched_terms", "chunk_index", "tags", "summary"}
        report.add("each result has the documented fields", bool(top) and hit_fields <= set(top), str(sorted(set(top))))
        scores = [h["score"] for h in r.json().get("results", [])] if r.status_code == 200 else []
        report.add("results are ordered best first, one per document", scores == sorted(scores, reverse=True) and len({h["document_id"] for h in r.json()["results"]}) == len(scores), str([round(s, 3) for s in scores]))
        report.add("the matching passage is shown, with the matched words", bool(top.get("snippet")) and bool(top.get("matched_terms")), f"matched_terms={top.get('matched_terms')}")
        state["marathon_query"] = MARATHON_QUERY

        r = search(MARATHON_QUERY, limit=1)
        report.add("limit=1 returns one result", r.status_code == 200 and r.json().get("count") == 1, short(r))
        r = search(MARATHON_QUERY, min_score=0)
        everything = r.json().get("count") if r.status_code == 200 else None
        report.add("min_score=0 shows every document", everything == 3, f"count={everything}")
        r = search(MARATHON_QUERY)
        report.add("the default minimum score (0.25) hides weak matches", r.status_code == 200 and all(h["score"] >= 0.25 for h in r.json()["results"]), short(r))
        r = search(MARATHON_QUERY, min_score=0.99)
        report.add("min_score=0.99 finds nothing", r.status_code == 200 and r.json().get("count") == 0, short(r))
        r = search(GIBBERISH_QUERY)
        if r.status_code == 200 and r.json().get("count") == 0:
            report.add("a nonsense search finds nothing (no results is not an error)", True)
        elif r.status_code == 200:
            report.add("a nonsense search finds nothing (no results is not an error)", False, "returned " + str([(h["filename"], round(h["score"], 3)) for h in r.json()["results"]]), status="WARN")
        else:
            report.add("a nonsense search finds nothing (no results is not an error)", False, short(r))
        r = search("   ")
        report.add("a blank search gives 400 empty_query", r.status_code == 400 and code_of(r) == "empty_query", short(r))
        r = search("a" * 501)
        report.add("a search over 500 characters gives 400 query_too_long", r.status_code == 400 and code_of(r) == "query_too_long", short(r))
        r = search(MARATHON_QUERY, limit=0)
        report.add("limit=0 is refused (422)", r.status_code == 422, short(r))
        for odd in ("a", "26.2", "?!?!", "😀", "SELECT * FROM documents; --", "<script>alert(1)</script>"):
            r = search(odd)
            report.add(f"an unusual search ({odd!r}) answers normally", r.status_code == 200 and isinstance(r.json().get("results"), list), short(r))

        # ------------------------------------------------------------------ isolation
        report.section("Each account sees only its own documents")
        bob, response = sign_up(client, "b", stamp)
        if not report.add("a second account signs up", bob is not None, short(response)):
            return finish(report, out, state, base, partial=True)
        bhead = auth(bob["token"])
        r = client.get("/documents", headers=bhead)
        report.add("the second account's list is empty", r.status_code == 200 and r.json() == [], short(r))
        r = client.get("/tags", headers=bhead)
        report.add("the second account has no tags", r.status_code == 200 and r.json() == [], short(r))
        r = client.get(f"/documents/{marathon['id']}", headers=bhead)
        report.add("opening the first account's document gives 404 not_found", r.status_code == 404 and code_of(r) == "not_found", short(r))
        r = client.delete(f"/documents/{marathon['id']}", headers=bhead)
        report.add("deleting it gives 404 too, and it is not deleted", r.status_code == 404 and client.get(f"/documents/{marathon['id']}", headers=head).status_code == 200, short(r))
        r = client.post("/search", json={"query": MARATHON_QUERY, "min_score": 0}, headers=bhead)
        report.add("searching finds none of the first account's documents", r.status_code == 200 and r.json().get("count") == 0, short(r))
        r = client.post("/upload", files={"file": (MARATHON_PDF.name, MARATHON_PDF.read_bytes(), "application/pdf")}, headers=bhead)
        report.add("the same PDF is not a duplicate for the second account", r.status_code == 200, short(r))
        if r.status_code == 200:
            second_id = r.json()["id"]
            r = client.post("/search", json={"query": MARATHON_QUERY}, headers=bhead)
            found = [h["document_id"] for h in r.json().get("results", [])] if r.status_code == 200 else []
            report.add("its search finds only its own copy", found == [second_id], str(found))
            client.delete(f"/documents/{second_id}", headers=bhead)
        r = client.get("/documents", headers=head)
        report.add("the first account still has its three documents", r.status_code == 200 and len(r.json()) == 3, short(r))

        # ------------------------------------------------------------------ delete
        report.section("Delete")
        r = upload("temp", f"qa-delete-{stamp}.txt", f"Temporary file {stamp}. Lighthouses guide ships away from rocky coasts using a rotating lamp.".encode(), "text/plain")
        temp = r.json() if r.status_code == 200 else {}
        report.add("upload a document to delete", r.status_code == 200, short(r))
        if temp:
            r = client.post("/search", json={"query": "how do lighthouses guide ships"}, headers=head)
            report.add("it can be found before deleting", r.status_code == 200 and ranks(r, temp["id"]) == 1, short(r))
            r = client.delete(f"/documents/{temp['id']}", headers=head)
            report.add("DELETE returns status deleted", r.status_code == 200 and r.json().get("status") == "deleted", short(r))
            r = client.get(f"/documents/{temp['id']}", headers=head)
            report.add("the deleted document is gone (404)", r.status_code == 404, short(r))
            r = client.post("/search", json={"query": "how do lighthouses guide ships", "min_score": 0}, headers=head)
            report.add("and no longer found by search", r.status_code == 200 and ranks(r, temp["id"]) is None, short(r))
            r = client.delete(f"/documents/{temp['id']}", headers=head)
            report.add("deleting it again gives 404", r.status_code == 404, short(r))
            r = client.get("/documents", headers=head)
            report.add("the other three are untouched", r.status_code == 200 and len(r.json()) == 3, short(r))

        state["account"] = {"email": alice["email"], "password": alice["password"]}

    return finish(report, out, state, base, partial=False)


def finish(report: Report, out: Path, state: dict, base: str, partial: bool) -> int:
    state["results"] = [asdict(r) for r in report.results]
    state["first_run_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if partial:
        write_results(report, out, base, restart="not run (the run stopped early)")
        print(f"\nStopped early. {report.count('FAIL')} check(s) failed.")
        return 1
    STATE_FILE.write_text(json.dumps(state, indent=2))
    write_results(report, out, base, restart="pending")
    fails = report.count("FAIL")
    print(f"\n{len(report.results)} checks: {report.count('PASS')} passed, {fails} failed, {report.count('WARN')} warnings, {report.count('SKIPPED')} skipped.")
    print("\nNext: restart the containers on the server, then run this again with --after-restart:")
    print("  docker compose -f docker-compose.prod.yml restart")
    return 1 if fails else 0


# ---------------------------------------------------------------------------------------------------------
# Second run, after the containers were restarted
# ---------------------------------------------------------------------------------------------------------


def second_run(base: str, out: Path) -> int:
    if not STATE_FILE.exists():
        print("No .qa-state.json here. Run the first part first (without --after-restart), from this folder.")
        return 2
    state = json.loads(STATE_FILE.read_text())
    report = Report([Result(**r) for r in state["results"]])
    report.section("After restarting the containers")

    with httpx.Client(base_url=base, timeout=180) as client:
        health = None
        for _ in range(30):  # the model takes a few seconds to load again
            try:
                health = client.get("/health")
                if health.status_code == 200 and health.json().get("model_loaded"):
                    break
            except httpx.TransportError:
                pass
            time.sleep(3)
        body = health.json() if health is not None and health.status_code == 200 else {}
        report.add("the server is back and healthy", bool(body) and body.get("database") == "ok", short(health) if health is not None else "no answer")
        report.add("the embedding model loaded again", body.get("model_loaded") is True, f"model_loaded={body.get('model_loaded')}")

        account = state["account"]
        r = client.post("/auth/login", json=account)
        report.add("the account still exists and its password works", r.status_code == 200, short(r))
        if r.status_code != 200:
            return finish_second(report, out, base)
        head = auth(r.json()["access_token"])

        documents = state["documents"]
        r = client.get("/documents", headers=head)
        listed = {d["id"]: d for d in r.json()} if r.status_code == 200 else {}
        report.add("all three documents are still there", set(listed) == {d["id"] for d in documents.values()}, f"{len(listed)} listed")
        report.add("each still has all its chunks", all(listed.get(d["id"], {}).get("chunk_count") == d["chunk_count"] for d in documents.values()))
        marathon = documents["marathon"]
        r = client.get(f"/documents/{marathon['id']}", headers=head)
        report.add("the extracted text is unchanged", r.status_code == 200 and r.json().get("text_length") == state.get("text_length"), short(r))
        r = client.post("/search", json={"query": state["marathon_query"]}, headers=head)
        found = [h["document_id"] for h in r.json().get("results", [])] if r.status_code == 200 else []
        report.add("search still finds the marathon PDF first", found[:1] == [marathon["id"]], str(found))
        r = client.get("/tags", headers=head)
        report.add("the tags are unchanged", r.status_code == 200 and sorted(t["tag"] for t in r.json()) == state.get("tags", []), short(r))

        # Clean up what the run uploaded.
        for document in documents.values():
            client.delete(f"/documents/{document['id']}", headers=head)
        r = client.get("/documents", headers=head)
        report.add("clean-up: the test account's documents are deleted", r.status_code == 200 and r.json() == [], short(r))

    STATE_FILE.unlink(missing_ok=True)
    return finish_second(report, out, base)


def finish_second(report: Report, out: Path, base: str) -> int:
    write_results(report, out, base, restart="done")
    fails = report.count("FAIL")
    print(f"\n{len(report.results)} checks: {report.count('PASS')} passed, {fails} failed, {report.count('WARN')} warnings, {report.count('SKIPPED')} skipped.")
    print(f"Results written to {out}")
    return 1 if fails else 0


# ---------------------------------------------------------------------------------------------------------
# The results file
# ---------------------------------------------------------------------------------------------------------


def write_results(report: Report, out: Path, base: str, restart: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Backend functionality pass (KV-50)",
        "",
        f"Server: {base}  ",
        f"Run: {now}, with `deploy/functionality_pass.py`  ",
        f"Checks: {len(report.results)}. Passed {report.count('PASS')}, failed {report.count('FAIL')}, "
        f"warnings {report.count('WARN')}, skipped {report.count('SKIPPED')}.  ",
        f"Restart check: {restart}",
        "",
        "Every check was made as a brand new account on the deployed server, over HTTPS, with the real "
        "embedding model. PASS means the answer was what the API documentation says. WARN is worth a look "
        "but is not necessarily a bug. SKIPPED means it cannot be checked from this script (reason given).",
        "",
    ]
    area = None
    for result in report.results:
        if result.area != area:
            area = result.area
            lines += ["", f"## {area}", "", "| Check | Result | Detail |", "|---|---|---|"]
        detail = result.detail.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {result.name.replace('|', chr(92) + '|')} | {result.status} | {detail if result.status != 'PASS' else ''} |")
    failures = [r for r in report.results if r.status == "FAIL"]
    lines += ["", "## Failures", ""]
    lines += [f"- {r.area}: {r.name} ({r.detail})" for r in failures] if failures else ["None."]
    lines += ["", "## Not covered by this script", "", "| What | Why |", "|---|---|"]
    lines += [f"| {what} | {why} |" for what, why in NOT_RUN]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="address of the API, e.g. https://3-13-43-176.sslip.io")
    parser.add_argument("--after-restart", action="store_true", help="the second part: run after restarting the containers")
    parser.add_argument("--out", type=Path, default=DEFAULT_RESULTS, help="where to write the results (default: docs/qa/functionality-pass.md)")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    try:
        return second_run(base, args.out) if args.after_restart else first_run(base, args.out)
    except httpx.TransportError as error:
        print(f"[FAIL] could not reach {base} - {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
