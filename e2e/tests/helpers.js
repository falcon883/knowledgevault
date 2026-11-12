import { test as base, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

export { expect };

export const API_URL = process.env.E2E_API_URL || `http://127.0.0.1:${process.env.E2E_API_PORT || '8100'}`;
export const PASSWORD = 'correct horse battery';

// The same key frontend/src/auth.js stores the sign-in token under.
const TOKEN_KEY = 'kv_access_token';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const FIXTURES = path.join(HERE, '..', 'fixtures');
export const TIDE_POOLS_PDF = path.join(FIXTURES, 'tide-pools.pdf');
export const BLANK_SCAN_PDF = path.join(FIXTURES, 'blank-scan.pdf');

// Two short notes about different things, so a search has a right answer.
// The questions reuse some of each note's own words on purpose: the stand-in
// embeddings in start_backend.py match shared words, and the backend drops
// results scoring under 0.25, so a question with almost no words in common
// would find nothing. (The real model needs no such help.)
export const SOURDOUGH = {
  title: 'Sourdough starter care',
  text:
    'Sourdough starter care\n\n' +
    'Feed your sourdough starter with equal parts flour and water every day. ' +
    'A healthy starter doubles in size within six hours of feeding and smells pleasantly sour. ' +
    'Keep it in the fridge if you bake only once a week.',
  filename: 'Sourdough starter care.txt',
  phrase: 'equal parts flour and water',
  query: 'how often should I feed my sourdough starter',
};
export const TOMATOES = {
  title: 'Growing tomatoes on a balcony',
  text:
    'Growing tomatoes on a balcony\n\n' +
    'Tomato plants need at least six hours of direct sun and a deep pot. ' +
    'Water the soil, not the leaves, and pinch off the side shoots so the plant puts its energy into fruit.',
  filename: 'Growing tomatoes on a balcony.txt',
  phrase: 'pinch off the side shoots',
  query: 'how much direct sun do tomato plants need in a deep pot',
};

let counter = 0;
export function uniqueEmail() {
  counter += 1;
  return `e2e-${Date.now()}-${counter}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

/** Create an account through the API (fast). Returns what is needed to sign in. */
export async function createAccount(request) {
  const email = uniqueEmail();
  const response = await request.post(`${API_URL}/auth/signup`, { data: { email, password: PASSWORD } });
  expect(response.status(), await response.text()).toBe(201);
  const body = await response.json();
  return { email, password: PASSWORD, token: body.access_token };
}

/** Make this browser context start out signed in as the given account. */
export async function signInAs(context, account) {
  await context.addInitScript(
    ([key, token]) => window.localStorage.setItem(key, token),
    [TOKEN_KEY, account.token],
  );
}

export const test = base.extend({
  /** A brand-new account, created through the API. */
  account: async ({ request }, use) => {
    await use(await createAccount(request));
  },

  /** A page that is already signed in as that account and showing the Capture tab. */
  app: async ({ page, context, account }, use) => {
    await signInAs(context, account);
    await page.goto('/#/capture');
    await expect(page.getByRole('heading', { name: 'Add to your vault' })).toBeVisible();
    await use(page);
  },
});

// --- things a person does on screen ----------------------------------------------

export function openTab(page, name) {
  return page.getByRole('navigation', { name: 'Primary' }).getByRole('button', { name, exact: true }).click();
}

/** Save a note or article typed into the Capture tab. Waits for the result message. */
export async function saveNote(page, { title, text }, kind = 'Note') {
  await openTab(page, 'Capture');
  await page.getByRole('group', { name: 'Document kind' }).getByRole('button', { name: kind }).click();
  await page.getByLabel('Title', { exact: true }).fill(title);
  await page.locator('#kv-text').fill(text);
  await page.getByRole('button', { name: 'Save to vault' }).click();
}

/** Choose a PDF in the Capture tab and save it. */
export async function savePdf(page, filePath) {
  await openTab(page, 'Capture');
  await page.getByRole('group', { name: 'Document kind' }).getByRole('button', { name: 'PDF' }).click();
  await page.getByLabel('Choose PDF', { exact: true }).setInputFiles(filePath);
  await page.getByRole('button', { name: 'Save to vault' }).click();
}

export async function expectSaved(page, filename) {
  const status = page.locator('.kv-status.ok');
  await expect(status).toContainText('Saved.');
  await expect(status).toContainText(filename);
}

export function addAnother(page) {
  return page.getByRole('button', { name: 'Add another' }).click();
}

/** The row for a document in the Browse list. */
export function browseRow(page, filename) {
  return page.locator('.kv-doc', { hasText: filename });
}

export function searchPanel(page) {
  return page.locator('section[aria-labelledby="search-heading"]');
}

export async function search(page, query) {
  await openTab(page, 'Search');
  await page.getByLabel('Describe what you want to find').fill(query);
  await searchButton(page).click();
}

/** The submit button inside the Search tab (the sidebar tab is also called "Search"). */
export function searchButton(page) {
  return searchPanel(page).getByRole('button', { name: 'Search', exact: true });
}
