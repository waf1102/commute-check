import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'phone', use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' } }
  ],
  webServer: [
    {
      command: 'python3 -m uvicorn tests.browser_server:app --host 127.0.0.1 --port 8001',
      cwd: '..',
      url: 'http://127.0.0.1:8001/health',
      reuseExistingServer: false
    },
    {
      command: 'npm run build && node build',
      url: 'http://127.0.0.1:4173',
      env: {
        BACKEND_URL: 'http://127.0.0.1:8001',
        HOST: '127.0.0.1',
        PORT: '4173',
        ORIGIN: 'http://127.0.0.1:4173'
      },
      reuseExistingServer: false
    }
  ]
});
