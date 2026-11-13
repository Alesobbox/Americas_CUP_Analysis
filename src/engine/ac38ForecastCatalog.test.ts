import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Ac38ForecastPanel } from '../components/dashboard/Ac38ForecastPanel'
import { SimulatorWorkspace } from '../components/dashboard/SimulatorWorkspace'
import type { Ac38Forecast } from '../types/prediction'
import { parseAc38Forecast, parsePredictionIndex } from './predictionCatalog'

const TEAMS = ['ETNZ', 'LUNA_ROSSA', 'GB1', 'ARC_USA', 'LA_ROCHE_POSAY', 'ALINGHI', 'AUSTRALIA']
const SHA_A = 'a'.repeat(64)
const SHA_B = 'b'.repeat(64)

function makeMatrix(val: number): Record<string, Record<string, number | null>> {
  const m: Record<string, Record<string, number | null>> = {}
  for (const a of TEAMS) {
    m[a] = {}
    for (const b of TEAMS) {
      m[a][b] = a === b ? null : val
    }
  }
  return m
}

function makeForecastFixture(): Ac38Forecast {
  const zeroMap = Object.fromEntries(TEAMS.map((t) => [t, 0.1]))
  const bounds = Object.fromEntries(TEAMS.map((t) => [t, { lower: 0.1, upper: 0.3 }]))
  const mcSe = Object.fromEntries(TEAMS.map((t) => [t, { lower: 0.001, upper: 0.001 }]))
  const expPos = Object.fromEntries(TEAMS.map((t, i) => [t, i + 1]))
  const dist = Object.fromEntries(TEAMS.map((t, i) => [t, TEAMS.map((_, k) => (k === i ? 1 : 0))]))
  const intervals = Object.fromEntries(
    TEAMS.map((t) => [
      t,
      {
        lower_p05_p95: { p05: 0.05, p50: 0.1, p95: 0.2 },
        upper_p05_p95: { p05: 0.2, p50: 0.3, p95: 0.4 },
      },
    ]),
  )
  const nullTrophy = Object.fromEntries(TEAMS.map((t) => [t, null]))
  const sensBase = {
    residual_scale: 1.0,
    zero_transfer: false,
    mapping_policy: 'confirmed_crew_then_principal_ac40_else_prior',
    evidence_scope: 'with_reconstructed',
    failure_probability: 0.0,
    conditional_on_completed: true,
    trials: 1000,
    resolved_trials: 800,
    unresolved_trials: 200,
    unresolved_fraction: 0.2,
    expected_fleet_position: expPos,
    trophy_rule_bounds: bounds,
    actual_mc_se_by_team: mcSe,
  }

  return {
    header: {
      schema_version: 'ac38-forecast-1',
      status: 'experimental_rule_bounds',
      experimental: true,
      generated_at_utc: '2026-11-12T10:00:00+00:00',
      issuance_cutoff_utc: '2026-10-01T00:00:00Z',
      conditioning: 'Conditional on completed races without reliability/timing stoppages.',
      model_ref: SHA_A,
      transfer_posterior_sha256: SHA_A,
      eligibility_ledger_sha256: SHA_B,
      inventory_sha256: SHA_A,
      backtest_report_sha256: SHA_B,
      seed: 2027,
      trials: 1000,
      selected_transfer_candidate: 'results_only',
      telemetry_retained: false,
      scale_kappa: 1,
      applied_ac75_updates: [],
      update_ess: 1000,
    },
    teams: TEAMS.map((id) => ({ id, campaign_team_id: `ac38:${id}`, name: id, role: id === 'ETNZ' ? 'Defender' : 'Challenger' })),
    entrant_coverage: {
      default_mapping_policy: 'confirmed_crew_then_principal_ac40_else_prior',
      evidence_scope: 'with_reconstructed',
      ac38_races_included: ['r1'],
      ac38_anchored_races: ['r1'],
      ac38_reconstructed_races: [],
      ac38_excluded_observations: [],
      teams: TEAMS.map((id) => ({
        team_id: id,
        campaign_team_id: `ac38:${id}`,
        team_name: id,
        observed: id !== 'AUSTRALIA',
        basis: id === 'AUSTRALIA' ? 'population_prior' : 'documented_principal_ac40_entry',
        source_entries: id === 'AUSTRALIA' ? [] : [{ entry_id: id, effect: 0.1 }],
        mapped_ac40_mean: id === 'AUSTRALIA' ? null : 0.1,
        mapped_ac40_sd: id === 'AUSTRALIA' ? null : 0.2,
      })),
      assumptions: ['Baseline historical transfer relationship applies unchanged.'],
    },
    rules: {
      tie_policy: 'ac38_protocol',
      sources: [
        { version: 'Protocol AC38.10', effective_date: '2026-09-04', url: 'https://ac38noticeboard.acofficials.org/' },
        { title: 'Noticeboard', doc_code: 'R246', url: 'https://ac38noticeboard.acofficials.org/' },
      ],
      unresolved_clauses: ['Tie clause pending'],
      resolved_trials: 800,
      unresolved_trials: 200,
      resolved_fraction: 0.8,
      unresolved_fraction: 0.2,
      first_unresolved_stage_counts: { round_robin: 200 },
      overlapping_reason_counts: { 'Tie clause pending': 200 },
      unresolved_reasons: ['Tie clause pending'],
    },
    forecast: {
      pairwise_single_match: makeMatrix(0.5),
      series_best_of_9: makeMatrix(0.5),
      series_best_of_13: makeMatrix(0.5),
      expected_fleet_position: expPos,
      fleet_position_distribution: dist,
      advancement_probabilities: {
        round_robin_top3: Object.fromEntries(TEAMS.map((t) => [t, 3 / 7])),
        repechage_1_win: Object.fromEntries(TEAMS.map((t) => [t, 1 / 7])),
        repechage_2_win: Object.fromEntries(TEAMS.map((t) => [t, 1 / 7])),
        semifinal: Object.fromEntries(TEAMS.map((t) => [t, 4 / 7])),
        semifinal_1_win: Object.fromEntries(TEAMS.map((t) => [t, 1 / 7])),
        semifinal_2_win: Object.fromEntries(TEAMS.map((t) => [t, 1 / 7])),
        challenger_final_win: Object.fromEntries(TEAMS.map((t) => [t, 1 / 7])),
      },
      trophy_probabilities: nullTrophy,
      trophy_rule_bounds: bounds,
    },
    uncertainty: {
      monte_carlo: {
        trials: 1000,
        seed: 2027,
        worst_case_95_half_width: 0.031,
        actual_mc_se_by_team: mcSe,
        pairwise_single_match_mc_se: makeMatrix(0.01),
      },
      posterior_nested_intervals: {
        policy: 'nested',
        quantiles: '5th-95th',
        stabilization_target_pp: 0.5,
        computation_cap_trials: 180000,
        converged_within_0_5pp: false,
        final_max_endpoint_delta: 0.02,
        reason: 'Reached computation cap',
        refinement_history: [],
        intervals_by_team: intervals,
      },
      transfer_parameter_summary: {
        beta_percentiles: { p05: -0.2, p50: 0.7, p95: 1.5 },
        tau_percentiles: { p05: 0.2, p50: 0.7, p95: 1.4 },
        rho_percentiles: { p05: -0.2, p50: 0.75, p95: 0.98 },
        prior_sensitivity: {},
      },
    },
    structural_sensitivities: [
      { ...sensBase, scenario_id: 'baseline', label: 'Baseline 1x', category: 'baseline' },
      { ...sensBase, scenario_id: 'zero', label: 'Zero transfer', category: 'structural', zero_transfer: true },
    ],
    historical_evaluation: {
      selection_rule: '1-SE rule',
      selected_candidate: 'results_only',
      telemetry_retained: false,
      accuracy_claim: 'No AC75 accuracy improvement over carryover claimed.',
      ac40_chronological: {},
      ac75_chronological: {},
      ac75_loto: {},
    },
  }
}

