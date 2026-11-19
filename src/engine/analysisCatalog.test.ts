import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import type { AnalysisDetail } from '../types/analysis'
import { validateAnalysisEnhancements } from './analysisCatalog'

const fixture = () => {
  const value = {
    race: { id: 'race' },
    boats: [
      {
        id: 'a',
        performance: {
          schema_version: '1.0',
          method_version: 'performance-1',
          overall_index: null,
          baseline_index: 100,
          notes: ['Same-race peers.'],
          dimensions: [
            {
              id: 'upwind',
              label: 'Upwind',
              index: 110,
              value: 10,
              peer_mean: 9,
              unit: 'kt',
              peer_count: 1,
              higher_is_better: true,
              coverage_s: 120,
              sample_count: 120,
              matched_legs: [1],
              quality: 'derived',
              formula: 'Exported formula',
              denominator: 'Other boats',
              source: 'Recorded telemetry',
            },
          ],
        },
        debrief: {
          schema_version: '1.0',
          method_version: 'debrief-1',
          items: [
            {
              id: 'loss',
              title: 'Review',
              detail: 'Review loss',
              timestamp_ms: 220000,
              value: 2,
              unit: 's',
              quality: 'derived',
              source: 'completed legs',
              kind: 'leg_deficit',
            },
          ],
        },
      },
    ],
    tactical_insights: {
      schema_version: '1.0',
      method_version: 'tactical-1',
      race_id: 'race',
      source: 'recorded official wind',
      snapshot_interval_ms: 10000,
      max_snapshot_age_ms: 12000,
      window_s: 120,
      projection_horizon_s: 300,
      availability_basis: 'Measurement timestamps',
      snapshots: [
        {
          timestamp_ms: 220000,
          window_start_ms: 100000,
          window_end_ms: 220000,
          coverage_s: 120,
          sample_count: 1200,
          quality: 'derived',
          source: 'recorded official wind',
          direction_change_deg: 4,
          direction_rate_deg_per_min: 2,
          speed_change_kt: 1,
          speed_coverage_s: 120,
          speed_sample_count: 1200,
          speed_quality: 'derived',
          speed_reason: null,
          projection_change_deg: null,
          projection_reason: 'Insufficient evidence for projection.',
          insights: [],
        },
      ],
    },
  } as AnalysisDetail
  const base = value.boats[0].performance!.dimensions[0]
  value.boats[0].performance!.dimensions = [
    'upwind_vmg',
    'downwind_vmg',
    'upwind_speed',
    'downwind_speed',
    'tack_retention',
    'gybe_retention',
  ].map((id) => ({
    ...base,
    id,
    unit: id.includes('retention') ? ('%' as const) : ('kt' as const),
    sample_count: 1,
  }))
  return value
}

