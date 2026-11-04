// Deterministic browser fixtures validate interface behavior, not forecast accuracy.
// They intercept only this browser context and never write public prediction data.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
let playwright
try { playwright = require('playwright') }
catch { playwright = require(process.env.REGATTA_PLAYWRIGHT || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')) }
const base = process.argv.find((arg) => arg.startsWith('--url='))?.slice(6) || process.env.REGATTA_URL || 'http://127.0.0.1:5173'
const output = path.resolve(process.argv.find((arg) => arg.startsWith('--output='))?.slice(9) || process.env.REGATTA_QA_OUTPUT || '.forecast/qa/forecast-browser')
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
const liveCard = () => page.locator('#forecast-panel-live article')
const preCard = () => page.locator('#forecast-panel-pre article')
const cupCard = () => page.locator('#forecast-panel-cup article')
const question = (name) => page.getByRole('tablist', { name: 'Forecast questions' }).getByRole('tab', { name, exact: true }).click()
const blur = () => page.evaluate(() => document.activeElement?.blur())
const boundText = (bound) => `${(bound.lower * 100).toFixed(1)}%–${(bound.upper * 100).toFixed(1)}%`
const countText = (record) => `${record.resolved_trials.toLocaleString('en-US')} resolved · ${record.unresolved_trials.toLocaleString('en-US')} unresolved of ${record.trials.toLocaleString('en-US')} trials`
let realCupArtifact = null

function checkScenarioMetadata(cupArtifact) {
  const evidence = cupArtifact.scenario_analysis
  assert.equal(evidence.schema_version, 'cup-scenarios-1')
  assert.equal(evidence.records.length, cupArtifact.evaluated_scenarios.length)
  assert.equal(evidence.records.length, evidence.build_budget.scenario_count)
  assert.ok(evidence.records.some((record) => record.scenario_id === evidence.baseline_scenario_id))
  assert.match(evidence.model_lineage.model_ref, /^[a-f0-9]{64}$/)
  assert.equal(evidence.model_lineage.model_ref, cupArtifact.header.model_ref)
  assert.equal(evidence.model_lineage.source_manifest_hash, cupArtifact.header.source_manifest_hash)
  assert.equal(evidence.model_lineage.training_cutoff_ms, Date.parse(`${evidence.model_lineage.training_before_day}T00:00:00Z`))
  for (const field of ['probabilities', 'win_prob_by_team']) assert.ok(Object.values(cupArtifact[field]).every((value) => value === null), 'Unconditional Cup point probabilities must remain unavailable')
  for (const record of evidence.records) {
    assert.ok(Number.isInteger(record.trials) && record.trials > 0)
    assert.equal(record.trials, evidence.build_budget.trials_per_scenario)
    assert.equal(record.seed, evidence.build_budget.seed)
    assert.equal(record.resolved_trials + record.unresolved_trials, record.trials)
    assert.equal(Object.values(record.resolved_win_counts).reduce((a, b) => a + b, 0), record.resolved_trials)
    assert.equal(Object.values(record.first_unresolved_stage_counts).reduce((a, b) => a + b, 0), record.unresolved_trials)
    assert.ok(Math.abs(record.resolved_fraction - record.resolved_trials / record.trials) < 1e-12)
    assert.ok(Math.abs(record.unresolved_fraction - record.unresolved_trials / record.trials) < 1e-12)
    assert.match(record.input_hash, /^[a-f0-9]{64}$/)
    assert.equal(record.model_ref, evidence.model_lineage.model_ref)
    assert.equal(record.source_manifest_hash, cupArtifact.header.source_manifest_hash)
    assert.ok(Math.abs(record.numerical_error.worst_case_95_half_width - 1.96 * Math.sqrt(.25 / record.trials)) < 1e-12)
    assert.match(record.numerical_error.scope, /integration only; excludes model\/rule/)
    for (const team of cupArtifact.teams) {
      assert.equal(record.rule_bounds[team.id].lower, record.resolved_win_counts[team.id] / record.trials)
      assert.equal(record.rule_bounds[team.id].upper, (record.resolved_win_counts[team.id] + record.unresolved_trials) / record.trials)
      if (record.unresolved_trials) assert.equal(record.probabilities[team.id], null)
    }
  }
  for (const team of cupArtifact.teams) {
    for (const side of ['lower', 'upper']) {
      const extreme = Math[side === 'lower' ? 'min' : 'max'](...evidence.records.map((record) => record.rule_bounds[team.id][side]))
      assert.ok(Math.abs(cupArtifact.scenario_envelope_by_team[team.id][side] - extreme) < .000050001)
      assert.deepEqual(evidence.extrema_by_team[team.id][`${side}_scenario_ids`], evidence.records.filter((record) => record.rule_bounds[team.id][side] === extreme).map((record) => record.scenario_id))
    }
  }
  return evidence
}

try {
  await check('key 5 opens three distinct forecast questions with one visible detail and keyboard navigation', async () => {
    await page.goto(`${base}/?race=${replay.id}&t=7`)
    await page.getByRole('banner').waitFor()
    await blur()
    await page.keyboard.press('5')
    await page.getByRole('heading', { name: 'Forecast', exact: true }).waitFor()
    await liveCard().getByText('60.0%', { exact: true }).waitFor()
    assert.equal(await page.locator('.forecast-grid article').count(), 3)
    assert.equal(await page.getByRole('article').count(), 1)
    assert.equal(await page.getByRole('tablist', { name: 'Forecast questions' }).getByRole('tab').count(), 3)
    assert.equal(await nav('Forecast').getAttribute('aria-current'), 'page')
    assert.equal(await page.locator('.forecast-evidence').count(), 0)
    await liveCard().getByText('Method and evidence', { exact: true }).click()
    await liveCard().getByText('Input: fixture-source', { exact: false }).waitFor()
    const liveTab = page.getByRole('tab', { name: 'Live race', exact: true })
    await liveTab.focus(); await liveTab.press('ArrowRight')
    await preCard().getByRole('heading', { name: 'Expected finishing position', exact: true }).waitFor()
    assert.equal(await page.getByRole('slider', { name: 'Forecast race playhead' }).count(), 0, 'Pre-race output has no live playhead control')
    await page.getByRole('tab', { name: 'Before the start', exact: true }).press('End')
    assert.equal(await page.getByRole('tab', { name: 'America’s Cup 2027', exact: true }).getAttribute('aria-selected'), 'true')
    await page.getByRole('tab', { name: 'America’s Cup 2027', exact: true }).press('Home')
    assert.equal(await liveTab.getAttribute('aria-selected'), 'true')
  })

  await check('legacy Cup scenario envelopes remain usable without inventing unavailable diagnostics', async () => {
    await question('America’s Cup 2027')
    const table = cupCard().getByRole('table', { name: 'Cup team bounds' })
    assert.equal(await table.locator('tbody tr').count(), teams.length)
    await cupCard().getByText('Scenario envelope', { exact: true }).waitFor()
    assert.equal(await cupCard().getByRole('combobox', { name: 'Cup scenario' }).count(), 0)
    assert.equal(await cupCard().getByText('Monte Carlo half-width:', { exact: false }).count(), 0)
    assert.equal(await table.locator('tbody tr').first().locator('td').innerText(), '1.0%–30.0%')
    assert.equal(await page.locator('.forecast-grid article').count(), 3)
  })

  await check('selected boat, backseeking and publication boundaries preserve causal output', async () => {
    await question('Live race')
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
    await question('Before the start')
    await page.getByRole('combobox', { name: 'Pre-race conditions' }).selectOption('scenario')
    await preCard().getByText('2.80', { exact: true }).first().waitFor()
    await page.getByRole('spinbutton', { name: 'Pre-race wind speed' }).fill('12.1')
    await preCard().getByText('Choose Generate forecast to prepare these exact conditions.', { exact: true }).waitFor()
    assert.equal(await preCard().getByText('2.80', { exact: true }).count(), 0)
    await question('Live race')
    await liveCard().getByText('No forecast had been published at this playhead.', { exact: true }).waitFor()
    await question('America’s Cup 2027')
    await cupCard().getByText('AUS', { exact: true }).waitFor()
    await question('Before the start')
    delayPreset = true
    await page.getByRole('spinbutton', { name: 'Pre-race wind speed' }).fill('12')
    await preCard().getByText('2.80', { exact: true }).first().waitFor()
    await page.getByRole('spinbutton', { name: 'Pre-race wind direction offset' }).fill('15')
    assert.equal(await preCard().getByText('2.80', { exact: true }).count(), 0)
    await page.getByRole('combobox', { name: 'Pre-race conditions' }).selectOption('recorded')
    await preCard().getByText('1.40', { exact: true }).first().waitFor()
  })

  await check('dashboard generation keeps exact conditions and explains unsupported directions before submission', async () => {
    await question('Before the start')
    await page.getByRole('combobox', { name: 'Pre-race conditions' }).selectOption('scenario')
    await page.getByRole('spinbutton', { name: 'Pre-race wind speed' }).fill('13.4')
    await page.getByRole('spinbutton', { name: 'Pre-race wind direction offset' }).fill('17')
    const generate = page.getByRole('button', { name: 'Generate forecast', exact: true })
    assert.equal(await generate.isDisabled(), true)
    await preCard().getByText('A direction response has not passed validation.', { exact: false }).waitFor()
    await page.getByRole('button', { name: 'Use 0° offset', exact: true }).click()
    assert.equal(await page.getByRole('spinbutton', { name: 'Pre-race wind direction offset' }).inputValue(), '0')
    const generated = structuredClone(preset)
    generated.header.conditions = { tws_kt: 13.4, direction_offset_deg: 0 }
    generated.header.scenario_hash = 'fixture-generated'
    generated.pre_race.expected_position_by_boat[ids[0]] = 2.33
    const generatedPath = 'scenarios/' + createHash('sha256').update(JSON.stringify(generated)).digest('hex') + '.json'
    const jobId = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
    let submitted = null
    const input = { race_id: replay.id, tws_kt: 13.4, direction_offset_deg: 0 }
    await page.route('**/api/forecast-scenarios', async (route) => {
      if (route.request().method() !== 'POST') return route.fallback()
      submitted = route.request().postDataJSON()
      routes[generatedPath] = generated
      index.races[0].presets.push({ id: 'generated13_4', scope: 'pre_race', tws_kt: 13.4, direction_offset_deg: 0, path: generatedPath, ...reference, scenario_hash: 'fixture-generated' })
      await route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ id: jobId, input, status: 'running', message: 'Preparing these exact conditions…' }) })
    })
    await page.route('**/api/forecast-scenarios/' + jobId, (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ id: jobId, input, status: 'complete', message: 'The exact forecast is ready.', path: generatedPath }) }))
    await generate.click()
    await preCard().getByText('2.33', { exact: true }).waitFor()
    assert.deepEqual(submitted, input)
    assert.equal(await preCard().locator('tbody tr').first().locator('td').first().innerText(), '2.33')
    await page.unroute('**/api/forecast-scenarios')
    await page.unroute('**/api/forecast-scenarios/' + jobId)
    await page.getByRole('combobox', { name: 'Pre-race conditions' }).selectOption('recorded')
  })

  await check('editing conditions during generation permits retrying the original conditions', async () => {
    await question('Before the start')
    await page.getByRole('combobox', { name: 'Pre-race conditions' }).selectOption('scenario')
    const wind = page.getByRole('spinbutton', { name: 'Pre-race wind speed' })
    await wind.fill('13.6')
    await page.getByRole('spinbutton', { name: 'Pre-race wind direction offset' }).fill('0')
    const generated = structuredClone(preset)
    generated.header.conditions = { tws_kt: 13.6, direction_offset_deg: 0 }
    generated.header.scenario_hash = 'fixture-retried'
    generated.pre_race.expected_position_by_boat[ids[0]] = 2.44
    const generatedPath = 'scenarios/' + createHash('sha256').update(JSON.stringify(generated)).digest('hex') + '.json'
    const jobId = 'cccccccc-cccc-cccc-cccc-cccccccccccc'
    const input = { race_id: replay.id, tws_kt: 13.6, direction_offset_deg: 0 }
    let submissions = 0
    await page.route('**/api/forecast-scenarios', async (route) => {
      if (route.request().method() !== 'POST') return route.fallback()
      submissions += 1
      assert.deepEqual(route.request().postDataJSON(), input)
      if (submissions === 2) {
        routes[generatedPath] = generated
        index.races[0].presets.push({ id: 'retried13_6', scope: 'pre_race', tws_kt: 13.6, direction_offset_deg: 0, path: generatedPath, ...reference, scenario_hash: 'fixture-retried' })
      }
      await route.fulfill({ status: submissions === 1 ? 202 : 200, contentType: 'application/json', body: JSON.stringify({ id: jobId, input, status: submissions === 1 ? 'running' : 'complete', message: 'Preparing these exact conditions…', ...(submissions === 2 ? { path: generatedPath } : {}) }) })
    })
    await page.route('**/api/forecast-scenarios/' + jobId, (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ id: jobId, input, status: 'running', message: 'Preparing these exact conditions…' }) }))
    await page.getByRole('button', { name: 'Generate forecast', exact: true }).click()
    await preCard().locator('.forecast-generation-status').getByText('Preparing these exact conditions…', { exact: true }).waitFor()
    await wind.fill('13.7')
    await wind.fill('13.6')
    await page.getByRole('button', { name: 'Generate forecast', exact: true }).click()
    await preCard().getByText('2.44', { exact: true }).waitFor()
    assert.equal(submissions, 2)
    await page.unroute('**/api/forecast-scenarios')
    await page.unroute('**/api/forecast-scenarios/' + jobId)
    await page.getByRole('combobox', { name: 'Pre-race conditions' }).selectOption('recorded')
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
    await question('Before the start')
    assert.equal(await page.getByRole('combobox', { name: 'Pre-race conditions' }).inputValue(), 'recorded')
    assert.equal(await liveCard().getByText('80.0%', { exact: true }).count(), 0)
    assert.equal(await liveCard().getByText('60.0%', { exact: true }).count(), 0)
  })

  await check('HTML artifact routing fails closed with three visible readiness summaries', async () => {
    htmlIndex = true
    await page.goto(`${base}/?race=${replay.id}&view=forecast&t=7`)
    await page.getByRole('heading', { name: 'Forecast', exact: true }).waitFor()
    await liveCard().getByText('Forecast unavailable: artifact did not return JSON', { exact: true }).waitFor()
    assert.equal(await page.locator('.forecast-grid article').count(), 3)
    assert.equal(await page.locator('.forecast-grid .forecast-status').filter({ hasText: 'Unavailable' }).count(), 3)
    assert.equal(await page.locator('.forecast-question-readiness').filter({ hasText: 'Unavailable' }).count(), 3)
    assert.equal(await liveCard().getByText('60.0%', { exact: true }).count(), 0)
    htmlIndex = false
  })

  for (const [width, height] of [[1586, 992], [1280, 720], [1096, 704], [390, 844]]) {
    await check(`Forecast responsive layout ${width}×${height}`, async () => {
      await page.setViewportSize({ width, height })
      await page.goto(`${base}/?race=${replay.id}&view=forecast&t=7`)
      await liveCard().getByText('60.0%', { exact: true }).waitFor()
      assert.equal(await page.locator('.forecast-grid article').count(), 3)
      for (const [id, label] of [['live', 'Live race'], ['pre', 'Before the start'], ['cup', 'America’s Cup 2027']]) {
        await question(label)
        assert.equal(await page.getByRole('article').count(), 1)
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)
        assert.equal(overflow, false, `${label} should not overflow the viewport`)
        await page.screenshot({ path: path.join(output, `forecast-fixture-${id}-${width}.png`), fullPage: true })
      }
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
      const cupResponse = await page.request.get(`${base}/data/predictions/${exported.cup_path}`)
      assert.equal(cupResponse.ok(), true)
      assert.match(cupResponse.headers()['content-type'], /json/)
      const exportedCup = await cupResponse.json()
      realCupArtifact = exportedCup
      await page.setViewportSize({ width: 1280, height: 720 })
      // Reproduce the reported gun-time view against the real dev-server route.
      await page.goto(`${base}/?race=${replay.id}&view=forecast&t=gun`)
      await page.getByRole('heading', { name: 'Forecast', exact: true }).waitFor()
      await page.waitForFunction(() => [...document.querySelectorAll('.forecast-card')].length === 3 && [...document.querySelectorAll('.forecast-card')].every((card) => !card.textContent.includes('Loading the')))
      assert.equal(await page.locator('.forecast-grid article').count(), 3)
      assert.equal(await page.getByText('Forecast unavailable:', { exact: false }).count(), 0, 'Exported contracts should parse successfully; evidence gaps have their own reasons')
      assert.equal(await liveCard().locator('tbody tr').count(), ids.length)
      assert.equal(await preCard().locator('tbody tr').count(), ids.length)
      await question('America’s Cup 2027')
      const teamTable = cupCard().getByRole('table', { name: 'Cup team bounds' })
      assert.equal(await teamTable.locator('tbody tr').count(), exportedCup.teams.length)
      if (['available', 'estimated'].includes(exportedCup.status)) {
        const evidence = checkScenarioMetadata(exportedCup)
        const baselineScenario = evidence.records.find((record) => record.scenario_id === evidence.baseline_scenario_id)
        await cupCard().getByText('Scenario envelope', { exact: true }).waitFor()
        const selector = cupCard().getByRole('combobox', { name: 'Cup scenario' })
        assert.equal(await selector.inputValue(), evidence.baseline_scenario_id)
        assert.equal(await selector.locator('option').count(), evidence.records.length)
        await cupCard().getByText(countText(baselineScenario), { exact: true }).waitFor()
        for (const [index, team] of exportedCup.teams.entries()) {
          const cells = teamTable.locator('tbody tr').nth(index).locator('td')
          assert.equal(await cells.nth(0).innerText(), boundText(exportedCup.rule_bounds_by_team[team.id]))
          assert.equal(await cells.nth(1).innerText(), boundText(exportedCup.scenario_envelope_by_team[team.id]))
          assert.equal(await cells.nth(2).innerText(), boundText(baselineScenario.rule_bounds[team.id]))
        }
        const selected = evidence.records.findLast((record) => record.scenario_id !== evidence.baseline_scenario_id) ?? baselineScenario
        await selector.selectOption(selected.scenario_id)
        await cupCard().getByText(countText(selected), { exact: true }).waitFor()
        await cupCard().getByText(`Monte Carlo half-width: ±${(selected.numerical_error.worst_case_95_half_width * 100).toFixed(2)} pp`, { exact: false }).waitFor()
        for (const [index, team] of exportedCup.teams.entries()) {
          const cells = teamTable.locator('tbody tr').nth(index).locator('td')
          assert.equal(await cells.nth(0).innerText(), boundText(exportedCup.rule_bounds_by_team[team.id]), 'Changing scenario must preserve baseline bounds')
          assert.equal(await cells.nth(1).innerText(), boundText(exportedCup.scenario_envelope_by_team[team.id]), 'Changing scenario must preserve the whole envelope')
          assert.equal(await cells.nth(2).innerText(), boundText(selected.rule_bounds[team.id]))
        }
        await cupCard().getByText('Scenario sensitivity and evidence', { exact: true }).click()
        assert.equal(await cupCard().getByRole('table', { name: 'Cup scenario sensitivity' }).locator('tbody tr').count(), evidence.records.length)
        await cupCard().getByRole('heading', { name: 'First unresolved stage', exact: true }).waitFor()
        await cupCard().getByRole('heading', { name: 'Overlapping reasons', exact: true }).waitFor()
        await cupCard().getByRole('heading', { name: 'Pinned strength model', exact: true }).waitFor()
        await cupCard().getByRole('link', { name: evidence.model_lineage.model_ref, exact: true }).waitFor()
        await cupCard().getByText(`training before ${evidence.model_lineage.training_before_day}`, { exact: false }).waitFor()
        await cupCard().getByText('Scenario sensitivity and evidence', { exact: true }).click()
        await cupCard().getByText('Envelope endpoint attribution', { exact: true }).click()
        const attribution = cupCard().getByRole('table', { name: 'Cup envelope endpoint attribution' })
        assert.equal(await attribution.locator('tbody tr').count(), exportedCup.teams.length)
        for (const [index, team] of exportedCup.teams.entries()) {
          const cells = attribution.locator('tbody tr').nth(index).locator('td')
          assert.equal(await cells.nth(0).innerText(), evidence.extrema_by_team[team.id].lower_scenario_ids.join(', '))
          assert.equal(await cells.nth(1).innerText(), evidence.extrema_by_team[team.id].upper_scenario_ids.join(', '))
        }
        await cupCard().getByText('Envelope endpoint attribution', { exact: true }).click()
        assert.equal(await page.locator('.forecast-grid article').count(), 3)
        assert.equal(await liveCard().locator('tbody tr').count(), ids.length)
        assert.equal(await preCard().locator('tbody tr').count(), ids.length)
      } else {
        await cupCard().getByRole('status').getByText('Cup probabilities are not ready:', { exact: false }).waitFor()
        assert.equal(await cupCard().getByRole('combobox', { name: 'Cup scenario' }).count(), 0)
        assert.ok((await teamTable.locator('tbody td').allInnerTexts()).every((text) => text === '—'))
        if (exportedCup.unresolved_reasons?.length || exportedCup.reason) {
          await cupCard().getByText('Why this is unavailable', { exact: true }).click()
          await cupCard().getByText((exportedCup.unresolved_reasons?.[0] ?? exportedCup.reason).replaceAll('_', ' '), { exact: false }).waitFor()
          await cupCard().getByText('Why this is unavailable', { exact: true }).click()
        }
      }
      const environment = JSON.parse(await fs.readFile(`public/data/environment/${replay.id}.json`, 'utf8'))
      const hour = environment.hourly.time_ms.findIndex((time) => time <= gun && gun < time + 3600000)
      assert.ok(hour >= 0, 'Historical API data should cover the reported race hour')
      const header = page.getByRole('banner')
      await header.locator('.conditions-disclosure > summary').click()
      await header.getByRole('link', { name: 'Open-Meteo model', exact: true }).waitFor()
      for (const [label, field, unit] of [['Sea', 'wave_height_m', 'm'], ['Air', 'air_temperature_c', '°C'], ['Water', 'water_temperature_c', '°C']]) {
        const value = environment.hourly[field][hour]
        assert.equal(typeof value, 'number', `${label} should have a real cached API value for this race`)
        const reading = header.getByText(`${label} ${value.toFixed(1)} ${unit}`, { exact: true })
        await reading.waitFor()
        assert.match(await reading.getAttribute('title'), /Open-Meteo historical model/)
      }
      await page.screenshot({ path: path.join(output, 'forecast-real-1280.png'), fullPage: true })
    })
    for (const [width, height] of [[1586, 992], [1280, 720], [1096, 704], [390, 844]]) {
      await check(`real Cup scenario evidence responsive layout ${width}×${height}`, async () => {
        await page.setViewportSize({ width, height })
        await page.goto(`${base}/?race=${replay.id}&view=forecast&t=gun`)
        await page.getByRole('heading', { name: 'Forecast', exact: true }).waitFor()
        await page.waitForFunction(() => [...document.querySelectorAll('.forecast-card')].length === 3 && [...document.querySelectorAll('.forecast-card')].every((card) => !card.textContent.includes('Loading the')))
        assert.equal(await page.locator('.forecast-grid article').count(), 3)
        await question('America’s Cup 2027')
        assert.equal(await cupCard().getByRole('table', { name: 'Cup team bounds' }).locator('tbody tr').count(), realCupArtifact.teams.length)
        if (['available', 'estimated'].includes(realCupArtifact.status)) {
          assert.equal(await cupCard().getByRole('combobox', { name: 'Cup scenario' }).inputValue(), realCupArtifact.scenario_analysis.baseline_scenario_id)
          await cupCard().getByText('Scenario sensitivity and evidence', { exact: true }).click()
          assert.equal(await cupCard().getByRole('table', { name: 'Cup scenario sensitivity' }).locator('tbody tr').count(), realCupArtifact.scenario_analysis.records.length)
          await cupCard().getByRole('link', { name: realCupArtifact.scenario_analysis.model_lineage.model_ref, exact: true }).waitFor()
        }
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, 'Expanded real Cup evidence must not overflow the viewport')
        await page.screenshot({ path: path.join(output, `forecast-real-${width}.png`), fullPage: true })
      })
    }
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
