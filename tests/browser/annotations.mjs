// Production-artifact regression checks for the six annotation revisions.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const playwright = require(process.env.REGATTA_PLAYWRIGHT || 'playwright')
const base = (process.env.REGATTA_URL || 'http://127.0.0.1:5173').replace(/\/$/, '')
const output = process.env.REGATTA_QA_OUTPUT || path.join(os.tmpdir(), 'ac40-annotation-revisions')
await fs.mkdir(output, { recursive: true })
const readData = async (relative) => {
  const response = await fetch(`${base}/data/${relative}`)
  assert.equal(response.status, 200, relative)
  assert.ok(response.headers.get('content-type')?.includes('json'), `${relative} must return JSON`)
  return response.json()
}
const analyses = new Map()
const analysisFor = async (raceId) => {
  if (!analyses.has(raceId)) analyses.set(raceId, await readData(`analysis/${raceId}.json`))
  return analyses.get(raceId)
}
const browser = await playwright.chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({
  viewport: { width: 1096, height: 704 },
  hasTouch: true,
  acceptDownloads: true,
})
await context.addInitScript(() => localStorage.setItem('regatta_view_mode', 'grid'))
const page = await context.newPage()
page.setDefaultTimeout(15000)
const checks = [],
  errors = [],
  consoleErrors = [],
  failedRequests = [],
  visualMetrics = [],
  screenshots = []
let expectedFailure = false
page.on('pageerror', (error) => errors.push(error.message))
page.on('console', (message) => {
  if (message.type() === 'error' && !expectedFailure) consoleErrors.push(message.text())
})
page.on('requestfailed', (request) => {
  if (
    !expectedFailure &&
    request.url().startsWith(base) &&
    request.failure()?.errorText !== 'net::ERR_ABORTED'
  )
    failedRequests.push(request.url())
})
const check = async (name, fn) => {
  await fn()
  checks.push(name)
  console.log('PASS ' + name)
}
const nav = async (name) =>
  page
    .getByRole('navigation', { name: 'Main Navigation' })
    .getByRole('button', { name, exact: true })
    .click()
const load = async (raceId = 'naples_pr1', view = 'replay') => {
  await page.goto(`${base}/?race=${encodeURIComponent(raceId)}&view=${view}&t=gun`)
  await page.getByRole('banner').waitFor()
  assert.equal(
    await page.getByRole('navigation', { name: 'Main Navigation' }).getByRole('button').count(),
    4
  )
}
const capture = async (name, locator) => {
  const target = path.join(output, name + '.png')
  if (locator) {
    const box = await locator.boundingBox(),
      viewport = page.viewportSize()
    if (box.height > viewport.height * 0.8 || box.width > viewport.width) {
      // Large element screenshots can include uncaptured offscreen compositor
      // regions in Chromium. Keep the real viewport and capture its top instead.
      await locator.evaluate((element) => {
        const header = document.querySelector('.tactical-header-container')
        const clearance =
          header && getComputedStyle(header).position === 'sticky'
            ? header.getBoundingClientRect().height + 8
            : 8
        window.scrollTo({
          top: Math.max(0, scrollY + element.getBoundingClientRect().top - clearance),
          behavior: 'instant',
        })
      })
      await page.screenshot({ path: target })
    } else await locator.screenshot({ path: target })
  } else await page.screenshot({ path: target })
  screenshots.push(target)
}
const noPageOverflow = async (label) => {
  const dimensions = await page.evaluate(() => ({
    viewport: innerWidth,
    document: document.documentElement.scrollWidth,
  }))
  assert.ok(
    dimensions.document <= dimensions.viewport + 1,
    `${label}: document overflow ${JSON.stringify(dimensions)}`
  )
}
const waitForPinned = async (axis, leg) =>
  page.waitForFunction(
    ([expectedAxis, expectedLeg]) => {
      const panel = document.querySelector('[aria-label="Pinned performance evidence"]')
      return (
        panel?.getAttribute('data-inspect-axis') === expectedAxis &&
        panel.getAttribute('data-inspect-leg') === expectedLeg
      )
    },
    [axis, leg]
  )

