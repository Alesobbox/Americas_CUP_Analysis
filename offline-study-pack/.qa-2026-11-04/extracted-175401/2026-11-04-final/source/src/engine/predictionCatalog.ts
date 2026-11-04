import type { CupPrediction, ForecastStatus, PredictionIndex, PredictionPreset, PredictionRaceReference, PredictionReference, RacePrediction } from '../types/prediction'

const statuses: ForecastStatus[] = ['available', 'estimated', 'gate_ambiguous', 'unavailable']
const usable = (status: ForecastStatus) => status === 'available' || status === 'estimated'
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const probability = (value: unknown) => finite(value) && value >= 0 && value <= 1
const nonempty = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0
const sameIds = (left: string[], right: string[]) => left.length === right.length && new Set(left).size === left.length && left.every((id) => right.includes(id))
const idList = (value: unknown): value is string[] => Array.isArray(value) && value.length > 0 && value.every(nonempty) && new Set(value).size === value.length

function invalid(message: string): never { throw new Error(`Forecast unavailable: ${message}`) }

function checkedPath(path: unknown): string {
  if (typeof path !== 'string' || !/^(?:predictions\/)?[a-zA-Z0-9_/-]+\.json$/.test(path) || path.includes('..') || path.startsWith('/')) invalid('unsafe artifact path')
  return path.startsWith('predictions/') ? `/data/${path}` : `/data/predictions/${path}`
}

async function readJson(path: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(path, { signal })
  if (!response.ok) invalid(`artifact could not be loaded (${response.status})`)
  if (!response.headers.get('content-type')?.toLowerCase().includes('json')) invalid('artifact did not return JSON')
  const expectedHash = /(?:^|[/_])([a-f0-9]{64})\.json$/.exec(path)?.[1]
  if (expectedHash) {
    if (!globalThis.crypto?.subtle) invalid('artifact integrity checking is unavailable in this browser')
    const body = await response.text()
    // Backend files contain canonical JSON plus one optional platform newline.
    // Hash the exact UTF-8 content; reserializing would change Python escapes.
    const canonicalBody = body.replace(/\r?\n$/, '')
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonicalBody))
    const actualHash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
    if (actualHash !== expectedHash) invalid('artifact content does not match its immutable hash')
    try { return JSON.parse(body) as unknown }
    catch { return invalid('artifact contains invalid JSON') }
  }
  try { return await response.json() as unknown }
  catch { return invalid('artifact contains invalid JSON') }
}

function verifyReference(header: PredictionReference, expected?: PredictionReference) {
  for (const key of ['model_ref', 'source_manifest_hash', 'scenario_hash'] as const) {
    if (expected?.[key] !== undefined && header[key] !== expected[key]) invalid(`${key.replaceAll('_', ' ')} does not match the forecast index`)
  }
}

export function parsePredictionIndex(value: unknown): PredictionIndex {
  if (!record(value) || value.schema_version !== 'prediction-index-1' || !Array.isArray(value.races)) invalid('unsupported index format')
  const ids = new Set<string>()
  for (const entry of value.races) {
    if (!record(entry) || !nonempty(entry.race_id) || ids.has(entry.race_id)) invalid('invalid or duplicate race in index')
    ids.add(entry.race_id)
    checkedPath(entry.path)
    if (entry.boat_ids !== undefined || entry.replay_boat_ids !== undefined) {
      if (!idList(entry.boat_ids) || !idList(entry.replay_boat_ids) || !entry.replay_boat_ids.every((id) => (entry.boat_ids as string[]).includes(id))) invalid('invalid scheduled/replay field in index')
    }
    if (entry.presets !== undefined) {
      if (!Array.isArray(entry.presets)) invalid('invalid preset list')
      const presetIds = new Set<string>()
      for (const preset of entry.presets) {
        if (!record(preset) || !nonempty(preset.id) || presetIds.has(preset.id) || preset.scope !== 'pre_race' || !finite(preset.tws_kt) || !finite(preset.direction_offset_deg)) invalid('invalid pre-race preset')
        presetIds.add(preset.id)
        if (preset.path !== undefined) checkedPath(preset.path)
      }
    }
  }
  checkedPath(value.cup_path)
  return value as unknown as PredictionIndex
}

