"""KV-21: automatic tags and summaries."""

import embeddings
from enrichment import document_vector, extract_tags, summarize

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
TOPIC_WORDS = {
    "galaxy", "galaxies", "telescope", "universe", "redshift", "astronomers",
    "starlight", "expansion", "expanding",
}
TABLE = (
    "Time | Team | Project\n6:30 PM | Team 1 | Alpha\n"
    "6:45 PM | Team 2 | Beta\n7:00 PM | Team 3 | Gamma"
)


def test_tags_and_summary_functions():
    vec = document_vector(embeddings.embed_texts([TEXT]))
    tags = extract_tags(TEXT, vec)
    summary = summarize(TEXT, vec)

    assert 1 <= len(tags) <= 5
    assert all(t == t.lower() for t in tags), "tags should be lowercase"
    assert any(w in TOPIC_WORDS for t in tags for w in t.split()), "no tag is about the topic"
    assert summary and len(summary) < len(TEXT)
    for sentence in summary.rstrip(".").split(". "):
        assert sentence.strip(". ") in TEXT, "summary should only reuse sentences from the text"


def test_upload_returns_tags_and_summary_everywhere(client, upload):
    r = upload("check_enrich.txt", TEXT.encode())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tags"] and body["summary"]

    listed = next(d for d in client.get("/documents").json() if d["id"] == body["id"])
    assert listed["tags"] == body["tags"] and listed["summary"] == body["summary"]

    found = client.post("/search", json={"query": "how fast is the universe expanding"}).json()
    hit = next(x for x in found["results"] if x["document_id"] == body["id"])
    assert hit["tags"] == body["tags"]


def test_table_style_text_still_gets_a_summary(upload):
    r = upload("check_table.txt", TABLE.encode())
    assert r.status_code == 200, r.text
    assert r.json()["summary"]
