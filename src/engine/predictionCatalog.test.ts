import { createElement } from 'react'
import { createHash } from 'node:crypto'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CupForecastCard, LiveForecastCard, PreRaceForecastCard } from '../components/dashboard/ForecastWorkspace'
import type { CupPrediction, RacePrediction } from '../types/prediction'
import type { ReplayManifest } from '../types/replay'
import { findExactPreset, loadPredictionIndex, loadRacePrediction, parseCupPrediction, parsePredictionIndex, parseRacePrediction, selectForecastCheckpoint } from './predictionCatalog'

const context = { raceId: 'race-a', boatIds: ['a', 'b'], boatClass: 'AC40', reference: { model_ref: 'model-1', source_manifest_hash: 'source-hash', scenario_hash: 'scenario-hash' } }
function fixture(): RacePrediction {
  return {
    header: { schema_version: 'prediction-1', race_id: 'race-a', boat_ids: ['a', 'b'], boat_class: 'AC40', model_ref: 'model-1', source_manifest_hash: 'source-hash', scenario_hash: 'scenario-hash', status_dictionary: ['available', 'estimated', 'gate_ambiguous', 'unavailable'], method_and_assumption_refs: ['Experimental source labels'], train_cutoff_ms: 100 },
    pre_race: { status: 'available', expected_position_by_boat: { a: 1.4, b: 1.7 }, nonfinish_score: 'N' },
    live: { state_timestamps_ms: [1000, 11000], published_at_ms: [7000, 17000], progress_band: ['early', 'late'], win_prob_by_boat: { a: [0.6, 0.8], b: [0.3, 0.1] }, no_finisher_prob: [0.1, 0.1], status_code: [0, 1], source_age_ms_by_boat: { a: [0, 3000], b: [0, 0] }, position_uncertainty_summary_by_boat: { a: [1, 4], b: [1, 1] }, quality_code_by_boat: { a: ['fresh', 'estimated'], b: ['fresh', 'fresh'] }, numerical_error: [0.0069, 0.0069] },
  }
}
function cupFixture(): CupPrediction {
  const ids = ['NZL', 'GBR', 'ITA', 'SUI', 'FRA', 'USA', 'AUS']
  return { header: { schema_version: 'cup-1', boat_class: 'AC75' }, status: 'estimated', teams: ids.map((id) => ({ id, name: id })), scenario_envelope_by_team: Object.fromEntries(ids.map((id) => [id, { lower: 0.01, upper: 0.6 }])), evaluated_scenarios: ['rho0_sigma1', 'rho1_sigma1'] }
}
function cupEvidenceFixture(): CupPrediction {
  const cup = cupFixture()
  const ids = cup.teams.map((team) => team.id)
  const modelRef = 'b'.repeat(64), sourceHash = 'a'.repeat(64)
  cup.header.model_ref = modelRef
  cup.header.source_manifest_hash = sourceHash
  cup.header.method_version = 'cup-ac38-conditional-2'
  cup.probabilities = Object.fromEntries(ids.map((id) => [id, null]))
  cup.win_prob_by_team = Object.fromEntries(ids.map((id) => [id, null]))
  cup.unresolved_reasons = ['Synthetic governing-rule effective date missing.', 'Synthetic tie resolution requires clarification.']
  const records = [
    { parameters: { rho: .5, sigma_multiplier: 1, match_concentration: 1, hazard_multiplier: 1 }, wins: [20, 10, 10, 5, 5, 5, 5] },
    { parameters: { rho: 1, sigma_multiplier: 2, match_concentration: 1, hazard_multiplier: 1 }, wins: [10, 10, 10, 10, 10, 10, 10] },
  ].map(({ parameters, wins }) => {
    const resolved = wins.reduce((a, b) => a + b, 0), unresolved = 100 - resolved
    return { scenario_id: `rho${parameters.rho}_sigma${parameters.sigma_multiplier}_c1_k1`, scenario: parameters,
      trials: 100, seed: 2027, input_hash: 'c'.repeat(64), model_ref: modelRef, source_manifest_hash: sourceHash,
      status: 'rule_bounds', resolved_trials: resolved, unresolved_trials: unresolved,
      resolved_fraction: resolved / 100, unresolved_fraction: unresolved / 100,
      resolved_win_counts: Object.fromEntries(ids.map((id, index) => [id, wins[index]])),
      first_unresolved_stage_counts: { qualification: unresolved }, overlapping_reason_counts: { 'Synthetic unresolved tie': unresolved },
      reason_count_policy: 'First-stage counts are exclusive; reasons may overlap.',
      rule_bounds: Object.fromEntries(ids.map((id, index) => [id, { lower: wins[index] / 100, upper: (wins[index] + unresolved) / 100 }])),
      probabilities: Object.fromEntries(ids.map((id) => [id, null])),
      numerical_error: { worst_case_95_half_width: 1.96 * Math.sqrt(.25 / 100), scope: 'Monte Carlo integration only; excludes model/rule uncertainty' },
      unresolved_reasons: ['Synthetic unresolved tie'], assumptions: ['Synthetic test fixture; no empirical forecast accuracy.'],
    }
  })
  cup.evaluated_scenarios = records.map((scenario) => scenario.scenario_id)
  cup.rule_bounds_by_team = records[0].rule_bounds
  cup.scenario_envelope_by_team = Object.fromEntries(ids.map((id) => [id, { lower: Math.min(...records.map((scenario) => scenario.rule_bounds[id].lower)), upper: Math.max(...records.map((scenario) => scenario.rule_bounds[id].upper)) }]))
  cup.scenario_analysis = { schema_version: 'cup-scenarios-1', baseline_scenario_id: records[0].scenario_id,
    model_lineage: { model_ref: modelRef, source_manifest_hash: sourceHash, training_before_day: '2026-09-26', training_cutoff_ms: Date.parse('2026-09-26T00:00:00Z') },
    mapping_provenance: { policy: 'Observed entries averaged; missing history retains prior.', teams: ids.map((id) => ({ team_id: id, observed: id !== 'AUS', source_entries: [], mapped_strength: id === 'AUS' ? null : 0 })) },
    simulation_inputs: { mapped_strength: Object.fromEntries(ids.filter((id) => id !== 'AUS').map((id) => [id, 0])), rules: {}, pooled_scale: .5, failure_probability: 0, conditional_on_completed_scored_races: true },
    build_budget: { trials_per_scenario: 100, scenario_count: 2, seed: 2027, profile: 'synthetic', common_random_numbers: true },
    conditioning: { transfer: 'Loading assumption; no AC75 calibration.', reliability: 'Conditional on completed scored races.', weather: 'No fitted weather response.' }, records,
    extrema_by_team: Object.fromEntries(ids.map((id) => [id, {
      lower_scenario_ids: records.filter((scenario) => scenario.rule_bounds[id].lower === cup.scenario_envelope_by_team![id]!.lower).map((scenario) => scenario.scenario_id),
      upper_scenario_ids: records.filter((scenario) => scenario.rule_bounds[id].upper === cup.scenario_envelope_by_team![id]!.upper).map((scenario) => scenario.scenario_id),
    }])), refinement_policy: { method: 'conservative_outer_bounds', status: 'retained', reason: 'Synthetic unresolved rule set.' },
  }
  return cup
}
const replay = { competitors: [{ id: 'a', team_code: 'ITA' }, { id: 'b', team_code: 'GBR' }] } as ReplayManifest

