import { excerptOf } from './excerpt.js';

// KV-39 — excerptOf feeds the Browse detail pane: it must tolerate every
// text-field name the backend has used and always return clean text.
describe('excerptOf', () => {
  it('returns an empty string for a missing record', () => {
    expect(excerptOf(null)).toBe('');
    expect(excerptOf(undefined)).toBe('');
  });

  it('returns an empty string when no known text field is present', () => {
    expect(excerptOf({ id: 1, filename: 'a.pdf' })).toBe('');
  });

  it('uses the first non-empty known field, in priority order', () => {
    expect(excerptOf({ text: 'from text', extracted_text: 'from extracted' })).toBe('from text');
    expect(excerptOf({ extracted_text: 'from extracted' })).toBe('from extracted');
    expect(excerptOf({ excerpt: '  ', snippet: 'from snippet' })).toBe('from snippet');
  });

  it('collapses runs of whitespace and trims', () => {
    expect(excerptOf({ text: '  alpha\n\n beta\t gamma  ' })).toBe('alpha beta gamma');
  });

  it('truncates past 600 characters with an ellipsis', () => {
    const long = 'a'.repeat(700);
    const out = excerptOf({ text: long });
    expect(out.endsWith('…')).toBe(true);
    expect(out.length).toBe(601);
  });

  it('falls back to the first chunk when no flat field exists', () => {
    expect(excerptOf({ chunks: ['chunk text'] })).toBe('chunk text');
    expect(excerptOf({ chunks: [{ content: 'object chunk' }] })).toBe('object chunk');
    expect(excerptOf({ chunks: [] })).toBe('');
  });
});
