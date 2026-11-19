import React from 'react'
import fs from 'node:fs'
import path from 'node:path'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type {
  AnalysisDetail,
  AnalysisDetailBoat,
  BoatPerformance,
  PerformanceDimension,
  TacticalInsights,
  TacticalSnapshot,
} from '../../types/analysis'
import {
  BoatPerformanceRadar,
  performanceChartMaximum,
  performanceView,
} from './BoatPerformanceRadar'
import { ArchiveObservedPolarSection, RaceObservedPolarSection } from './ObservedPolarPanel'
import { TeamDebrief } from './TeamDebrief'
import { selectTacticalSnapshot, TacticalInsightsPanel } from './TacticalInsightsPanel'

const dimension = (id: string, index: number | null): PerformanceDimension => ({
  id,
  label: id,
  index,
  value: 5,
  peer_mean: 6,
  unit: id.includes('retention') ? '%' : 'kt',
  peer_count: 2,
  higher_is_better: true,
  coverage_s: 120,
  sample_count: id.includes('retention') ? 7 : 2,
  matched_legs: [1, 3],
  quality: index === null ? 'unavailable' : 'derived',
  formula: 'Mean of matched-leg peer ratios',
  denominator: 'Other eligible boats',
  source: 'recorded telemetry',
  ...(index === null ? { reason: 'No comparable peers' } : {}),
})
const performance = (): BoatPerformance => ({
  schema_version: '1.0',
  method_version: 'performance-1',
  baseline_index: 100,
  notes: ['Compare matching completed legs.'],
  overall_index: null,
  reason: 'One dimension unavailable.',
  dimensions: [
    dimension('upwind_vmg', 113),
    dimension('downwind_vmg', 201.5),
    dimension('upwind_speed', 0),
    dimension('downwind_speed', 98),
    dimension('tack_retention', null),
    dimension('gybe_retention', 101),
  ],
})
const boat = (): AnalysisDetailBoat =>
  ({
    id: 'a',
    team_code: 'ITA',
    team_name: 'Boat A',
    color: '#ef4444',
    performance: performance(),
  }) as AnalysisDetailBoat
const snapshot = (timestamp_ms: number): TacticalSnapshot => ({
  timestamp_ms,
  window_start_ms: timestamp_ms - 120000,
  window_end_ms: timestamp_ms,
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
  projection_change_deg: 10,
  projection_reason: 'Conditional trend extrapolation; timing is unvalidated.',
  insights: [
    {
      id: 'wind_direction',
      title: 'Direction trend',
      detail: `Observed direction at ${timestamp_ms}`,
      quality: 'derived',
      source: 'recorded official wind',
      kind: 'observed_direction',
    },
  ],
})
const series = (): TacticalInsights => ({
  schema_version: '1.0',
  method_version: 'tactical-1',
  race_id: 'race',
  source: 'recorded official wind',
  snapshot_interval_ms: 10000,
  max_snapshot_age_ms: 12000,
  window_s: 120,
  projection_horizon_s: 300,
  availability_basis: 'Measurement timestamps; arrival-time availability unknown.',
  snapshots: [snapshot(200000), snapshot(210000), snapshot(220000)],
})
const detail = (tactical = series()): AnalysisDetail =>
  ({ race: { id: 'race' }, tactical_insights: tactical }) as AnalysisDetail

