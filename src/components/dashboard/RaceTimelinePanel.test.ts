import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { RaceTimelinePanel, type DashboardEvent, type RaceTimelinePanelProps } from './RaceTimelinePanel'

const replay = JSON.parse(fs.readFileSync(path.resolve('public/data/replays/naples_pr1.json'), 'utf8')) as ReplayManifest
const gun = replay.chronology.gun_time
const frame = { timestamp: gun + 43_000, index: 0, fraction: 0, boats: {}, marks: {} } as ReplayFrame

function render(events?: DashboardEvent[], initialFilter: RaceTimelinePanelProps['initialFilter'] = 'all') {
  return renderToStaticMarkup(React.createElement(RaceTimelinePanel, {
    replay, frame, playing: false, speed: 1, onToggle: vi.fn(), onSeek: vi.fn(),
    onStep: vi.fn(), onSpeed: vi.fn(), selectedId: null, events, initialFilter,
  }))
}

describe('race timeline source events', () => {
  it('shows unavailability without inventing milestones', () => {
    const html = render()
    expect(html).toContain('Event feed unavailable for this race')
    expect(html).not.toContain('Gate 1')
    expect(html).not.toContain('Mark -04:28')
    expect(html).not.toContain('scrubber-tick-dot')
    expect(html).toContain('ELAPSED FROM GUN')
    expect(html).toContain('+00:43')
  })

  it('renders only finite, in-window exported events with their provenance', () => {
    const events: DashboardEvent[] = [
      { id: 'gate-1', timestamp_ms: gun + 30_000, type: 'gate', label: 'Gate 1 reconstructed', source: 'source leg timing', quality: 'reconstructed' },
      { id: 'start', timestamp_ms: gun, type: 'start', label: 'Gun', source: 'session chronology', quality: 'official' },
      { id: 'missing', timestamp_ms: null as unknown as number, type: 'gate', label: 'Absent gate', source: 'none', quality: 'unavailable', unavailable_reason: 'No crossing' },
      { id: 'outside', timestamp_ms: replay.chronology.window_end + 1, type: 'finish', label: 'Outside race', source: 'none', quality: 'reconstructed' },
      { id: 'future', timestamp_ms: gun + 90_000, type: 'finish', label: 'Future finish hidden', source: 'source timing', quality: 'reconstructed' },
    ]
    const html = render(events)
    expect(html).toContain('Gun')
    expect(html).toContain('Gate 1 calculated')
    expect(html).toContain('source leg timing')
    expect(html).toContain('calculated')
    expect(html).not.toContain('reconstructed')
    expect(html).not.toContain('Absent gate')
    expect(html).not.toContain('Outside race')
    expect(html).not.toContain('Future finish hidden')
    expect((html.match(/class="scrubber-tick-dot"/g) ?? [])).toHaveLength(2)
    expect(html.indexOf('Gun')).toBeLessThan(html.indexOf('Gate 1 calculated'))
  })

  it('filters by exported event type, independent of label text', () => {
    const events: DashboardEvent[] = [
      { id: 'wind', timestamp_ms: gun + 1000, type: 'wind_shift', label: 'Veer right', source: 'official wind', quality: 'derived' },
      { id: 'gate', timestamp_ms: gun + 2000, type: 'gate', label: 'Windward gate', source: 'leg timing', quality: 'reconstructed' },
    ]
    const html = render(events, 'wind_shifts')
    expect(html).toContain('Veer right')
    expect(html).not.toContain('Windward gate')
    expect((html.match(/class="scrubber-tick-dot"/g) ?? [])).toHaveLength(1)
  })
})
