import path from "node:path"
import { fileURLToPath } from "node:url"

import { defineConfig, devices } from "@playwright/test"

const currentFilePath = fileURLToPath(import.meta.url)
const currentDir = path.dirname(currentFilePath)
const fullstackDir = path.resolve(currentDir, "..")
const backendScript = path.resolve(fullstackDir, "tests/e2e_tests/start_backend_e2e.sh")
const frontendScript = path.resolve(fullstackDir, "tests/e2e_tests/start_frontend_e2e.sh")

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ["line"],
    ["html", { open: "never", outputFolder: path.resolve(fullstackDir, "runtime/test_results/e2e_tests/html-report") }],
    ["json", { outputFile: path.resolve(fullstackDir, "runtime/test_results/e2e_tests/report.json") }],
  ],
  use: {
    baseURL: "http://127.0.0.1:4174",
    headless: true,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  outputDir: path.resolve(fullstackDir, "runtime/test_results/e2e_tests/artifacts"),
  webServer: [
    {
      command: `bash "${backendScript}"`,
      url: "http://127.0.0.1:8001/api/v1/system/health/",
      reuseExistingServer: !process.env.CI,
      stdout: "pipe",
      stderr: "pipe",
      timeout: 120 * 1000,
    },
    {
      command: `bash "${frontendScript}"`,
      url: "http://127.0.0.1:4174/login",
      reuseExistingServer: !process.env.CI,
      stdout: "pipe",
      stderr: "pipe",
      timeout: 120 * 1000,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 960 },
      },
    },
  ],
})
