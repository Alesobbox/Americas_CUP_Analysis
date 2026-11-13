import { createHash } from 'node:crypto'
import { mkdtemp, mkdir, rename, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import type { AddressInfo } from 'node:net'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createServer, preview } from 'vite'
import type { ViteDevServer } from 'vite'
import { forecastArtifactsPlugin } from '../../scripts/forecastArtifacts'

describe('forecast artifact routing during a running development session', () => {
  let server: ViteDevServer | undefined
  let directory: string
  let predictions: string
  let base: string

  beforeEach(async () => {
    directory = await mkdtemp(path.join(tmpdir(), 'regatta-forecast-routing-'))
    predictions = path.join(directory, 'public', 'data', 'predictions')
    await mkdir(predictions, { recursive: true })
    await writeFile(path.join(directory, 'index.html'), '<!doctype html><title>Application fallback</title>')
    server = await createServer({
      configFile: false,
      root: directory,
      publicDir: path.join(directory, 'public'),
      plugins: [forecastArtifactsPlugin()],
      server: {
        host: '127.0.0.1', port: 0, strictPort: true, hmr: false,
        watch: { ignored: ['**/public/data/predictions', '**/public/data/predictions/**', '**/public/data/environment', '**/public/data/environment/**'] },
      },
      optimizeDeps: { noDiscovery: true, include: [] },
      logLevel: 'silent',
    })
    await server.listen()
    const address = server.httpServer!.address() as AddressInfo
    base = `http://127.0.0.1:${address.port}`
  })

  afterEach(async () => {
    await server?.close()
    server = undefined
    if (directory) await rm(directory, { recursive: true, force: true })
  })

  async function publish(relative: string, body: string) {
    const target = path.join(predictions, relative)
    await mkdir(path.dirname(target), { recursive: true })
    await writeFile(target, body)
    return `/data/predictions/${relative}`
  }

  async function expectJson(url: string, body: string) {
    const response = await fetch(`${base}${url}`)
    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toMatch(/^application\/json\b/)
    expect(await response.text()).toBe(body)
  }

  it('serves an index and immutable nested objects published after startup', async () => {
    const objects = [
      ['races', 'new_race_', { race_id: 'new_race', available: false }],
      ['cup', '', { schema_version: 'cup-1', status: 'unavailable' }],
      ['manifests', '', { sources: ['audited-source'] }],
    ] as const
    const references: string[] = []
    for (const [folder, prefix, value] of objects) {
      const canonical = JSON.stringify(value)
      const hash = createHash('sha256').update(canonical).digest('hex')
      const relative = `${folder}/${prefix}${hash}.json`
      const url = await publish(relative, `${canonical}\n`)
      references.push(relative)
      await expectJson(url, `${canonical}\n`)
      const downloaded = await (await fetch(`${base}${url}`)).text()
      expect(createHash('sha256').update(downloaded.replace(/\n$/, '')).digest('hex')).toBe(hash)
    }
    const index = `${JSON.stringify({ races: [{ path: references[0] }], cup_path: references[1], source_manifest_path: references[2] })}\n`
    await expectJson(await publish('index.json', index), index)
    const mdUrl = await publish('ac38_report.md', '# AC38 Report\n')
    const mdResp = await fetch(`${base}${mdUrl}`)
    expect(mdResp.status).toBe(200)
    expect(mdResp.headers.get('content-type')).toMatch(/^text\/markdown\b/)
    expect(await mdResp.text()).toBe('# AC38 Report\n')
  })

  it('reads an atomically replaced index and its newly published object without restarting', async () => {
    const oldIndex = '{"generation":1}\n'
    await expectJson(await publish('index.json', oldIndex), oldIndex)
    const artifact = '{"generation":2,"status":"unavailable"}\n'
    const hash = createHash('sha256').update(artifact.trimEnd()).digest('hex')
    const relative = `races/new_${hash}.json`
    await publish(relative, artifact)
    const newIndex = `${JSON.stringify({ generation: 2, path: relative })}\n`
    const replacement = path.join(predictions, 'index.publication.tmp')
    await writeFile(replacement, newIndex)
    await rename(replacement, path.join(predictions, 'index.json'))
    await expectJson('/data/predictions/index.json', newIndex)
    await expectJson(`/data/predictions/${relative}`, artifact)
  })

  it('handles HEAD and query strings while returning JSON errors for missing objects', async () => {
    const body = '{"state":"published"}\n'
    const url = await publish('index.json', body)
    const head = await fetch(`${base}${url}`, { method: 'HEAD' })
    expect(head.status).toBe(200)
    expect(head.headers.get('content-type')).toMatch(/^application\/json\b/)
    expect(await head.text()).toBe('')
    await expectJson(`${url}?publication=latest`, body)
    const missing = await fetch(`${base}/data/predictions/races/never-published.json`)
    expect(missing.status).toBe(404)
    expect(missing.headers.get('content-type')).toMatch(/^application\/json\b/)
    expect(await missing.text()).not.toContain('Application fallback')
  })

  it('also serves historical environment JSON published after startup', async () => {
    const environment = path.join(directory, 'public', 'data', 'environment')
    await mkdir(environment, { recursive: true })
    const body = '{"schema_version":"environment-1","race_id":"new_race"}\n'
    await writeFile(path.join(environment, 'new_race.json'), body)
    await expectJson('/data/environment/new_race.json', body)
    const missing = await fetch(`${base}/data/environment/absent.json`)
    expect(missing.status).toBe(404)
    expect(missing.headers.get('content-type')).toMatch(/^application\/json\b/)
  })

  it('does not expose files outside the forecast directory through encoded traversal', async () => {
    const secret = '{"outside":"must not be served"}\n'
    await writeFile(path.join(directory, 'public', 'data', 'outside.json'), secret)
    for (const suffix of ['%2e%2e%2foutside.json', '..%5coutside.json', '%2e%2e%2f%2e%2e%2findex.html']) {
      const response = await fetch(`${base}/data/predictions/${suffix}`)
      expect(response.status).toBeGreaterThanOrEqual(400)
      expect(await response.text()).not.toBe(secret)
    }
  })

  it('serves newly generated scenarios and the local API in a production preview without rebuilding', async () => {
    await mkdir(path.join(directory, 'dist'), { recursive: true })
    await writeFile(path.join(directory, 'dist/index.html'), '<!doctype html><title>Production application</title>')
    const production = await preview({ configFile: false, root: directory, publicDir: path.join(directory, 'public'), plugins: [forecastArtifactsPlugin()], build: { outDir: 'dist' }, preview: { host: '127.0.0.1', port: 0, strictPort: true }, logLevel: 'silent' })
    try {
      const address = production.httpServer.address() as AddressInfo
      const productionBase = `http://127.0.0.1:${address.port}`
      const body = '{"exact_conditions":{"tws_kt":13,"direction_offset_deg":0}}\n'
      const hash = createHash('sha256').update(body.trim()).digest('hex')
      const url = await publish(`scenarios/${hash}.json`, body)
      const response = await fetch(productionBase + url)
      expect(response.headers.get('content-type')).toMatch(/^application\/json\b/)
      expect(await response.text()).toBe(body)
      const service = await fetch(productionBase + '/api/forecast-scenarios')
      expect(service.status).toBe(200)
      expect(await service.json()).toMatchObject({ direction_offset_deg: 0, available: false })
    } finally { await new Promise<void>((resolve, reject) => production.httpServer.close((error) => error ? reject(error) : resolve())) }
  })
})