export function parseRacePrediction(value: unknown, context: { raceId: string; boatIds: string[]; boatClass: string; reference?: PredictionRaceReference; scope?: string; conditions?: { tws_kt: number; direction_offset_deg: number } }): RacePrediction {
  if (!record(value) || !record(value.header) || !record(value.pre_race) || !record(value.live)) invalid('incomplete race artifact')
  const h = value.header
  if (h.schema_version !== 'prediction-1' || h.race_id !== context.raceId) invalid('artifact does not match the selected race')
  if (!idList(h.boat_ids)) invalid('competitor field does not match the selected race')
  const fieldIds = h.boat_ids
  const rosterDeclared = h.replay_boat_ids !== undefined || h.scheduled_entries !== undefined || context.reference?.boat_ids !== undefined || context.reference?.replay_boat_ids !== undefined
  if (rosterDeclared) {
    if (!idList(context.reference?.boat_ids) || !sameIds(fieldIds, context.reference.boat_ids) || !idList(h.replay_boat_ids) || !sameIds(h.replay_boat_ids, context.boatIds) || !idList(context.reference.replay_boat_ids) || !sameIds(context.reference.replay_boat_ids, context.boatIds) || !context.boatIds.every((id) => fieldIds.includes(id))) invalid('scheduled/replay competitor field does not match the forecast index and selected race')
    if (!Array.isArray(h.scheduled_entries) || h.scheduled_entries.some((entry) => !record(entry) || !nonempty(entry.id) || !nonempty(entry.team_code) || !nonempty(entry.team_name)) || !sameIds(h.scheduled_entries.map((entry) => entry.id as string), fieldIds)) invalid('scheduled roster does not contain the complete competitor field')
  } else if (!sameIds(fieldIds, context.boatIds)) invalid('competitor field does not match the selected race')
  if (h.boat_class !== context.boatClass) invalid('boat class does not match the selected race')
  if (context.scope && h.scope !== context.scope) invalid('scenario scope does not match this card')
  if (context.conditions && (!record(h.conditions) || h.conditions.tws_kt !== context.conditions.tws_kt || h.conditions.direction_offset_deg !== context.conditions.direction_offset_deg)) invalid('scenario conditions do not match the exact selected wind')
  if (![h.model_ref, h.source_manifest_hash, h.scenario_hash].every(nonempty)) invalid('model and input provenance is missing')
  verifyReference(h, context.reference)
  if (!Array.isArray(h.status_dictionary) || !sameIds(h.status_dictionary as string[], statuses) || !Array.isArray(h.method_and_assumption_refs)) invalid('quality and method definitions are missing')
  const pre = value.pre_race
  if (!statuses.includes(pre.status as ForecastStatus) || !record(pre.expected_position_by_boat) || !sameIds(Object.keys(pre.expected_position_by_boat), fieldIds)) invalid('incomplete pre-race predictions')
  if (pre.nonfinish_score !== 'N' && pre.nonfinish_score !== fieldIds.length) invalid('nonfinish position does not match the scheduled field')
  for (const position of Object.values(pre.expected_position_by_boat)) {
    if (usable(pre.status as ForecastStatus) ? !finite(position) || position < 1 || position > fieldIds.length : position !== null) invalid('invalid or unavailable expected position')
  }
  const live = value.live
  if (!Array.isArray(live.state_timestamps_ms)) invalid('checkpoint times are missing')
  const count = live.state_timestamps_ms.length
  for (const key of ['published_at_ms', 'progress_band', 'no_finisher_prob', 'status_code', 'numerical_error']) {
    if (!Array.isArray(live[key]) || live[key].length !== count) invalid(`checkpoint column ${key} is incomplete`)
  }
  if (live.reason_code !== undefined && (!Array.isArray(live.reason_code) || live.reason_code.length !== count)) invalid('checkpoint reasons are incomplete')
  for (const key of ['win_prob_by_boat', 'source_age_ms_by_boat', 'position_uncertainty_summary_by_boat', 'quality_code_by_boat']) {
    const columns = live[key]
    if (!record(columns) || !sameIds(Object.keys(columns), fieldIds) || Object.values(columns).some((column) => !Array.isArray(column) || column.length !== count)) invalid(`checkpoint column ${key} does not contain the complete field`)
  }
  const prediction = value as unknown as RacePrediction
  for (let i = 0; i < count; i++) {
    const stateTime = prediction.live.state_timestamps_ms[i]
    const publication = prediction.live.published_at_ms[i]
    if (!finite(stateTime) || !finite(publication) || publication < stateTime || (i > 0 && (stateTime <= prediction.live.state_timestamps_ms[i - 1] || publication < prediction.live.published_at_ms[i - 1]))) invalid('checkpoint chronology is invalid')
    if (finite(h.train_cutoff_ms) && h.train_cutoff_ms > stateTime) invalid('training cutoff is later than the forecast state')
    const status = checkpointStatus(prediction, i)
    if (!status) invalid('checkpoint quality is unknown')
    const values = [...fieldIds.map((id) => prediction.live.win_prob_by_boat[id][i]), prediction.live.no_finisher_prob[i]]
    if (usable(status)) {
      if (!values.every(probability) || Math.abs((values as number[]).reduce((sum, p) => sum + p, 0) - 1) > 1e-5) invalid('joint winning probabilities are incomplete or do not sum to one')
    } else if (!values.every((p) => p === null)) invalid('unavailable checkpoint contains probabilities')
    for (const id of fieldIds) {
      const age = prediction.live.source_age_ms_by_boat[id][i]
      if (age !== null && (!finite(age) || age < 0)) invalid('source age is invalid')
    }
    const error = prediction.live.numerical_error[i]
    if (error !== null && (!finite(error) || error < 0 || error > 1)) invalid('simulation precision is invalid')
  }
  return prediction
}

