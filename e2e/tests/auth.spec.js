import { test, expect, PASSWORD, uniqueEmail, createAccount } from './helpers.js';

async function fillAndSubmit(page, email, password, button) {
  await page.getByLabel('Email').fill(email);
  await page.locator('#kv-auth-password').fill(password); // not getByLabel: the show-password button is also labelled Password
  await page.getByRole('button', { name: button, exact: true }).last().click();
}

test.describe('signing up and in', () => {
  test('a visitor sees the sign-in screen first', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Primary' })).toHaveCount(0);
  });

  test('sign up, stay signed in after a refresh, sign out, sign in again', async ({ page }) => {
    const email = uniqueEmail();
    await page.goto('/');
    await page.getByRole('group', { name: 'Sign in or sign up' }).getByRole('button', { name: 'Sign up' }).click();
    await fillAndSubmit(page, email, PASSWORD, 'Sign up');
    await expect(page.getByRole('heading', { name: 'Add to your vault' })).toBeVisible();

    await page.reload();
    await expect(page.getByRole('heading', { name: 'Add to your vault' })).toBeVisible();

    await page.getByRole('button', { name: 'Sign out' }).click();
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();

    await fillAndSubmit(page, email, PASSWORD, 'Sign in');
    await expect(page.getByRole('heading', { name: 'Add to your vault' })).toBeVisible();
  });

  test('a wrong password is refused with a clear message', async ({ page, request }) => {
    const account = await createAccount(request);
    await page.goto('/');
    await fillAndSubmit(page, account.email, 'not the password', 'Sign in');
    await expect(page.getByRole('alert')).toContainText('Wrong email or password.');
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
  });

  test('signing up with an email that already has an account says so', async ({ page, request }) => {
    const account = await createAccount(request);
    await page.goto('/');
    await page.getByRole('group', { name: 'Sign in or sign up' }).getByRole('button', { name: 'Sign up' }).click();
    await fillAndSubmit(page, account.email, PASSWORD, 'Sign up');
    await expect(page.getByRole('alert')).toContainText('An account with this email already exists');
  });

  test('a short password is caught when signing up', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('group', { name: 'Sign in or sign up' }).getByRole('button', { name: 'Sign up' }).click();
    await fillAndSubmit(page, uniqueEmail(), 'short', 'Sign up');
    await expect(page.getByRole('alert')).toContainText('at least 8 characters');
  });

  test('a link to a tab opens that tab once signed in', async ({ app: page }) => {
    await page.goto('/#/search');
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Search your knowledge' })).toBeVisible();
  });
});
