import { createServer } from 'node:http'
import type { Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import path from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createScenarioMiddleware, validateScenarioInput } from '../../scripts/forecastScenarios'

const input = { race_id: 'naples_pr1', tws_kt: 13, direction_offset_deg: 0 }
const scenarioPath = `scenarios/${'a'.repeat(64)}.json`

describe('local exact-forecast preparation', () => {
  let directory: string, server: Server, base: string
  const runner = vi.fn()
  beforeEach(async () => {
    runner.mockReset()
    directory = await mkdtemp(path.join(tmpdir(), 'regatta-scenario-api-'))
    await mkdir(path.join(directory, 'public/data/predictions/scenarios'), { recursive: true })
    await mkdir(path.join(directory, '.forecast/dataset'), { recursive: true })
    await writeFile(path.join(directory, '.forecast/dataset/index.json'), '{}')
    await writeFile(path.join(directory, 'public/data/predictions/index.json'), JSON.stringify({ races: [{ race_id: input.race_id, path: 'races/unchanged.json', presets: [] }, { race_id: 'another_race', path: 'races/also_unchanged.json' }], cup_path: 'cup/unchanged.json' }))
    const middleware = createScenarioMiddleware(directory, runner)
    server = createServer((request, response) => middleware(request, response, () => { response.writeHead(404); response.end() }))
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
    base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`
  })
  afterEach(async () => {
    await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()))
    await rm(directory, { recursive: true, force: true })
  })
  const post = (body: unknown, headers = {}) => fetch(base + '/api/forecast-scenarios', { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) })

  it('reports local readiness without starting a model or reading telemetry', async () => {
    const response = await fetch(base + '/api/forecast-scenarios')
    expect(await response.json()).toMatchObject({ available: true, direction_offset_deg: 0 })
    expect(runner).not.toHaveBeenCalled()
  })

  it('rejects unsupported directions, unsafe race IDs, extra keys and invalid numbers', async () => {
    for (const value of [{ ...input, direction_offset_deg: 17 }, { ...input, race_id: '../secret' }, { ...input, tws_kt: -1 }, { ...input, tws_kt: 81 }, { ...input, code: 'do not execute' }, { ...input, tws_kt: '13' }]) {
      expect((await post(value)).status).toBe(422)
    }
    expect(runner).not.toHaveBeenCalled()
    expect(() => validateScenarioInput({ ...input, tws_kt: Number.NaN })).toThrow('between 0 and 80')
    expect(() => validateScenarioInput({ ...input, direction_offset_deg: 17 })).toThrow('has not passed validation')
  })

  it('confines generation to the same-origin local dashboard and a published race', async () => {
    expect((await post(input, { Origin: 'https://another.example' })).status).toBe(403)
    expect((await post({ ...input, race_id: 'unknown' })).status).toBe(404)
    expect((await fetch(base + '/api/forecast-scenarios', { method: 'POST', body: '{}' })).status).toBe(415)
    expect((await post({ ...input, extra: 'x'.repeat(3000) })).status).toBe(413)
    expect(runner).not.toHaveBeenCalled()
  })

  it('reuses an exact published artifact and preserves the index and baseline references', async () => {
    const indexPath = path.join(directory, 'public/data/predictions/index.json')
    const index = JSON.parse(await readFile(indexPath, 'utf8'))
    index.races[0].presets.push({ tws_kt: 13, direction_offset_deg: 0, path: scenarioPath, status: 'estimated' })
    const before = JSON.stringify(index)
    await writeFile(indexPath, before)
    await writeFile(path.join(directory, 'public/data/predictions', scenarioPath), '{}')
    const response = await post(input)
    expect(response.status).toBe(200)
    const job = await response.json()
    expect(job).toMatchObject({ status: 'complete', input, path: scenarioPath })
    expect(await readFile(indexPath, 'utf8')).toBe(before)
    expect(runner).not.toHaveBeenCalled()
  })

  it('deduplicates the same running scenario, rejects competing writes, and reports completion', async () => {
    let complete!: (value: { path: string; status: string }) => void
    runner.mockImplementation((_input, progress) => { progress('Checking exact conditions...'); return new Promise((resolve) => { complete = resolve }) })
    const first = await (await post(input)).json()
    const duplicate = await (await post(input)).json()
    expect(duplicate.id).toBe(first.id)
    expect((await post({ ...input, tws_kt: 14 })).status).toBe(409)
    expect(runner).toHaveBeenCalledTimes(1)
    complete({ path: scenarioPath, status: 'estimated' })
    await vi.waitFor(async () => {
      const job = await (await fetch(base + '/api/forecast-scenarios/' + first.id)).json()
      expect(job).toMatchObject({ status: 'complete', path: scenarioPath, input })
    })
  })

  it('reports failed jobs with a retryable state and never substitutes another scenario', async () => {
    runner.mockRejectedValue(new Error('Forecast preparation failed. Please retry.'))
    const first = await (await post(input)).json()
    await vi.waitFor(async () => {
      const job = await (await fetch(base + '/api/forecast-scenarios/' + first.id)).json()
      expect(job).toMatchObject({ status: 'failed', input, error: 'Forecast preparation failed. Please retry.' })
      expect(job.path).toBeUndefined()
    })
    expect((await fetch(base + '/api/forecast-scenarios/not-a-job')).status).toBe(404)
  })
  it('serializes publication across two servers sharing the same workspace', async () => {
    let finish!: (value: { path: string; status: string }) => void
    runner.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
    const competingRunner = vi.fn().mockResolvedValue({ path: scenarioPath, status: 'estimated' })
    const middleware = createScenarioMiddleware(directory, competingRunner)
    const other = createServer((request, response) => middleware(request, response, () => { response.writeHead(404); response.end() }))
    await new Promise<void>((resolve) => other.listen(0, '127.0.0.1', resolve))
    const otherBase = `http://127.0.0.1:${(other.address() as AddressInfo).port}`
    try {
      expect((await post(input)).status).toBe(202)
      const conflict = await fetch(otherBase + '/api/forecast-scenarios', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...input, tws_kt: 14 }) })
      expect(conflict.status).toBe(409)
      expect(competingRunner).not.toHaveBeenCalled()
      finish({ path: scenarioPath, status: 'estimated' })
      await vi.waitFor(async () => { await expect(readFile(path.join(directory, '.forecast/scenario-generation.lock'))).rejects.toThrow() })
    } finally { await new Promise<void>((resolve) => other.close(() => resolve())) }
  })

  it('does not steal a dead-server lock while its publisher child is still alive', async () => {
    const exited = spawn(process.execPath, ['-e', 'process.exit(0)'], { windowsHide: true })
    await once(exited, 'close')
    const lock = path.join(directory, '.forecast/scenario-generation.lock')
    await writeFile(lock, JSON.stringify({ version: 1, pid: exited.pid, child_pid: process.pid, token: 'orphan-publisher' }))
    expect((await post(input)).status).toBe(409)
    expect(runner).not.toHaveBeenCalled()
    expect(JSON.parse(await readFile(lock, 'utf8')).child_pid).toBe(process.pid)
  })

  it('recovers a lock only after its server and publisher child have both exited', async () => {
    const exited = spawn(process.execPath, ['-e', 'process.exit(0)'], { windowsHide: true })
    await once(exited, 'close')
    await writeFile(path.join(directory, '.forecast/scenario-generation.lock'), JSON.stringify({ version: 1, pid: exited.pid, child_pid: exited.pid, token: 'finished-publisher' }))
    runner.mockResolvedValue({ path: scenarioPath, status: 'estimated' })
    const response = await post(input)
    expect(response.status).toBe(202)
    expect(runner).toHaveBeenCalledTimes(1)
  })

})
