import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { chromium } from 'playwright'

const base = process.env.REGATTA_URL || 'http://127.0.0.1:5173'
const output = process.env.REGATTA_QA_OUTPUT || path.join(os.tmpdir(), 'ac40-browser-feedback')
await fs.mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 775, height: 704 } })
await page.addInitScript(() => localStorage.setItem('regatta_view_mode', 'grid'))
page.setDefaultTimeout(15000)
const errors = [], checks = []
page.on('pageerror', (error) => errors.push(error.message))
const check = async (name, fn) => { await fn(); checks.push(name); console.log('PASS ' + name) }
const nav = (name) => page.getByRole('navigation', { name: 'Main Navigation' }).getByRole('button', { name, exact: true }).click()
const canvas = page.locator('canvas[aria-label="Live vessel positions"]')
try {
  await page.goto(base + '/?race=naples_pr1&t=240')
  await page.locator('.fleet-table tbody tr').first().waitFor()
  await check('boats start enlarged with readable team and VMG labels at course zoom', async () => {
    assert.equal(await page.getByLabel('Course boat size', { exact: true }).inputValue(), 'enhanced')
    await page.waitForFunction(() => document.querySelectorAll('.course-boat-label').length === 9)
    assert.equal(await page.locator('.course-label-vmg').count(), 9)
    const rectangles = await page.locator('.course-boat-label').evaluateAll((elements) => elements.map((element) => {
      const r = element.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }
    }))
    for (let a = 0; a < rectangles.length; a++) {
      assert.ok(rectangles[a].height >= 40)
      for (let b = a + 1; b < rectangles.length; b++) {
        const left = rectangles[a], right = rectangles[b]
        const area = Math.max(0, Math.min(left.x + left.width, right.x + right.width) - Math.max(left.x, right.x)) * Math.max(0, Math.min(left.y + left.height, right.y + right.height) - Math.max(left.y, right.y))
        assert.ok(area < 1, 'Team labels overlap')
      }
    }
    await page.getByLabel('Course boat size', { exact: true }).selectOption('true')
    assert.equal(await page.locator('.course-boat-label').count(), 9)
    await page.getByLabel('Course boat size', { exact: true }).selectOption('enhanced')
  })
  await check('switching between Grid and Map preserves scale, center and the visible fleet', async () => {
    const before = JSON.parse(await canvas.getAttribute('data-viewport'))
    await page.getByRole('button', { name: 'OpenStreetMap view', exact: true }).click()
    await page.locator('.maplibregl-canvas').waitFor()
    await page.waitForFunction((scale) => {
      const raw = document.querySelector('canvas[aria-label="Live vessel positions"]')?.getAttribute('data-viewport')
      return raw && Math.abs(JSON.parse(raw).scale / scale - 1) < .01
    }, before.scale)
    await page.waitForTimeout(750)
    const after = JSON.parse(await canvas.getAttribute('data-viewport'))
    assert.ok(Math.abs(after.scale / before.scale - 1) < .01, 'Map must retain Grid pixels per metre')
    assert.ok(Math.hypot(after.center[0] - before.center[0], after.center[1] - before.center[1]) < 2, 'Map must retain the course center')
    assert.equal(await page.locator('.course-boat-label').count(), 9)
    await page.screenshot({ path: path.join(output, 'readable-map-775.png'), fullPage: true })
    await page.getByRole('button', { name: 'Technical 2D metric grid view', exact: true }).click()
    assert.equal(await page.locator('.course-boat-label').count(), 9)
  })
  await check('highlighted trails remain independent of full-fleet visibility', async () => {
    await page.getByLabel('Trail visibility', { exact: true }).selectOption('highlighted')
    assert.equal(await canvas.getAttribute('data-trail-scope'), 'highlighted')
    assert.equal(await canvas.getAttribute('data-visible-boat'), 'all')
    await page.locator('.course-boat-label').filter({ hasText: 'ITA G' }).click()
    await page.getByText('Trail settings & boat B', { exact: true }).click()
    await page.getByLabel('Highlighted comparison boat', { exact: true }).selectOption({ label: 'NZL B' })
    const highlighted = (await canvas.getAttribute('data-highlighted-boats')).split(',')
    assert.equal(new Set(highlighted).size, 2)
    assert.equal(await page.locator('.course-boat-label[aria-pressed=true]').count(), 2)
    assert.equal(await page.locator('.fleet-table tbody tr').count(), 9)
    await page.getByLabel('Course trail colour', { exact: true }).selectOption('vmg')
    await page.getByLabel('VMG labels', { exact: true }).uncheck()
    assert.equal(await page.locator('.course-label-vmg').count(), 0)
    await page.getByLabel('VMG labels', { exact: true }).check()
    await page.getByLabel('Trail visibility', { exact: true }).selectOption('none')
    assert.equal(await canvas.getAttribute('data-trail-scope'), 'none')
    assert.equal(await page.locator('.course-boat-label').count(), 9)
    await page.getByLabel('Trail visibility', { exact: true }).selectOption('highlighted')
    await page.screenshot({ path: path.join(output, 'highlighted-trails-775.png'), fullPage: true })
  })
  await check('reports and analysis use plain result wording without changing evidence', async () => {
    await nav('Reports')
    await page.getByRole('table', { name: 'Race report metrics' }).waitFor()
    await page.getByRole('columnheader', { name: 'Result', exact: true }).waitFor()
    assert.equal(/reconstruct/i.test(await page.locator('body').innerText()), false)
    await nav('Analysis')
    await page.getByRole('heading', { name: 'Race metrics', exact: true }).waitFor()
    assert.equal(/reconstruct/i.test(await page.locator('body').innerText()), false)
    await page.getByRole('tab', { name: 'Historical view', exact: true }).click()
    await page.getByRole('heading', { name: 'Manoeuvre distributions', exact: true }).waitFor()
    assert.equal(/reconstruct/i.test(await page.locator('body').innerText()), false)
    await page.getByRole('tab', { name: 'Race report', exact: true }).click()
  })
  await check('selected profile and peer baseline have explicit signed differences', async () => {
    const controls = page.getByRole('group', { name: 'Inspect a performance dimension' })
    assert.equal(await controls.getByRole('button').count(), 6)
    await page.getByRole('group', { name: 'Performance comparison legend' }).waitFor()
    const available = page.locator('.performance-difference-value').filter({ hasText: /[+−]\d/ })
    assert.ok(await available.count() > 0)
    await page.getByRole('button', { name: 'Inspect Downwind course VMG', exact: true }).click()
    await page.getByRole('region', { name: 'Pinned performance evidence' }).waitFor()
    await page.screenshot({ path: path.join(output, 'performance-differences-775.png'), fullPage: true })
  })
  await check('unsupported direction is explained before generation with an explicit supported action', async () => {
    await nav('Forecast')
    await page.getByRole('tab', { name: 'Before the start', exact: true }).click()
    await page.getByLabel('Pre-race conditions', { exact: true }).selectOption('scenario')
    await page.getByLabel('Pre-race wind speed', { exact: true }).fill('13')
    await page.getByLabel('Pre-race wind direction offset', { exact: true }).fill('17')
    assert.equal(await page.getByRole('button', { name: 'Generate forecast', exact: true }).isDisabled(), true)
    await page.getByRole('button', { name: 'Use 0° offset', exact: true }).click()
    assert.equal(await page.getByLabel('Pre-race wind direction offset', { exact: true }).inputValue(), '0')
    const invalid = await page.request.post(base + '/api/forecast-scenarios', { data: { race_id: 'naples_pr1', tws_kt: 13, direction_offset_deg: 17 } })
    assert.equal(invalid.status(), 422)
  })
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(output, 'results.json'), JSON.stringify({ checks, errors }, null, 2))
  console.log(checks.length + ' feedback browser checks passed; captures in ' + output)
} finally { await browser.close() }
