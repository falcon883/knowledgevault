import { highlightSegments } from './highlight.js';

// KV-57 — highlightSegments feeds the Search screen: it must highlight the
// backend's matched_terms inside a snippet (case-insensitive, whole words)
// and leave the snippet untouched when there is nothing to highlight.
describe('highlightSegments', () => {
  it('returns one plain segment when the term list is empty', () => {
    expect(highlightSegments('Too much water, not too little.', [])).toEqual([
      { text: 'Too much water, not too little.', highlight: false },
    ]);
  });

  it('returns one plain segment when terms are missing or blank', () => {
    expect(highlightSegments('Too much water.', undefined)).toEqual([
      { text: 'Too much water.', highlight: false },
    ]);
    expect(highlightSegments('Too much water.', ['  ', null, 7])).toEqual([
      { text: 'Too much water.', highlight: false },
    ]);
  });

  it('highlights a matching word and keeps the original case', () => {
    expect(
      highlightSegments('Most houseplants die from too much water.', [
        'houseplant',
        'houseplants',
        'water',
      ]),
    ).toEqual([
      { text: 'Most ', highlight: false },
      { text: 'houseplants', highlight: true },
      { text: ' die from too much ', highlight: false },
      { text: 'water', highlight: true },
      { text: '.', highlight: false },
    ]);
  });

  it('matches case-insensitively', () => {
    const out = highlightSegments('Water the Houseplant weekly.', ['water', 'houseplant']);
    expect(out.filter((s) => s.highlight).map((s) => s.text)).toEqual([
      'Water',
      'Houseplant',
    ]);
  });

  it('matches whole words only, not words that contain a term', () => {
    const out = highlightSegments('The waterfall needs water.', ['water']);
    expect(out).toEqual([
      { text: 'The waterfall needs ', highlight: false },
      { text: 'water', highlight: true },
      { text: '.', highlight: false },
    ]);
  });

  it('highlights the longest term when one term is a prefix of another', () => {
    const out = highlightSegments('houseplants', ['houseplant', 'houseplants']);
    expect(out).toEqual([{ text: 'houseplants', highlight: true }]);
  });

  it('highlights every occurrence, not just the first', () => {
    const out = highlightSegments('water in, water out.', ['water']);
    expect(out.filter((s) => s.highlight)).toHaveLength(2);
  });

  it('returns no segments for empty text', () => {
    expect(highlightSegments('', ['water'])).toEqual([]);
  });

  it('does not throw on terms with regex characters', () => {
    expect(() => highlightSegments('Use c++ here.', ['c++'])).not.toThrow();
  });

  it('segments always join back to the exact input text', () => {
    const text = 'Most houseplants die from too much water, not too little.';
    const out = highlightSegments(text, ['houseplant', 'houseplants', 'water']);
    expect(out.map((s) => s.text).join('')).toBe(text);
  });
});
