// @ts-check
import { defineConfig, devices } from '@playwright/test';

/**
 * KV-32 - end-to-end tests.
 *
 * `npm test` (in this folder) starts two servers, runs the tests in a real
 * browser, and stops the servers again:
 *
 *   1. the API, on a throwaway schema with a stand-in embedding model
 *      (start_backend.py), and
 *   2. the real frontend: a production build served by `vite preview`,
 *      pointed at that API.
 *
 * Ports are different from the dev servers (8000, 5173), so you can keep those
 * running. Postgres with pgvector must be running (see the backend README).
 */

const API_PORT = process.env.E2E_API_PORT || '8100';
const WEB_PORT = process.env.E2E_WEB_PORT || '4173';
const API_URL = `http://127.0.0.1:${API_PORT}`;
const WEB_URL = `http://127.0.0.1:${WEB_PORT}`;

// Which Python runs the API. Activate backend/.venv first, or set E2E_PYTHON.
const PYTHON = process.env.E2E_PYTHON || 'python';

// The tests read these (see tests/helpers.js).
process.env.E2E_API_URL = API_URL;

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  // Every test signs up its own account, so tests do not share data and can run side by side.
  fullyParallel: true,
  workers: process.env.CI ? 2 : undefined,
  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: WEB_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `${PYTHON} start_backend.py`,
      url: `${API_URL}/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: { E2E_API_PORT: API_PORT, E2E_WEB_ORIGIN: WEB_URL },
    },
    {
      command: `npm --prefix ../frontend run build && npm --prefix ../frontend run preview -- --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: WEB_URL,
      timeout: 180_000,
      reuseExistingServer: false,
      env: { VITE_API_URL: API_URL },
    },
  ],
});
