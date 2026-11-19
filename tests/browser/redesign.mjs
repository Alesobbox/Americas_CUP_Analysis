import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { chromium } from 'playwright'

const base = process.env.REGATTA_URL || 'http://127.0.0.1:5173'
const output = process.env.REGATTA_QA_OUTPUT || path.join(os.tmpdir(), 'ac40-redesign-qa')
await fs.mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
await context.addInitScript(() => localStorage.setItem('regatta_view_mode', 'grid'))
const page = await context.newPage()
page.setDefaultTimeout(15000)
const errors = [],
  requests = [],
  responses = [],
  checks = []
page.on('pageerror', (error) => errors.push(error.message))
page.on('request', (request) => requests.push(request.url()))
page.on('response', (response) => {
  if (response.ok()) responses.push(response.url())
})
const nav = (name) =>
  page
    .getByRole('navigation', { name: 'Main Navigation' })
    .getByRole('button', { name, exact: true })
    .click()
const check = async (name, run) => {
  await run()
  checks.push(name)
  console.log('PASS ' + name)
}
const load = async () => {
  await page.goto(base + '/?race=naples_pr1&t=240')
  await page.locator('.fleet-table tbody tr').first().waitFor()
}
try {
  await load()
  await check('local font and course-first desktop layout', async () => {
    await page.evaluate(() => document.fonts.ready)
    assert.ok(await page.evaluate(() => document.fonts.check('500 16px "DM Sans"')))
    assert.ok(requests.some((url) => url.endsWith('/fonts/dm-sans-variable.ttf')))
    assert.equal(
      requests.some((url) => /fonts\.googleapis|fonts\.gstatic|tile\.openstreetmap/.test(url)),
      false
    )
    const map = await page.locator('.map-viewport-frame').boundingBox()
    const fleet = await page.locator('.race-status-leaderboard-card').boundingBox()
    const transport = await page.locator('.transport-controls-row').boundingBox()
    assert.ok(map.width > fleet.width * 2)
    assert.ok(transport.y >= map.y + map.height)
  })
  await check('race library loads one compact index and no other race telemetry', async () => {
    requests.length = 0
    responses.length = 0
    await page.getByRole('button', { name: 'Race library', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Choose race' })
    await dialog.getByRole('img').first().waitFor()
    assert.equal(await dialog.locator('.race-option').count(), 28)
    assert.equal(requests.filter((url) => url.includes('/data/replays/')).length, 0)
    assert.equal(
      requests.filter((url) => url.endsWith('/data/presentation/race_previews.json')).length,
      1
    )
    assert.equal(
      responses.filter((url) => url.endsWith('/data/presentation/race_previews.json')).length,
      1
    )
    const search = dialog.getByRole('searchbox')
    await search.fill('Cagliari')
    assert.equal(await dialog.locator('.race-option').count(), 9)
    await search.fill('no-such-race')
    await dialog.getByText('No races match', { exact: false }).waitFor()
    await search.fill('')
    const close = dialog.getByRole('button', { name: 'Close race picker' })
    await close.focus()
    await page.keyboard.press('Shift+Tab')
    assert.equal(
      await dialog
        .locator('.race-option')
        .last()
        .evaluate((element) => element === document.activeElement),
      true
    )
    await page.keyboard.press('Tab')
    assert.equal(await close.evaluate((element) => element === document.activeElement), true)
    await page.keyboard.press('Escape')
    assert.equal(
      await page
        .getByRole('button', { name: 'Race library', exact: true })
        .evaluate((element) => element === document.activeElement),
      true
    )
  })
  await check('missing course artwork retains the searchable race catalog', async () => {
    await page.route('**/data/presentation/race_previews.json', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
    )
    await load()
    await page.getByRole('button', { name: 'Race library', exact: true }).click()
    assert.equal(await page.locator('.race-option').count(), 28)
    await page
      .getByRole('dialog', { name: 'Choose race' })
      .getByText('Available in replay', { exact: true })
      .first()
      .waitFor()
    await page.keyboard.press('Escape')
    await page.unroute('**/data/presentation/race_previews.json')
  })
  await check('settings traps focus and restores its opener', async () => {
    const opener = page.getByRole('button', { name: 'Settings', exact: true })
    await opener.click()
    const dialog = page.getByRole('dialog', { name: 'Dashboard settings' })
    const close = dialog.getByRole('button', { name: 'Close settings' })
    await close.focus()
    await page.keyboard.press('Shift+Tab')
    assert.equal(
      await dialog.getByRole('checkbox').evaluate((element) => element === document.activeElement),
      true
    )
    await page.keyboard.press('Tab')
    assert.equal(await close.evaluate((element) => element === document.activeElement), true)
    await page.keyboard.press('Escape')
    assert.equal(await opener.evaluate((element) => element === document.activeElement), true)
  })
  await check('fullscreen retains playback and exits cleanly', async () => {
    await page.getByRole('button', { name: 'Toggle fullscreen', exact: true }).click()
    await page.waitForFunction(() => !!document.fullscreenElement)
    await page.getByRole('slider', { name: 'Race playhead', exact: true }).waitFor()
    await page.getByRole('button', { name: 'Reset view', exact: true }).click()
    await page.getByRole('button', { name: 'Toggle fullscreen', exact: true }).click()
    await page.waitForFunction(() => !document.fullscreenElement)
  })
  for (const [width, height] of [
    [1440, 1000],
    [1280, 720],
    [768, 1024],
    [390, 844],
    [320, 740],
  ]) {
    await check('all workspaces fit at ' + width + '×' + height, async () => {
      await page.setViewportSize({ width, height })
      for (const view of ['Replay', 'Analysis', 'Compare', 'Reports']) {
        await nav(view)
        if (view === 'Analysis')
          await page.getByRole('heading', { name: 'Race metrics', exact: true }).waitFor()
        await page.evaluate(() => scrollTo(0, 0))
        assert.ok(
          await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
          view + ' overflows at ' + width
        )
        await page.screenshot({
          path: path.join(output, view.toLowerCase() + '-' + width + '.png'),
        })
      }
    })
  }
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(output, 'results.json'), JSON.stringify({ checks, errors }, null, 2))
  console.log(checks.length + ' redesign browser checks passed; screenshots in ' + output)
} finally {
  await browser.close()
}
