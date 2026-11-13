"""
KnowledgeVault backend - KV-48: show the passage that matched.

A search result used to show the first 300 characters of its best-matching
chunk. A chunk is up to 800 characters, so the sentence that actually matched
the query was often further in, and a person had to read the titles to tell
the results apart. This module picks the part of the chunk to show instead:
the sentence that shares the most words with the query, followed by as much of
what comes after it as fits.

It only looks at words (no model), so it is fast and predictable. If no word
of the query appears in the chunk (the match was by meaning alone), it falls
back to the start of the chunk, as before.
"""

import re

from chunking import _sentence_spans

_WORD = re.compile(r"[a-z0-9]+")

# Words that say nothing about the topic. Kept short on purpose.
STOPWORDS = frozenset(
    """
    a an the and or but if so as of to in on at by for with from into onto over under about
    is are was were be been being am do does did done doing have has had having
    i me my we our you your he she it its they them their this that these those
    what which who whom whose when where why how can could should would will may might must
    not no yes than then there here very just also more most some any each other such own
    during make makes made get gets getting got use used using like way ways many much
    """.split()
)

# Endings removed so "vaccines" matches "vaccine" and "running" matches "run".
_SUFFIXES = ("ing", "ed", "es", "s", "ly")
MIN_STEM = 3


def stem(word: str) -> str:
    """A rough stem: drop one common ending if enough of the word is left."""
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= MIN_STEM:
            word = word[: -len(suffix)]
            break
    # "running" -> "runn" -> "run"; "bubbles" -> "bubbl" and "bubble" -> "bubble" -> "bubbl"
    if len(word) > MIN_STEM and word[-1] == word[-2] and word[-1] not in "aeiou":
        word = word[:-1]
    if len(word) > MIN_STEM and word.endswith("e"):
        word = word[:-1]
    return word


def query_stems(query: str) -> set[str]:
    """The topic words of a query, as stems. Numbers count ("26" in "26 miles")."""
    words = _WORD.findall(query.lower())
    return {stem(w) for w in words if w not in STOPWORDS and (len(w) >= 3 or w.isdigit())}


def _cut(text: str, limit: int) -> str:
    """Shorten to `limit` characters at a word boundary, with a trailing ellipsis."""
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    return text[: cut if cut > 0 else limit].rstrip(" ,;:") + "…"


def best_passage(chunk_text: str, query: str, limit: int = 300) -> tuple[str, list[str]]:
    """
    Choose what to show for a result.

    Returns (passage, matched_words). The passage starts at the sentence of the
    chunk with the most query words and continues with the sentences after it
    while they fit in `limit` characters. matched_words are the words of the
    passage that match the query, lowercase, in the order they appear, each
    once, so a screen can highlight them.
    """
    text = " ".join(chunk_text.split())  # one line, single spaces
    stems = query_stems(query)
    if not text or not stems:
        return _cut(text, limit), []

    sentences = list(_sentence_spans(text, 0, len(text)))
    best_index, best_hits = 0, 0
    for index, (start, end) in enumerate(sentences):
        hits = len({stem(w) for w in _WORD.findall(text[start:end].lower())} & stems)
        if hits > best_hits:  # strictly greater: on a tie the earlier sentence wins
            best_index, best_hits = index, hits

    if best_hits == 0:
        return _cut(text, limit), []

    start = sentences[best_index][0]
    end = sentences[best_index][1]
    for next_start, next_end in sentences[best_index + 1 :]:
        if next_end - start > limit:
            break
        end = next_end
    passage = _cut(text[start:end], limit)

    matched: list[str] = []
    for word in _WORD.findall(passage.lower()):
        if stem(word) in stems and word not in matched:
            matched.append(word)
    return passage, matched