export function checkpointStatus(prediction: RacePrediction, index: number): ForecastStatus | null {
  const code = prediction.live.status_code[index]
  const status = typeof code === 'number' ? prediction.header.status_dictionary[code] : code
  return statuses.includes(status) ? status : null
}

/** Publication time controls access, including when seeking backwards. No closest/future fallback. */
export function selectForecastCheckpoint(prediction: RacePrediction, playhead: number): { index: number | null; reason?: string } {
  let low = 0
  let high = prediction.live.published_at_ms.length - 1
  let index = -1
  while (low <= high) {
    const middle = Math.floor((low + high) / 2)
    if (prediction.live.published_at_ms[middle] <= playhead) { index = middle; low = middle + 1 }
    else high = middle - 1
  }
  if (index < 0) return { index: null, reason: 'No forecast had been published at this playhead.' }
  const age = playhead - prediction.live.state_timestamps_ms[index]
  if (prediction.header.max_state_age_ms !== undefined && age > prediction.header.max_state_age_ms) return { index: null, reason: 'The last published forecast is too old for this playhead.' }
  return { index }
}

export function findExactPreset(presets: PredictionPreset[] | undefined, tws: number, offset: number) {
  return presets?.find((preset) => preset.scope === 'pre_race' && preset.tws_kt === tws && preset.direction_offset_deg === offset)
}

