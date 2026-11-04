import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdir, open, readFile, stat, unlink } from 'node:fs/promises'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { randomUUID } from 'node:crypto'
import path from 'node:path'

export interface ScenarioInput { race_id: string; tws_kt: number; direction_offset_deg: number }
export interface ScenarioJob {
  id: string; input: ScenarioInput; status: 'queued' | 'running' | 'complete' | 'failed'
  message: string; path?: string; reason?: string; error?: string
}
interface ScenarioResult { path: string; status: string; reason?: string }
type Runner = (input: ScenarioInput, progress: (message: string) => void, childReady?: (pid: number) => Promise<void>) => Promise<ScenarioResult>
const endpoint = '/api/forecast-scenarios'
const artifactPath = /^scenarios\/[a-f0-9]{64}\.json$/
class ScenarioBusyError extends Error {}

interface WorkspaceLock { childReady: (pid: number) => Promise<void>; release: () => Promise<void> }
const alive = (pid: number): boolean => {
  try { process.kill(pid, 0); return true } catch (error) { return (error as NodeJS.ErrnoException).code !== 'ESRCH' }
}

async function acquireWorkspaceLock(root: string): Promise<WorkspaceLock> {
  const directory = path.join(root, '.forecast')
  await mkdir(directory, { recursive: true })
  const filename = path.join(directory, 'scenario-generation.lock')
  const record = { version: 1, pid: process.pid, token: randomUUID(), started_at_ms: Date.now(), child_pid: undefined as number | undefined }
  const create = async () => {
    const handle = await open(filename, 'wx')
    try { await handle.writeFile(JSON.stringify(record), 'utf8') } finally { await handle.close() }
  }
  try { await create() } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error
    let old: string
    try { old = await readFile(filename, 'utf8') } catch { throw new ScenarioBusyError() }
    let owner: { version?: number; pid?: number; child_pid?: number } = {}
    try { owner = JSON.parse(old) } catch { /* A crashed initial write cannot have launched a publisher. */ }
    const validPid = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value) && value > 0
    // A child can outlive its server. Both must have exited before recovery.
    // Version 1 children cannot publish until their PID is written and acknowledged.
    const abandoned = validPid(owner.pid)
      ? !alive(owner.pid) && (validPid(owner.child_pid) ? !alive(owner.child_pid) : owner.version === 1)
      : Date.now() - (await stat(filename)).mtimeMs > 10 * 60 * 1000
    if (!abandoned || await readFile(filename, 'utf8') !== old) throw new ScenarioBusyError()
    try { await unlink(filename); await create() } catch { throw new ScenarioBusyError() }
  }
  return {
    childReady: async (pid) => {
      const handle = await open(filename, 'r+')
      try {
        const current = JSON.parse(await handle.readFile('utf8'))
        if (current.token !== record.token) throw new Error('Forecast preparation ownership changed. Please retry.')
        record.child_pid = pid
        const bytes = Buffer.from(JSON.stringify(record))
        await handle.truncate(0)
        await handle.write(bytes, 0, bytes.length, 0)
        await handle.sync()
      } finally { await handle.close() }
    },
    release: async () => {
      try {
        const current = JSON.parse(await readFile(filename, 'utf8'))
        if (current.token === record.token) await unlink(filename)
      } catch { /* Never remove another job's lock. */ }
    },
  }
}

export function validateScenarioInput(value: unknown): ScenarioInput {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Enter a race and exact wind conditions.')
  const input = value as Record<string, unknown>
  if (Object.keys(input).some((key) => !['race_id', 'tws_kt', 'direction_offset_deg'].includes(key))) throw new Error('Unexpected forecast input.')
  if (typeof input.race_id !== 'string' || !/^[a-zA-Z0-9_-]{1,128}$/.test(input.race_id)) throw new Error('Choose a valid race.')
  if (typeof input.tws_kt !== 'number' || !Number.isFinite(input.tws_kt) || input.tws_kt < 0 || input.tws_kt > 80) throw new Error('Wind speed must be between 0 and 80 knots.')
  if (typeof input.direction_offset_deg !== 'number' || !Number.isFinite(input.direction_offset_deg) || Math.abs(input.direction_offset_deg) > 180) throw new Error('Direction offset must be between −180° and +180°.')
  if (input.direction_offset_deg !== 0) throw new Error('The current forecast model supports a fixed course direction (0° offset). A direction response has not passed validation.')
  return input as unknown as ScenarioInput
}