describe('additive analysis contracts', () => {
  it('accepts the shipped enhancements for every catalog race (or synthetic fixture without public/data)', () => {
    const liveManifestPath = path.resolve('public/data/manifests.json')
    if (!fs.existsSync(liveManifestPath)) {
      const synthetic = JSON.parse(
        fs.readFileSync(path.resolve('tests/fixtures/synthetic_analysis.json'), 'utf8')
      ) as AnalysisDetail
      expect(synthetic.tactical_insights?.race_id).toBe(synthetic.race.id)
      expect(() => validateAnalysisEnhancements(synthetic)).not.toThrow()
      return
    }
    const manifest = JSON.parse(fs.readFileSync(liveManifestPath, 'utf8')) as {
      regattas: Array<{ races: Array<{ id: string }> }>
    }
    const races = manifest.regattas.flatMap((regatta) => regatta.races)
    for (const race of races) {
      const detail = JSON.parse(
        fs.readFileSync(path.resolve(`public/data/analysis/${race.id}.json`), 'utf8')
      ) as AnalysisDetail
      expect(detail.tactical_insights?.race_id).toBe(race.id)
      expect(
        detail.boats.every((boat) => boat.performance?.dimensions.length === 6 && boat.debrief)
      ).toBe(true)
      expect(() => validateAnalysisEnhancements(detail), race.id).not.toThrow()
    }
  })
  it('supports old exports and complete optional enhancements', () => {
    expect(() =>
      validateAnalysisEnhancements({ race: { id: 'race' }, boats: [] } as unknown as AnalysisDetail)
    ).not.toThrow()
    expect(() => validateAnalysisEnhancements(fixture())).not.toThrow()
  })
  it('rejects non-finite scores, invalid peer counts, duplicate axes and fake baselines', () => {
    const nonfinite = fixture()
    nonfinite.boats[0].performance!.dimensions[0].index = Infinity
    expect(() => validateAnalysisEnhancements(nonfinite)).toThrow('Boat performance')
    const peers = fixture()
    peers.boats[0].performance!.dimensions[0].peer_count = -1
    expect(() => validateAnalysisEnhancements(peers)).toThrow('Boat performance')
    const duplicate = fixture()
    duplicate.boats[0].performance!.dimensions.push(duplicate.boats[0].performance!.dimensions[0])
    expect(() => validateAnalysisEnhancements(duplicate)).toThrow('Boat performance')
    const baseline = fixture()
    baseline.boats[0].performance!.baseline_index = 0
    expect(() => validateAnalysisEnhancements(baseline)).toThrow('Boat performance')
  })
  it('rejects mismatched races, future windows and unordered tactical snapshots', () => {
    const mismatch = fixture()
    mismatch.tactical_insights!.race_id = 'other'
    expect(() => validateAnalysisEnhancements(mismatch)).toThrow('Tactical insights')
    const future = fixture()
    future.tactical_insights!.snapshots[0].window_end_ms += 1
    expect(() => validateAnalysisEnhancements(future)).toThrow('Tactical insights')
    const unsorted = fixture()
    unsorted.tactical_insights!.snapshots.push({ ...unsorted.tactical_insights!.snapshots[0] })
    expect(() => validateAnalysisEnhancements(unsorted)).toThrow('Tactical insights')
  })
  it('rejects invalid debrief timestamps rather than emitting broken replay links', () => {
    const invalid = fixture()
    invalid.boats[0].debrief!.items[0].timestamp_ms = NaN
    expect(() => validateAnalysisEnhancements(invalid)).toThrow('Team debrief')
  })
  it('validates selected-leg peer identities, intervals, counts and scope metadata', () => {
    const value = fixture()
    value.boats.push({ ...value.boats[0], id: 'b', performance: undefined, debrief: undefined })
    const dimension = value.boats[0].performance!.dimensions[0]
    dimension.leg_evidence = [
      {
        leg: 1,
        index: 110,
        value: 10,
        peer_mean: 9,
        peer_count: 1,
        peer_ids: ['b'],
        coverage_s: 120,
        sample_count: 1,
        start_ms: 100000,
        end_ms: 220000,
        quality: 'derived',
        peers: [
          {
            id: 'b',
            team_code: 'B',
            team_name: 'Boat B',
            value: 9,
            coverage_s: 120,
            sample_count: 1,
            start_ms: 100000,
            end_ms: 220000,
            quality: 'derived',
          },
        ],
      },
    ]
    value.boats[0].performance!.scope = {
      expected_legs: [1, 2],
      matched_legs: [1],
      expected_leg_count: 2,
      matched_leg_count: 1,
      min_peer_count: 1,
      covered_s: 120,
      excluded_legs: [{ leg: 2, reason: 'Missing crossing' }],
    }
    expect(() => validateAnalysisEnhancements(value)).not.toThrow()
    const corrupt = structuredClone(value)
    corrupt.boats[0].performance!.dimensions[0].leg_evidence![0].peer_ids = ['a']
    expect(() => validateAnalysisEnhancements(corrupt)).toThrow('Boat performance evidence')
    const interval = structuredClone(value)
    interval.boats[0].performance!.dimensions[0].leg_evidence![0].peers![0].end_ms = 1
    expect(() => validateAnalysisEnhancements(interval)).toThrow('Boat performance evidence')
    const scope = structuredClone(value)
    scope.boats[0].performance!.scope!.excluded_legs = []
    expect(() => validateAnalysisEnhancements(scope)).toThrow('Boat performance evidence')
    const duplicate = structuredClone(value)
    duplicate.boats[0].performance!.dimensions[0].leg_evidence!.push(dimension.leg_evidence[0])
    expect(() => validateAnalysisEnhancements(duplicate)).toThrow('Boat performance evidence')
    const wrongUnit = structuredClone(value)
    wrongUnit.boats[0].performance!.dimensions[0].unit = '%'
    expect(() => validateAnalysisEnhancements(wrongUnit)).toThrow('Boat performance')
  })
  it('validates observed ground-speed polar contracts and rejects inverted bootstrap bounds', () => {
    const valid = fixture()
    valid.boats[0].polar = {
      schema_version: '1.0',
      method_version: 'polar-1',
      quality: 'derived',
      reason: null,
      evaluation_scope: 'out_of_sample_archive_cv',
      steady_sample_count: 100,
      steady_coverage_s: 100,
      leg_cluster_count: 2,
      sog_residual_kt: { value: 0.4, ci_low_kt: 0.1, ci_high_kt: 0.7, bootstrap_se_kt: 0.15 },
      wind_vmg_residual_kt: { value: 0.3, ci_low_kt: 0.0, ci_high_kt: 0.6, bootstrap_se_kt: 0.15 },
      loro_sog_residual_kt: 0.42,
      lodo_sog_residual_kt: 0.4,
      above_p90_share: 0.12,
      traffic_excluded_s: 10,
      observed_bins: { upwind: [], downwind: [] },
    }
    valid.polar_analysis = {
      schema_version: '1.0',
      method_version: 'polar-1',
      race_id: 'race',
      quality: 'derived',
      reason: null,
      evaluation_scope: 'out_of_sample_archive_cv',
      caveats: ['Observed ground-speed polar: SOG includes surface current.'],
      definitions: {},
      validation_summary: null,
      brackets: { upwind: [], downwind: [] },
    }
    expect(() => validateAnalysisEnhancements(valid)).not.toThrow()

    const badCi = structuredClone(valid)
    badCi.boats[0].polar!.sog_residual_kt!.ci_low_kt = 0.8
    expect(() => validateAnalysisEnhancements(badCi)).toThrow('Boat polar')

    const mismatchPolar = structuredClone(valid)
    mismatchPolar.polar_analysis!.race_id = 'other'
    expect(() => validateAnalysisEnhancements(mismatchPolar)).toThrow('Observed polar')
  })
})