async function verifyChartLabels(radar, label) {
  const collisions = await radar.locator('.performance-radar').evaluate((svg) =>
    [...svg.querySelectorAll('.performance-active-score')].flatMap((score) => {
      const own = score.getBoundingClientRect()
      return [...svg.querySelectorAll('.radar-tick, .radar-label')]
        .filter((element) => {
          const other = element.getBoundingClientRect()
          return (
            own.left < other.right - 0.5 &&
            own.right > other.left + 0.5 &&
            own.top < other.bottom - 0.5 &&
            own.bottom > other.top + 0.5
          )
        })
        .map((element) => ({ score: score.textContent, collidedWith: element.textContent }))
    })
  )
  assert.deepEqual(collisions, [], `${label}: active score must not overlap ticks or axis labels`)
}

async function verifyInnerScroll(wrapper, label) {
  const state = await wrapper.evaluate((element) => {
    const previous = element.scrollLeft
    element.scrollLeft = element.scrollWidth
    const result = {
      width: element.clientWidth,
      content: element.scrollWidth,
      scrolled: element.scrollLeft,
    }
    element.scrollLeft = previous
    return result
  })
  assert.ok(
    state.content > state.width && state.scrolled > 0,
    `${label}: wide evidence must scroll inside its own container`
  )
}

async function verifyAnalysisPalette(label) {
  const metrics = await page.evaluate(() => {
    const root = document.querySelector('.tactical-dashboard-root .analysis-modal')
    const canvas = document.createElement('canvas'),
      context = canvas.getContext('2d', { willReadFrequently: true })
    canvas.width = canvas.height = 1
    const rgba = (css) => {
      context.clearRect(0, 0, 1, 1)
      context.fillStyle = '#000'
      context.fillStyle = css
      context.fillRect(0, 0, 1, 1)
      return [...context.getImageData(0, 0, 1, 1).data]
    }
    const background = (element) => {
      for (let node = element; node; node = node.parentElement) {
        const color = rgba(getComputedStyle(node).backgroundColor)
        if (color[3] === 255) return color
      }
      return [255, 255, 255, 255]
    }
    const luminance = (color) =>
      color
        .slice(0, 3)
        .map((part) => part / 255)
        .map((part) => (part <= 0.04045 ? part / 12.92 : ((part + 0.055) / 1.055) ** 2.4))
        .reduce((sum, part, index) => sum + part * [0.2126, 0.7152, 0.0722][index], 0)
    const contrast = (a, b) => {
      const left = luminance(a),
        right = luminance(b)
      return (Math.max(left, right) + 0.05) / (Math.min(left, right) + 0.05)
    }
    const surfaces = [
      '.modal-head',
      '.analysis-main-tabs',
      '.analysis-section',
      '.analysis-metric',
      '.analysis-definitions',
      '.debrief-item',
      '.analysis-controls select',
    ].flatMap((selector) =>
      [...root.querySelectorAll(selector)]
        .slice(0, 3)
        .map((element) => ({ selector, background: background(element) }))
    )
    const text = [
      '.modal-head h2',
      '.analysis-section-heading h4',
      '.analysis-main-tabs button',
      '.analysis-table th',
      '.analysis-metric strong',
      '.analysis-metric-meta',
      '.analysis-definitions summary',
      '.debrief-item h5',
      '.radar-label',
      '.analysis-state.error',
    ].flatMap((selector) =>
      [...root.querySelectorAll(selector)].slice(0, 4).map((element) => {
        const style = getComputedStyle(element),
          foreground = rgba(element instanceof SVGElement ? style.fill : style.color),
          backdrop = background(element)
        return {
          selector,
          color: foreground,
          background: backdrop,
          contrast: contrast(foreground, backdrop),
        }
      })
    )
    return {
      rootBackground: background(root),
      colorScheme: getComputedStyle(root).colorScheme,
      surfaces,
      text,
    }
  })
  assert.deepEqual(
    metrics.rootBackground.slice(0, 3),
    [255, 255, 255],
    `${label}: Analysis must be white`
  )
  assert.equal(metrics.colorScheme, 'light')
  for (const surface of metrics.surfaces)
    assert.ok(
      surface.background.slice(0, 3).every((part) => part >= 235),
      `${label}: dark ${surface.selector}`
    )
  for (const sample of metrics.text)
    assert.ok(
      sample.contrast >= 4.5,
      `${label}: insufficient ${sample.selector} contrast ${sample.contrast.toFixed(2)}`
    )
  visualMetrics.push({ label, ...metrics })
}