afterEach(() => vi.unstubAllGlobals())

describe('forecast contracts and time access', () => {
  it('uses publication time, including backward seeks and exact boundaries', () => {
    const prediction = parseRacePrediction(fixture(), context)
    expect(selectForecastCheckpoint(prediction, 6999).index).toBeNull()
    expect(selectForecastCheckpoint(prediction, 7000).index).toBe(0)
    expect(selectForecastCheckpoint(prediction, 16999).index).toBe(0)
    expect(selectForecastCheckpoint(prediction, 17000).index).toBe(1)
    expect(selectForecastCheckpoint(prediction, 8000).index).toBe(0)
    expect(selectForecastCheckpoint(prediction, 2000).index).toBeNull()
  })
  it('rejects stale states when the build supplies a validity limit', () => {
    const prediction = fixture()
    prediction.header.max_state_age_ms = 9000
    expect(selectForecastCheckpoint(prediction, 10000).index).toBe(0)
    expect(selectForecastCheckpoint(prediction, 10001).index).toBeNull()
  })
  it('fails closed for wrong race, class, omitted opponents, or stale hashes', () => {
    expect(() => parseRacePrediction(fixture(), { ...context, raceId: 'other' })).toThrow('selected race')
    expect(() => parseRacePrediction(fixture(), { ...context, boatClass: 'AC75' })).toThrow('boat class')
    expect(() => parseRacePrediction(fixture(), { ...context, boatIds: ['a'] })).toThrow('competitor field')
    expect(() => parseRacePrediction(fixture(), { ...context, reference: { source_manifest_hash: 'new-hash' } })).toThrow('source manifest hash')
    expect(() => parseRacePrediction(fixture(), { ...context, reference: { scenario_hash: 'other-scenario' } })).toThrow('scenario hash')
  })
  it('rejects incomplete parallel columns and invalid joint probability mass', () => {
    const incomplete = fixture()
    incomplete.live.quality_code_by_boat.b = []
    expect(() => parseRacePrediction(incomplete, context)).toThrow('complete field')
    const mass = fixture()
    mass.live.win_prob_by_boat.a[0] = 0.9
    expect(() => parseRacePrediction(mass, context)).toThrow('sum to one')
    const missing = fixture()
    missing.live.win_prob_by_boat.b[0] = null
    expect(() => parseRacePrediction(missing, context)).toThrow('incomplete')
  })
  it('preserves a source-only scheduled DNS only with matching index and header rosters', () => {
    const prediction = fixture()
    prediction.header.boat_ids.push('dns')
    prediction.header.replay_boat_ids = ['a', 'b']
    prediction.header.scheduled_entries = [{ id: 'a', team_code: 'OTHER A', team_name: 'A' }, { id: 'b', team_code: 'OTHER B', team_name: 'B' }, { id: 'dns', team_code: 'DNS', team_name: 'Scheduled boat without replay' }]
    prediction.pre_race.expected_position_by_boat.dns = 3
    prediction.pre_race.nonfinish_score = 3
    prediction.live.win_prob_by_boat.dns = [0, 0]
    prediction.live.source_age_ms_by_boat.dns = [null, null]
    prediction.live.position_uncertainty_summary_by_boat.dns = [null, null]
    prediction.live.quality_code_by_boat.dns = ['unavailable', 'unavailable']
    const fullContext = { ...context, reference: { ...context.reference, boat_ids: ['a', 'b', 'dns'], replay_boat_ids: ['a', 'b'] } }
    expect(parseRacePrediction(prediction, fullContext)).toBe(prediction)
    expect(() => parseRacePrediction(prediction, context)).toThrow('scheduled/replay')
    expect(() => parseRacePrediction(prediction, { ...fullContext, reference: { ...fullContext.reference, boat_ids: ['a', 'b'] } })).toThrow('scheduled/replay')
    expect(() => parseRacePrediction(prediction, { ...fullContext, reference: { ...fullContext.reference, replay_boat_ids: ['a'] } })).toThrow('scheduled/replay')
    const missingRoster = structuredClone(prediction)
    missingRoster.header.scheduled_entries?.pop()
    expect(() => parseRacePrediction(missingRoster, fullContext)).toThrow('complete competitor field')
    const missingColumn = structuredClone(prediction)
    delete missingColumn.live.win_prob_by_boat.dns
    expect(() => parseRacePrediction(missingColumn, fullContext)).toThrow('complete field')
    const pre = renderToStaticMarkup(createElement(PreRaceForecastCard, { prediction, error: null, replay, selectedId: 'a' }))
    const live = renderToStaticMarkup(createElement(LiveForecastCard, { prediction, error: null, replay, selectedId: 'a', playhead: 7000 }))
    expect(pre).toContain('nonfinish scored N (3)')
    expect(pre).toContain('DNS')
    expect(pre).toContain('ITA')
    expect(pre).not.toContain('OTHER A')
    expect(live).toContain('DNS')
    expect(live).toContain('0.0%')
    const unsupported = renderToStaticMarkup(createElement(PreRaceForecastCard, { prediction: null, rosterPrediction: prediction, error: 'Scenario unsupported.', replay, selectedId: 'a' }))
    expect(unsupported).toContain('DNS')
    expect(unsupported).toContain('nonfinish scored N (3)')
    expect(unsupported).not.toContain('1.40')
  })
  it('preserves unknown values as null and refuses numeric values in unavailable states', () => {
    const unavailable = fixture()
    unavailable.pre_race.status = 'unavailable'
    unavailable.pre_race.expected_position_by_boat = { a: null, b: null }
    unavailable.live.status_code[1] = 2
    unavailable.live.win_prob_by_boat.a[1] = null
    unavailable.live.win_prob_by_boat.b[1] = null
    unavailable.live.no_finisher_prob[1] = null
    expect(parseRacePrediction(unavailable, context).live.win_prob_by_boat.a[1]).toBeNull()
    unavailable.live.win_prob_by_boat.a[1] = 0
    expect(() => parseRacePrediction(unavailable, context)).toThrow('unavailable checkpoint')
  })
  it('rejects future training and publication before state time', () => {
    const training = fixture()
    training.header.train_cutoff_ms = 2000
    expect(() => parseRacePrediction(training, context)).toThrow('training cutoff')
    const publication = fixture()
    publication.live.published_at_ms[0] = 900
    expect(() => parseRacePrediction(publication, context)).toThrow('chronology')
  })
  it('selects only exact pre-race presets without nearest-cell borrowing', () => {
    const presets = [{ id: '12_0', tws_kt: 12, direction_offset_deg: 0, scope: 'pre_race' as const, path: 'scenarios/a.json' }]
    expect(findExactPreset(presets, 12, 0)?.id).toBe('12_0')
    expect(findExactPreset(presets, 12.1, 0)).toBeUndefined()
    expect(findExactPreset(presets, 12, 1)).toBeUndefined()
    expect(() => parseRacePrediction(fixture(), { ...context, scope: 'pre_race' })).toThrow('scope')
    const exact = fixture()
    exact.header.scope = 'pre_race'
    exact.header.conditions = { tws_kt: 12, direction_offset_deg: 0 }
    expect(parseRacePrediction(exact, { ...context, scope: 'pre_race', conditions: { tws_kt: 12, direction_offset_deg: 0 } })).toBe(exact)
    expect(() => parseRacePrediction(exact, { ...context, scope: 'pre_race', conditions: { tws_kt: 12.1, direction_offset_deg: 0 } })).toThrow('exact selected wind')
  })
})

