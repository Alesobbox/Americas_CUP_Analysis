import { afterEach, describe, expect, it, vi } from 'vitest'
import { environmentalReading, environmentHourIndex, loadRaceEnvironment, parseRaceEnvironment } from './environment'
import type { RaceEnvironment } from './environment'

const hour = 3_600_000
const start = Date.parse('2026-09-22T12:00:00Z')
function fixture(): RaceEnvironment {
  const source = {
    provider: 'Open-Meteo' as const, product: 'historical_model' as const,
    request_url: 'https://archive-api.open-meteo.com/v1/archive?latitude=40.8&longitude=14.2',
    response_sha256: 'a'.repeat(64), retrieved_at: '2026-10-16T12:00:00Z',
    grid_location: { latitude: 40.8, longitude: 14.2 }, response_file: `responses/${'a'.repeat(64)}.json`,
  }
  return {
    schema_version: 'environment-1', context: 'historical_replay_only', race_id: 'naples_pr1',
    requested_location: { latitude: 40.8, longitude: 14.2 },
    units: { time_ms: 'Unix milliseconds UTC', air_temperature_c: '°C', wave_height_m: 'm', water_temperature_c: '°C' },
    hourly: { time_ms: [start, start + hour, start + 3 * hour], air_temperature_c: [24, 25, 26], wave_height_m: [0.4, null, 0.5], water_temperature_c: [23, 24, 25] },
    sources: { air: source, marine: { ...source, request_url: 'https://marine-api.open-meteo.com/v1/marine?latitude=40.8&longitude=14.2' } }, errors: {},
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('historical environmental data', () => {
  it('validates race identity, declared units, location and provenance', () => {
    expect(parseRaceEnvironment(fixture(), 'naples_pr1').hourly.wave_height_m[0]).toBe(0.4)
    expect(() => parseRaceEnvironment(fixture(), 'other-race')).toThrow('another race')
    expect(() => parseRaceEnvironment({ ...fixture(), schema_version: 'environment-2' }, 'naples_pr1')).toThrow('format')
    expect(() => parseRaceEnvironment({ ...fixture(), context: 'live_forecast' }, 'naples_pr1')).toThrow('format')
    expect(() => parseRaceEnvironment({ ...fixture(), units: { ...fixture().units, air_temperature_c: '°F' } }, 'naples_pr1')).toThrow('units')
    expect(() => parseRaceEnvironment({ ...fixture(), requested_location: { latitude: 100, longitude: 14 } }, 'naples_pr1')).toThrow('location')
    const missingProvenance = fixture()
    delete missingProvenance.sources.marine
    expect(() => parseRaceEnvironment(missingProvenance, 'naples_pr1')).toThrow('provenance')
    const invalidProvenance = fixture()
    invalidProvenance.sources.air!.response_sha256 = 'url-is-not-a-hash'
    expect(() => parseRaceEnvironment(invalidProvenance, 'naples_pr1')).toThrow('provenance')
  })

  it('rejects misaligned, unordered or nonfinite hourly columns', () => {
    for (const change of [
      (value: RaceEnvironment) => { value.hourly.time_ms[1] = value.hourly.time_ms[0] },
      (value: RaceEnvironment) => { value.hourly.time_ms[1] += 1000 },
      (value: RaceEnvironment) => { value.hourly.time_ms[1] = Infinity },
      (value: RaceEnvironment) => { value.hourly.air_temperature_c.pop() },
      (value: RaceEnvironment) => { value.hourly.wave_height_m[1] = -0.1 },
      (value: RaceEnvironment) => { value.hourly.water_temperature_c[1] = NaN },
    ]) {
      const value = fixture()
      change(value)
      expect(() => parseRaceEnvironment(value, 'naples_pr1')).toThrow('Environmental data unavailable')
    }
  })

  it('selects only the containing UTC hour without future data, long holds, or gap interpolation', () => {
    const data = fixture()
    expect(environmentHourIndex(data, start - 1)).toBeNull()
    expect(environmentHourIndex(data, start)).toBe(0)
    expect(environmentHourIndex(data, start + hour - 1)).toBe(0)
    expect(environmentHourIndex(data, start + hour)).toBe(1)
    expect(environmentHourIndex(data, start + 2 * hour)).toBeNull()
    expect(environmentHourIndex(data, start + 3 * hour - 1)).toBeNull()
    expect(environmentHourIndex(data, start + 3 * hour)).toBe(2)
    expect(environmentHourIndex(data, start + 4 * hour)).toBeNull()
    expect(environmentHourIndex(data, start + 1000)).toBe(0)
    expect(environmentHourIndex(data, NaN)).toBeNull()
    expect(environmentHourIndex({ ...data, hourly: { time_ms: [], air_temperature_c: [], wave_height_m: [], water_temperature_c: [] } }, start)).toBeNull()
  })

  it('makes the modeled origin, valid hour and provider request visible in the reading description', () => {
    const data = fixture()
    const reading = environmentalReading(data, 'wave_height_m', start + 9999)
    expect(reading).toMatchObject({ text: '0.4 m', modeled: true })
    expect(reading.title).toContain('Significant wave height: Open-Meteo historical model')
    expect(reading.title).toContain('2026-09-22 12:00 UTC')
    expect(reading.title).toContain('not a boat measurement')
    expect(reading.title).toContain(data.sources.marine!.request_url)
    expect(environmentalReading(data, 'air_temperature_c', start).text).toBe('24.0 °C')
  })

  it('preserves available marine values when the air source fails', () => {
    const data = fixture()
    delete data.sources.air
    data.errors.air = 'Open-Meteo air request returned HTTP 503.'
    data.hourly.air_temperature_c.fill(null)
    const parsed = parseRaceEnvironment(data, 'naples_pr1')
    expect(environmentalReading(parsed, 'air_temperature_c', start)).toEqual({ text: 'unavailable', title: data.errors.air, modeled: false })
    expect(environmentalReading(parsed, 'water_temperature_c', start).text).toBe('23.0 °C')
    expect(environmentalReading(parsed, 'wave_height_m', start).text).toBe('0.4 m')
  })

  it('keeps null hours and unknown hours unavailable and distinguishes loading from errors', () => {
    const data = fixture()
    expect(environmentalReading(data, 'wave_height_m', start + hour)).toMatchObject({ text: 'unavailable', modeled: false })
    expect(environmentalReading(data, 'air_temperature_c', start - 1).title).toContain('no air temperature value for this UTC hour')
    expect(environmentalReading(null, 'air_temperature_c', start).text).toBe('loading…')
    expect(environmentalReading(null, 'air_temperature_c', start, 'Network request failed.')).toEqual({ text: 'unavailable', title: 'Network request failed.', modeled: false })
  })

  it('loads the selected race once per call and forwards abort and cache controls', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture()), { headers: { 'content-type': 'application/json; charset=utf-8' } }))
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()
    expect((await loadRaceEnvironment('naples_pr1', controller.signal)).race_id).toBe('naples_pr1')
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith('/data/environment/naples_pr1.json', { signal: controller.signal, cache: 'no-cache' })
  })

  it('rejects missing data, HTML fallback, wrong-race responses and unsafe identifiers', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockResolvedValueOnce(new Response('{}', { status: 404, headers: { 'content-type': 'application/json' } }))
    await expect(loadRaceEnvironment('naples_pr1')).rejects.toThrow('HTTP 404')
    fetchMock.mockResolvedValueOnce(new Response('<html>application</html>', { headers: { 'content-type': 'text/html' } }))
    await expect(loadRaceEnvironment('naples_pr1')).rejects.toThrow('did not return JSON')
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(fixture()), { headers: { 'content-type': 'application/json' } }))
    await expect(loadRaceEnvironment('other')).rejects.toThrow('another race')
    await expect(loadRaceEnvironment('../other')).rejects.toThrow('race identifier')
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })
})
