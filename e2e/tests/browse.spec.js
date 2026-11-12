import {
  test, expect, saveNote, savePdf, expectSaved, addAnother, openTab, browseRow, search,
  SOURDOUGH, TOMATOES, TIDE_POOLS_PDF,
} from './helpers.js';

test.describe('browsing the vault', () => {
  test('an empty vault says so', async ({ app: page }) => {
    await openTab(page, 'Browse');
    await expect(page.getByText('No documents yet.')).toBeVisible();
    await expect(page.getByText('0 saved items')).toBeVisible();
  });

  test('selecting a document shows its details and an excerpt of its text', async ({ app: page }) => {
    await saveNote(page, SOURDOUGH);
    await expectSaved(page, SOURDOUGH.filename);
    await openTab(page, 'Browse');

    await browseRow(page, SOURDOUGH.filename).locator('.kv-doc-main').click();
    const detail = page.locator('.kv-detail');
    await expect(detail.getByRole('heading', { name: SOURDOUGH.filename })).toBeVisible();
    await expect(detail).toContainText('Text'); // type
    await expect(detail.locator('.kv-excerpt-text')).toContainText(SOURDOUGH.phrase);

    // Clicking it again closes the details and the vault overview comes back.
    await browseRow(page, SOURDOUGH.filename).locator('.kv-doc-main').click();
    await expect(page.getByRole('heading', { name: 'Vault overview' })).toBeVisible();
  });

  test('the type filter separates PDFs from text', async ({ app: page }) => {
    await saveNote(page, SOURDOUGH);
    await expectSaved(page, SOURDOUGH.filename);
    await addAnother(page);
    await savePdf(page, TIDE_POOLS_PDF);
    await expectSaved(page, 'tide-pools.pdf');
    await openTab(page, 'Browse');
    await expect(page.locator('.kv-doc')).toHaveCount(2);

    await page.getByLabel('Filter document type').selectOption('PDF');
    await expect(page.locator('.kv-doc')).toHaveCount(1);
    await expect(browseRow(page, 'tide-pools.pdf')).toBeVisible();

    await page.getByLabel('Filter document type').selectOption('Text');
    await expect(page.locator('.kv-doc')).toHaveCount(1);
    await expect(browseRow(page, SOURDOUGH.filename)).toBeVisible();
  });

  test('the newest document comes first, and the sort can be changed', async ({ app: page }) => {
    await saveNote(page, SOURDOUGH);
    await expectSaved(page, SOURDOUGH.filename);
    await addAnother(page);
    await saveNote(page, TOMATOES);
    await expectSaved(page, TOMATOES.filename);
    await openTab(page, 'Browse');

    const titles = page.locator('.kv-doc .kv-doc-title');
    await expect(titles).toHaveText([TOMATOES.filename, SOURDOUGH.filename]);
    await page.getByLabel('Sort documents').selectOption('oldest');
    await expect(titles).toHaveText([SOURDOUGH.filename, TOMATOES.filename]);
    await page.getByLabel('Sort documents').selectOption('name');
    await expect(titles).toHaveText([TOMATOES.filename, SOURDOUGH.filename]); // A to Z: Growing, then Sourdough
  });
});

test.describe('deleting', () => {
  test('cancelling keeps the document', async ({ app: page }) => {
    await saveNote(page, SOURDOUGH);
    await expectSaved(page, SOURDOUGH.filename);
    await openTab(page, 'Browse');

    await page.getByRole('button', { name: `Delete ${SOURDOUGH.filename}` }).click();
    await expect(page.getByText(`Delete “${SOURDOUGH.filename}”?`)).toBeVisible();
    await page.getByRole('button', { name: 'Cancel' }).click();
    await expect(browseRow(page, SOURDOUGH.filename)).toBeVisible();
  });

  test('confirming removes it, from the list and from the server', async ({ app: page }) => {
    await saveNote(page, SOURDOUGH);
    await expectSaved(page, SOURDOUGH.filename);
    await openTab(page, 'Browse');
    await browseRow(page, SOURDOUGH.filename).locator('.kv-doc-main').click();

    await page.getByRole('button', { name: `Delete ${SOURDOUGH.filename}` }).click();
    await page.getByRole('button', { name: 'Yes, delete' }).click();
    await expect(page.getByText(`Deleted "${SOURDOUGH.filename}".`)).toBeVisible();
    await expect(browseRow(page, SOURDOUGH.filename)).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Vault overview' })).toBeVisible();

    await page.reload();
    await expect(page.getByText('No documents yet.')).toBeVisible();
  });

  test('a deleted document no longer turns up in search', async ({ app: page }) => {
    await saveNote(page, SOURDOUGH);
    await expectSaved(page, SOURDOUGH.filename);
    await openTab(page, 'Browse');
    await page.getByRole('button', { name: `Delete ${SOURDOUGH.filename}` }).click();
    await page.getByRole('button', { name: 'Yes, delete' }).click();
    await expect(browseRow(page, SOURDOUGH.filename)).toHaveCount(0);

    await search(page, SOURDOUGH.query);
    await expect(page.getByText(/^No matches for/)).toBeVisible();
  });
});
