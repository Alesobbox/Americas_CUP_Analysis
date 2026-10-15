import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { EventsNotesPanel } from './EventsNotesPanel'
import type { DashboardEvent } from './RaceTimelinePanel'

const replay = JSON.parse(fs.readFileSync(path.resolve('public/data/replays/naples_pr1.json'), 'utf8')) as ReplayManifest
const gun = replay.chronology.gun_time
const frame = { timestamp: gun + 25_000, index: 0, fraction: 0, boats: {}, marks: {} } as ReplayFrame

function render(events?: DashboardEvent[]) {
  return renderToStaticMarkup(React.createElement(EventsNotesPanel, {
    replay, frame, selectedId: null, onSeek: vi.fn(), events,
  }))
}

describe('events and notes provenance', () => {
  it('shows no invented race events while the analysis feed is unavailable', () => {
    const html = render()
    expect(html).toContain('Event feed unavailable for this race')
    expect(html).not.toContain('Start sequence area entered')
    expect(html).not.toContain('ITA B port')
  })

  it('renders the supplied event with source and quality, ignoring an unavailable timestamp', () => {
    const html = render([
      { id: 'gate', timestamp_ms: gun + 20_000, type: 'gate', boat_id: replay.competitors[0].id,
        label: 'First crossing', source: 'source leg timing', quality: 'reconstructed' },
      { id: 'missing', timestamp_ms: null as unknown as number, type: 'gate', label: 'Missing crossing',
        source: 'none', quality: 'unavailable', unavailable_reason: 'No timing' },
    ])
    expect(html).toContain('First crossing')
    expect(html).toContain('source leg timing')
    expect(html).toContain('reconstructed')
    expect(html).toContain(replay.competitors[0].team_code)
    expect(html).not.toContain('Missing crossing')
    expect(html).not.toContain('Event options')
  })
})