describe('peer-relative boat performance graph', () => {
  it('shows exported raw indices, baseline and evidence without recalculating ratios', () => {
    const html = renderToStaticMarkup(React.createElement(BoatPerformanceRadar, { boat: boat() }))
    expect(html).toContain('100 = other eligible boats’ mean')
    expect(html).toContain('113.0')
    expect(html).toContain('201.5')
    expect(html).toContain('data-score="201.5"')
    expect(html).toContain('data-score="0"')
    expect(html).toContain('0–225')
    expect(html).toContain('Boat performance evidence')
    expect(html).toContain('No comparable peers')
    expect(html).toContain('COVERAGE / OBSERVATIONS')
    expect(html).toContain('120.000 s / 2 legs')
    expect(html).toContain('120.000 s / 7 events')
    expect(html).not.toContain('83.3')
    expect(html).not.toContain('radar-fill')
    expect(html.match(/radar-score-point/g) ?? []).toHaveLength(5)
    expect(html).toContain('aria-label="Inspect Upwind course VMG"')
    expect(html).toContain('aria-pressed="true"')
    expect(html).toContain('Pinned performance evidence')
    expect(html).toContain('Heuristic profile summary')
  })
  it('fills only a complete graph and leaves unavailable values distinct from zero', () => {
    const value = boat()
    value.performance!.dimensions[4] = dimension('tack_retention', 99)
    value.performance!.overall_index = 102
    const complete = renderToStaticMarkup(
      React.createElement(BoatPerformanceRadar, { boat: value })
    )
    expect(complete).toContain('radar-fill')
    expect(complete).toContain('102.0')
    delete value.performance
    const legacy = renderToStaticMarkup(React.createElement(BoatPerformanceRadar, { boat: value }))
    expect(legacy).toContain('unavailable in this export')
    expect(legacy).not.toContain('<svg')
  })
  it('makes the selected profile, peer baseline and signed exported differences explicit', () => {
    const html = renderToStaticMarkup(React.createElement(BoatPerformanceRadar, { boat: boat() }))
    expect(html).toContain('Performance comparison legend')
    expect(html).toContain('selected boat')
    expect(html).toContain('Other boats’ mean')
    expect(html).toContain('Solid blue profile: the selected boat')
    expect(html).toContain('data-index-difference="13"')
    expect(html).toContain('+13.0%')
    expect(html).toContain('+101.5%')
    expect(html).toContain('−2.0%')
    expect(html).toContain('−100.0%')
    expect(html).not.toContain('−16.7%') // Raw means 5/6 must not replace the exported index.
    expect(html).toContain('VS OTHERS')
  })
  it('does not draw an unavailable dimension as a zero peer difference', () => {
    const html = renderToStaticMarkup(React.createElement(BoatPerformanceRadar, { boat: boat() }))
    const missing = html.match(
      /<button[^>]*data-axis-id="tack_retention"[^>]*>(.*?)<\/button>/
    )?.[1]
    expect(missing).toContain('data-index-difference=""')
    expect(missing).toContain('No comparable value')
    expect(missing).not.toContain('<i style=')
    expect(missing).not.toContain('<b style=')
    expect(missing).not.toContain('+0.0%')
  })
  it('selects a Python-exported leg value and never manufactures unsupported axes', () => {
    const value = dimension('upwind_vmg', 110)
    value.leg_evidence = [
      {
        leg: 1,
        index: 127.0241,
        value: 19.5725,
        peer_mean: 15.4085,
        peer_count: 6,
        peer_ids: ['a', 'b', 'c', 'd', 'e', 'f'],
        coverage_s: 230,
        sample_count: 1,
      },
    ]
    expect(performanceView(value, 'all').index).toBe(110)
    expect(performanceView(value, '1').index).toBe(127.0241)
    expect(performanceView(value, '2').index).toBeNull()
    expect(performanceView(value, '2').reason).toContain('No qualifying comparison')
  })
  it('shares a domain across boats and preserves distinct 151/201 overflow values', () => {
    const first = boat(),
      second = boat()
    first.performance!.dimensions[0].index = 151
    second.performance!.dimensions[0].index = 201
    expect(performanceChartMaximum([first, second])).toBe(225)
    const firstHtml = renderToStaticMarkup(
      React.createElement(BoatPerformanceRadar, { boat: first, boats: [first, second] })
    )
    const secondHtml = renderToStaticMarkup(
      React.createElement(BoatPerformanceRadar, { boat: second, boats: [first, second] })
    )
    expect(firstHtml).toContain('data-chart-maximum="225"')
    expect(secondHtml).toContain('data-chart-maximum="225"')
    expect(firstHtml).toContain('data-focused-score="151"')
    expect(secondHtml).toContain('data-focused-score="201"')
  })
  it('keeps 99, 100 and 101 distinct in the focused detail drawing', () => {
    const positions = [99, 100, 101].map((score) => {
      const value = boat()
      value.performance!.dimensions[0].index = score
      const html = renderToStaticMarkup(React.createElement(BoatPerformanceRadar, { boat: value }))
      return Number(html.match(/cx="([0-9.]+)" cy="38" r="6"/)?.[1])
    })
    expect(positions).toEqual([167, 200, 233])
  })
  const liveNaplesAnalysis = path.resolve('public/data/analysis/naples_pr1.json')
  it.skipIf(!fs.existsSync(liveNaplesAnalysis))(
    'preserves the actual Naples arithmetic and exposes exported peer/interval evidence',
    () => {
      const detail = JSON.parse(fs.readFileSync(liveNaplesAnalysis, 'utf8')) as AnalysisDetail
      const value = detail.boats.find((entry) => entry.team_code === 'ITA G')!
      const axis = value.performance!.dimensions.find((entry) => entry.id === 'downwind_vmg')!
      expect(performanceView(axis, 'all').index).toBeCloseTo(109.9671, 4)
      expect(performanceView(axis, '2').index).toBeCloseTo(127.0241, 4)
      expect(performanceView(axis, '4').index).toBeCloseTo(92.9101, 4)
      expect((100 * axis.value!) / axis.peer_mean!).toBeCloseTo(108.0853, 4)
      expect(axis.leg_evidence!.map((entry) => entry.peer_count)).toEqual([6, 4])
      const html = renderToStaticMarkup(
        React.createElement(BoatPerformanceRadar, {
          boat: value,
          raceId: detail.race.id,
          boats: detail.boats,
          replayAvailable: true,
          onReviewLeg: () => {},
        })
      )
      expect(html).toContain('data-performance-race="naples_pr1"')
      expect(html).toContain('data-performance-boat="' + value.id + '"')
      expect(html).toContain('Review leg 1 in replay')
      expect(html).toContain('Decimal detail shows arithmetic, not measurement certainty')
    }
  )
})

