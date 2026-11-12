import { test, expect, openTab, saveNote, expectSaved, browseRow, search, searchPanel, SOURDOUGH, TOMATOES } from './helpers.js';

// The path a volunteer follows in the pilot: add something, find it by what it
// means, read it, and remove it. One test, start to finish, through the real UI.
test('a person can add a note, find it by meaning, read it and delete it', async ({ app: page }) => {
  // Add two notes about different things.
  await saveNote(page, SOURDOUGH);
  await expectSaved(page, SOURDOUGH.filename);
  await page.getByRole('button', { name: 'Add another' }).click();
  await saveNote(page, TOMATOES);
  await expectSaved(page, TOMATOES.filename);

  // Browse shows both.
  await page.getByRole('button', { name: 'View in Browse' }).click();
  await expect(page.getByRole('heading', { name: 'Your documents' })).toBeVisible();
  await expect(page.getByText('2 saved items')).toBeVisible();
  await expect(browseRow(page, SOURDOUGH.filename)).toBeVisible();
  await expect(browseRow(page, TOMATOES.filename)).toBeVisible();

  // A plain-language question brings the right note to the top.
  await search(page, SOURDOUGH.query);
  const results = searchPanel(page).locator('.kv-doc');
  await expect(results.first()).toContainText(SOURDOUGH.filename);

  // Opening the result shows the words from the document itself.
  await results.first().click();
  await expect(results.first()).toContainText(SOURDOUGH.phrase);

  // Delete it from Browse, and it is gone for good.
  await openTab(page, 'Browse');
  await page.getByRole('button', { name: `Delete ${SOURDOUGH.filename}` }).click();
  await page.getByRole('button', { name: 'Yes, delete' }).click();
  await expect(page.getByText(`Deleted "${SOURDOUGH.filename}".`)).toBeVisible();
  await page.reload();
  await expect(browseRow(page, SOURDOUGH.filename)).toHaveCount(0);
  await expect(browseRow(page, TOMATOES.filename)).toBeVisible();
});