describe('static JSON loading', () => {
  it('rejects HTML fallback pages before JSON decoding', async () => {
    const json = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, headers: new Headers({ 'content-type': 'text/html' }), json }))
    await expect(loadPredictionIndex()).rejects.toThrow('did not return JSON')
    expect(json).not.toHaveBeenCalled()
  })
  it('rejects missing files and aborts through the supplied signal', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: false, status: 404 })
    vi.stubGlobal('fetch', fetcher)
    const controller = new AbortController()
    await expect(loadRacePrediction('race-a.json', context, controller.signal)).rejects.toThrow('404')
    expect(fetcher).toHaveBeenCalledWith('/data/predictions/race-a.json', { signal: controller.signal })
  })
  it('rejects unsafe paths and duplicate race entries', () => {
    expect(() => parsePredictionIndex({ schema_version: 'prediction-index-1', races: [{ race_id: 'a', path: '../private.json' }], cup_path: 'cup_2027.json' })).toThrow('unsafe')
    expect(() => parsePredictionIndex({ schema_version: 'prediction-index-1', races: [{ race_id: 'a', path: 'a.json' }, { race_id: 'a', path: 'a.json' }], cup_path: 'cup_2027.json' })).toThrow('duplicate')
  })
  it('checks immutable payload bytes without changing Python ASCII escapes or key order', async () => {
    const prediction = fixture()
    prediction.header.method_and_assumption_refs = ['Naples · α']
    const body = JSON.stringify(prediction).replaceAll('·', '\\u00b7').replaceAll('α', '\\u03b1')
    const hash = createHash('sha256').update(body).digest('hex')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body + '\r\n', { headers: { 'content-type': 'application/json' } })))
    const parsed = await loadRacePrediction(`races/race-a_${hash}.json`, context)
    expect(parsed.header.method_and_assumption_refs).toEqual(['Naples · α'])
  })
  it('rejects modified content at an immutable path even if declared header hashes are unchanged', async () => {
    const body = JSON.stringify(fixture())
    const hash = createHash('sha256').update(body).digest('hex')
    const modified = body.replace('0.6', '0.7')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(modified + '\n', { headers: { 'content-type': 'application/json' } })))
    await expect(loadRacePrediction(`races/race-a_${hash}.json`, context)).rejects.toThrow('immutable hash')
  })
})

