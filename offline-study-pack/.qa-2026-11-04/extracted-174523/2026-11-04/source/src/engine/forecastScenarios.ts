export interface ScenarioInput { race_id: string; tws_kt: number; direction_offset_deg: number }
export interface ScenarioService { available: boolean; direction_offset_deg: number; message: string }
interface ScenarioJob { id: string; input: ScenarioInput; status: 'queued' | 'running' | 'complete' | 'failed'; message: string; path?: string; reason?: string; error?: string }
const base = '/api/forecast-scenarios'

async function json(url: string, options: RequestInit): Promise<Record<string, unknown>> {
  const response = await fetch(url, options)
  if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Forecast preparation is unavailable in this installation. Use a published scenario or the recorded start conditions.')
  const value = await response.json() as Record<string, unknown>
  if (!response.ok) throw new Error(typeof value.error === 'string' ? value.error : 'The forecast could not be prepared. Please retry.')
  return value
}

export async function loadScenarioService(signal?: AbortSignal): Promise<ScenarioService> {
  const value = await json(base, { signal })
  if (typeof value.available !== 'boolean' || typeof value.direction_offset_deg !== 'number' || typeof value.message !== 'string') throw new Error('Forecast preparation is unavailable in this installation.')
  return value as unknown as ScenarioService
}

function checkedJob(value: Record<string, unknown>, input: ScenarioInput): ScenarioJob {
  const job = value as unknown as ScenarioJob
  if (typeof job.id !== 'string' || !/^[a-f0-9-]{36}$/.test(job.id) || !['queued', 'running', 'complete', 'failed'].includes(job.status) || typeof job.message !== 'string' ||
    job.input?.race_id !== input.race_id || job.input?.tws_kt !== input.tws_kt || job.input?.direction_offset_deg !== input.direction_offset_deg ||
    (job.status === 'complete' && (typeof job.path !== 'string' || !/^scenarios\/[a-f0-9]{64}\.json$/.test(job.path)))) throw new Error('The prepared forecast does not match these exact conditions. Please retry.')
  return job
}

export async function prepareScenario(input: ScenarioInput, signal: AbortSignal, progress: (message: string) => void): Promise<ScenarioJob> {
  let job = checkedJob(await json(base, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input), signal }), input)
  while (job.status === 'queued' || job.status === 'running') {
    progress(job.message)
    await new Promise<void>((resolve, reject) => {
      const abort = () => { clearTimeout(timer); reject(new DOMException('Cancelled', 'AbortError')) }
      const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, 750)
      if (signal.aborted) abort()
      else signal.addEventListener('abort', abort, { once: true })
    })
    job = checkedJob(await json(`${base}/${job.id}`, { signal }), input)
  }
  if (job.status === 'failed') throw new Error(job.error || job.message)
  progress(job.message)
  return job
}
