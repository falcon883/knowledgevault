import js from '@eslint/js';
import globals from 'globals';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';

// KV-39 — ESLint flat config for the frontend.
// react/prop-types is off deliberately: this codebase passes props
// without PropTypes throughout (React 18, internal app, no library
// surface), and the rule would flag every component without adding
// safety the test suite does not already give.
export default [
  { ignores: ['dist', 'node_modules'] },
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    settings: { react: { version: 'detect' } },
    plugins: { react, 'react-hooks': reactHooks },
    rules: {
      ...js.configs.recommended.rules,
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
    },
  },
  {
    // Test files also use Vitest globals (describe/it/expect/vi).
    files: ['**/*.test.{js,jsx}', 'src/test/**'],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node, describe: 'readonly', it: 'readonly', test: 'readonly', expect: 'readonly', vi: 'readonly', beforeEach: 'readonly', afterEach: 'readonly' },
    },
  },
];
