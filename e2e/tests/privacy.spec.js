import { test, expect, createAccount, signInAs, saveNote, expectSaved, openTab, search, searchPanel, SOURDOUGH } from './helpers.js';

// Accounts keep their documents apart (KV-42), seen from the browser.
test('one person cannot see, or search, another person\'s documents', async ({ app: page, browser, request }) => {
  await saveNote(page, SOURDOUGH);
  await expectSaved(page, SOURDOUGH.filename);

  const other = await createAccount(request);
  const context = await browser.newContext();
  await signInAs(context, other);
  const otherPage = await context.newPage();
  await otherPage.goto('/#/browse');

  await expect(otherPage.getByText('No documents yet.')).toBeVisible();
  await expect(otherPage.getByText(SOURDOUGH.filename)).toHaveCount(0);

  await search(otherPage, SOURDOUGH.query);
  await expect(otherPage.getByText(/^No matches for/)).toBeVisible();
  await expect(searchPanel(otherPage).locator('.kv-doc')).toHaveCount(0);

  await context.close();

  // The first person still has theirs.
  await openTab(page, 'Browse');
  await expect(page.locator('.kv-doc', { hasText: SOURDOUGH.filename })).toBeVisible();
});