async function verifyReportMetrics(raceId) {
  const analysis = await analysisFor(raceId)
  const reference = analysis.boats.find(
    (boat) => typeof boat.metrics.distance_m?.value === 'number'
  )
  const table = page.getByRole('table', { name: 'Race report metrics', exact: true })
  await table.waitFor()
  if (reference)
    await page.waitForFunction(
      ([boatId, value]) =>
        document
          .querySelector(`[data-boat-id="${boatId}"] [data-metric-id="distance_m"]`)
          ?.getAttribute('data-value') === String(value),
      [reference.id, reference.metrics.distance_m.value]
    )
  for (const boat of analysis.boats) {
    const row = table.locator(`tr[data-boat-id="${boat.id}"]`)
    for (const id of ['distance_m', 'sog_mean_kt', 'tack_count', 'gybe_count']) {
      const metric = boat.metrics[id],
        cell = row.locator(`[data-metric-id="${id}"]`)
      assert.equal(
        await cell.getAttribute('data-value'),
        metric?.value == null ? '' : String(metric.value),
        `${raceId} ${boat.team_code} ${id}`
      )
      assert.equal(await cell.getAttribute('data-quality'), metric?.quality ?? 'unavailable')
      if (metric?.value === null) assert.ok((await cell.innerText()).includes('Unavailable'))
      if (metric?.value != null && metric.coverage_s !== null)
        assert.ok((await cell.innerText()).includes(`${metric.coverage_s.toFixed(1)} s covered`))
    }
  }
  return { analysis, table }
}

