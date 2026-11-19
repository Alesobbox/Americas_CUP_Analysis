import React from 'react'
import fs from 'node:fs'
import path from 'node:path'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { AnalysisDetail, AnalysisIndex, ArchivePolarModel } from '../../types/analysis'
import type { PolarExperiments, TimingResearch, WindForecastModel } from '../../types/research'
import { ArchiveAc38ResearchSection, RaceAc38ResearchSection } from './Ac38ResearchPanel'
import { ArchiveObservedPolarSection } from './ObservedPolarPanel'
import { RaceTimingResearch, RaceWindResearch } from './RaceResearchDetails'

function emptyIndex(): AnalysisIndex {
  return { schema_version: '2.0', races: [], histories: [] }
}

const comparison = {
  day_equal: { kernel: { days: 2, mean_rmse_kt: 0, mean_mae_kt: 0 } },
  sample_weighted: { kernel: { sample_count: 20, rmse_kt: 0, mae_kt: 0, bias_kt: 0 } },
}

function polarResearch(): PolarExperiments {
  return {
    schema_version: 'test',
    status: 'evaluated',
    scope: 'retrospective',
    cohort: { sample_count: 20, days: 2, races: 3 },
    model_comparison: { leave_one_day_out: comparison, chronological: comparison },
  }
}

function windModel(): WindForecastModel {
  const scores = { brier: 0, log_loss: 0, circular_crps_deg: 0 }
  return {
    schema_version: '1.0',
    status: 'experimental',
    availability_basis: 'recorded time',
    counts: { races: 3, context_days: 2, scored_targets: 10, censored_targets: 4 },
    target: { definition: 'endpoint', horizon_s: 180, threshold_deg: 5 },
    limitations: [],
    validation: {
      probabilistic_persistence: {
        day_equal: scores,
        sample_weighted: scores,
        scored_days: 2,
        scored_targets: 10,
      },
    },
  }
}

function timing(): TimingResearch {
  return {
    schema_version: 'timing-research-1',
    scope: 'retrospective',
    caveats: [],
    boats: [
      {
        boat_id: 'a',
        team_code: 'A',
        ledger: {
          quality: 'partial',
          complete_finish: false,
          reason: 'Observed prefix only',
          accounted_elapsed_s: 10,
          reconciliation_error_s: 0,
          components: [
            { kind: 'start_delay', leg: null, elapsed_s: 1 },
            { kind: 'leg', leg: 1, elapsed_s: 9 },
          ],
        },
        phases: { quality: 'derived', seconds: { unavailable: 1, other_sailing: 8 } },
        detector_evaluation: {
          status: 'insufficient_reviewed_labels',
          precision: null,
          recall: null,
        },
        turns: [
          {
            timestamp_ms: 5000,
            type: 'TACK',
            leg: 1,
            cost_quality: 'conditional',
            review_status: 'unreviewed',
            horizons: [
              {
                horizon_s: 20,
                observed_duration_s: 10,
                coverage_s: 10,
                right_censored: true,
                censor_reason: 'source_gap',
                progress_deficit_m: null,
                polar_reference_deficit_m: null,
              },
            ],
            recovery: {
              right_censored: true,
              recovery_s: null,
              speed_regime: 'severe_speed_collapse',
            },
          },
        ],
      },
    ],
  }
}

