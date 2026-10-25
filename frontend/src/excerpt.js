/**
 * Shared excerpt helper (KV-30 / KV-31).
 *
 * Pull the source excerpt out of a full document record. The detail
 * endpoint's text field name has varied across backend iterations, so
 * accept the known candidates and use the first non-empty string.
 */
export function excerptOf(record) {
  if (!record) return '';
  let raw = [
    record.excerpt,
    record.text_preview,
    record.preview,
    record.snippet,
    record.text,
    record.content,
    record.extracted_text,
    record.raw_text,
    record.text_content,
    record.page_content,
    record.body,
    record.first_chunk,
    record.first_chunk_text,
  ].find((v) => typeof v === 'string' && v.trim());
  // Some backend shapes embed the chunks in the document record instead
  // of exposing a flat text field; fall back to the first chunk's text.
  if (!raw && Array.isArray(record.chunks) && record.chunks.length > 0) {
    const first = record.chunks[0];
    if (typeof first === 'string') {
      raw = first;
    } else if (first && typeof first === 'object') {
      raw = [first.text, first.content, first.snippet, first.page_content].find(
        (v) => typeof v === 'string' && v.trim(),
      );
    }
  }
  if (!raw) return '';
  const clean = raw.replace(/\s+/g, ' ').trim();
  return clean.length > 600 ? `${clean.slice(0, 600).trimEnd()}…` : clean;
}
