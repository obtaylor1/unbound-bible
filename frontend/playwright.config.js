import { defineConfig, devices } from '@playwright/test'
import process from 'node:process'

import { parsePort, shellQuote } from './playwright.runtime.js'

const externalBaseURL = process.env.E2E_BASE_URL
const localBaseURL = 'http://127.0.0.1:4173'
const localApiPort = parsePort(process.env.E2E_API_PORT || '8011')
const localApiURL = `http://127.0.0.1:${localApiPort}`
const e2ePython = process.env.E2E_PYTHON || 'python3'

const localWebServers = [
  {
    command: `${shellQuote(e2ePython)} ../backend/tests/run_e2e_server.py --port ${localApiPort}`,
    url: `${localApiURL}/api/v1/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      ...process.env,
      ENVIRONMENT: 'test',
      JWT_SECRET_KEY: 'playwright-only-secret-with-at-least-32-characters',
      AUTH_RATE_LIMIT: '1000',
    },
  },
  {
    command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4173',
    url: localBaseURL,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      ...process.env,
      VITE_API_TARGET: localApiURL,
    },
  },
]

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: [['line'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: externalBaseURL || localBaseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: externalBaseURL ? undefined : localWebServers,
  projects: [
    {
      name: 'desktop-chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'tablet-chromium',
      use: {
        ...devices['iPad (gen 7) landscape'],
        browserName: 'chromium',
      },
    },
    {
      name: 'tablet-portrait-768',
      use: {
        ...devices['iPad (gen 7)'],
        browserName: 'chromium',
        viewport: { width: 768, height: 1024 },
      },
    },
    {
      name: 'mobile-chromium',
      use: {
        ...devices['iPhone 13'],
        browserName: 'chromium',
        viewport: { width: 390, height: 844 },
      },
    },
    {
      name: 'mobile-320',
      use: {
        ...devices['iPhone SE'],
        browserName: 'chromium',
        viewport: { width: 320, height: 568 },
      },
    },
  ],
})
