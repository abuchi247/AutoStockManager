import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:3000';
const shouldStartFrontend = process.env.PLAYWRIGHT_SKIP_WEBSERVER !== 'true';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI
    ? [['line'], ['html', { open: 'never' }]]
    : 'list',
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      // Core business flows run once on a desktop viewport.
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      testIgnore: /performance-accessibility\.spec\.ts/,
    },
    {
      // Performance/accessibility checks run on representative desktop and
      // mobile viewports. Requirements: 19.7
      name: 'desktop-1440',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
      testMatch: /performance-accessibility\.spec\.ts/,
    },
    {
      name: 'mobile-393',
      use: { ...devices['Pixel 5'] },
      testMatch: /performance-accessibility\.spec\.ts/,
    },
  ],
  ...(shouldStartFrontend
    ? {
        webServer: {
          command: 'npm run start -- --hostname 127.0.0.1',
          url: baseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          env: {
            ...process.env,
            PORT: new URL(baseURL).port || '3000',
          },
        },
      }
    : {}),
});
