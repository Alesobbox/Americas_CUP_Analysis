import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { RaceTimelinePanel, type DashboardEvent, type TimelineFilter } from './RaceTimelinePanel'

const replay = JSON.parse(fs.readFileSync(path.resolve('public/data/replays/naples_pr1.json'), 'utf8')) as ReplayManifest
const gun = replay.chronology.gun_time
const frame = { timestamp: gun + 160_000, index: 0, fraction: 0, boats: {}, marks: {} } as ReplayFrame
const feed: DashboardEvent[] = [
  { id: 'gun', timestamp_ms: gun, type: 'start', label: 'Start from source', source: 'session', quality: 'official' },
  { id: 'gate', timestamp_ms: gun + 150_000, type: 'gate', label: 'First crossing', source: 'leg timing', quality: 'reconstructed' },
  { id: 'tack', timestamp_ms: gun + 25_000, type: 'tack', label: 'Boat manoeuvre', source: 'detector', quality: 'reconstructed' },
  { id: 'shift', timestamp_ms: gun + 30_000, type: 'wind_shift', label: 'Direction change', source: 'official wind', quality: 'derived' },
]

function render(filter: TimelineFilter, events: DashboardEvent[] = feed) {
  return renderToStaticMarkup(React.createElement(RaceTimelinePanel, {
    replay, frame, playing: false, speed: 1, onToggle: vi.fn(), onSeek: vi.fn(),
    onStep: vi.fn(), onSpeed: vi.fn(), selectedId: null, initialFilter: filter, events,
  }))
}

describe('timeline event feed stress cases', () => {
  it('partitions tick marks and rows by type without duplicate IDs', () => {
    const duplicated = [...feed, feed[0]]
    for (const [filter, expected] of [['all', 4], ['marks', 2], ['maneuvers', 1], ['wind_shifts', 1]] as const) {
      const html = render(filter, duplicated)
      expect((html.match(/class="scrubber-tick-dot"/g) ?? [])).toHaveLength(expected)
      expect((html.match(/class="timeline-event-item/g) ?? [])).toHaveLength(expected)
    }
  })

  it('does not turn an unavailable event or an out-of-window event into a seek target', () => {
    const html = render('all', [
      { ...feed[0], id: 'no-time', timestamp_ms: null as unknown as number, unavailable_reason: 'No crossing' },
      { ...feed[1], id: 'future', timestamp_ms: replay.chronology.window_end + 1000 },
    ])
    expect(html).not.toContain('class="scrubber-tick-dot"')
    expect(html).toContain('No sourced events for this filter')
    expect(html).not.toContain('future')
  })
})
