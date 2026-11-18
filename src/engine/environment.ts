import type {
  CanonicalChannel,
  EnvironmentField,
  EnvironmentalReading,
  EnvironmentSeriesV2,
  ProviderLink,
  RaceEnvironment,
  RaceEnvironmentV1,
  RaceEnvironmentV2,
} from '../types/environment'

export type {
  CanonicalChannel,
  ChannelProvenance,
  EnvironmentField,
  EnvironmentalReading,
  EnvironmentSeriesV2,
  EnvironmentSourceV1,
  ProviderLink,
  RaceEnvironment,
  RaceEnvironmentV1,
  RaceEnvironmentV2,
} from '../types/environment'

type EnvironmentProduct = 'air' | 'marine'

interface Location {
  latitude: number
  longitude: number
}

type V1Field = 'air_temperature_c' | 'wave_height_m' | 'water_temperature_c'
const HOUR_MS = 3_600_000
const v1Fields: V1Field[] = ['air_temperature_c', 'wave_height_m', 'water_temperature_c']
const v1ProductFor = (field: V1Field): EnvironmentProduct => (field === 'air_temperature_c' ? 'air' : 'marine')

const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const nonempty = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0
const location = (value: unknown): value is Location =>
  record(value) && finite(value.latitude) && Math.abs(value.latitude) <= 90 && finite(value.longitude) && Math.abs(value.longitude) <= 180

function invalid(reason: string): never {
  throw new Error(`Environmental data unavailable: ${reason}`)
}

function validateOrderedUtcHours(times: unknown): number[] {
  if (!Array.isArray(times)) invalid('missing hourly times.')
  const arr = times as number[]
  if (
    arr.some(
      (time, index) =>
        !finite(time) ||
        !Number.isSafeInteger(time) ||
        !Number.isFinite(new Date(time).getTime()) ||
        time % HOUR_MS !== 0 ||
        (index > 0 && time <= arr[index - 1]),
    )
  )
    invalid('hourly times must be ordered UTC hours.')
  return arr
}

function parseRaceEnvironmentV1(value: Record<string, any>, raceId: string): RaceEnvironmentV1 {
  if (value.context !== 'historical_replay_only') invalid('unsupported historical data format.')
  if (value.race_id !== raceId) invalid('the data belongs to another race.')
  if (!location(value.requested_location)) invalid('invalid race location.')
  if (
    !record(value.units) ||
    value.units.time_ms !== 'Unix milliseconds UTC' ||
    value.units.air_temperature_c !== '°C' ||
    value.units.wave_height_m !== 'm' ||
    value.units.water_temperature_c !== '°C'
  )
    invalid('unexpected time or measurement units.')
  if (!record(value.hourly)) invalid('missing hourly times.')
  const times = validateOrderedUtcHours(value.hourly.time_ms)
  for (const field of v1Fields) {
    const column = value.hourly[field]
    if (!Array.isArray(column) || column.length !== times.length || column.some((item) => item !== null && (!finite(item) || (field === 'wave_height_m' && item < 0))))
      invalid(`invalid ${field} hourly values.`)
  }
  if (!record(value.sources) || !record(value.errors)) invalid('missing source information.')
  for (const product of ['air', 'marine'] as const) {
    const error = value.errors[product]
    if (error !== undefined && !nonempty(error)) invalid(`invalid ${product} source error.`)
    const source = value.sources[product]
    if (source !== undefined) {
      if (
        !record(source) ||
        source.provider !== 'Open-Meteo' ||
        source.product !== 'historical_model' ||
        !nonempty(source.request_url) ||
        !/^https:\/\/[a-z0-9-]+\.open-meteo\.com\//i.test(source.request_url) ||
        typeof source.response_sha256 !== 'string' ||
        !/^[a-f0-9]{64}$/.test(source.response_sha256) ||
        !nonempty(source.retrieved_at) ||
        !Number.isFinite(Date.parse(source.retrieved_at)) ||
        !location(source.grid_location) ||
        source.response_file !== `responses/${source.response_sha256}.json`
      )
        invalid(`invalid ${product} model provenance.`)
    } else if (v1Fields.filter((field) => v1ProductFor(field) === product).some((field) => (value.hourly as RaceEnvironmentV1['hourly'])[field].some((item: number | null) => item !== null))) {
      invalid(`${product} values have no model provenance.`)
    }
  }
  return value as RaceEnvironmentV1
}

