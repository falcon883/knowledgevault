import {
  test, expect, saveNote, savePdf, expectSaved, addAnother, openTab, search, searchButton, searchPanel,
  SOURDOUGH, TOMATOES, TIDE_POOLS_PDF,
} from './helpers.js';

test.describe('searching', () => {
  test('before any search, the screen offers ideas and the Search button waits for a query', async ({ app: page }) => {
    await openTab(page, 'Search');
    await expect(page.getByText('Try searching for:')).toBeVisible();
    await expect(searchButton(page)).toBeDisabled();
    await page.getByLabel('Describe what you want to find').fill('tide pools');
    await expect(searchButton(page)).toBeEnabled();
  });

  test('a category card opens Browse already filtered to that type', async ({ app: page }) => {
    await saveNote(page, SOURDOUGH);
    await expectSaved(page, SOURDOUGH.filename);
    await addAnother(page);
    await savePdf(page, TIDE_POOLS_PDF);
    await expectSaved(page, 'tide-pools.pdf');

    await openTab(page, 'Search');
    await searchPanel(page).getByRole('button', { name: /PDFs/ }).click();
    await expect(page.getByRole('heading', { name: 'Your documents' })).toBeVisible();
    await expect(page.locator('.kv-doc')).toHaveCount(1);
    await expect(page.locator('.kv-doc', { hasText: 'tide-pools.pdf' })).toBeVisible();
  });

  test('searching an empty vault finds nothing and says so', async ({ app: page }) => {
    await search(page, 'anything at all');
    await expect(page.getByText('No matches for “anything at all”.')).toBeVisible();
  });

  test('a question in plain words ranks the matching document first', async ({ app: page }) => {
    await saveNote(page, SOURDOUGH);
    await expectSaved(page, SOURDOUGH.filename);
    await addAnother(page);
    await saveNote(page, TOMATOES);
    await expectSaved(page, TOMATOES.filename);
    await addAnother(page);
    await savePdf(page, TIDE_POOLS_PDF);
    await expectSaved(page, 'tide-pools.pdf');

    const results = searchPanel(page).locator('.kv-doc');

    await search(page, TOMATOES.query);
    await expect(results.first()).toContainText(TOMATOES.filename);

    await search(page, SOURDOUGH.query);
    await expect(results.first()).toContainText(SOURDOUGH.filename);

    await search(page, 'what animals live in a tide pool when the tide goes out');
    await expect(results.first()).toContainText('tide-pools.pdf');
    await expect(results.first()).toContainText(/tide|pool/i); // the snippet shows the matching words
  });

  test('a result opens to show a preview of the document, and closes again', async ({ app: page }) => {
    await saveNote(page, SOURDOUGH);
    await expectSaved(page, SOURDOUGH.filename);
    await search(page, SOURDOUGH.query);

    const first = searchPanel(page).locator('.kv-doc').first();
    await expect(first).toHaveAttribute('aria-expanded', 'false');
    await first.click();
    await expect(first).toHaveAttribute('aria-expanded', 'true');
    await expect(first.locator('.kv-doc-summary')).toContainText(SOURDOUGH.phrase);
    await first.click();
    await expect(first).toHaveAttribute('aria-expanded', 'false');
  });

  test('the query and results are still there after visiting another tab', async ({ app: page }) => {
    await saveNote(page, SOURDOUGH);
    await expectSaved(page, SOURDOUGH.filename);
    await search(page, SOURDOUGH.query);
    await expect(searchPanel(page).locator('.kv-doc').first()).toContainText(SOURDOUGH.filename);

    await openTab(page, 'Browse');
    await openTab(page, 'Search');
    await expect(page.getByLabel('Describe what you want to find')).toHaveValue(SOURDOUGH.query);
    await expect(searchPanel(page).locator('.kv-doc').first()).toContainText(SOURDOUGH.filename);
  });
});
