export type EnvironmentField = 'air_temperature_c' | 'wave_height_m' | 'water_temperature_c'
type EnvironmentProduct = 'air' | 'marine'

interface Location { latitude: number; longitude: number }
export interface EnvironmentSource {
  provider: 'Open-Meteo'
  product: 'historical_model'
  request_url: string
  response_sha256: string
  retrieved_at: string
  grid_location: Location
  response_file: string
}

export interface RaceEnvironment {
  schema_version: 'environment-1'
  context: 'historical_replay_only'
  race_id: string
  requested_location: Location
  units: { air_temperature_c: '°C'; wave_height_m: 'm'; water_temperature_c: '°C'; time_ms: 'Unix milliseconds UTC' }
  hourly: { time_ms: number[]; air_temperature_c: Array<number | null>; wave_height_m: Array<number | null>; water_temperature_c: Array<number | null> }
  sources: Partial<Record<EnvironmentProduct, EnvironmentSource>>
  errors: Partial<Record<EnvironmentProduct, string>>
}

export interface EnvironmentalReading { text: string; title: string; modeled: boolean }

const HOUR_MS = 3_600_000
const fields: EnvironmentField[] = ['air_temperature_c', 'wave_height_m', 'water_temperature_c']
const productFor = (field: EnvironmentField): EnvironmentProduct => field === 'air_temperature_c' ? 'air' : 'marine'
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const nonempty = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0
const location = (value: unknown): value is Location => record(value) && finite(value.latitude) && Math.abs(value.latitude) <= 90 && finite(value.longitude) && Math.abs(value.longitude) <= 180
function invalid(reason: string): never { throw new Error(`Environmental data unavailable: ${reason}`) }

export function parseRaceEnvironment(value: unknown, raceId: string): RaceEnvironment {
  if (!record(value) || value.schema_version !== 'environment-1' || value.context !== 'historical_replay_only') invalid('unsupported historical data format.')
  if (value.race_id !== raceId) invalid('the data belongs to another race.')
  if (!location(value.requested_location)) invalid('invalid race location.')
  if (!record(value.units) || value.units.time_ms !== 'Unix milliseconds UTC' || value.units.air_temperature_c !== '°C' || value.units.wave_height_m !== 'm' || value.units.water_temperature_c !== '°C') invalid('unexpected time or measurement units.')
  if (!record(value.hourly) || !Array.isArray(value.hourly.time_ms)) invalid('missing hourly times.')
  const times = value.hourly.time_ms
  if (times.some((time, index) => !finite(time) || !Number.isSafeInteger(time) || !Number.isFinite(new Date(time).getTime()) || time % HOUR_MS !== 0 || (index > 0 && time <= times[index - 1]))) invalid('hourly times must be ordered UTC hours.')
  for (const field of fields) {
    const column = value.hourly[field]
    if (!Array.isArray(column) || column.length !== times.length || column.some((item) => item !== null && (!finite(item) || (field === 'wave_height_m' && item < 0)))) invalid(`invalid ${field} hourly values.`)
  }
  if (!record(value.sources) || !record(value.errors)) invalid('missing source information.')
  for (const product of ['air', 'marine'] as const) {
    const error = value.errors[product]
    if (error !== undefined && !nonempty(error)) invalid(`invalid ${product} source error.`)
    const source = value.sources[product]
    if (source !== undefined) {
      if (!record(source) || source.provider !== 'Open-Meteo' || source.product !== 'historical_model' || !nonempty(source.request_url) || !/^https:\/\/[a-z0-9-]+\.open-meteo\.com\//i.test(source.request_url) || typeof source.response_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(source.response_sha256) || !nonempty(source.retrieved_at) || !Number.isFinite(Date.parse(source.retrieved_at)) || !location(source.grid_location) || source.response_file !== `responses/${source.response_sha256}.json`) invalid(`invalid ${product} model provenance.`)
    } else if (fields.filter((field) => productFor(field) === product).some((field) => (value.hourly as RaceEnvironment['hourly'])[field].some((item) => item !== null))) {
      invalid(`${product} values have no model provenance.`)
    }
  }
  return value as unknown as RaceEnvironment
}

export async function loadRaceEnvironment(raceId: string, signal?: AbortSignal): Promise<RaceEnvironment> {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(raceId)) invalid('invalid race identifier.')
  const response = await fetch(`/data/environment/${encodeURIComponent(raceId)}.json`, { signal, cache: 'no-cache' })
  if (!response.ok) invalid(`historical data request returned HTTP ${response.status}.`)
  if (!response.headers.get('content-type')?.toLowerCase().includes('application/json')) invalid('historical data request did not return JSON.')
  return parseRaceEnvironment(await response.json(), raceId)
}

/** The valid UTC hour contains the playhead; no future samples or gap filling. */
export function environmentHourIndex(environment: RaceEnvironment, timestamp: number): number | null {
  if (!Number.isFinite(timestamp)) return null
  const times = environment.hourly.time_ms
  let lower = 0
  let upper = times.length
  while (lower < upper) {
    const middle = (lower + upper) >>> 1
    if (times[middle] <= timestamp) lower = middle + 1
    else upper = middle
  }
  const index = lower - 1
  return index >= 0 && timestamp - times[index] < HOUR_MS ? index : null
}

export function environmentalReading(environment: RaceEnvironment | null, field: EnvironmentField, timestamp: number, error?: string | null): EnvironmentalReading {
  if (!environment) return { text: error ? 'unavailable' : 'loading…', title: error || 'Loading historical environmental model data for this race.', modeled: false }
  const product = productFor(field)
  const sourceError = environment.errors[product]
  if (sourceError) return { text: 'unavailable', title: sourceError, modeled: false }
  const source = environment.sources[product]
  if (!source) return { text: 'unavailable', title: 'No historical model response is available for this source.', modeled: false }
  const quantity = field === 'wave_height_m' ? 'Significant wave height' : field === 'air_temperature_c' ? 'Air temperature' : 'Water temperature'
  const index = environmentHourIndex(environment, timestamp)
  const value = index === null ? null : environment.hourly[field][index]
  if (index === null || value === null) return { text: 'unavailable', title: `Open-Meteo historical model has no ${quantity.toLowerCase()} value for this UTC hour. ${source.request_url}`, modeled: false }
  const validHour = new Date(environment.hourly.time_ms[index]).toISOString().slice(0, 16).replace('T', ' ')
  return {
    text: `${value.toFixed(1)} ${field === 'wave_height_m' ? 'm' : '°C'}`,
    title: `${quantity}: Open-Meteo historical model. Hourly model sample at ${validHour} UTC; displayed only within that UTC hour. Model grid ${source.grid_location.latitude}, ${source.grid_location.longitude}; not a boat measurement. ${source.request_url}`,
    modeled: true,
  }
}