describe('playhead tactical insight selection', () => {
  it('selects the latest reached snapshot and rewinds without retaining later observations', () => {
    expect(selectTacticalSnapshot(series(), 'race', 219999).snapshot?.timestamp_ms).toBe(210000)
    expect(selectTacticalSnapshot(series(), 'race', 220000).snapshot?.timestamp_ms).toBe(220000)
    expect(selectTacticalSnapshot(series(), 'race', 200000).snapshot?.timestamp_ms).toBe(200000)
    const html = renderToStaticMarkup(
      React.createElement(TacticalInsightsPanel, {
        detail: detail(),
        raceId: 'race',
        playhead: 209999,
      })
    )
    expect(html).toContain('data-as-of="200000"')
    expect(html).toContain('Observed direction at 200000')
    expect(html).not.toContain('Observed direction at 210000')
    expect(html).toContain('Conditional trend extrapolation')
    expect(html).toContain('arrival-time availability unknown')
  })
  it('rejects another race, an unreached window, stale windows and invalid playheads', () => {
    expect(selectTacticalSnapshot(series(), 'other', 210000).snapshot).toBeNull()
    expect(selectTacticalSnapshot(series(), 'race', 199999).snapshot).toBeNull()
    expect(selectTacticalSnapshot(series(), 'race', 232000).snapshot?.timestamp_ms).toBe(220000)
    expect(selectTacticalSnapshot(series(), 'race', 232001).snapshot).toBeNull()
    expect(selectTacticalSnapshot(series(), 'race', NaN).snapshot).toBeNull()
    expect(selectTacticalSnapshot(undefined, 'race', 220000).snapshot).toBeNull()
    const html = renderToStaticMarkup(
      React.createElement(TacticalInsightsPanel, {
        detail: detail(),
        raceId: 'other',
        playhead: 220000,
      })
    )
    expect(html).toContain('unavailable for this race')
    expect(html).not.toContain('Observed direction')
  })
  it('preserves valid speed observations when direction coverage is unavailable', () => {
    const tactical = series()
    tactical.snapshots[0] = {
      ...snapshot(200000),
      quality: 'unavailable',
      reason: 'Direction stream missing.',
      direction_change_deg: null,
      direction_rate_deg_per_min: null,
      projection_change_deg: null,
      insights: [
        {
          id: 'speed',
          title: 'Observed wind speed change',
          detail: 'Recorded wind speed increased.',
          quality: 'derived',
          source: 'recorded official wind',
          kind: 'observed_speed',
        },
      ],
    }
    const html = renderToStaticMarkup(
      React.createElement(TacticalInsightsPanel, {
        detail: detail(tactical),
        raceId: 'race',
        playhead: 200000,
      })
    )
    expect(html).toContain('Direction stream missing.')
    expect(html).toContain('Recorded wind speed increased.')
    expect(html).toContain('1200 speed samples')
  })
  it('shows a missing speed stream beside valid direction observations', () => {
    const tactical = series()
    tactical.snapshots[0] = {
      ...snapshot(200000),
      speed_coverage_s: 20,
      speed_sample_count: 30,
      speed_quality: 'unavailable',
      speed_reason: 'Official speed observations have a gap.',
      speed_change_kt: null,
    }
    const html = renderToStaticMarkup(
      React.createElement(TacticalInsightsPanel, {
        detail: detail(tactical),
        raceId: 'race',
        playhead: 200000,
      })
    )
    expect(html).toContain('20 s covered')
    expect(html).toContain('30 speed samples')
    expect(html).toContain('Official speed observations have a gap.')
    expect(html).toContain('Direction trend')
  })
  it('explains sessions that ended before the source gun', () => {
    const tactical = {
      ...series(),
      snapshots: [],
      reason: 'Replay window ends before the source gun; no post-gun tactical interval.',
    }
    expect(selectTacticalSnapshot(tactical, 'race', 200000).reason).toBe(tactical.reason)
    const html = renderToStaticMarkup(
      React.createElement(TacticalInsightsPanel, {
        detail: detail(tactical),
        raceId: 'race',
        playhead: 200000,
      })
    )
    expect(html).toContain(tactical.reason)
    expect(html).toContain('data-as-of=""')
  })
  it('exposes exported tactical formulas and denominators in the evidence disclosure', () => {
    const tactical = series()
    tactical.definitions = {
      speed_change_kt: {
        label: 'Recorded speed change',
        unit: 'kt',
        formula: 'Last minus first valid speed.',
        window: 'Trailing 120 seconds',
        denominator: 'Paired endpoints',
        source: 'Official wind speed',
      },
    }
    const html = renderToStaticMarkup(
      React.createElement(TacticalInsightsPanel, {
        detail: detail(tactical),
        raceId: 'race',
        playhead: 200000,
      })
    )
    expect(html).toContain('Recorded speed change (kt)')
    expect(html).toContain('Last minus first valid speed.')
    expect(html).toContain('Window: Trailing 120 seconds')
    expect(html).toContain('Denominator: Paired endpoints')
    expect(html).toContain('Source: Official wind speed')
  })
})

