"""
KnowledgeVault backend - KV-21: automatic tagging and summarization.

Both run locally on the same sentence-transformers model that already
embeds the chunks (see embeddings.py), so there is no extra API key, cost,
or third-party dependency (Project Charter risk table, Section 3.5).

Tags: pull candidate keywords and two-word phrases out of the text, embed
them, and keep the ones closest in meaning to the document as a whole. A
small diversity penalty stops the list from being five near-duplicates
(KeyBERT-style selection).

Summary: extractive. Embed each sentence and keep the few that sit closest
to the document's overall meaning, in their original order. It reuses the
document's own sentences, so it can't invent anything.
"""

from __future__ import annotations

import re
from collections import Counter

import numpy as np

import embeddings

NUM_TAGS = 5
MAX_CANDIDATES = 40
SUMMARY_SENTENCES = 3
MAX_SENTENCES_CONSIDERED = 200
MAX_SUMMARY_CHARS = 600
FALLBACK_SUMMARY_CHARS = 300
DIVERSITY = 0.3  # 0 = pure relevance, higher = more variety between tags

STOPWORDS = set(
    """
    a about above after again against all also am an and any are as at be because
    been before being below between both but by can could did do does doing down
    during each few for from further had has have having he her here hers him his
    how i if in into is it its just may me might more most must my no nor not now
    of off on once only or other our out over own per same shall she should so some
    such than that the their theirs them then there these they this those through
    to too under until up upon us very via was we were what when where which while
    who whom why will with within without would you your yours yet
    """.split()
)

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z\-]{2,}")
SEGMENT_RE = re.compile(r"[.,;:!?()\[\]\n|/]+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def _unit(vectors: np.ndarray) -> np.ndarray:
    """Scale each vector (or one vector) to length 1 so dot product = cosine."""
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.where(norms == 0, 1.0, norms)


def document_vector(chunk_vectors) -> np.ndarray:
    """One vector for the whole document: the average of its chunk vectors."""
    return _unit(np.mean(np.asarray(chunk_vectors, dtype=float), axis=0))


def _candidate_phrases(text: str) -> list[str]:
    """Single words and adjacent word pairs, never crossing a stopword or punctuation."""
    counts: Counter = Counter()
    for segment in SEGMENT_RE.split(text):
        run: list[str] = []
        for token in TOKEN_RE.findall(segment) + [None]:  # None flushes the last run
            word = token.lower() if token else None
            if word and word not in STOPWORDS:
                run.append(word)
                continue
            for i, w in enumerate(run):
                counts[w] += 1
                if i + 1 < len(run):
                    counts[f"{w} {run[i + 1]}"] += 1
            run = []
    # most_common keeps first-seen order for ties, so this is deterministic.
    return [phrase for phrase, _ in counts.most_common(MAX_CANDIDATES)]


def extract_tags(text: str, doc_vector: np.ndarray, num_tags: int = NUM_TAGS) -> list[str]:
    candidates = _candidate_phrases(text)
    if not candidates:
        return []

    vectors = _unit(np.asarray(embeddings.embed_texts(candidates), dtype=float))
    relevance = vectors @ doc_vector

    selected: list[int] = []
    remaining = list(range(len(candidates)))
    while remaining and len(selected) < num_tags:
        best, best_score = None, -np.inf
        for i in remaining:
            words = set(candidates[i].split())
            # Skip a word that is already inside a chosen phrase, or a phrase
            # that contains a chosen word ("galaxy" vs "distant galaxy").
            if any(
                words <= set(candidates[j].split()) or set(candidates[j].split()) <= words
                for j in selected
            ):
                continue
            redundancy = max((vectors[i] @ vectors[j] for j in selected), default=0.0)
            score = (1 - DIVERSITY) * relevance[i] - DIVERSITY * redundancy
            if score > best_score:
                best, best_score = i, score
        if best is None:
            break
        selected.append(best)
        remaining.remove(best)

    return [candidates[i] for i in selected]


def _split_sentences(text: str) -> list[str]:
    flat = re.sub(r"\s+", " ", text).strip()
    sentences = [s.strip() for s in SENTENCE_RE.split(flat)]
    # Drop fragments (headings, table cells) and run-ons that aren't real sentences.
    good = [s for s in sentences if 40 <= len(s) <= 400]
    return good[:MAX_SENTENCES_CONSIDERED]


def summarize(text: str, doc_vector: np.ndarray, num_sentences: int = SUMMARY_SENTENCES) -> str | None:
    flat = re.sub(r"\s+", " ", text).strip()
    if not flat:
        return None

    sentences = _split_sentences(text)
    if not sentences:
        # Schedules, tables and slide dumps have no real sentences. Fall back
        # to the opening of the document rather than returning nothing.
        return flat[:FALLBACK_SUMMARY_CHARS].rstrip() + ("..." if len(flat) > FALLBACK_SUMMARY_CHARS else "")

    vectors = _unit(np.asarray(embeddings.embed_texts(sentences), dtype=float))
    scores = vectors @ doc_vector
    top = sorted(np.argsort(-scores)[:num_sentences])  # back into reading order
    summary = " ".join(sentences[i] for i in top)
    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[:MAX_SUMMARY_CHARS].rsplit(" ", 1)[0].rstrip(",;:") + "..."
    return summary


def enrich(text: str, chunk_vectors) -> tuple[str | None, str | None]:
    """
    Returns (tags, summary) for a document. `tags` is comma-separated to match
    Document.tags. Either can be None if the text has nothing usable.
    """
    if not text or not text.strip() or len(chunk_vectors) == 0:
        return None, None
    doc_vector = document_vector(chunk_vectors)
    tags = extract_tags(text, doc_vector)
    summary = summarize(text, doc_vector)
    return (", ".join(tags) or None), summary