describe('AC38 research evidence panels', () => {
  it.runIf(fs.existsSync(path.resolve('public/data/research/polar_experiments.json')))(
    'renders regenerated archive and race research without invalid numeric displays',
    () => {
      const index: AnalysisIndex = JSON.parse(
        fs.readFileSync('public/data/analysis/index.json', 'utf8')
      )
      const archive = renderToStaticMarkup(
        React.createElement(ArchiveAc38ResearchSection, { index })
      )
      expect(archive).toContain('AC38 research comparisons')
      expect(archive).not.toContain('NaN')
      for (const race of [index.races[0], index.races[index.races.length - 1]]) {
        const detail: AnalysisDetail = JSON.parse(
          fs.readFileSync(`public/data/${race.analysis_file}`, 'utf8')
        )
        const html = renderToStaticMarkup(
          React.createElement(RaceAc38ResearchSection, {
            detail,
            boatId: detail.boats[0].id,
          })
        )
        expect(html).toContain('Exact checkpoint timing ledger')
        expect(html).not.toContain('NaN')
      }
    }
  )

  it('omits absent extensions and unavailable download links', () => {
    const html = renderToStaticMarkup(
      React.createElement(ArchiveAc38ResearchSection, { index: emptyIndex() })
    )
    expect(html).toBe('')
  })

  it('renders sample counts, chronological comparisons and real zero scores', () => {
    const index = {
      ...emptyIndex(),
      polar_research: polarResearch(),
      wind_forecast_model: windModel(),
    }
    const html = renderToStaticMarkup(React.createElement(ArchiveAc38ResearchSection, { index }))
    expect(html).toContain('20 accepted')
    expect(html).toContain('earlier days predict later days')
    expect(html).toContain('0.000 kt')
    expect(html).toContain('0.0000')
    expect(html).toContain('4 endpoint targets are censored')
    expect(html).toContain('/data/research/polar_experiments.json')
    expect(html).not.toContain('NaN')
  })

  it('keeps unreviewed candidates, censored horizons and partial finishes explicit', () => {
    const html = renderToStaticMarkup(
      React.createElement(RaceTimingResearch, { report: timing(), boatId: 'a', gunMs: 0 })
    )
    expect(html).toContain('Observed prefix only')
    expect(html).toContain('Censored: source gap')
    expect(html).toContain('unreviewed')
    expect(html).toContain(
      'Unavailable until candidate and background windows receive independent review'
    )
    expect(html).not.toContain('0.0 m')
    expect(html).toContain('not verified touchdowns')
    expect(html).not.toMatch(/reconstruct/i)

    const completeReport = timing()
    completeReport.boats[0].ledger = {
      ...completeReport.boats[0].ledger,
      quality: 'reconstructed',
      complete_finish: true,
      reason: null,
    }
    const completeHtml = renderToStaticMarkup(
      React.createElement(RaceTimingResearch, { report: completeReport, boatId: 'a', gunMs: 0 })
    )
    expect(completeHtml).toContain('Complete calculated finish.')
    expect(completeHtml).not.toMatch(/reconstruct/i)
  })

  it('does not fabricate a forecast for the first training day', () => {
    const html = renderToStaticMarkup(
      React.createElement(RaceWindResearch, {
        gunMs: 0,
        report: {
          schema_version: '1.0',
          availability_basis: 'recorded time',
          unavailable_prediction_count: 3,
          reference_model: 'probabilistic_persistence',
          predictions: [],
        },
      })
    )
    expect(html).toContain('No forecast was eligible from earlier-day training data')
    expect(html).not.toContain('0.0%')
  })

  it('renders recorded-time probabilities with their endpoint and training scope', () => {
    const html = renderToStaticMarkup(
      React.createElement(RaceWindResearch, {
        gunMs: 0,
        report: {
          schema_version: '1.0',
          availability_basis: 'recorded time',
          unavailable_prediction_count: 0,
          reference_model: 'probabilistic_persistence',
          training_days: 2,
          predictions: [
            {
              timestamp_ms: 10000,
              target_timestamp_ms: 190000,
              current_twd_deg: 359,
              methods: {
                probabilistic_persistence: { probability_shift_ge_5deg: 0.25, center_twd_deg: 1 },
              },
              target_status: 'censored',
            },
          ],
        },
      })
    )
    expect(html).toContain('25.0%')
    expect(html).toContain('+3:10')
    expect(html).toContain('Training uses 2 earlier days')
    expect(html).toContain('live delivery times are unverified')
  })

  it('supports unavailable chronological metrics and explicitly identifies legacy aggregation', () => {
    const metric = { label: 'Unavailable chronological', folds: 0, status: 'unavailable' }
    const model: ArchivePolarModel = {
      schema_version: '1.0',
      method_version: 'polar-1',
      evaluation_scope: 'legacy',
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
        eligible_races: 2,
        excluded_races: 0,
        distinct_days: 2,
        boat_leg_clusters: 4,
        steady_coverage_s: 20,
        steady_cells: 4,
      },
      tack_fixed_effect: {
        specification: 'fixed',
        bootstrap_draws: 0,
        upwind: null,
        downwind: null,
        overall: null,
      },
      validation: {
        baseline_mode_only: metric,
        leave_one_race_out: metric,
        leave_one_day_out: metric,
        chronological: metric,
      },
      team_residuals: [],
      curves: { upwind: [], downwind: [] },
    }
    const html = renderToStaticMarkup(
      React.createElement(ArchiveObservedPolarSection, { polarModel: model })
    )
    expect(html).toContain('weighted cell means')
    expect(html).toContain('Unavailable chronological')
    expect(html).not.toContain('NaN')
  })
})
