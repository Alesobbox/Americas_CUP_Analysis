// Deterministic browser fixtures validate interface behavior, not forecast accuracy.
// They intercept only this browser context and never write public prediction data.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
let playwright
try { playwright = require('playwright') }
catch { playwright = require(process.env.REGATTA_PLAYWRIGHT || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')) }
const base = process.argv.find((arg) => arg.startsWith('--url='))?.slice(6) || process.env.REGATTA_URL || 'http://127.0.0.1:5173'
const output = path.resolve('.forecast/qa/forecast-browser')
await fs.mkdir(output, { recursive: true })
const replay = JSON.parse(await fs.readFile('public/data/replays/naples_pr1.json', 'utf8'))
const ids = replay.competitors.map((boat) => boat.id)
const gun = replay.chronology.gun_time
const reference = { model_ref: 'synthetic-browser-fixture', source_manifest_hash: 'fixture-source', scenario_hash: 'fixture-baseline' }
const header = { schema_version: 'prediction-1', race_id: replay.id, boat_ids: ids, boat_class: 'AC40', ...reference,
  status_dictionary: ['available', 'estimated', 'gate_ambiguous', 'unavailable'], method_and_assumption_refs: ['Synthetic browser fixture. No calibration evidence.'] }
const live = {
  state_timestamps_ms: [gun, gun + 10000], published_at_ms: [gun + 6000, gun + 16000], progress_band: ['early', 'early'],
  win_prob_by_boat: Object.fromEntries(ids.map((id, i) => [id, i === 0 ? [.6, .8] : [.3 / (ids.length - 1), .1 / (ids.length - 1)]])),
  no_finisher_prob: [.1, .1], status_code: [0, 1], source_age_ms_by_boat: Object.fromEntries(ids.map((id) => [id, [0, 3000]])),
  position_uncertainty_summary_by_boat: Object.fromEntries(ids.map((id) => [id, [2, 8]])),
  quality_code_by_boat: Object.fromEntries(ids.map((id) => [id, ['fresh', 'estimated']])), numerical_error: [.0069, .0069],
}
const baseline = { header, pre_race: { status: 'available', nonfinish_score: 'N', expected_position_by_boat: Object.fromEntries(ids.map((id) => [id, 1.4])) }, live }
const preset = { ...baseline, header: { ...header, scope: 'pre_race', scenario_hash: 'fixture-preset', conditions: { tws_kt: 12, direction_offset_deg: 0 } },
  pre_race: { ...baseline.pre_race, expected_position_by_boat: Object.fromEntries(ids.map((id) => [id, 2.8])) } }
const index = { schema_version: 'prediction-index-1', races: [{ race_id: replay.id, path: 'race.json', ...reference,
  presets: [{ id: 'tws12_dir0', scope: 'pre_race', tws_kt: 12, direction_offset_deg: 0, path: 'scenarios/preset12_0.json', ...reference, scenario_hash: 'fixture-preset' }] }], cup_path: 'cup_2027.json' }
const teams = ['NZL', 'GBR', 'ITA', 'SUI', 'FRA', 'USA', 'AUS'].map((id) => ({ id, name: id }))
const cup = { header: { schema_version: 'cup-1', boat_class: 'AC75', ...reference }, status: 'estimated', teams,
  scenario_envelope_by_team: Object.fromEntries(teams.map((team) => [team.id, { lower: .01, upper: .3 }])), evaluated_scenarios: ['fixture-1'] }
const browser = await playwright.chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1280, height: 720 } })
await context.addInitScript(() => localStorage.setItem('regatta_view_mode', 'grid'))
const page = await context.newPage()
page.setDefaultTimeout(15000)
const errors = []
page.on('pageerror', (error) => errors.push(error.message))
let htmlIndex = false
let delayPreset = false
const routes = { 'index.json': index, 'race.json': baseline, 'cup_2027.json': cup, 'scenarios/preset12_0.json': preset }
await context.route('**/data/predictions/**', async (route) => {
  const file = new URL(route.request().url()).pathname.replace('/data/predictions/', '')
  if (file === 'index.json' && htmlIndex) return route.fulfill({ contentType: 'text/html', body: '<html>SPA fallback</html>' })
  if (file.startsWith('scenarios/') && delayPreset) await new Promise((resolve) => setTimeout(resolve, 150))
  return route.fulfill({ contentType: 'application/json', body: JSON.stringify(routes[file] ?? {}) })
})
const checks = []
const check = async (name, fn) => { await fn(); checks.push(name); console.log('PASS ' + name) }
const nav = (name) => page.getByRole('navigation', { name: 'Main Navigation' }).getByRole('button', { name, exact: true })
const liveCard = () => page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Win this race at the playhead', exact: true }) })
const preCard = () => page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Expected finishing position', exact: true }) })
const blur = () => page.evaluate(() => document.activeElement?.blur())