describe('the three forecast cards', () => {
  it('renders only the published probability and never substitutes a future checkpoint', () => {
    const html = renderToStaticMarkup(createElement(LiveForecastCard, { prediction: fixture(), error: null, playhead: 8000, replay, selectedId: 'a' }))
    expect(html).toContain('60.0%')
    expect(html).not.toContain('80.0%')
    const before = renderToStaticMarkup(createElement(LiveForecastCard, { prediction: fixture(), error: null, playhead: 2000, replay, selectedId: 'a' }))
    expect(before).toContain('No forecast had been published')
    expect(before).not.toContain('60.0%')
  })
  it('hides stale pre-race output on scenario errors and names the nonfinish scoring convention', () => {
    const html = renderToStaticMarkup(createElement(PreRaceForecastCard, { prediction: fixture(), error: 'No exact scenario exists.', replay, selectedId: 'a' }))
    expect(html).toContain('nonfinish scored N (2)')
    expect(html).toContain('No exact scenario exists.')
    expect(html).not.toContain('1.40')
  })
  it('requires all seven Cup entrants while permitting non-additive scenario envelopes', () => {
    expect(parseCupPrediction(cupFixture()).teams).toHaveLength(7)
    const missing = cupFixture()
    missing.teams.pop()
    expect(() => parseCupPrediction(missing)).toThrow('all six Challengers')
    const html = renderToStaticMarkup(createElement(CupForecastCard, { prediction: cupFixture(), error: null }))
    expect(html).toContain('America’s Cup 2027')
    expect(html).toContain('not calibrated AC75 confidence intervals')
    expect(html).toContain('AUS')
  })
  it('reconciles detailed Cup bounds and renders distinct uncertainty layers', () => {
    const cup = parseCupPrediction(cupEvidenceFixture())
    const html = renderToStaticMarkup(createElement(CupForecastCard, { prediction: cup, error: null }))
    expect(html).toContain('Baseline assumptions: rule bounds')
    expect(html).toContain('All tested assumptions: outer envelope')
    expect(html).toContain('Selected scenario: rule bounds')
    expect(html).toContain('aria-label="Cup scenario"')
    expect(html).toContain('60 resolved · 40 unresolved of 100 trials')
    expect(html).toContain('Monte Carlo half-width: ±9.80 pp')
    expect(html).toContain('First unresolved stage')
    expect(html).toContain('Overlapping reasons')
    expect(html).toContain('Pinned strength model')
    expect(html).toContain('training before 2026-09-26')
    expect(html).toContain('population prior retained')
    expect(html).toContain('Envelope endpoint attribution')
    expect(html).toContain('Unresolved evidence')
    expect(html).toContain('Synthetic governing-rule effective date missing.')
    expect(html).toContain('Synthetic tie resolution requires clarification.')
    expect(html).toContain('20.0%–60.0%')
  })
  it('requires method-2 Cup evidence while retaining legacy and unavailable compatibility', () => {
    for (const status of ['available', 'estimated'] as const) {
      const cup = cupEvidenceFixture()
      cup.status = status
      delete cup.scenario_analysis
      expect(() => parseCupPrediction(cup)).toThrow('scenario evidence is required')
      cup.probabilities!.NZL = .9
      expect(() => parseCupPrediction(cup)).toThrow('scenario evidence is required')
    }
    const legacy = cupFixture()
    legacy.header.method_version = 'cup-ac38-conditional-1'
    expect(parseCupPrediction(legacy)).toBe(legacy)
    const unavailable: CupPrediction = { ...cupFixture(), header: { ...cupFixture().header, method_version: 'cup-ac38-conditional-2' }, status: 'unavailable', scenario_envelope_by_team: null, rule_bounds_by_team: null }
    expect(parseCupPrediction(unavailable)).toBe(unavailable)
  })
  it('requires complete null headline Cup containers alongside scenario evidence', () => {
    for (const field of ['probabilities', 'win_prob_by_team'] as const) {
      for (const mutation of ['point', 'missing-team', 'extra-team', 'missing-container']) {
        const cup = cupEvidenceFixture()
        if (mutation === 'point') cup[field]!.NZL = .9
        if (mutation === 'missing-team') delete cup[field]!.NZL
        if (mutation === 'extra-team') cup[field]!.INVENTED = null
        if (mutation === 'missing-container') delete cup[field]
        expect(() => parseCupPrediction(cup), `${field}/${mutation}`).toThrow('headline Cup probability containers')
      }
    }
  })
  it('rejects Cup scenario count, baseline, endpoint and missing-prior corruption', () => {
    for (const mutation of ['count', 'first-stage', 'endpoint', 'point', 'baseline', 'missing', 'model', 'parameters']) {
      const cup = cupEvidenceFixture()
      const evidence = cup.scenario_analysis!
      const scenario = evidence.records[0]
      if (mutation === 'count') scenario.resolved_trials++
      if (mutation === 'first-stage') scenario.first_unresolved_stage_counts.qualification++
      if (mutation === 'endpoint') evidence.extrema_by_team.NZL.lower_scenario_ids = ['invented']
      if (mutation === 'point') scenario.probabilities.NZL = .5
      if (mutation === 'baseline') evidence.baseline_scenario_id = 'invented'
      if (mutation === 'missing') evidence.mapping_provenance.teams.find((team) => team.team_id === 'AUS')!.mapped_strength = 0
      if (mutation === 'model') cup.header.model_ref = 'd'.repeat(64)
      if (mutation === 'parameters') scenario.scenario.rho = 1
      expect(() => parseCupPrediction(cup), mutation).toThrow()
    }
  })
  it('preserves structural Cup ranges when scenario evidence is unavailable', () => {
    const html = renderToStaticMarkup(createElement(CupForecastCard, { prediction: cupEvidenceFixture(), error: 'Evidence fetch failed.' }))
    expect(html).toContain('Evidence fetch failed.')
    expect(html).not.toContain('60 resolved')
    expect(html).not.toContain('20.0%–60.0%')
    expect(html).not.toContain('aria-label="Cup scenario"')
  })
  it('does not display unsupported Cup numbers in an unavailable artifact', () => {
    const cup = cupFixture()
    cup.status = 'unavailable'
    expect(() => parseCupPrediction(cup)).toThrow('unavailable Cup artifact contains estimates')
    const html = renderToStaticMarkup(createElement(CupForecastCard, { prediction: cup, error: 'Rules unresolved.' }))
    expect(html).toContain('Rules unresolved.')
    expect(html).not.toContain('60.0%')
  })
  it('shows the full Cup field and evidence reason when unavailable bounds are null', () => {
    const cup = { ...cupFixture(), status: 'unavailable' as const, reason: 'AC75 evidence unresolved.', scenario_envelope_by_team: null, rule_bounds_by_team: null }
    const parsed = parseCupPrediction(cup)
    const html = renderToStaticMarkup(createElement(CupForecastCard, { prediction: parsed, error: null }))
    expect(parsed.teams).toHaveLength(7)
    expect(html).toContain('AC75 evidence unresolved.')
    expect(html).toContain('Cup probabilities are not ready:')
    expect(html).toContain('<details><summary>Why this is unavailable</summary>')
    expect(html).not.toContain('<p role="status" class="forecast-unavailable">AC75 evidence unresolved.')
    expect(html).toContain('AUS')
    expect(html).not.toContain('60.0%')
    expect(() => parseCupPrediction({ ...cup, status: 'estimated' })).toThrow('incomplete field')
    expect(() => parseCupPrediction({ ...cup, unresolved_reasons: [42] })).toThrow('invalid Cup evidence reasons')
  })
})
