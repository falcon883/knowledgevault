import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// KV-39 — Vitest + React Testing Library setup.
// Tests live next to the code they cover (*.test.js / *.test.jsx) and run
// in jsdom, so component tests see the same DOM APIs the browser gives
// the app (localStorage, location.hash, history).
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
  },
});