describe('ac38 forecast schema and dashboard views', () => {
  it('validates coherent ac38-forecast-1 artifacts and index optional paths', () => {
    const valid = makeForecastFixture()
    expect(parseAc38Forecast(valid).header.schema_version).toBe('ac38-forecast-1')
    const idx = parsePredictionIndex({
      schema_version: 'prediction-index-1',
      races: [],
      cup_path: 'cup_2027.json',
      ac38_forecast_path: `ac38_${SHA_A}.json`,
    })
    expect(idx.ac38_forecast_path).toBe(`ac38_${SHA_A}.json`)
    expect(() =>
      parsePredictionIndex({
        schema_version: 'prediction-index-1',
        races: [],
        cup_path: 'cup_2027.json',
        ac38_forecast_path: '../escape.json',
      }),
    ).toThrow('unsafe')
  })

  it('rejects non-complementary pairs, unresolved point probabilities, and duplicate sensitivities', () => {
    const badPair = makeForecastFixture()
    badPair.forecast.pairwise_single_match.ETNZ.LUNA_ROSSA = 0.7
    expect(() => parseAc38Forecast(badPair)).toThrow('complementarity')

    const badPoint = makeForecastFixture()
    badPoint.forecast.trophy_probabilities.ETNZ = 0.25
    expect(() => parseAc38Forecast(badPoint)).toThrow('must be null')

    const badDup = makeForecastFixture()
    badDup.structural_sensitivities[1].zero_transfer = false
    expect(() => parseAc38Forecast(badDup)).toThrow('duplicated scenario')

    const badHash = makeForecastFixture()
    badHash.header.transfer_posterior_sha256 = 'not-a-sha'
    expect(() => parseAc38Forecast(badHash)).toThrow('sha256')

    const leaked = makeForecastFixture() as unknown as Record<string, unknown>
    leaked.active_conditionals = [[0.1]]
    expect(() => parseAc38Forecast(leaked)).toThrow('leaked')

    const badNested = makeForecastFixture()
    badNested.uncertainty.posterior_nested_intervals.intervals_by_team.ETNZ.lower_p05_p95.p05 = 0.99
    expect(() => parseAc38Forecast(badNested)).toThrow('ordering')

    const badMcSe = makeForecastFixture()
    badMcSe.uncertainty.monte_carlo.actual_mc_se_by_team.ETNZ.lower = -0.1
    expect(() => parseAc38Forecast(badMcSe)).toThrow('actual_mc_se_by_team')
  })

  it('renders Experimental notice, cutoff, conditioning, and both simulator modes', () => {
    const fcHtml = renderToStaticMarkup(createElement(Ac38ForecastPanel, { forecast: makeForecastFixture(), error: null }))
    expect(fcHtml).toContain('Experimental')
    expect(fcHtml).toContain('2026-10-01T00:00:00Z')
    expect(fcHtml).toContain('Conditional on completed races')
    expect(fcHtml).toContain('Population prior')
    expect(fcHtml).toContain('Protocol AC38.10 (2026-09-04)')
    expect(fcHtml).not.toContain('undefined')

    const simHtml = renderToStaticMarkup(createElement(SimulatorWorkspace))
    expect(simHtml).toContain('AC37 historical simulation')
    expect(simHtml).toContain('AC38 forecast')
  })
})