const scenarioBootstrap = [
  'import os, runpy, sys, threading',
  "if sys.stdin.readline().strip() != 'start': sys.exit(125)",
  'watchdog = threading.Timer(600, lambda: os._exit(124))',
  'watchdog.daemon = True',
  'watchdog.start()',
  "sys.argv = ['pipeline.prediction', *sys.argv[1:]]",
  "runpy.run_module('pipeline.prediction', run_name='__main__')",
].join('\n')

function pythonRunner(root: string): Runner {
  return (input, progress, childReady) => new Promise((resolve, reject) => {
    const local = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
    const python = process.env.REGATTA_PYTHON || (existsSync(local) ? local : 'python')
    // Constant bootstrap, separate validated argv, no shell. The publisher waits
    // until the shared lock records its PID; EOF before that means no publication.
    const child = spawn(python, ['-u', '-c', scenarioBootstrap, 'build', '--race', input.race_id,
      '--tws-knots', String(input.tws_kt), '--direction-offset-deg', String(input.direction_offset_deg)],
    { cwd: root, shell: false, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] })
    let output = '', error = '', timedOut = false
    const timeout = setTimeout(() => { timedOut = true; child.kill() }, 10 * 60 * 1000)
    child.stdin.on('error', () => { /* An exited child can close the handshake pipe. */ })
    child.once('spawn', () => {
      if (!child.pid || !childReady) { child.kill(); reject(new Error('Forecast preparation ownership is unavailable. Please retry.')); return }
      void childReady(child.pid).then(() => child.stdin.end('start\n'), () => {
        child.kill(); reject(new Error('The forecast workspace could not be reserved. Please retry.'))
      })
    })
    child.stdout.on('data', (chunk) => { output = (output + String(chunk)).slice(-16384) })
    child.stderr.on('data', (chunk) => {
      const text = String(chunk); error = (error + text).slice(-4000)
      if (text.includes('Verifying dataset')) progress('Checking the recorded race data and preparing the exact scenario…')
    })
    child.once('error', () => { clearTimeout(timeout); reject(new Error('The local forecasting service could not start. Retry, or use a published scenario.')) })
    child.once('close', (code) => {
      clearTimeout(timeout)
      if (code !== 0) {
        const reason = timedOut || code === 124 ? 'Forecast preparation took too long. Retry, or use a published scenario.'
          : /Raw source changed|cache content hash|Unsealed forecasting/.test(error) ? 'The local forecasting data needs a refresh before this scenario can be prepared.'
          : 'This forecast could not be prepared. Retry, or use the recorded start conditions.'
        reject(new Error(reason)); return
      }
      try {
        const result = JSON.parse(output.trim().split(/\r?\n/).at(-1) ?? '{}') as ScenarioResult
        if (!artifactPath.test(result.path) || !['available', 'estimated', 'unavailable'].includes(result.status)) throw new Error()
        resolve(result)
      } catch { reject(new Error('The forecasting service returned an incomplete result. Please retry.')) }
    })
  })
}

