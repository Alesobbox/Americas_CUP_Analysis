import type { CupPrediction, ForecastStatus, PredictionIndex, PredictionPreset, PredictionReference, RacePrediction } from '../types/prediction'

const statuses: ForecastStatus[] = ['available', 'estimated', 'gate_ambiguous', 'unavailable']
const usable = (status: ForecastStatus) => status === 'available' || status === 'estimated'
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const probability = (value: unknown) => finite(value) && value >= 0 && value <= 1
const nonempty = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0
const sameIds = (left: string[], right: string[]) => left.length === right.length && new Set(left).size === left.length && left.every((id) => right.includes(id))

function invalid(message: string): never { throw new Error(`Forecast unavailable: ${message}`) }

function checkedPath(path: unknown): string {
  if (typeof path !== 'string' || !/^(?:predictions\/)?[a-zA-Z0-9_/-]+\.json$/.test(path) || path.includes('..') || path.startsWith('/')) invalid('unsafe artifact path')
  return path.startsWith('predictions/') ? `/data/${path}` : `/data/predictions/${path}`
}

async function readJson(path: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(path, { signal })
  if (!response.ok) invalid(`artifact could not be loaded (${response.status})`)
  if (!response.headers.get('content-type')?.toLowerCase().includes('json')) invalid('artifact did not return JSON')
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

export function parseRacePrediction(value: unknown, context: { raceId: string; boatIds: string[]; boatClass: string; reference?: PredictionReference; scope?: string }): RacePrediction {
  if (!record(value) || !record(value.header) || !record(value.pre_race) || !record(value.live)) invalid('incomplete race artifact')
  const h = value.header
  if (h.schema_version !== 'prediction-1' || h.race_id !== context.raceId) invalid('artifact does not match the selected race')
  if (!Array.isArray(h.boat_ids) || !h.boat_ids.every(nonempty) || !sameIds(h.boat_ids, context.boatIds)) invalid('competitor field does not match the selected race')
  if (h.boat_class !== context.boatClass) invalid('boat class does not match the selected race')
  if (context.scope && h.scope !== context.scope) invalid('scenario scope does not match this card')
  if (![h.model_ref, h.source_manifest_hash, h.scenario_hash].every(nonempty)) invalid('model and input provenance is missing')
  verifyReference(h, context.reference)
  if (!Array.isArray(h.status_dictionary) || !sameIds(h.status_dictionary as string[], statuses) || !Array.isArray(h.method_and_assumption_refs)) invalid('quality and method definitions are missing')
  const pre = value.pre_race
  if (!statuses.includes(pre.status as ForecastStatus) || !record(pre.expected_position_by_boat) || !sameIds(Object.keys(pre.expected_position_by_boat), context.boatIds)) invalid('incomplete pre-race predictions')
  if (pre.nonfinish_score !== 'N' && pre.nonfinish_score !== context.boatIds.length) invalid('nonfinish position does not match the scheduled field')
  for (const position of Object.values(pre.expected_position_by_boat)) {
    if (usable(pre.status as ForecastStatus) ? !finite(position) || position < 1 || position > context.boatIds.length : position !== null) invalid('invalid or unavailable expected position')
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
    if (!record(columns) || !sameIds(Object.keys(columns), context.boatIds) || Object.values(columns).some((column) => !Array.isArray(column) || column.length !== count)) invalid(`checkpoint column ${key} does not contain the complete field`)
  }
  const prediction = value as unknown as RacePrediction
  for (let i = 0; i < count; i++) {
    const stateTime = prediction.live.state_timestamps_ms[i]
    const publication = prediction.live.published_at_ms[i]
    if (!finite(stateTime) || !finite(publication) || publication < stateTime || (i > 0 && (stateTime <= prediction.live.state_timestamps_ms[i - 1] || publication < prediction.live.published_at_ms[i - 1]))) invalid('checkpoint chronology is invalid')
    if (finite(h.train_cutoff_ms) && h.train_cutoff_ms > stateTime) invalid('training cutoff is later than the forecast state')
    const status = checkpointStatus(prediction, i)
    if (!status) invalid('checkpoint quality is unknown')
    const values = [...context.boatIds.map((id) => prediction.live.win_prob_by_boat[id][i]), prediction.live.no_finisher_prob[i]]
    if (usable(status)) {
      if (!values.every(probability) || Math.abs((values as number[]).reduce((sum, p) => sum + p, 0) - 1) > 1e-5) invalid('joint winning probabilities are incomplete or do not sum to one')
    } else if (!values.every((p) => p === null)) invalid('unavailable checkpoint contains probabilities')
    for (const id of context.boatIds) {
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
  if (value.teams.length !== 7 || value.teams.some((team) => !record(team) || !nonempty(team.id) || !nonempty(team.name)) || new Set(value.teams.map((team) => team.id)).size !== 7) invalid('the Cup field must include the Defender and all six Challengers')
  const ids = value.teams.map((team) => team.id as string)
  for (const key of ['scenario_envelope_by_team', 'rule_bounds_by_team']) {
    const bounds = value[key]
    if (bounds === undefined) continue
    if (!record(bounds) || !sameIds(Object.keys(bounds), ids)) invalid('Cup scenarios contain an incomplete field')
    for (const bound of Object.values(bounds)) {
      if (bound === null && !usable(value.status as ForecastStatus)) continue
      if (!record(bound) || !probability(bound.lower) || !probability(bound.upper) || (bound.lower as number) > (bound.upper as number)) invalid('invalid Cup scenario or rule bounds')
    }
  }
  if (usable(value.status as ForecastStatus) && !record(value.scenario_envelope_by_team) && !record(value.rule_bounds_by_team)) invalid('Cup estimates are missing')
  if (!usable(value.status as ForecastStatus) && ['scenario_envelope_by_team', 'rule_bounds_by_team'].some((key) => record(value[key]) && Object.values(value[key]).some((p) => p !== null))) invalid('unavailable Cup artifact contains estimates')
  return value as unknown as CupPrediction
}

export async function loadPredictionIndex(signal?: AbortSignal) { return parsePredictionIndex(await readJson('/data/predictions/index.json', signal)) }
export async function loadRacePrediction(path: string, context: Parameters<typeof parseRacePrediction>[1], signal?: AbortSignal) { return parseRacePrediction(await readJson(checkedPath(path), signal), context) }
export async function loadCupPrediction(path: string, signal?: AbortSignal) { return parseCupPrediction(await readJson(checkedPath(path), signal)) }
