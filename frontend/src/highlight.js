/**
 * KV-57 — highlight the query words the backend matched, inside a search
 * snippet.
 *
 * POST /search returns matched_terms with every result: the words of the
 * snippet that match the query, lowercase, in order, each once (KV-48,
 * backend/passage.py). This splits a snippet into segments so the screen
 * can wrap the matching words in <mark> and leave the rest as plain text.
 *
 * Rules, straight from the ticket:
 *  - case-insensitive, whole words only: "water" highlights in "too much
 *    water" but not inside "waterfall";
 *  - longest term first: with ["houseplant", "houseplants"], the whole
 *    word "houseplants" highlights instead of "houseplant" plus a stray "s";
 *  - an empty term list returns the text unchanged (one plain segment);
 *  - the segments join back to the exact input, so a screen reader reads
 *    the snippet as normal text.
 */
export function highlightSegments(text, terms) {
  if (!text) return [];
  const clean = (Array.isArray(terms) ? terms : [])
    .filter((t) => typeof t === 'string' && t.trim())
    .map((t) => t.trim());
  if (clean.length === 0) return [{ text, highlight: false }];
  // Longest first, so a longer term wins over its own prefix.
  const sorted = [...new Set(clean.map((t) => t.toLowerCase()))].sort(
    (a, b) => b.length - a.length,
  );
  const escaped = sorted.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const pattern = new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi');
  const segments = [];
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const at = match.index ?? 0;
    if (at > last) segments.push({ text: text.slice(last, at), highlight: false });
    segments.push({ text: match[0], highlight: true });
    last = at + match[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last), highlight: false });
  return segments;
}