export function createScenarioMiddleware(root: string, runner: Runner = pythonRunner(root)) {
  const jobs = new Map<string, ScenarioJob>()
  let running: ScenarioJob | null = null
  const indexPath = path.join(root, 'public/data/predictions/index.json')
  const reply = (response: ServerResponse, status: number, value: unknown) => {
    const body = JSON.stringify(value) + '\n'
    response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Content-Length': Buffer.byteLength(body) })
    response.end(body)
  }
  return (request: IncomingMessage, response: ServerResponse, next: () => void) => {
    const pathname = (request.url ?? '').split(/[?#]/, 1)[0]
    if (pathname !== endpoint && !pathname.startsWith(endpoint + '/')) { next(); return }
    const host = request.headers.host ?? ''
    if (!/^(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$/.test(host) || (request.headers.origin && request.headers.origin !== `http://${host}` && request.headers.origin !== `https://${host}`)) {
      reply(response, 403, { error: 'Forecast preparation is available only from this local dashboard.' }); return
    }
    if (request.method === 'GET') {
      if (pathname === endpoint) {
        const ready = existsSync(indexPath) && existsSync(path.join(root, '.forecast/dataset/index.json'))
        reply(response, 200, { available: ready, direction_offset_deg: 0, message: ready ? 'Exact wind-speed scenarios can be prepared here. The current model uses a fixed course direction.' : 'Forecast preparation is unavailable in this installation. Published scenarios remain available.' })
        return
      }
      const id = pathname.slice(endpoint.length + 1)
      const job = jobs.get(id)
      reply(response, job ? 200 : 404, job ?? { error: 'This preparation session is no longer available. Please retry.' }); return
    }
    if (request.method !== 'POST' || pathname !== endpoint) { reply(response, 405, { error: 'Method not allowed.' }); return }
    if (!request.headers['content-type']?.startsWith('application/json')) { reply(response, 415, { error: 'Forecast inputs must be JSON.' }); return }
    void (async () => {
      let text = ''
      for await (const chunk of request) {
        text += String(chunk)
        if (Buffer.byteLength(text) > 2048) { reply(response, 413, { error: 'Forecast input is too large.' }); return }
      }
      let input: ScenarioInput
      try { input = validateScenarioInput(JSON.parse(text)) } catch (error) { reply(response, 422, { error: error instanceof Error ? error.message : 'Invalid forecast inputs.' }); return }
      let index: { races: Array<{ race_id: string; presets?: Array<{ tws_kt: number; direction_offset_deg: number; path?: string; status?: string; reason?: string }> }> }
      try { index = JSON.parse(await readFile(indexPath, 'utf8')) } catch { reply(response, 503, { error: 'Published forecasting data is unavailable. Please retry.' }); return }
      const race = index.races?.find((entry) => entry.race_id === input.race_id)
      if (!race) { reply(response, 404, { error: 'No forecast field is published for this race.' }); return }
      const same = (candidate: ScenarioInput) => candidate.race_id === input.race_id && candidate.tws_kt === input.tws_kt && candidate.direction_offset_deg === input.direction_offset_deg
      if (running) {
        if (same(running.input)) reply(response, 202, running)
        else reply(response, 409, { error: 'Another exact forecast is being prepared. Please retry when it finishes.' })
        return
      }
      const published = race.presets?.find((preset) => preset.tws_kt === input.tws_kt && preset.direction_offset_deg === input.direction_offset_deg && preset.path && artifactPath.test(preset.path) && existsSync(path.join(root, 'public/data/predictions', preset.path)))
      let workspaceLock: WorkspaceLock | undefined
      if (!published) {
        try { workspaceLock = await acquireWorkspaceLock(root) } catch (error) {
          reply(response, error instanceof ScenarioBusyError ? 409 : 503, { error: error instanceof ScenarioBusyError ? 'Another exact forecast is being prepared in this workspace. Please retry when it finishes.' : 'The local forecast workspace could not be opened. Please retry.' }); return
        }
      }
      const job: ScenarioJob = { id: randomUUID(), input, status: published ? 'complete' : 'running', message: published ? published.status === 'unavailable' ? 'These exact conditions do not have enough earlier race support.' : 'The exact forecast is ready.' : 'Preparing the forecast for these exact conditions…', ...(published ? { path: published.path, reason: published.reason } : {}) }
      jobs.set(job.id, job)
      if (jobs.size > 24) for (const [id, old] of jobs) { if (old !== running && old.status !== 'running') { jobs.delete(id); break } }
      reply(response, published ? 200 : 202, job)
      if (published) return
      running = job
      void Promise.resolve().then(() => runner(input, (message) => { job.message = message }, workspaceLock?.childReady)).then((result) => {
        job.status = 'complete'; job.path = result.path; job.reason = result.reason
        job.message = result.status === 'unavailable' ? 'These exact conditions do not have enough earlier race support.' : 'The exact forecast is ready.'
      }, (error: unknown) => {
        job.status = 'failed'; job.error = error instanceof Error ? error.message : 'Forecast preparation failed. Please retry.'; job.message = job.error
      }).finally(async () => { await workspaceLock?.release(); if (running === job) running = null })
    })().catch(() => { if (!response.headersSent) reply(response, 500, { error: 'Forecast preparation failed. Please retry.' }) })
  }
}
