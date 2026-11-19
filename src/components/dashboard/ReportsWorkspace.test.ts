import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { AnalysisDetail } from '../../types/analysis'
import type { ReplayManifest } from '../../types/replay'
import {
  primaryDownloads,
  ReportsWorkspace,
  technicalDownloads,
  type Artifact,
} from './ReportsWorkspace'
const metric = (value: number | null, quality = 'partial') => ({
  value,
  unit: 'kt',
  quality,
  coverage_s: value === null ? null : 847.085,
  reason: value === null ? 'no valid racing window' : 'observed incomplete leg',
})
const replay = {
  id: 'race',
  name: 'Race',
  competitors: [
    {
      id: 'boat',
      team_code: 'GBR B',
      team_name: 'Boat',
      summary: { avg_speed_kt: 9876, distance_sailed_m: 8765 },
    },
  ],
} as unknown as ReplayManifest
const detail = {
  race: { id: 'race' },
  boats: [
    {
      id: 'boat',
      classification: 'RET',
      official_rank: null,
      official_elapsed_s: null,
      metrics: {
        sog_mean_kt: metric(null),
        distance_m: metric(12769.8969),
        tack_count: { ...metric(7), unit: 'events' },
        gybe_count: { ...metric(4), unit: 'events' },
      },
      source_conflicts: ['Source start conflict'],
    },
  ],
} as unknown as AnalysisDetail
const artifact = (id: string, extra: Partial<Artifact> = {}): Artifact => ({
  id,
  url: `/data/${id}`,
  race_id: 'race',
  label: id,
  view: 'Reports',
  bytes: 500,
  format: 'json',
  kind: 'analysis',
  status: 'current',
  primary_download: true,
  ...extra,
})
describe('canonical professional reports', () => {
  it('uses analysis values, partial coverage and reasons without legacy summary fallback', () => {
    const html = renderToStaticMarkup(
      React.createElement(ReportsWorkspace, {
        replay,
        analysisDetail: detail,
        catalog: [],
        onOpenRace: () => {},
      })
    )
    for (const text of [
      '12,769.90',
      '847.1 s covered',
      'no valid racing window',
      'Source start conflict',
      'data-value="12769.8969"',
      '<details class="technical-data">',
    ])
      expect(html).toContain(text)
    for (const text of ['9876', '8765', 'Artifact library']) expect(html).not.toContain(text)
  })
  it('keeps missing or mismatched analysis unavailable instead of borrowing replay values', () => {
    for (const analysis of [null, { ...detail, race: { ...detail.race, id: 'other' } }]) {
      const html = renderToStaticMarkup(
        React.createElement(ReportsWorkspace, {
          replay,
          analysisDetail: analysis,
          catalog: [],
          onOpenRace: () => {},
        })
      )
      expect(html).toContain('Historical analysis is unavailable or still loading')
      expect(html).not.toContain('12,769.90')
      expect(html).not.toContain('9876')
    }
  })
  it('offers only current producer-classified race exports and preserves the searchable complete catalog', () => {
    const items = [
      artifact('primary'),
      artifact('retained', { status: 'retained' }),
      artifact('raw', { status: 'supporting', primary_download: false }),
      artifact('global', { race_id: null }),
      artifact('other', { race_id: 'other' }),
      artifact('legacy', { primary_download: undefined, status: undefined }),
    ]
    expect(primaryDownloads(items, 'race').map((item) => item.id)).toEqual(['primary'])
    expect(technicalDownloads(items, 'race', 'all', '')).toHaveLength(6)
    expect(technicalDownloads(items, 'race', 'retained', '').map((item) => item.id)).toEqual([
      'retained',
    ])
    expect(technicalDownloads(items, 'race', 'supporting', 'RAW').map((item) => item.id)).toEqual([
      'raw',
    ])
    expect(technicalDownloads(items, 'race', 'current', '').map((item) => item.id)).toEqual([
      'primary',
      'raw',
      'legacy',
    ])
  })
})
