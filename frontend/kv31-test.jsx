/* KV-31 jsdom assertions for SearchScreen + App tab persistence. Bundled with esbuild, run in node. */
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost/',
  pretendToBeVisual: true,
});
globalThis.window = dom.window;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.HTMLSelectElement = dom.window.HTMLSelectElement;
globalThis.MouseEvent = dom.window.MouseEvent;
globalThis.Event = dom.window.Event;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const LONG_SNIPPET = ('word '.repeat(120)).trim(); // ~600 chars
const fetchCalls = [];
globalThis.fetch = async (url, opts = {}) => {
  const u = String(url);
  fetchCalls.push(`${opts.method || 'GET'} ${u}`);
  const ok = (body, status = 200) => ({ ok: status < 300, status, json: async () => body });
  if (u.endsWith('/health')) return ok({ status: 'ok' });
  if (u.endsWith('/documents')) return ok([]);
  if ((opts.method || 'GET') === 'POST' && u.endsWith('/search')) {
    return ok({
      query: 'test query',
      results: [
        { document_id: 1, filename: 'top.pdf', score: 0.9, snippet: 'short snippet text', tags: 'research', summary: 'Top summary' },
        { document_id: 2, filename: 'second.txt', score: 0.45, snippet: LONG_SNIPPET, tags: '', summary: 'Second summary' },
      ],
    });
  }
  if (u.endsWith('/documents/1')) return ok({ id: 1, extracted_text: 'Real excerpt from the full document record.' });
  if (u.endsWith('/documents/2')) return ok({ id: 2 });
  return ok({}, 404);
};

const React = await import('react');
const { act } = React;
const { createRoot } = await import('react-dom/client');
const { default: App } = await import('./src/App.jsx');
const { default: BrowseScreen } = await import('./src/screens/BrowseScreen.jsx');

let failures = 0;
function check(name, cond) {
  if (cond) console.log(`PASS ${name}`);
  else { failures += 1; console.log(`FAIL ${name}`); }
}
const flush = async () => { await act(async () => { await new Promise((r) => setTimeout(r, 10)); }); };
const text = () => document.body.textContent;
const q = (sel) => document.querySelector(sel);
const qa = (sel) => [...document.querySelectorAll(sel)];
// React tracks input values via a wrapped setter; bypass it so the
// synthetic input event registers as a real change.
const nativeValueSetter = Object.getOwnPropertyDescriptor(
  window.HTMLInputElement.prototype,
  'value',
).set;
function setInputValue(el, value) {
  nativeValueSetter.call(el, value);
  el.dispatchEvent(new window.Event('input', { bubbles: true }));
}

const root = createRoot(document.getElementById('root'));
await act(async () => { root.render(React.createElement(App)); });
await flush(); await flush();

// 1. Run a search
const input = q('#kv-query');
await act(async () => { setInputValue(input, 'test query'); });
await flush();
const form = q('form');
await act(async () => { form.dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })); });
await flush(); await flush();
check('search renders 2 results', qa('.kv-doc-title').length === 2);

// 2. No misleading "% match" label; "Relevance" shown instead
check('no percent-match text', !text().includes('% match'));
check('Relevance label present', qa('.kv-relevance-label').length === 2);

// 3. Relevance scale: top hit bar is full width, second is half (0.45/0.9)
const bars = qa('.kv-relevance-bar i').map((el) => el.style.width);
check('top result bar is 100%', bars[0] === '100%');
check('second result bar is 50%', bars[1] === '50%');

// 4. Snippet honesty: short snippet as-is, long one truncated with single trailing ellipsis
const snippets = qa('.kv-snippet').map((el) => el.textContent);
check('short snippet not wrapped in ellipses', snippets[0] === 'short snippet text');
check('long snippet ends with single ellipsis', snippets[1].endsWith('…') && !snippets[1].startsWith('…'));
check('long snippet truncated near 280 chars', snippets[1].length < LONG_SNIPPET.length && snippets[1].length <= 285);

// 5. Expand top result -> real excerpt from GET /documents/1
const topRow = qa('.kv-doc').find((b) => b.textContent.includes('top.pdf'));
await act(async () => { topRow.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
await flush(); await flush();
check('detail fetch hit /documents/1', fetchCalls.some((c) => c.includes('/documents/1')));
check('expanded preview shows real excerpt', text().includes('Real excerpt from the full document record.'));

// 6. Expand result with no text in record -> summary fallback
const secondRow = qa('.kv-doc').find((b) => b.textContent.includes('second.txt'));
await act(async () => { secondRow.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
await flush(); await flush();
check('excerpt-less result falls back to summary', text().includes('Second summary'));

// 7. Tab switch preserves query and results (no remount)
const navButtons = qa('.kv-tab');
const browseBtn = navButtons.find((b) => b.textContent.includes('Browse'));
await act(async () => { browseBtn.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
await flush();
const searchBtn = qa('.kv-tab').find((b) => b.textContent.includes('Search'));
await act(async () => { searchBtn.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
await flush();
check('query survives tab switch', q('#kv-query').value === 'test query');
check('results survive tab switch', qa('.kv-doc-title').length === 2);
check('search still the active tab panel', q('.kv-screen:not([hidden]) #kv-query') !== null);

// 8. Browse refetches when its refreshSignal changes (upload-flow navigation)
const before = fetchCalls.filter((c) => c.endsWith('GET http://localhost:8000/documents')).length;
const broot = document.createElement('div');
document.body.appendChild(broot);
const brootRoot = createRoot(broot);
await act(async () => { brootRoot.render(React.createElement(BrowseScreen, { refreshSignal: 0 })); });
await flush();
await act(async () => { brootRoot.render(React.createElement(BrowseScreen, { refreshSignal: 1 })); });
await flush();
const after = fetchCalls.filter((c) => c.endsWith('GET http://localhost:8000/documents')).length;
check('Browse refetches on refreshSignal change', after >= before + 2);

console.log(failures === 0 ? 'ALL PASS' : `${failures} FAILURES`);
process.exit(failures === 0 ? 0 : 1);
