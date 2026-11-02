"""
KnowledgeVault backend - chunking strategy (KV-14, improved in KV-38).

Documents are cut into chunks of about 800 characters, and each chunk gets its
own embedding. KV-14 cut every 800 characters wherever that landed, which
often split a word or a sentence, so a snippet could start or stop halfway
through a thought and a match could fall across the cut. Now the cut is placed
at a natural break instead:

  1. Text is first split into sentences (never after "Dr.", "e.g.", an
     initial, or a decimal point) inside its paragraphs.
  2. Sentences are packed into a chunk until the next one would not fit in
     CHUNK_SIZE characters. If a paragraph break falls in the second half of
     the chunk, the chunk ends there, so paragraphs stay together.
  3. The next chunk starts with the last sentence or two of the previous one
     (up to CHUNK_OVERLAP characters), so an idea that straddles a cut is
     whole in at least one chunk.

Text without sentence breaks, such as a table or a schedule, falls back to
lines, then to words, so it still chunks and no line or word is cut in two.
Only a single "word" longer than CHUNK_SIZE (a long base64 blob, say) is cut
by length. No chunk is ever longer than CHUNK_SIZE.

The original fixed-window version is kept as chunk_text_fixed so the two can be
compared (compare_chunking.py) and so documents stored before KV-38 can be
re-chunked (rechunk_documents.py).
"""

import re

CHUNK_SIZE = 800  # characters per chunk, at most
CHUNK_OVERLAP = 150  # characters shared between consecutive chunks, at most
MIN_FILL = 0.5  # a paragraph break is used as the cut only if the chunk is at least this full

_BLANK_LINE = re.compile(r"\n[ \t\r\f\v]*\n\s*")
_LINE_BREAK = re.compile(r"\n")
_WHITESPACE = re.compile(r"\s+")
# Sentence punctuation, optional closing quotes or brackets, then whitespace.
_SENTENCE_END = re.compile(r"[.!?]+[\"'”’)\]]*\s+")

# A period after one of these does not end a sentence.
_ABBREVIATIONS = frozenset(
    "mr mrs ms mx dr prof sr jr st mt vs etc e.g i.e cf al approx fig figs eq no nos vol vols "
    "pp ch sec inc ltd co corp dept est u.s u.k a.m p.m ph.d jan feb mar apr jun jul aug sep sept "
    "oct nov dec".split()
)


def _trimmed(text: str, start: int, end: int):
    """Yield (start, end) with surrounding whitespace removed, unless nothing is left."""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start < end:
        yield start, end


def _split_on(pattern: re.Pattern, text: str, start: int, end: int):
    """Spans of text[start:end] between matches of `pattern`, trimmed, empty ones dropped."""
    position = start
    for match in pattern.finditer(text, start, end):
        yield from _trimmed(text, position, match.start())
        position = match.end()
    yield from _trimmed(text, position, end)


def _ends_sentence(text: str, start: int, end: int, match: re.Match) -> bool:
    """Is this punctuation the end of a sentence, rather than an abbreviation or a decimal?"""
    after = match.end()
    if after < end and text[after].islower():
        return False  # "e.g. the", "approx. three"
    if match.group().startswith(".") and not match.group().startswith(".."):
        before = text[max(start, match.start() - 24) : match.start()]
        word = re.split(r"\s", before)[-1].lower().lstrip("\"'(“[")
        if word in _ABBREVIATIONS or (len(word) == 1 and word.isalpha()):
            return False  # "Dr. Smith", "J. Smith"
    return True


def _sentence_spans(text: str, start: int, end: int):
    position = start
    for match in _SENTENCE_END.finditer(text, start, end):
        if _ends_sentence(text, start, end, match):
            yield from _trimmed(text, position, match.end())
            position = match.end()
    yield from _trimmed(text, position, end)


def _fit(text: str, start: int, end: int, size: int):
    """The span itself if it fits, otherwise its lines, otherwise its words, otherwise slices."""
    if end - start <= size:
        yield start, end
        return
    for line_start, line_end in _split_on(_LINE_BREAK, text, start, end):
        if line_end - line_start <= size:
            yield line_start, line_end
            continue
        for word_start, word_end in _split_on(_WHITESPACE, text, line_start, line_end):
            if word_end - word_start <= size:
                yield word_start, word_end
                continue
            for cut in range(word_start, word_end, size):
                yield cut, min(cut + size, word_end)


def _atoms(text: str, size: int) -> list[tuple[int, int, bool]]:
    """
    The smallest pieces a chunk is built from, in order, as (start, end,
    begins_a_paragraph). Each is at most `size` long.
    """
    atoms = []
    for para_start, para_end in _split_on(_BLANK_LINE, text, 0, len(text)):
        first = True
        for sentence_start, sentence_end in _sentence_spans(text, para_start, para_end):
            for start, end in _fit(text, sentence_start, sentence_end, size):
                atoms.append((start, end, first))
                first = False
    return atoms


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into chunks of at most `chunk_size` characters that start and end
    at sentence (or, failing that, line or word) boundaries, with up to
    `overlap` characters repeated from one chunk to the next.

    Returns an empty list for empty/whitespace-only input rather than a
    single empty chunk.
    """
    text = text.strip()
    return [text[start:end] for start, end in chunk_spans(text, chunk_size, overlap)]


def chunk_spans(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[tuple[int, int]]:
    """Where each chunk of chunk_text(text) sits in `text` (already stripped), as (start, end)."""
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    if not text.strip():
        return []

    atoms = _atoms(text, chunk_size)
    count = len(atoms)

    def reach(first: int) -> int:
        """Index just past the last atom that fits in a chunk starting at atoms[first]."""
        end = first + 1  # a single atom always fits
        while end < count and atoms[end][1] - atoms[first][0] <= chunk_size:
            end += 1
        return end

    chunks = []
    start = 0  # first atom of this chunk (may be repeated from the last one)
    new_from = 0  # first atom that no chunk holds yet
    while new_from < count:
        end = reach(start)
        while end <= new_from:  # only repeated atoms fit: repeat fewer of them
            start += 1
            end = reach(start)

        if end < count:
            # Prefer to stop where a paragraph starts, if that leaves the chunk fairly full.
            for cut in range(end, new_from, -1):
                if atoms[cut][2] and atoms[cut - 1][1] - atoms[start][0] >= chunk_size * MIN_FILL:
                    end = cut
                    break

        chunks.append((atoms[start][0], atoms[end - 1][1]))
        chunk_start, new_from = start, end

        # The next chunk repeats the last few atoms, up to `overlap` characters of them,
        # but never all of this chunk (that would not move forward).
        start = end
        while start - 1 > chunk_start and atoms[end - 1][1] - atoms[start - 1][0] <= overlap:
            start -= 1
    return chunks


def chunk_text_fixed(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    The KV-14 chunker: fixed-size windows with overlap, cut wherever they land.
    No longer used for new uploads; kept for compare_chunking.py and for tests.
    """
    text = text.strip()
    if not text:
        return []

    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_length:
            break
        start = end - overlap

    return chunks


def boundary_quality(chunks: list[str]) -> dict:
    """
    How many chunks start like the start of a sentence and end like the end of
    one. A rough measure for comparing chunkers, not a grammar check: tables and
    lists will not score well whatever the chunker does.
    """
    clean_start = sum(1 for c in chunks if c[:1].isupper() or c[:1].isdigit() or c[:1] in "\"'“([-*•#")
    clean_end = sum(1 for c in chunks if re.search(r"[.!?][\"'”’)\]]*$", c))
    return {"chunks": len(chunks), "clean_start": clean_start, "clean_end": clean_end}
