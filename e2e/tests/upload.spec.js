import {
  test, expect, saveNote, savePdf, expectSaved, addAnother, openTab,
  SOURDOUGH, TIDE_POOLS_PDF, BLANK_SCAN_PDF,
} from './helpers.js';

test.describe('adding documents', () => {
  test('a typed note is saved, indexed and offered in Browse', async ({ app: page }) => {
    await saveNote(page, SOURDOUGH);
    await expectSaved(page, SOURDOUGH.filename);
    await expect(page.locator('.kv-status.ok')).toContainText(/\(\d+ chunks?\)/);

    await page.getByRole('button', { name: 'View in Browse' }).click();
    await expect(page.getByRole('heading', { name: 'Your documents' })).toBeVisible();
    await expect(page.locator('.kv-doc', { hasText: SOURDOUGH.filename })).toBeVisible();
  });

  test('a note without a title is named after its first line', async ({ app: page }) => {
    await page.getByRole('group', { name: 'Document kind' }).getByRole('button', { name: 'Article' }).click();
    await page.locator('#kv-text').fill('Why the sky is blue\n\nShort wavelengths of sunlight scatter off air molecules more than long ones do.');
    await expect(page.getByText('will be saved as “Why the sky is blue.txt”')).toBeVisible();
    await page.getByRole('button', { name: 'Save to vault' }).click();
    await expectSaved(page, 'Why the sky is blue.txt');
  });

  test('a PDF is saved with its text indexed', async ({ app: page }) => {
    await savePdf(page, TIDE_POOLS_PDF);
    await expectSaved(page, 'tide-pools.pdf');
  });

  test('the same content twice is reported as already saved', async ({ app: page }) => {
    await saveNote(page, SOURDOUGH);
    await expectSaved(page, SOURDOUGH.filename);
    await addAnother(page);

    // Same words under a different title: the backend recognises the text.
    await saveNote(page, { title: 'A copy of my notes', text: SOURDOUGH.text });
    const message = page.locator('.kv-status.duplicate');
    await expect(message).toContainText('Already in your vault.');
    await expect(message).toContainText(SOURDOUGH.filename);

    // And nothing extra was added.
    await openTab(page, 'Browse');
    await expect(page.getByText('1 saved item', { exact: true })).toBeVisible();
  });

  test('a PDF with no text in it is refused by the server with an explanation', async ({ app: page }) => {
    await savePdf(page, BLANK_SCAN_PDF);
    const message = page.locator('.kv-status.error');
    await expect(message).toContainText('No readable text found.');
    await expect(message).toContainText('scanned PDF');

    await openTab(page, 'Browse');
    await expect(page.getByText('No documents yet.')).toBeVisible();
  });

  test('a file that is not a PDF is turned away before it is sent', async ({ app: page }) => {
    await page.getByLabel('Choose PDF', { exact: true }).setInputFiles({
      name: 'notes.docx',
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      buffer: Buffer.from('not a pdf'),
    });
    await expect(page.getByRole('alert')).toContainText('That file is not a PDF.');
    await expect(page.getByRole('button', { name: 'Save to vault' })).toBeDisabled();
  });

  test('an empty file is turned away before it is sent', async ({ app: page }) => {
    await page.getByLabel('Choose PDF', { exact: true }).setInputFiles({
      name: 'empty.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.alloc(0),
    });
    await expect(page.getByRole('alert')).toContainText('empty (0 bytes)');
    await expect(page.getByRole('button', { name: 'Save to vault' })).toBeDisabled();
  });
});