describe('evidence-linked team debrief', () => {
  it('uses exported observations and timestamps for replay review', () => {
    const value = boat()
    value.debrief = {
      schema_version: '1.0',
      method_version: 'debrief-1',
      items: [
        {
          id: 'leg',
          title: 'Review leg 2',
          detail: 'Completed leg behind peer mean.',
          timestamp_ms: 210000,
          value: 4.5,
          unit: 's',
          quality: 'reconstructed',
          source: 'completed leg timing',
          kind: 'leg_deficit',
          peer_count: 2,
        },
      ],
    }
    const html = renderToStaticMarkup(
      React.createElement(TeamDebrief, {
        boat: value,
        raceId: 'race',
        replayAvailable: true,
        onOpenReplay: () => {},
      })
    )
    expect(html).toContain('data-review-timestamp="210000"')
    expect(html).toContain('4.5 s')
    expect(html).toContain('Review in replay')
    expect(html).toContain('2 peers')
    const disabled = renderToStaticMarkup(
      React.createElement(TeamDebrief, {
        boat: value,
        raceId: 'race',
        replayAvailable: false,
        onOpenReplay: () => {},
      })
    )
    expect(disabled).toContain('disabled=""')
    expect(disabled).toContain('Replay unavailable')
  })
})

describe('observed ground-speed polar and conditional residuals', () => {
  it('renders race observed ground-speed polar with honest caveats and bootstrap confidence intervals', () => {
    const sampleBoat = {
      ...boat(),
      polar: {
        schema_version: '1.0' as const,
        method_version: 'polar-1',
        quality: 'derived' as const,
        reason: null,
        evaluation_scope: 'out_of_sample_archive_cv',
        steady_sample_count: 240,
        steady_coverage_s: 240,
        leg_cluster_count: 4,
        sog_residual_kt: { value: 0.45, ci_low_kt: 0.12, ci_high_kt: 0.78, bootstrap_se_kt: 0.17 },
        wind_vmg_residual_kt: {
          value: 0.31,
          ci_low_kt: -0.02,
          ci_high_kt: 0.64,
          bootstrap_se_kt: 0.17,
        },
        loro_sog_residual_kt: 0.49,
        lodo_sog_residual_kt: 0.45,
        port_sog_residual_kt: 0.3,
        starboard_sog_residual_kt: 0.6,
        above_p90_share: 0.145,
        traffic_excluded_s: 32,
        observed_bins: {
          upwind: [
            {
              tack: 'PORT' as const,
              tws_bin_kt: 12,
              twa_bin_deg: 45,
              sog_mean_kt: 26.5,
              sog_p90_kt: 28.0,
              wind_vmg_mean_kt: 18.7,
              predicted_sog_kt: 26.0,
              sample_count: 30,
            },
          ],
          downwind: [],
        },
      },
    } as AnalysisDetailBoat
    const raceDetail = {
      race: { id: 'race' },
      boats: [sampleBoat],
      polar_analysis: {
        schema_version: '1.0' as const,
        method_version: 'polar-1',
        race_id: 'race',
        quality: 'derived' as const,
        reason: null,
        evaluation_scope: 'out_of_sample_archive_cv',
        caveats: ['Observed ground-speed polar'],
        definitions: {},
        validation_summary: null,
        brackets: {
          upwind: [
            {
              id: 'race_window',
              label: 'Race wind (11.0–13.0 kt)',
              tws_min_kt: 11,
              tws_max_kt: 13,
              tws_ref_kt: 12,
              points: [
                {
                  twa_deg: 40,
                  mean_sog_kt: 24.5,
                  p50_sog_kt: 24.6,
                  p90_sog_kt: 26.2,
                  mean_wind_vmg_kt: 18.8,
                  p50_wind_vmg_kt: 18.9,
                  p90_wind_vmg_kt: 20.1,
                  effective_coverage_s: 120,
                  support_clusters: 4,
                },
                {
                  twa_deg: 45,
                  mean_sog_kt: 26.1,
                  p50_sog_kt: 26.2,
                  p90_sog_kt: 27.9,
                  mean_wind_vmg_kt: 18.5,
                  p50_wind_vmg_kt: 18.6,
                  p90_wind_vmg_kt: 19.8,
                  effective_coverage_s: 140,
                  support_clusters: 5,
                },
              ],
            },
          ],
          downwind: [],
        },
      },
    } as unknown as AnalysisDetail
    const html = renderToStaticMarkup(
      React.createElement(RaceObservedPolarSection, { detail: raceDetail, boat: sampleBoat })
    )
    expect(html).toContain('Observed ground-speed polar')
    expect(html).toContain('SOG includes surface current')
    expect(html).toContain('observed upper conditional percentile')
    expect(html).toContain('fixed effect')
    expect(html).toContain('95% bootstrap CI')
    expect(html).not.toContain('credible interval')
    expect(html).toContain('14.5%')
  })
  it('renders archive Day-Grouped vs LORO CV validation and fixed-effect tack contrast', () => {
    const html = renderToStaticMarkup(
      React.createElement(ArchiveObservedPolarSection, {
        selectedTeam: 'NZL B',
        polarModel: {
          schema_version: '1.0',
          method_version: 'polar-1',
          evaluation_scope: '28-session AC40 archive',
          steady_state_filter: {
            sample_cadence_hz: 1,
            min_sog_kt: 5,
            max_sog_kt: 50,
            min_tws_kt: 2,
            max_tws_kt: 35,
            upwind_abs_twa_deg: [28, 75],
            downwind_abs_twa_deg: [105, 172],
            manoeuvre_exclusion_s: 6.5,
            gate_exclusion_s: 8,
            max_turn_rate_deg_s: 6,
            min_competitor_separation_m: 60,
          },
          caveats: [],
          definitions: {},
          counts: {
            eligible_races: 25,
            excluded_races: 3,
            distinct_days: 8,
            boat_leg_clusters: 987,
            steady_coverage_s: 131620,
            steady_cells: 29601,
          },
          tack_fixed_effect: {
            specification: 'Two-category fixed effect',
            bootstrap_draws: 500,
            upwind: {
              contrast_kt: -0.174,
              ci_low_kt: -0.312,
              ci_high_kt: -0.049,
              bootstrap_se_kt: 0.069,
              coverage_s: 76293,
            },
            downwind: {
              contrast_kt: -0.044,
              ci_low_kt: -0.195,
              ci_high_kt: 0.104,
              bootstrap_se_kt: 0.077,
              coverage_s: 55327,
            },
            overall: {
              contrast_kt: -0.119,
              ci_low_kt: -0.215,
              ci_high_kt: -0.027,
              bootstrap_se_kt: 0.051,
              coverage_s: 131620,
            },
          },
          validation: {
            baseline_mode_only: {
              label: 'Unconditioned leg-mode baseline',
              folds: 8,
              sog_rmse_kt: 3.878,
              sog_mae_kt: 3.007,
              sog_r2: 0.5,
              vmg_rmse_kt: 4.844,
              vmg_mae_kt: 3.698,
              vmg_r2: 0.405,
              p50_pinball_loss_kt: 1.497,
              p90_pinball_loss_kt: 0.658,
              p50_empirical_coverage: 0.5085,
              p90_empirical_coverage: 0.8551,
            },
            leave_one_race_out: {
              label: 'Leave-One-Race-Out CV (LORO)',
              folds: 25,
              sog_rmse_kt: 2.289,
              sog_mae_kt: 1.64,
              sog_r2: 0.8259,
              vmg_rmse_kt: 1.831,
              vmg_mae_kt: 1.359,
              vmg_r2: 0.915,
              p50_pinball_loss_kt: 0.819,
              p90_pinball_loss_kt: 0.354,
              p50_empirical_coverage: 0.5018,
              p90_empirical_coverage: 0.9103,
            },
            leave_one_day_out: {
              label: 'Day-Grouped CV (Leave-One-Day-Out)',
              folds: 8,
              sog_rmse_kt: 2.421,
              sog_mae_kt: 1.756,
              sog_r2: 0.8052,
              vmg_rmse_kt: 1.986,
              vmg_mae_kt: 1.469,
              vmg_r2: 0.9,
              p50_pinball_loss_kt: 0.886,
              p90_pinball_loss_kt: 0.41,
              p50_empirical_coverage: 0.504,
              p90_empirical_coverage: 0.8755,
            },
          },
          team_residuals: [
            {
              team_code: 'NZL B',
              race_count: 24,
              leg_cluster_count: 112,
              steady_coverage_s: 15200,
              lodo_sog_residual_kt: {
                value: 0.468,
                ci_low_kt: 0.128,
                ci_high_kt: 0.839,
                bootstrap_se_kt: 0.185,
              },
              loro_sog_residual_kt: {
                value: 0.384,
                ci_low_kt: 0.07,
                ci_high_kt: 0.712,
                bootstrap_se_kt: 0.167,
              },
              in_sample_sog_residual_kt: {
                value: 0.39,
                ci_low_kt: 0.08,
                ci_high_kt: 0.7,
                bootstrap_se_kt: 0.16,
              },
              wind_vmg_residual_kt: {
                value: 0.312,
                ci_low_kt: 0.035,
                ci_high_kt: 0.603,
                bootstrap_se_kt: 0.155,
              },
              upwind_sog_residual_kt: 0.52,
              downwind_sog_residual_kt: 0.39,
              port_sog_residual_kt: 0.41,
              starboard_sog_residual_kt: 0.51,
              above_p90_share: 0.154,
              bootstrap_draws: 500,
            },
          ],
          curves: { upwind: [], downwind: [] },
        },
      })
    )
    expect(html).toContain('Day-grouped vs. Leave-One-Race-Out validation')
    expect(html).toContain('Two-category fixed effect for tack')
    expect(html).toContain('polar-row-selected')
    expect(html).toContain('leg-cluster bootstrap confidence intervals')
    expect(html).not.toContain('credible interval')
  })
})