export function parseCupPrediction(value: unknown): CupPrediction {
  if (!record(value) || !record(value.header) || value.header.schema_version !== 'cup-1' || value.header.boat_class !== 'AC75' || !statuses.includes(value.status as ForecastStatus) || !Array.isArray(value.teams)) invalid('unsupported America’s Cup artifact')
  if (value.reason !== undefined && typeof value.reason !== 'string') invalid('invalid Cup evidence reason')
  if (value.unresolved_reasons !== undefined && (!Array.isArray(value.unresolved_reasons) || !value.unresolved_reasons.every(nonempty))) invalid('invalid Cup evidence reasons')
  if (value.teams.length !== 7 || value.teams.some((team) => !record(team) || !nonempty(team.id) || !nonempty(team.name)) || new Set(value.teams.map((team) => team.id)).size !== 7) invalid('the Cup field must include the Defender and all six Challengers')
  const ids = value.teams.map((team) => team.id as string)
  if (usable(value.status as ForecastStatus) && value.header.method_version === 'cup-ac38-conditional-2' && !record(value.scenario_analysis)) invalid('Cup scenario evidence is required for a usable cup-ac38-conditional-2 publication')
  for (const key of ['scenario_envelope_by_team', 'rule_bounds_by_team']) {
    const bounds = value[key]
    if (bounds === undefined) continue
    if (bounds === null && !usable(value.status as ForecastStatus)) continue
    if (!record(bounds) || !sameIds(Object.keys(bounds), ids)) invalid('Cup scenarios contain an incomplete field')
    for (const bound of Object.values(bounds)) {
      if (bound === null && !usable(value.status as ForecastStatus)) continue
      if (!record(bound) || !probability(bound.lower) || !probability(bound.upper) || (bound.lower as number) > (bound.upper as number)) invalid('invalid Cup scenario or rule bounds')
    }
  }
  if (usable(value.status as ForecastStatus) && !record(value.scenario_envelope_by_team) && !record(value.rule_bounds_by_team)) invalid('Cup estimates are missing')
  if (!usable(value.status as ForecastStatus) && ['scenario_envelope_by_team', 'rule_bounds_by_team'].some((key) => record(value[key]) && Object.values(value[key]).some((p) => p !== null))) invalid('unavailable Cup artifact contains estimates')
  if (value.scenario_analysis !== undefined) validateCupScenarioEvidence(value, ids)
  return value as unknown as CupPrediction
}

