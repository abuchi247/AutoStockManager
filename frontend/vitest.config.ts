import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Playwright owns the e2e directory; Vitest only runs unit/component tests.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules/**', '.next/**', 'e2e/**'],
  },
});