try {
  const inventory = await readData('artifacts.json')
  for (const [width, height] of [
    [1096, 704],
    [1586, 992],
    [1280, 720],
    [390, 844],
  ]) {
    const size = `${width}x${height}`
    await page.setViewportSize({ width, height })
    await check(`four supported KPIs and compact wind HUD at ${size}`, async () => {
      await load()
      const kpis = page.getByRole('article', {
        name: 'Selected Boat Performance KPIs',
        exact: true,
      })
      await kpis.waitFor()
      assert.equal(await kpis.locator('.banner-kpi-item').count(), 4)
      assert.deepEqual(await kpis.locator('.kpi-item-title').allTextContents(), [
        'SOG',
        'VMG',
        'TWA',
        'TWS',
      ])
      assert.equal(await kpis.getByText('HEEL', { exact: true }).count(), 0)
      const overlay = page.locator('.tactical-map-overlay')
      assert.equal(await overlay.getByText('Current', { exact: true }).count(), 0)
      assert.equal(await overlay.locator('.hud-card-v-divider').count(), 0)
      assert.equal(await overlay.locator('.hud-metric-cell').count(), 1)
      const toolbar = await page
        .getByRole('toolbar', { name: 'Tactical map action toolbar' })
        .boundingBox()
      const map = await page.locator('.map-viewport-frame').boundingBox()
      const hud = await page.locator('.map-top-left-hud').boundingBox()
      assert.ok(
        toolbar.x >= map.x - 1 && toolbar.x + toolbar.width <= map.x + map.width + 1,
        'Map tools remain inside the map'
      )
      assert.ok(
        toolbar.y + toolbar.height <= hud.y || hud.y + hud.height <= toolbar.y,
        'Toolbar and wind HUD remain separate'
      )
      await page.getByRole('button', { name: 'All Boats', exact: true }).click()
      await page.keyboard.press('Escape')
      assert.equal(await page.locator('.hdr-dropdown-popover').count(), 0)
      await noPageOverflow(`Replay ${size}`)
      await capture(`replay-${size}`)
      if (width === 1096) {
        await page.getByRole('button', { name: 'All Boats', exact: true }).click()
        await page.locator('.map-viewport-frame').click({ position: { x: 20, y: 200 } })
        assert.equal(
          await page.locator('.hdr-dropdown-popover').count(),
          0,
          'Outside pointer closes the boat menu'
        )
        await page.getByRole('button', { name: 'All Boats', exact: true }).click()
        await nav('Analysis')
        assert.equal(
          await page.locator('.hdr-dropdown-popover').count(),
          0,
          'Navigation closes the boat menu'
        )
      }
    })
    await check(`white Analysis and interactive performance evidence at ${size}`, async () => {
      await nav('Analysis')
      const radar = page.getByRole('region', { name: 'Boat performance', exact: true })
      const pinned = page.getByRole('region', { name: 'Pinned performance evidence', exact: true })
      await radar.getByRole('button', { name: /Inspect Upwind course VMG/ }).waitFor()
      const analysis = await analysisFor('naples_pr1')
      const boatId = (await radar.getAttribute('data-performance-context')).slice(
        'naples_pr1:'.length
      )
      const selectedBoat = analysis.boats.find((boat) => boat.id === boatId)
      assert.ok(selectedBoat)
      await verifyAnalysisPalette(`Race report ${size}`)
      await verifyChartLabels(radar, `Default axis ${size}`)
      await capture(`performance-circle-${size}`, radar.locator('.performance-radar'))
      await capture(`performance-support-${size}`, radar.locator('.performance-inspector-controls'))
      const downwind = radar.getByRole('button', {
        name: 'Inspect Downwind course VMG',
        exact: true,
      })
      await downwind.focus()
      await page.keyboard.press('Enter')
      await waitForPinned('downwind_vmg', 'all')
      assert.equal(await downwind.getAttribute('aria-pressed'), 'true')
      await verifyChartLabels(radar, `Downwind axis ${size}`)
      const speed = radar.getByRole('button', { name: 'Inspect Upwind speed', exact: true })
      await speed.focus()
      await page.keyboard.press('Space')
      await waitForPinned('upwind_speed', 'all')
      await verifyChartLabels(radar, `Speed axis ${size}`)
      await radar.getByRole('button', { name: 'Inspect Upwind course VMG', exact: true }).tap()
      await waitForPinned('upwind_vmg', 'all')
      const dimension = selectedBoat.performance.dimensions.find(
        (entry) => entry.id === 'upwind_vmg'
      )
      assert.equal(
        Number(await pinned.getAttribute('data-exported-index')),
        dimension.index,
        'Aggregate index uses the published mean of leg ratios'
      )
      const scope = page.getByLabel('Performance leg scope', { exact: true })
      const options = await scope
        .locator('option')
        .evaluateAll((nodes) => nodes.map((node) => node.value))
      const leg = options.find((value) => value !== 'all')
      assert.ok(leg, 'A completed leg is selectable')
      await scope.selectOption(leg)
      await waitForPinned('upwind_vmg', leg)
      const legEvidence = dimension.leg_evidence.find((entry) => entry.leg === Number(leg))
      assert.ok(legEvidence)
      assert.equal(Number(await pinned.getAttribute('data-exported-index')), legEvidence.index)
      await radar.getByRole('button', { name: 'Inspect Downwind course VMG', exact: true }).tap()
      await waitForPinned('downwind_vmg', leg)
      assert.equal(
        await pinned.getAttribute('data-exported-index'),
        '',
        'An unsupported upwind-leg/downwind-axis combination stays unavailable'
      )
      await radar.getByRole('button', { name: 'Inspect Upwind course VMG', exact: true }).tap()
      await waitForPinned('upwind_vmg', leg)
      await pinned.locator('details.performance-leg-evidence > summary').first().click()
      const peerTable = pinned.getByRole('table', { name: `Leg ${leg} peer evidence`, exact: true })
      assert.equal(await peerTable.locator('tbody tr').count(), legEvidence.peer_count)
      for (const peerId of legEvidence.peer_ids) {
        const peer = analysis.boats.find((boat) => boat.id === peerId)
        assert.ok(peer && (await peerTable.innerText()).includes(peer.team_code))
      }
      await noPageOverflow(`Race report ${size}`)
      if (width === 390)
        await verifyInnerScroll(
          radar.locator('.performance-evidence'),
          'Mobile performance evidence'
        )
      await capture(`performance-${size}`, radar)
      await capture(`performance-evidence-${size}`, pinned)
      const review = pinned.getByRole('button', {
        name: `Review leg ${leg} in replay`,
        exact: true,
      })
      const start = Number(await review.getAttribute('data-performance-start')),
        end = Number(await review.getAttribute('data-performance-end'))
      assert.equal(await review.getAttribute('data-performance-race'), 'naples_pr1')
      assert.equal(await review.getAttribute('data-performance-boat'), boatId)
      assert.equal(start, legEvidence.start_ms)
      assert.equal(end, legEvidence.end_ms)
      await review.click()
      const interval = page.getByRole('region', { name: 'Reviewed leg interval', exact: true })
      await interval.waitFor()
      assert.equal(await page.locator('.boat-code-strong').innerText(), selectedBoat.team_code)
      assert.equal(
        Number(
          await page
            .getByRole('slider', { name: 'Race playhead', exact: true })
            .getAttribute('aria-valuenow')
        ),
        Math.round(start)
      )
      await interval.getByRole('button', { name: 'Seek to leg end', exact: true }).click()
      assert.equal(
        Number(
          await page
            .getByRole('slider', { name: 'Race playhead', exact: true })
            .getAttribute('aria-valuenow')
        ),
        Math.round(end)
      )
      await interval.getByRole('button', { name: 'Clear review interval', exact: true }).click()
      assert.equal(
        await page.getByRole('region', { name: 'Reviewed leg interval', exact: true }).count(),
        0
      )
      await nav('Analysis')
      await waitForPinned('upwind_vmg', 'all')
      await page.getByRole('tab', { name: 'Historical view', exact: true }).click()
      await page.getByRole('heading', { name: 'Manoeuvre distributions', exact: true }).waitFor()
      await verifyAnalysisPalette(`Historical view ${size}`)
      await noPageOverflow(`History ${size}`)
      await capture(`history-${size}`)
    })
    await check(
      `canonical race report and quiet complete download library at ${size}`,
      async () => {
        await nav('Reports')
        const { analysis, table } = await verifyReportMetrics('naples_pr1')
        const retired = analysis.boats.find((boat) => boat.team_code === 'GBR B')
        assert.ok(retired)
        for (const id of ['distance_m', 'sog_mean_kt']) {
          assert.equal(retired.metrics[id].value, null)
          assert.ok(
            (
              await table
                .locator(`tr[data-boat-id="${retired.id}"] [data-metric-id="${id}"]`)
                .innerText()
            ).includes('Unavailable')
          )
        }
        const exports = page.getByRole('region', { name: 'Race exports', exact: true })
        await exports.getByRole('link').first().waitFor()
        const expected = inventory.artifacts.filter(
          (item) =>
            item.race_id === 'naples_pr1' && item.primary_download && item.status === 'current'
        )
        assert.ok(expected.length > 0 && expected.length <= 8, 'Race downloads stay concise')
        assert.deepEqual(
          (
            await exports
              .getByRole('link')
              .evaluateAll((nodes) => nodes.map((node) => node.getAttribute('href')))
          ).sort(),
          expected.map((item) => item.url).sort()
        )
        const csvs = expected.filter((item) => item.format === 'csv')
        assert.ok(csvs.length >= 2, 'Canonical summary and boat/leg CSVs are available')
        for (const csv of csvs) {
          const response = await fetch(base + csv.url),
            text = await response.text()
          assert.equal(response.status, 200)
          assert.ok(!response.headers.get('content-type')?.includes('html'))
          assert.ok(
            text.split(/\r?\n/)[0].includes('race_id') && text.split(/\r?\n/)[0].includes('boat_id')
          )
        }
        const technical = page.locator('details.technical-data')
        assert.equal(
          await technical.getAttribute('open'),
          null,
          'Technical objects are initially collapsed'
        )
        await capture(`race-exports-${size}`, exports)
        await technical.getByText('Technical data and provenance', { exact: true }).click()
        const scope = page.getByLabel('Technical data scope', { exact: true }),
          search = page.getByLabel('Search technical data', { exact: true })
        const rows = page
          .getByRole('table', { name: 'Technical downloads', exact: true })
          .locator('tbody tr')
        await scope.selectOption('all')
        assert.equal(await rows.count(), inventory.artifacts.length)
        const reference =
          inventory.artifacts.find((item) => item.status === 'retained') ?? inventory.artifacts[0]
        await search.fill(reference.id)
        assert.equal(await rows.count(), 1)
        assert.equal(await rows.getByRole('link').getAttribute('href'), reference.url)
        await search.fill('')
        for (const [value, expectedCount] of [
          ['catalogs', inventory.artifacts.filter((item) => item.kind === 'catalog').length],
          ['supporting', inventory.artifacts.filter((item) => item.status === 'supporting').length],
          ['retained', inventory.artifacts.filter((item) => item.status === 'retained').length],
        ]) {
          await scope.selectOption(value)
          assert.equal(await rows.count(), expectedCount)
        }
        await noPageOverflow(`Reports ${size}`)
        await capture(`technical-library-${size}`)
      }
    )
  }
  await check(
    'boat and race changes reset inspection scope and match/partial leg scopes render cleanly',
    async () => {
      await page.setViewportSize({ width: 1096, height: 704 })
      await load('naples_pr1', 'analysis')
      const radar = page.getByRole('region', { name: 'Boat performance', exact: true })
      await radar
        .getByRole('button', { name: 'Inspect Downwind course VMG', exact: true })
        .waitFor()
      await radar.getByRole('button', { name: 'Inspect Downwind course VMG', exact: true }).click()
      await page.getByLabel('Performance leg scope', { exact: true }).selectOption('2')
      await waitForPinned('downwind_vmg', '2')
      await page.locator('.analysis-team-select').filter({ hasText: 'ITA G' }).first().click()
      await waitForPinned('upwind_vmg', 'all')
      const fleet = await analysisFor('naples_pr1'),
        itaG = fleet.boats.find((boat) => boat.team_code === 'ITA G')
      await radar.getByRole('button', { name: 'Inspect Downwind course VMG', exact: true }).click()
      await waitForPinned('downwind_vmg', 'all')
      assert.equal(
        Number(
          await page
            .getByRole('region', { name: 'Pinned performance evidence', exact: true })
            .getAttribute('data-exported-index')
        ),
        itaG.performance.dimensions.find((entry) => entry.id === 'downwind_vmg').index
      )
      await page.getByLabel('Performance leg scope', { exact: true }).selectOption('2')
      const match = await analysisFor('naples_mr_final')
      await page.locator('.analysis-controls select').first().selectOption('naples_mr_final')
      await page.waitForFunction(
        (contexts) =>
          contexts.includes(
            document
              .querySelector('[data-performance-context]')
              ?.getAttribute('data-performance-context')
          ),
        match.boats.map((boat) => `naples_mr_final:${boat.id}`)
      )
      await waitForPinned('upwind_vmg', 'all')
      await page.locator('.analysis-team-select').filter({ hasText: 'ITA B' }).first().click()
      await waitForPinned('upwind_vmg', 'all')
      await radar.getByText(/6 of 6 course legs compared/).waitFor()
      await verifyAnalysisPalette('Match six-of-six scope')
      await verifyChartLabels(radar, 'Match default axis')
      await capture('match-six-of-six-1096x704', radar)
      await capture(
        'match-scope-support-1096x704',
        radar.locator('.performance-inspector-controls')
      )
      await capture('match-circle-1096x704', radar.locator('.performance-radar'))
      await nav('Reports')
      await verifyReportMetrics('naples_mr_final')
      await page.setViewportSize({ width: 390, height: 844 })
      await nav('Analysis')
      await page
        .getByRole('region', { name: 'Boat performance', exact: true })
        .getByText(/6 of 6 course legs compared/)
        .waitFor()
      await noPageOverflow('Match scope mobile')
      await capture(
        'match-six-of-six-390x844',
        page.getByRole('region', { name: 'Boat performance', exact: true })
      )
      await capture('match-scope-support-390x844', page.locator('.performance-inspector-controls'))
      await capture('match-circle-390x844', page.locator('.performance-radar'))
    }
  )
  await check(
    'missing analysis preserves white errors and never revives legacy Reports metrics',
    async () => {
      expectedFailure = true
      await page.route('**/data/analysis/naples_pr1.json', (route) =>
        route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
      )
      await load('naples_pr1', 'reports')
      await page
        .getByText('Historical analysis is unavailable or still loading.', { exact: false })
        .waitFor()
      const values = await page
        .getByRole('table', { name: 'Race report metrics', exact: true })
        .locator('[data-metric-id]')
        .evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-value')))
      assert.ok(
        values.length > 0 && values.every((value) => value === ''),
        'Missing canonical analysis cannot fall back to replay summary numbers'
      )
      await nav('Analysis')
      await page
        .getByRole('alert')
        .filter({ hasText: 'Detailed analysis is unavailable (404)' })
        .waitFor()
      await verifyAnalysisPalette('Missing analysis error')
      await capture('missing-analysis-error-390x844')
      await page.unroute('**/data/analysis/naples_pr1.json')
      await load('naples_pr1', 'analysis')
      await page.getByRole('region', { name: 'Pinned performance evidence', exact: true }).waitFor()
      expectedFailure = false
    }
  )
  assert.deepEqual(errors, [], 'Browser exceptions')
  assert.deepEqual(failedRequests, [], 'Failed application requests')
  assert.deepEqual(consoleErrors, [], 'Unexpected console errors')
  await fs.writeFile(
    path.join(output, 'results.json'),
    JSON.stringify(
      { checks, errors, failedRequests, consoleErrors, visualMetrics, screenshots },
      null,
      2
    )
  )
  console.log(
    JSON.stringify({
      checks: checks.length,
      errors: errors.length,
      failedRequests: failedRequests.length,
      screenshots: screenshots.length,
      output,
    })
  )
} catch (error) {
  await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: false }).catch(() => {})
  await fs.writeFile(
    path.join(output, 'results.json'),
    JSON.stringify(
      {
        checks,
        error: error.message,
        errors,
        failedRequests,
        consoleErrors,
        visualMetrics,
        screenshots,
      },
      null,
      2
    )
  )
  throw error
} finally {
  await browser.close()
}