try {
  await check('key 5 opens exactly three forecast outputs and shows evidence quality', async () => {
    await page.goto(`${base}/?race=${replay.id}&t=7`)
    await page.getByRole('banner').waitFor()
    await blur()
    await page.keyboard.press('5')
    await page.getByRole('heading', { name: 'Forecast', exact: true }).waitFor()
    await liveCard().getByText('60.0%', { exact: true }).waitFor()
    assert.equal(await page.locator('.forecast-grid>article').count(), 3)
    assert.equal(await nav('Forecast').getAttribute('aria-current'), 'page')
    await page.getByText('calibration has not been established', { exact: false }).waitFor()
    await liveCard().getByText('Method and evidence', { exact: true }).click()
    await liveCard().getByText('Input: fixture-source', { exact: false }).waitFor()
  })

  await check('selected boat, backseeking and publication boundaries preserve causal output', async () => {
    await page.getByRole('combobox', { name: 'Forecast selected boat' }).selectOption(ids[1])
    assert.equal(await liveCard().locator('tbody tr[aria-selected="true"] th').innerText(), replay.competitors[1].team_code)
    const slider = page.getByRole('slider', { name: 'Forecast race playhead' })
    await slider.focus()
    await slider.press('End')
    await liveCard().getByText('80.0%', { exact: true }).waitFor()
    await slider.press('Home')
    await liveCard().getByText('No forecast had been published at this playhead.', { exact: true }).waitFor()
    assert.equal(await liveCard().getByText('60.0%', { exact: true }).count(), 0)
    assert.equal(await liveCard().getByText('80.0%', { exact: true }).count(), 0)
  })

  await check('exact custom conditions lazy-load only pre-race output and hide stale ranks immediately', async () => {
    await page.getByRole('combobox', { name: 'Pre-race conditions' }).selectOption('scenario')
    await preCard().getByText('2.80', { exact: true }).first().waitFor()
    await page.getByRole('spinbutton', { name: 'Pre-race wind speed' }).fill('12.1')
    await preCard().getByText('No supported pre-race artifact exists', { exact: false }).waitFor()
    assert.equal(await preCard().getByText('2.80', { exact: true }).count(), 0)
    await liveCard().getByText('No forecast had been published at this playhead.', { exact: true }).waitFor()
    await page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Win the whole America’s Cup', exact: true }) }).getByText('AUS', { exact: true }).waitFor()
    delayPreset = true
    await page.getByRole('spinbutton', { name: 'Pre-race wind speed' }).fill('12')
    await preCard().getByText('2.80', { exact: true }).first().waitFor()
    await page.getByRole('spinbutton', { name: 'Pre-race wind direction offset' }).fill('15')
    assert.equal(await preCard().getByText('2.80', { exact: true }).count(), 0)
    await page.getByRole('combobox', { name: 'Pre-race conditions' }).selectOption('recorded')
    await preCard().getByText('1.40', { exact: true }).first().waitFor()
  })

  await check('typing, focused controls and open modal dialogs block global navigation shortcuts', async () => {
    await page.getByRole('combobox', { name: 'Pre-race conditions' }).selectOption('scenario')
    const wind = page.getByRole('spinbutton', { name: 'Pre-race wind speed' })
    await wind.focus()
    await page.keyboard.press('4')
    assert.equal(await nav('Forecast').getAttribute('aria-current'), 'page')
    await nav('Forecast').focus()
    await page.keyboard.press('1')
    assert.equal(await nav('Forecast').getAttribute('aria-current'), 'page')
    await page.getByRole('button', { name: 'Settings', exact: true }).click()
    await page.getByRole('dialog', { name: 'Dashboard settings' }).waitFor()
    await blur()
    await page.keyboard.press('1')
    assert.equal(await nav('Forecast').getAttribute('aria-current'), 'page')
    await page.getByRole('button', { name: 'Close settings' }).click()
    await blur()
    await page.keyboard.press('1')
    await page.locator('canvas[aria-label="Live vessel positions"]').waitFor()
    await blur()
    await page.keyboard.press('5')
    await page.getByRole('heading', { name: 'Forecast', exact: true }).waitFor()
  })

  await check('changing race resets scenario selection and clears prior field values', async () => {
    await page.locator('.header-dropdown-container').first().getByRole('button').first().click()
    await page.locator('.hdr-dropdown-popover .popover-item').filter({ hasText: 'Match Race Final' }).first().click()
    await page.getByRole('heading', { name: 'Forecast', exact: true }).waitFor()
    await liveCard().getByText('There is no forecast artifact for this race.', { exact: true }).waitFor()
    assert.equal(await page.getByRole('combobox', { name: 'Pre-race conditions' }).inputValue(), 'recorded')
    assert.equal(await liveCard().getByText('80.0%', { exact: true }).count(), 0)
    assert.equal(await liveCard().getByText('60.0%', { exact: true }).count(), 0)
  })

  await check('HTML artifact routing fails closed with three visible unavailable cards', async () => {
    htmlIndex = true
    await page.goto(`${base}/?race=${replay.id}&view=forecast&t=7`)
    await page.getByRole('heading', { name: 'Forecast', exact: true }).waitFor()
    await liveCard().getByText('Forecast unavailable: artifact did not return JSON', { exact: true }).waitFor()
    assert.equal(await page.locator('.forecast-grid>article').count(), 3)
    assert.equal(await page.locator('.forecast-grid .forecast-status').filter({ hasText: 'Unavailable' }).count(), 3)
    assert.equal(await liveCard().getByText('60.0%', { exact: true }).count(), 0)
    htmlIndex = false
  })

  for (const [width, height] of [[1586, 992], [1280, 720], [390, 844]]) {
    await check(`Forecast responsive layout ${width}×${height}`, async () => {
      await page.setViewportSize({ width, height })
      await page.goto(`${base}/?race=${replay.id}&view=forecast&t=7`)
      await liveCard().getByText('60.0%', { exact: true }).waitFor()
      assert.equal(await page.locator('.forecast-grid>article').count(), 3)
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)
      assert.equal(overflow, false, 'Forecast should not overflow the viewport')
      await page.screenshot({ path: path.join(output, `forecast-fixture-${width}.png`), fullPage: true })
    })
  }
  if (process.argv.includes('--real')) {
    await check('real exported artifacts load with complete fields and explicit evidence limitations', async () => {
      await context.unroute('**/data/predictions/**')
      const response = await page.request.get(`${base}/data/predictions/index.json`)
      assert.equal(response.ok(), true)
      assert.match(response.headers()['content-type'], /json/)
      const exported = await response.json()
      assert.equal(exported.schema_version, 'prediction-index-1')
      assert.equal(exported.races.length, 28)
      assert.ok(exported.races.some((entry) => entry.race_id === replay.id))
      await page.setViewportSize({ width: 1280, height: 720 })
      await page.goto(`${base}/?race=${replay.id}&view=forecast&t=7`)
      await page.getByRole('heading', { name: 'Forecast', exact: true }).waitFor()
      await page.waitForFunction(() => [...document.querySelectorAll('.forecast-card')].length === 3 && [...document.querySelectorAll('.forecast-card')].every((card) => !card.textContent.includes('Loading the')))
      assert.equal(await page.locator('.forecast-grid>article').count(), 3)
      assert.equal(await page.getByText('Forecast unavailable:', { exact: false }).count(), 0, 'Exported contracts should parse successfully; evidence gaps have their own reasons')
      assert.equal(await liveCard().locator('tbody tr').count(), ids.length)
      assert.equal(await preCard().locator('tbody tr').count(), ids.length)
      assert.equal(await page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Win the whole America’s Cup', exact: true }) }).locator('tbody tr').count(), 7)
      await page.screenshot({ path: path.join(output, 'forecast-real-1280.png'), fullPage: true })
    })
    await check('all 28 real forecast fields retain every scheduled entry including source-only DNS', async () => {
      const exported = await (await page.request.get(`${base}/data/predictions/index.json`)).json()
      let scheduledEntries = 0
      for (const entry of exported.races) {
        assert.ok(Array.isArray(entry.boat_ids), 'Real index must pin the complete scheduled field')
        assert.ok(Array.isArray(entry.replay_boat_ids), 'Real index must pin its replay subset')
        await page.goto(`${base}/?race=${entry.race_id}&view=forecast&t=7`)
        await page.getByRole('heading', { name: 'Forecast', exact: true }).waitFor()
        await page.waitForFunction(() => !document.body.textContent.includes('Loading the'))
        assert.equal(await page.getByText('Forecast unavailable:', { exact: false }).count(), 0, `Contract failure for ${entry.race_id}`)
        assert.equal(await liveCard().locator('tbody tr').count(), entry.boat_ids.length, `Live field for ${entry.race_id}`)
        assert.equal(await preCard().locator('tbody tr').count(), entry.boat_ids.length, `Pre-race field for ${entry.race_id}`)
        scheduledEntries += entry.boat_ids.length
      }
      assert.equal(scheduledEntries, 227, 'Forecast archive must retain all source scheduled boat-races')
    })
  }
  assert.deepEqual(errors, [])
  await fs.writeFile(path.join(output, 'results.json'), JSON.stringify({ data: process.argv.includes('--real') ? 'synthetic route fixtures and a separate real-artifact smoke check' : 'synthetic route fixtures only', checks, pageErrors: errors }, null, 2))
  console.log(`${checks.length} focused Forecast browser checks passed; captures and data provenance in ${output}`)
} finally {
  await context.close()
  await browser.close()
}
