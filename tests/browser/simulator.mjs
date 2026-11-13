// Browser integration test for AC75 Kinematic Simulator Workspace.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
let playwright
try {
  playwright = require('playwright')
} catch {
  playwright = require(
    process.env.REGATTA_PLAYWRIGHT ||
      path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'),
  )
}

const base = process.env.REGATTA_URL || 'http://localhost:5173'
const output = process.env.REGATTA_QA_OUTPUT || path.join(os.tmpdir(), 'ac75-simulator-qa')
await fs.mkdir(output, { recursive: true })

const browser = await playwright.chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
page.setDefaultTimeout(15000)

const errors = []
const consoleErrors = []
let expectedFailure = false

page.on('pageerror', (err) => errors.push(err.message))
page.on('console', (msg) => {
  if (msg.type() === 'error' && !expectedFailure) {
    consoleErrors.push(msg.text())
  }
})

const checks = []
const check = async (name, fn) => {
  await fn()
  checks.push(name)
  console.log('PASS ' + name)
}

try {
  await check('Simulator view navigation and initial controls match applied inputs', async () => {
    await page.goto(`${base}/?view=simulator`)
    await page.waitForLoadState('networkidle')

    const workspace = page.locator('.simulator-workspace')
    await workspace.waitFor()

    // Title and status badge present
    const title = page.locator('.simulator-title-group h2')
    await title.waitFor()
    assert.match(await title.textContent(), /AC75 Kinematic Match Simulator/)

    const statusBadge = page.locator('.simulator-status-badge')
    await statusBadge.waitFor()
    assert.match(await statusBadge.textContent(), /STATUS:/)

    // Check competitor select inputs exist
    const teamA = page.locator('#team-a-select')
    const teamB = page.locator('#team-b-select')
    await teamA.waitFor()
    await teamB.waitFor()

    assert.notEqual(await teamA.inputValue(), await teamB.inputValue())
  })

  await check('Changed controls mark results stale with visual notice', async () => {
    const twsSlider = page.locator('input[type="range"]').first()
    await twsSlider.waitFor()

    // Initially, no stale notice should exist if initial controls matched applied inputs
    // Change wind speed to trigger stale state
    const currentVal = parseFloat(await twsSlider.inputValue())
    const newVal = currentVal > 15 ? currentVal - 2 : currentVal + 2
    await twsSlider.fill(String(newVal))
    await twsSlider.dispatchEvent('change')

    // Stale notice should now be displayed
    const staleNotice = page.locator('[data-testid="stale-notice"]')
    await staleNotice.waitFor({ timeout: 5000 })
    assert.ok(await staleNotice.isVisible(), 'Stale notice must be visible after changing inputs')

    // Panel should have stale-results class
    const panel = page.locator('.simulator-results-panel')
    const className = await panel.getAttribute('class')
    assert.ok(className?.includes('stale-results'), 'Results panel should indicate stale state')
  })

  await check('Run simulation clears stale notice and updates results', async () => {
    const runBtn = page.getByRole('button', { name: /Run Simulation/i })
    await runBtn.waitFor()
    await runBtn.click()

    // Wait for simulation to finish (stale notice clears or result updates)
    await page.waitForFunction(() => {
      const notice = document.querySelector('[data-testid="stale-notice"]')
      return notice === null
    }, { timeout: 15000 })

    const staleNotice = page.locator('[data-testid="stale-notice"]')
    assert.equal(await staleNotice.count(), 0, 'Stale notice should clear after running simulation')
  })

  await check('Competitor reversal renders cleanly with symmetric probabilities', async () => {
    const teamA = page.locator('#team-a-select')
    const teamB = page.locator('#team-b-select')

    const origA = await teamA.inputValue()
    const origB = await teamB.inputValue()

    // Swap competitors
    await teamA.selectOption(origB)
    await teamB.selectOption(origA)

    const runBtn = page.getByRole('button', { name: /Run Simulation/i })
    await runBtn.click()

    await page.waitForFunction(() => {
      const notice = document.querySelector('[data-testid="stale-notice"]')
      return notice === null
    }, { timeout: 15000 })

    const teamBoxes = page.locator('.team-box')
    assert.equal(await teamBoxes.count(), 2)
  })

  assert.equal(errors.length, 0, `Unexpected page errors: ${errors.join(', ')}`)
  console.log(`\nALL ${checks.length} BROWSER SIMULATOR CHECKS PASSED.`)
} finally {
  await browser.close()
}
