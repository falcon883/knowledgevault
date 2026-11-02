"""KV-38: chunks break at sentence boundaries, stay near 800 characters, and overlap."""

import random

import pytest

from chunking import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    _sentence_spans,
    boundary_quality,
    chunk_spans,
    chunk_text,
    chunk_text_fixed,
)

WORDS = (
    "starter flour water bake oven warm dough rise jar morning feed kitchen bread salt yeast "
    "recipe budget quarter team review report plan garden soil seed light shade prune trail "
    "park camp road lake river summit map ticket".split()
)


def prose(rng, sentences, low=6, high=16):
    """Sentences made of random words, ending with a full stop, in paragraphs of 3 to 6."""
    out = []
    for number in range(sentences):
        words = [rng.choice(WORDS) for _ in range(rng.randint(low, high))]
        out.append(words[0].capitalize() + " " + " ".join(words[1:]) + ".")
        if number % rng.randint(3, 6) == 5:
            out.append("\n\n")
        else:
            out.append(" ")
    return "".join(out).strip()


def sentences_of(text):
    return [text[a:b] for a, b in _sentence_spans(text, 0, len(text))]


# --- basics ------------------------------------------------------------------------


def test_empty_and_blank_text_make_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("  \n\n \t ") == []


def test_short_text_is_one_chunk():
    assert chunk_text("  Just one short note.  ") == ["Just one short note."]


def test_overlap_must_be_smaller_than_the_size():
    with pytest.raises(ValueError):
        chunk_text("anything", chunk_size=100, overlap=100)


# --- where it cuts -----------------------------------------------------------------


def test_prose_is_cut_only_at_sentence_boundaries():
    text = prose(random.Random(1), 120)
    chunks = chunk_text(text)
    assert len(chunks) > 5
    quality = boundary_quality(chunks)
    assert quality["clean_start"] == quality["clean_end"] == len(chunks), "every chunk is whole sentences"
    assert boundary_quality(chunk_text_fixed(text))["clean_end"] < len(chunks) / 2, "the old chunker was not"


def test_no_chunk_is_longer_than_the_size_and_most_are_close_to_it():
    chunks = chunk_text(prose(random.Random(2), 200))
    assert max(len(c) for c in chunks) <= CHUNK_SIZE
    full = [c for c in chunks[:-1] if len(c) >= CHUNK_SIZE * 0.7]
    assert len(full) >= (len(chunks) - 1) * 0.8, "chunks should be near 800 characters, not tiny"


def test_consecutive_chunks_overlap_by_whole_sentences():
    text = prose(random.Random(3), 150, low=6, high=12)  # sentences well under the overlap
    chunks = chunk_text(text)
    for before, after in zip(chunks, chunks[1:]):
        shared = [s for s in sentences_of(before) if s in sentences_of(after)]
        assert shared, "the next chunk starts with something the last one ended with"
        repeated = after[: after.index(shared[-1]) + len(shared[-1])]
        assert len(repeated) <= CHUNK_OVERLAP
        assert before.endswith(repeated)


def test_a_paragraph_break_is_used_when_the_chunk_is_fairly_full():
    a = " ".join(f"Sentence number {n} about the first topic goes right here." for n in range(8))  # ~450
    b = " ".join(f"Sentence number {n} about the second topic goes right here." for n in range(8))  # ~470
    chunks = chunk_text(a + "\n\n" + b)
    assert chunks[0] == a, "the first paragraph stays together instead of being filled up with the second"
    assert b in chunks[1]


def test_a_paragraph_break_is_ignored_when_the_chunk_would_be_nearly_empty():
    short = "A short opening line."
    long_part = " ".join(f"Sentence number {n} of the long paragraph is right here." for n in range(14))
    chunks = chunk_text(short + "\n\n" + long_part)
    assert chunks[0].startswith(short) and "Sentence number 0" in chunks[0]
    assert len(chunks[0]) > CHUNK_SIZE * 0.7


