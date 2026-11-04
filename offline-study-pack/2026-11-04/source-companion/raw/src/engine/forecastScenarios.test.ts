import { afterEach, describe, expect, it, vi } from 'vitest'
import { loadScenarioService, prepareScenario } from './forecastScenarios'

const input = { race_id: 'naples_pr1', tws_kt: 13, direction_offset_deg: 0 }
const job = { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', input, status: 'complete', message: 'The exact forecast is ready.', path: `scenarios/${'a'.repeat(64)}.json` }
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
afterEach(() => vi.unstubAllGlobals())

describe('exact scenario dashboard client', () => {
  it('reads service readiness and provides a usable fallback for a static-only installation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ available: true, direction_offset_deg: 0, message: 'Ready' })))
    expect(await loadScenarioService()).toMatchObject({ available: true, direction_offset_deg: 0 })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>Application</html>', { headers: { 'Content-Type': 'text/html' } })))
    await expect(loadScenarioService()).rejects.toThrow('Use a published scenario')
  })

  it('posts the exact entered numbers and accepts only their matching completed job', async () => {
    const fetcher = vi.fn().mockResolvedValue(response(job))
    vi.stubGlobal('fetch', fetcher)
    const progress = vi.fn()
    expect(await prepareScenario(input, new AbortController().signal, progress)).toMatchObject(job)
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual(input)
    expect(progress).toHaveBeenCalledWith(job.message)
  })

  it('rejects mismatched conditions or arbitrary result paths instead of showing stale ranks', async () => {
    for (const invalid of [{ ...job, input: { ...input, tws_kt: 12 } }, { ...job, path: '../other.json' }]) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(invalid)))
      await expect(prepareScenario(input, new AbortController().signal, vi.fn())).rejects.toThrow('does not match these exact conditions')
    }
  })

  it('surfaces a service conflict as a retryable explanation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ error: 'Another exact forecast is being prepared.' }, 409)))
    await expect(prepareScenario(input, new AbortController().signal, vi.fn())).rejects.toThrow('Another exact forecast')
  })
})
