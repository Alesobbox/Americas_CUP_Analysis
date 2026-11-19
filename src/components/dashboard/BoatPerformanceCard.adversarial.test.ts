import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { BoatPerformanceCard } from './BoatPerformanceCard'

const liveReplayPath = path.resolve('public/data/replays/naples_pr1.json')
const replay = JSON.parse(
  fs.readFileSync(
    fs.existsSync(liveReplayPath)
      ? liveReplayPath
      : path.resolve('tests/fixtures/synthetic_replay.json'),
    'utf8'
  )
) as ReplayManifest
const boat = replay.competitors[0]

describe('performance card missing-data cases', () => {
  it('falls back to a real catalog boat when selection is unknown', () => {
    const frame = {
      index: 0,
      timestamp: replay.chronology.window_start,
      boats: {},
      marks: {},
    } as ReplayFrame
    const html = renderToStaticMarkup(
      React.createElement(BoatPerformanceCard, { replay, frame, selectedId: 'unknown' })
    )
    expect(html).toContain(boat.team_code)
    expect(html).toContain('Unavailable')
  })

  it('keeps invalid readings unavailable, real zeros visible and unsupported channels absent', () => {
    const frame = {
      index: 0,
      timestamp: replay.chronology.window_start,
      marks: {},
      boats: { [boat.id]: { sog: NaN, vmg: 0, twa: 0, tws: 0 } },
    } as ReplayFrame
    const html = renderToStaticMarkup(
      React.createElement(BoatPerformanceCard, { replay, frame, selectedId: boat.id })
    )
    expect(html).not.toContain('NaN')
    expect(html).not.toContain('HEEL')
    expect(html.match(/Unavailable/g) ?? []).toHaveLength(1)
    expect(html).toContain('0.0 kt')
    expect(html).toContain('0°')
  })
})