# --- sentence detection --------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Dr. Smith met J. Doe at 3.5 p.m. today. They left.", ["Dr. Smith met J. Doe at 3.5 p.m. today.", "They left."]),
        ("Use a jar, e.g. a glass one. It works.", ["Use a jar, e.g. a glass one.", "It works."]),
        ("Is it done? Yes! Good.", ["Is it done?", "Yes!", "Good."]),
        ('He said "stop." Then he left.', ['He said "stop."', "Then he left."]),
        ("See Fig. 3 for details. Next part.", ["See Fig. 3 for details.", "Next part."]),
        ("Wait... then go. Done.", ["Wait... then go.", "Done."]),
        ("It costs 4.50 dollars. Cheap.", ["It costs 4.50 dollars.", "Cheap."]),
    ],
)
def test_sentences_are_not_split_at_abbreviations_or_decimals(text, expected):
    assert sentences_of(text) == expected


def test_windows_line_endings_work():
    text = "First paragraph here. More of it.\r\n\r\nSecond paragraph here. And more."
    assert chunk_text(text, chunk_size=45, overlap=10)[0] == "First paragraph here. More of it."


# --- text without sentences ----------------------------------------------------------


def test_a_schedule_with_no_punctuation_is_cut_between_lines():
    lines = [f"Mon {9 + n % 8}:00 Room {100 + n} Group {n}" for n in range(120)]
    chunks = chunk_text("\n".join(lines))
    assert len(chunks) > 3
    for chunk in chunks:
        assert len(chunk) <= CHUNK_SIZE
        assert set(chunk.split("\n")) <= set(lines), "no line was cut in two"
    assert chunks[0].split("\n")[0] == lines[0] and chunks[-1].split("\n")[-1] == lines[-1]
    for before, after in zip(chunks, chunks[1:]):
        assert after.split("\n")[0] in before.split("\n"), "lines carry over as the overlap"


def test_one_long_line_with_no_punctuation_is_cut_between_words():
    words = [WORDS[n % len(WORDS)] + str(n) for n in range(600)]
    chunks = chunk_text(" ".join(words))
    assert len(chunks) > 3
    for chunk in chunks:
        assert len(chunk) <= CHUNK_SIZE
        assert set(chunk.split()) <= set(words), "no word was cut in two"


def test_a_long_sentence_is_still_split():
    sentence = "This sentence just keeps going " + "and going " * 200 + "until it finally stops."
    chunks = chunk_text(sentence)
    assert len(chunks) > 2
    assert all(len(c) <= CHUNK_SIZE for c in chunks)


def test_text_with_no_spaces_at_all_is_cut_by_length():
    blob = "".join(chr(97 + n % 26) for n in range(3000))
    chunks = chunk_text(blob)
    assert all(len(c) <= CHUNK_SIZE for c in chunks)
    assert "".join(chunks) == blob


# --- nothing is lost -----------------------------------------------------------------


def assert_complete(text, size, overlap):
    """Chunks run from the first character to the last with nothing but whitespace left out."""
    text = text.strip()
    spans = chunk_spans(text, size, overlap)
    assert [text[a:b] for a, b in spans] == chunk_text(text, size, overlap)
    if not text:
        assert spans == []
        return
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    for (a, b), (c, d) in zip(spans, spans[1:]):
        assert a < c and b < d, "each chunk moves forward"
        assert not text[b:c].strip(), "text was dropped between two chunks"
    for a, b in spans:
        assert 0 < b - a <= size and text[a:b] == text[a:b].strip()


@pytest.mark.parametrize("seed", range(40))
def test_random_documents_are_chunked_completely_and_within_the_limit(seed):
    rng = random.Random(seed)
    kind = seed % 4
    if kind == 0:
        text = prose(rng, rng.randint(1, 150))
    elif kind == 1:
        text = "\n".join(" ".join(str(rng.randint(0, 999)) for _ in range(rng.randint(2, 9))) for _ in range(rng.randint(1, 200)))
    elif kind == 2:
        text = " ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 900)))
    else:
        text = "\n\n".join(prose(rng, rng.randint(1, 12)) for _ in range(rng.randint(1, 15))) + "\r\n\r\n   \t\n" + "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(0, 900)))
    size = rng.choice([CHUNK_SIZE, 300, 120])
    overlap = rng.choice([0, 30, size // 5])
    assert_complete(text, size, overlap)


def test_every_word_survives_whole():
    """The old chunker cut words in two; the new one keeps every word of the text, intact."""
    text = prose(random.Random(9), 100)
    assert set(" ".join(chunk_text(text)).split()) == set(text.split())
    assert not set(" ".join(chunk_text_fixed(text)).split()) <= set(text.split()), "the old chunks had cut words"