function validateCupScenarioEvidence(value: Record<string, unknown>, ids: string[]) {
  const evidence = value.scenario_analysis
  const integer = (n: unknown): n is number => finite(n) && Number.isInteger(n) && n >= 0
  const counts = (v: unknown): v is Record<string, number> => record(v) && Object.values(v).every(integer)
  for (const field of ['probabilities', 'win_prob_by_team']) {
    const headline = value[field]
    if (!record(headline) || !sameIds(Object.keys(headline), ids) || Object.values(headline).some((number) => number !== null)) invalid('headline Cup probability containers must include every team with null values')
  }
  if (!record(evidence) || evidence.schema_version !== 'cup-scenarios-1' || !Array.isArray(evidence.records) || !evidence.records.length || !record(evidence.build_budget) || !record(evidence.model_lineage) || !record(evidence.mapping_provenance) || !record(evidence.simulation_inputs) || !record(evidence.simulation_inputs.mapped_strength) || !record(evidence.extrema_by_team) || !record(evidence.conditioning) || !Object.values(evidence.conditioning).every(nonempty) || !record(evidence.refinement_policy) || !nonempty(evidence.refinement_policy.reason)) invalid('invalid Cup scenario evidence')
  if (!record(value.header) || (evidence.model_lineage.model_ref ?? null) !== (value.header.model_ref ?? null)) invalid('Cup header/model lineage mismatch')
  if (evidence.model_lineage.model_ref !== undefined && (!nonempty(evidence.model_lineage.model_ref) || !/^[a-f0-9]{64}$/.test(evidence.model_lineage.model_ref) || evidence.model_lineage.source_manifest_hash !== value.header.source_manifest_hash || !nonempty(evidence.model_lineage.training_before_day) || !/^\d{4}-\d{2}-\d{2}$/.test(evidence.model_lineage.training_before_day) || evidence.model_lineage.training_cutoff_ms !== Date.parse(`${evidence.model_lineage.training_before_day}T00:00:00Z`))) invalid('invalid pinned Cup model lineage')
  const budget = evidence.build_budget
  if (!integer(budget.trials_per_scenario) || budget.trials_per_scenario < 1 || !integer(budget.seed) || budget.scenario_count !== evidence.records.length) invalid('invalid Cup scenario budget')
  const scenarioIds: string[] = []
  for (const scenario of evidence.records) {
    if (!record(scenario) || !nonempty(scenario.scenario_id) || !record(scenario.scenario) || !Object.values(scenario.scenario).every(finite) || !integer(scenario.trials) || !integer(scenario.resolved_trials) || !integer(scenario.unresolved_trials) || scenario.trials !== budget.trials_per_scenario || scenario.seed !== budget.seed || scenario.resolved_trials + scenario.unresolved_trials !== scenario.trials) invalid('Cup trial counts do not reconcile')
    const parameters = scenario.scenario
    if (!probability(parameters.rho) || !finite(parameters.sigma_multiplier) || parameters.sigma_multiplier < 0 || !finite(parameters.match_concentration) || parameters.match_concentration <= 0 || !finite(parameters.hazard_multiplier) || parameters.hazard_multiplier <= 0 || scenario.scenario_id !== `rho${parameters.rho}_sigma${parameters.sigma_multiplier}_c${parameters.match_concentration}_k${parameters.hazard_multiplier}`) invalid('Cup scenario parameter or ID mismatch')
    scenarioIds.push(scenario.scenario_id)
    const n = scenario.trials
    if (!finite(scenario.resolved_fraction) || !finite(scenario.unresolved_fraction) || Math.abs(scenario.resolved_fraction - scenario.resolved_trials / n) > 1e-12 || Math.abs(scenario.unresolved_fraction - scenario.unresolved_trials / n) > 1e-12) invalid('Cup trial fractions do not reconcile')
    if (!counts(scenario.resolved_win_counts) || !sameIds(Object.keys(scenario.resolved_win_counts), ids) || Object.values(scenario.resolved_win_counts).reduce((a, b) => a + b, 0) !== scenario.resolved_trials || !counts(scenario.first_unresolved_stage_counts) || Object.values(scenario.first_unresolved_stage_counts).reduce((a, b) => a + b, 0) !== scenario.unresolved_trials || !counts(scenario.overlapping_reason_counts) || Object.values(scenario.overlapping_reason_counts).some((count) => count > n)) invalid('Cup unresolved attribution does not reconcile')
    if (Object.values(scenario.overlapping_reason_counts).reduce((a, b) => a + b, 0) < scenario.unresolved_trials || scenario.status !== (scenario.unresolved_trials > 0 ? 'rule_bounds' : 'conditional_scenario')) invalid('Cup unresolved reason or status mismatch')
    if (!record(scenario.rule_bounds) || !sameIds(Object.keys(scenario.rule_bounds), ids) || !record(scenario.probabilities) || !sameIds(Object.keys(scenario.probabilities), ids)) invalid('incomplete Cup scenario field')
    for (const id of ids) {
      const bound = scenario.rule_bounds[id]
      const count = scenario.resolved_win_counts[id]
      if (!record(bound) || !probability(bound.lower) || !probability(bound.upper) || Math.abs((bound.lower as number) - count / n) > 1e-12 || Math.abs((bound.upper as number) - (count + scenario.unresolved_trials) / n) > 1e-12) invalid('Cup bounds do not reconstruct from counts')
      if (scenario.unresolved_trials > 0 ? scenario.probabilities[id] !== null : !probability(scenario.probabilities[id]) || Math.abs((scenario.probabilities[id] as number) - count / n) > 1e-12) invalid('unresolved Cup point estimate')
    }
    if (!record(scenario.numerical_error) || !finite(scenario.numerical_error.worst_case_95_half_width) || Math.abs(scenario.numerical_error.worst_case_95_half_width - 1.96 * Math.sqrt(.25 / n)) > 1e-12 || !nonempty(scenario.numerical_error.scope) || !scenario.numerical_error.scope.includes('excludes model/rule')) invalid('invalid Cup Monte Carlo precision')
    if (!nonempty(scenario.input_hash) || !/^[a-f0-9]{64}$/.test(scenario.input_hash) || !record(value.header) || scenario.source_manifest_hash !== value.header.source_manifest_hash || scenario.model_ref !== (evidence.model_lineage.model_ref ?? null)) invalid('Cup scenario lineage mismatch')
    if (!Array.isArray(scenario.unresolved_reasons) || !scenario.unresolved_reasons.every(nonempty) || !Array.isArray(scenario.assumptions) || !scenario.assumptions.every(nonempty)) invalid('invalid Cup scenario assumptions')
  }
  if (new Set(scenarioIds).size !== scenarioIds.length || !scenarioIds.includes(evidence.baseline_scenario_id as string) || !Array.isArray(value.evaluated_scenarios) || JSON.stringify(value.evaluated_scenarios) !== JSON.stringify(scenarioIds)) invalid('Cup baseline or scenario index mismatch')
  const typed = evidence as unknown as NonNullable<CupPrediction['scenario_analysis']>
  const baseline = typed.records.find((scenario) => scenario.scenario_id === typed.baseline_scenario_id)!
  for (const id of ids) {
    for (const side of ['lower', 'upper'] as const) {
      const extreme = Math[side === 'lower' ? 'min' : 'max'](...typed.records.map((scenario) => scenario.rule_bounds[id][side]))
      const extrema = typed.extrema_by_team[id]?.[`${side}_scenario_ids`]
      const expected = typed.records.filter((scenario) => scenario.rule_bounds[id][side] === extreme).map((scenario) => scenario.scenario_id)
      const envelope = record(value.scenario_envelope_by_team) ? value.scenario_envelope_by_team[id] : null
      const base = record(value.rule_bounds_by_team) ? value.rule_bounds_by_team[id] : null
      if (!record(envelope) || !finite(envelope[side]) || Math.abs(envelope[side] - extreme) > .000050001 || !record(base) || !finite(base[side]) || Math.abs(base[side] - baseline.rule_bounds[id][side]) > .000050001 || JSON.stringify(extrema) !== JSON.stringify(expected)) invalid('Cup envelope or endpoint attribution mismatch')
    }
  }
  const mapping = typed.mapping_provenance.teams
  if (!Array.isArray(mapping) || !mapping.every(record) || !sameIds(mapping.map((team) => team.team_id), ids) || mapping.some((team) => typeof team.observed !== 'boolean' || (team.observed ? !finite(team.mapped_strength) : team.mapped_strength !== null) || !Array.isArray(team.source_entries) || !team.source_entries.every((entry) => record(entry) && nonempty(entry.entry_id) && finite(entry.effect)))) invalid('Cup missing-history mapping is invalid')
  const strengths = evidence.simulation_inputs.mapped_strength
  if (Object.keys(strengths).some((id) => !ids.includes(id)) || Object.values(strengths).some((strength) => !finite(strength)) || mapping.some((team) => team.observed ? strengths[team.team_id] !== team.mapped_strength : team.team_id in strengths)) invalid('Cup mapping disagrees with simulator inputs')
}

export async function loadPredictionIndex(signal?: AbortSignal) { return parsePredictionIndex(await readJson('/data/predictions/index.json', signal)) }
export async function loadRacePrediction(path: string, context: Parameters<typeof parseRacePrediction>[1], signal?: AbortSignal) { return parseRacePrediction(await readJson(checkedPath(path), signal), context) }
export async function loadCupPrediction(path: string, signal?: AbortSignal) { return parseCupPrediction(await readJson(checkedPath(path), signal)) }
