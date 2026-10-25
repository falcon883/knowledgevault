"""KV-16: semantic search returns the right document first."""

import pytest

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


@pytest.fixture
def library(upload):
    ids = []
    for name, text in DOCS.items():
        r = upload(name, text.encode())
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])
    return ids


@pytest.mark.parametrize(
    "query, expected",
    [
        ("how do I make dinner with pasta", "check_cooking.txt"),
        ("how old is the universe", "check_space.txt"),
        ("did we stay under budget this quarter", "check_finance.txt"),
    ],
)
def test_best_match_comes_first(client, library, query, expected):
    r = client.post("/search", json={"query": query, "limit": 3, "min_score": 0})
    assert r.status_code == 200, r.text
    results = r.json()["results"]

    ours = [x for x in results if x["document_id"] in library]
    assert ours[0]["filename"] == expected
    assert ours == sorted(ours, key=lambda x: -x["score"]), "results not ranked"

    ids = [x["document_id"] for x in results]
    assert len(ids) == len(set(ids)), "same document returned twice"


def test_low_scoring_noise_is_hidden_by_default(client, library):
    junk = "quantum chromodynamics and medieval falconry"
    everything = client.post("/search", json={"query": junk, "min_score": 0}).json()
    filtered = client.post("/search", json={"query": junk}).json()
    assert filtered["count"] <= everything["count"]
    assert all(x["score"] >= 0.25 for x in filtered["results"]), "default cutoff not applied"


def test_search_validation(client):
    assert client.post("/search", json={"query": "   "}).status_code == 400
    assert client.post("/search", json={"query": "x", "limit": 0}).status_code == 422
    assert client.post("/search", json={}).status_code == 422