function parseRaceEnvironmentV2(value: Record<string, any>, raceId: string): RaceEnvironmentV2 {
  if (value.race_id !== raceId) invalid('the data belongs to another race.')
  if (!record(value.location) || !finite(value.location.latitude) || !finite(value.location.longitude)) invalid('unsupported historical data format: invalid race location.')
  if (!record(value.channels)) invalid('unsupported historical data format: missing channels specification.')
  const requiredChannels: CanonicalChannel[] = ['currents', 'waves', 'air_temperature', 'water_temperature']
  for (const ch of requiredChannels) {
    if (!record(value.channels[ch])) invalid(`unsupported historical data format: missing channel '${ch}'.`)
  }
  if (!record(value.course_centre)) invalid('unsupported historical data format: missing course_centre time series.')
  validateOrderedUtcHours(value.course_centre.time_ms)
  return value as RaceEnvironmentV2
}

export function parseRaceEnvironment(value: unknown, raceId: string): RaceEnvironment {
  if (!record(value)) invalid('unsupported historical data format.')
  if (value.schema_version === 'environment-1') {
    return parseRaceEnvironmentV1(value, raceId)
  }
  if (value.schema_version === 'environment-2') {
    return parseRaceEnvironmentV2(value, raceId)
  }
  invalid('unsupported historical data format.')
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
  const times = environment.schema_version === 'environment-2' ? environment.course_centre.time_ms : environment.hourly.time_ms
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

function channelForField(field: EnvironmentField): CanonicalChannel {
  switch (field) {
    case 'current_speed_mps':
    case 'current_dir_towards_deg':
      return 'currents'
    case 'wave_height_m':
    case 'wave_period_s':
    case 'wave_dir_from_deg':
      return 'waves'
    case 'air_temperature_c':
      return 'air_temperature'
    case 'water_temperature_c':
      return 'water_temperature'
  }
}

function getSeriesValue(series: EnvironmentSeriesV2, field: EnvironmentField, index: number): number | null {
  switch (field) {
    case 'current_speed_mps':
      return series.current_speed_mps[index] ?? null
    case 'current_dir_towards_deg':
      return series.current_dir_towards_deg[index] ?? null
    case 'wave_height_m':
      return series.wave_height_m[index] ?? null
    case 'wave_period_s':
      return series.wave_period_s[index] ?? null
    case 'wave_dir_from_deg':
      return series.wave_dir_from_deg[index] ?? null
    case 'air_temperature_c':
      return series.air_temperature_c[index] ?? null
    case 'water_temperature_c':
      return series.water_temperature_c[index] ?? null
  }
}

export function environmentalReading(environment: RaceEnvironment | null, field: EnvironmentField, timestamp: number, error?: string | null): EnvironmentalReading {
  if (!environment) return { text: error ? 'unavailable' : 'loading…', title: error || 'Loading historical environmental model data for this race.', modeled: false }

  if (environment.schema_version === 'environment-1') {
    if (field !== 'air_temperature_c' && field !== 'wave_height_m' && field !== 'water_temperature_c') {
      return { text: 'unavailable', title: `Field ${field} is not available in environment-1 schema.`, modeled: false }
    }
    const product = v1ProductFor(field)
    const sourceError = environment.errors[product]
    if (sourceError) return { text: 'unavailable', title: sourceError, modeled: false }
    const source = environment.sources[product]
    if (!source) return { text: 'unavailable', title: 'No historical model response is available for this source.', modeled: false }
    const quantity = field === 'wave_height_m' ? 'Significant wave height' : field === 'air_temperature_c' ? 'Air temperature' : 'Water temperature'
    const index = environmentHourIndex(environment, timestamp)
    const value = index === null ? null : environment.hourly[field][index]
    if (index === null || value === null)
      return { text: 'unavailable', title: `Open-Meteo historical model has no ${quantity.toLowerCase()} value for this UTC hour. ${source.request_url}`, modeled: false }
    const validHour = new Date(environment.hourly.time_ms[index]).toISOString().slice(0, 16).replace('T', ' ')
    return {
      text: `${value.toFixed(1)} ${field === 'wave_height_m' ? 'm' : '°C'}`,
      title: `${quantity}: Open-Meteo historical model. Hourly model sample at ${validHour} UTC; displayed only within that UTC hour. Model grid ${source.grid_location.latitude}, ${source.grid_location.longitude}; not a boat measurement. ${source.request_url}`,
      modeled: true,
    }
  }

  // Schema environment-2
  const chName = channelForField(field)
  const ch = environment.channels[chName]
  if (!ch || ch.quality_status === 'unavailable' || ch.quality_status === 'excluded') {
    return { text: 'unavailable', title: `${ch?.provider ?? 'Model'} data is unavailable for this session${ch?.fallback_reason ? ': ' + ch.fallback_reason : '.'}`, modeled: false }
  }

  const index = environmentHourIndex(environment, timestamp)
  const times = environment.course_centre.time_ms
  const val = index === null ? null : getSeriesValue(environment.course_centre, field, index)

  if (index === null || val === null || val === undefined || !Number.isFinite(val)) {
    return { text: 'unavailable', title: `${ch.provider} has no ${field} value for this UTC hour.`, modeled: false }
  }

  const validHour = new Date(times[index]).toISOString().slice(0, 16).replace('T', ' ')
  const depthText = ch.depth_m !== null && ch.depth_m !== undefined ? ` at depth ${ch.depth_m.toFixed(1)} m` : ''
  const convText = ch.temperature_convention ? ` (${ch.temperature_convention})` : ''

  let text = ''
  let quantityName = ''
  if (field === 'wave_height_m') {
    quantityName = 'Significant wave height'
    text = `${val.toFixed(1)} m`
  } else if (field === 'wave_period_s') {
    quantityName = 'Energy wave period Tm-1,0'
    text = `${val.toFixed(1)} s`
  } else if (field === 'wave_dir_from_deg') {
    quantityName = 'Mean wave direction (from)'
    text = `${Math.round(val)}° T`
  } else if (field === 'air_temperature_c') {
    quantityName = 'Air temperature (2 m)'
    text = `${val.toFixed(1)} °C`
  } else if (field === 'water_temperature_c') {
    quantityName = `Near-surface water temperature${depthText}${convText}`
    text = `${val.toFixed(1)} °C`
  } else if (field === 'current_speed_mps') {
    quantityName = 'Surface current speed'
    const kt = val * 1.943844
    text = `${kt.toFixed(1)} kt`
  } else if (field === 'current_dir_towards_deg') {
    quantityName = 'Surface current direction (towards)'
    text = `${Math.round(val)}° T`
  }

  return {
    text,
    title: `${quantityName}: ${ch.provider} (${ch.dataset}). Hourly model sample at ${validHour} UTC${depthText}; not a boat measurement. Status: ${ch.quality_status}.`,
    modeled: true,
  }
}

export function getProviderLinks(environment: RaceEnvironment | null): ProviderLink[] {
  if (!environment) return []
  if (environment.schema_version === 'environment-1') {
    return [{ label: 'Open-Meteo model', url: 'https://open-meteo.com/' }]
  }

  const links: ProviderLink[] = []
  const seen = new Set<string>()

  const checkAndAdd = (label: string, url: string) => {
    if (!seen.has(label)) {
      seen.add(label)
      links.push({ label, url })
    }
  }

  for (const ch of Object.values(environment.channels)) {
    const p = (ch.provider || '').toLowerCase()
    const pid = (ch.provider_id || '').toLowerCase()
    if (pid.includes('copernicus') || p.includes('copernicus')) {
      checkAndAdd('Copernicus Marine', 'https://marine.copernicus.eu/')
    } else if (pid.includes('parthenope') || p.includes('parthenope')) {
      checkAndAdd('UniParthenope CCMMMA', 'https://meteo.uniparthenope.it/')
    } else if (pid.includes('hycom') || p.includes('hycom')) {
      checkAndAdd('HYCOM GOFS 3.1', 'https://www.hycom.org/')
    } else if (pid.includes('open_meteo') || p.includes('open-meteo') || p.includes('arome') || p.includes('icon')) {
      checkAndAdd('Open-Meteo model', 'https://open-meteo.com/')
    }
  }

  return links
}

export function getEnvironmentalReadings(
  environment: RaceEnvironment | null,
  timestamp: number,
  error?: string | null,
): Array<EnvironmentalReading & { label: string }> {
  if (!environment || environment.schema_version === 'environment-1') {
    return [
      { label: 'Sea', ...environmentalReading(environment, 'wave_height_m', timestamp, error) },
      { label: 'Air', ...environmentalReading(environment, 'air_temperature_c', timestamp, error) },
      { label: 'Water', ...environmentalReading(environment, 'water_temperature_c', timestamp, error) },
    ]
  }

  // Schema environment-2
  // Current: speed + towards bearing
  const curSpd = environmentalReading(environment, 'current_speed_mps', timestamp, error)
  const curDir = environmentalReading(environment, 'current_dir_towards_deg', timestamp, error)
  let curReading: EnvironmentalReading
  if (!curSpd.modeled) {
    curReading = curSpd
  } else {
    // If slack (< 0.01 m/s), bearing is null / omitted
    const index = environmentHourIndex(environment, timestamp)
    const spdMps = index === null ? null : environment.course_centre.current_speed_mps[index]
    if (spdMps !== null && spdMps < 0.01) {
      curReading = {
        text: 'Slack (<0.1 kt)',
        title: `${curSpd.title} (slack current below 0.01 m/s threshold; bearing omitted)`,
        modeled: true,
      }
    } else if (curDir.modeled) {
      curReading = {
        text: `${curSpd.text} · ${curDir.text}`,
        title: `${curSpd.title} Towards ${curDir.text}.`,
        modeled: true,
      }
    } else {
      curReading = curSpd
    }
  }

  // Sea: wave height + period + from bearing
  const seaHs = environmentalReading(environment, 'wave_height_m', timestamp, error)
  const seaTp = environmentalReading(environment, 'wave_period_s', timestamp, error)
  const seaDir = environmentalReading(environment, 'wave_dir_from_deg', timestamp, error)
  let seaReading: EnvironmentalReading
  if (!seaHs.modeled) {
    seaReading = seaHs
  } else {
    // If calm (< 0.05 m), period and direction are null / omitted
    const index = environmentHourIndex(environment, timestamp)
    const hsVal = index === null ? null : environment.course_centre.wave_height_m[index]
    if (hsVal !== null && hsVal < 0.05) {
      seaReading = {
        text: `${seaHs.text}`,
        title: `${seaHs.title} (calm sea below 0.05 m threshold; period and direction omitted)`,
        modeled: true,
      }
    } else if (seaTp.modeled && seaDir.modeled) {
      seaReading = {
        text: `${seaHs.text} · ${seaTp.text} · ${seaDir.text}`,
        title: `${seaHs.title} Wave period ${seaTp.text}, coming from ${seaDir.text}.`,
        modeled: true,
      }
    } else {
      seaReading = seaHs
    }
  }

  // Air
  const airReading = environmentalReading(environment, 'air_temperature_c', timestamp, error)

  // Water
  const waterReading = environmentalReading(environment, 'water_temperature_c', timestamp, error)

  return [
    { label: 'Current', ...curReading },
    { label: 'Sea', ...seaReading },
    { label: 'Air', ...airReading },
    { label: 'Water', ...waterReading },
  ]
}
