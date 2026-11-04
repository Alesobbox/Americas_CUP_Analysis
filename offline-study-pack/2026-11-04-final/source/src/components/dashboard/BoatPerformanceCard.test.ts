import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { BoatPerformanceCard } from './BoatPerformanceCard'

const replay = JSON.parse(fs.readFileSync(path.resolve('public/data/replays/naples_pr1.json'), 'utf8')) as ReplayManifest
const selected = replay.competitors[0]
const index = 120
const telemetry = replay.telemetry.boats[selected.id]
const frame = {
  timestamp: replay.telemetry.timestamps[index], index, fraction: 0,
  boats: { [selected.id]: {
    sog: telemetry.sog[index], vmg: telemetry.vmg[index],
    twa: telemetry.twa[index], tws: telemetry.tws[index],
  } }, marks: {},
} as ReplayFrame

describe('selected boat performance provenance', () => {
  it('shows the four supported replay channels without permanent placeholders', () => {
    const html = renderToStaticMarkup(React.createElement(BoatPerformanceCard, { replay, frame, selectedId: selected.id }))
    expect(html).toContain(selected.team_code)
    expect(html).toContain(`${telemetry.sog[index].toFixed(1)} kt`)
    expect(html).toContain(`${telemetry.vmg[index].toFixed(1)} kt`)
    expect(html).not.toContain('HEEL')
    expect((html.match(/class="banner-kpi-item"/g) ?? [])).toHaveLength(4)
    for (const channel of ['SOG', 'VMG', 'TWA', 'TWS']) expect(html).toContain(`>${channel}</span>`)
    expect(html).not.toContain('trend-delta-text')
    expect((html.match(/class="mini-sparkline-svg"/g) ?? [])).toHaveLength(4)
  })

  it('never substitutes made-up readings or curves for a missing frame', () => {
    const empty = { ...frame, boats: {}, index: -1 } as ReplayFrame
    const html = renderToStaticMarkup(React.createElement(BoatPerformanceCard, { replay, frame: empty, selectedId: selected.id }))
    expect((html.match(/Unavailable/g) ?? [])).toHaveLength(4)
    expect(html).not.toContain('trend-delta-text')
    expect(html).not.toContain('mini-sparkline-svg')
  })
})
