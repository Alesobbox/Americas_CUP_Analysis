import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { BoatPerformanceCard } from './BoatPerformanceCard'

const replay = JSON.parse(fs.readFileSync(path.resolve('public/data/replays/naples_pr1.json'), 'utf8')) as ReplayManifest
const boat = replay.competitors[0]

describe('performance card missing-data cases', () => {
  it('falls back to a real catalog boat when selection is unknown', () => {
    const frame = { index: 0, timestamp: replay.chronology.window_start, boats: {}, marks: {} } as ReplayFrame
    const html = renderToStaticMarkup(React.createElement(BoatPerformanceCard, { replay, frame, selectedId: 'unknown' }))
    expect(html).toContain(boat.team_code)
    expect(html).toContain('Unavailable')
  })

  it('does not display NaN as a reading or derive heel from speed', () => {
    const frame = {
      index: 0, timestamp: replay.chronology.window_start, marks: {},
      boats: { [boat.id]: { sog: NaN, vmg: 0, twa: 0, tws: 0 } },
    } as ReplayFrame
    const html = renderToStaticMarkup(React.createElement(BoatPerformanceCard, { replay, frame, selectedId: boat.id }))
    expect(html).not.toContain('NaN')
    expect(html).toContain('HEEL')
    expect(html).toContain('Heel is not a channel in the exported replay')
  })
})
