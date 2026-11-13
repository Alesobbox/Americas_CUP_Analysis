import { readFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { spawn } from 'node:child_process'
import path from 'node:path'
import type { IncomingMessage, ServerResponse } from 'node:http'

function negZeroSafe(n: number, decimals = 2): number {
  const val = Number((-n).toFixed(decimals))
  return Object.is(val, -0) ? 0 : val
}

export function reverseCatalogScenario(s: Record<string, any>): Record<string, any> {
  if (s.schema_version === 'kinematic-race-sim-2') {
    const inp = s.applied_inputs ?? {}
    const teamA = inp.team_a ?? s.team_a
    const teamB = inp.team_b ?? s.team_b

    const negateAccounting = (acct: Record<string, any> | undefined) => {
      if (!acct) return acct
      const out: Record<string, any> = { ...acct }
      for (const k of ['straight_delta_s', 'maneuver_delta_s', 'start_delta_s', 'total_mean_delta_s']) {
        if (typeof acct[k] === 'number') {
          out[k] = negZeroSafe(acct[k], 2)
        }
      }
      if (acct.quantiles_delta_t_s && typeof acct.quantiles_delta_t_s === 'object') {
        const q = acct.quantiles_delta_t_s
        out.quantiles_delta_t_s = {
          p025: typeof q.p975 === 'number' ? negZeroSafe(q.p975, 2) : undefined,
          p05: typeof q.p95 === 'number' ? negZeroSafe(q.p95, 2) : undefined,
          p10: typeof q.p90 === 'number' ? negZeroSafe(q.p90, 2) : undefined,
          p25: typeof q.p75 === 'number' ? negZeroSafe(q.p75, 2) : undefined,
          p50: typeof q.p50 === 'number' ? negZeroSafe(q.p50, 2) : undefined,
          p75: typeof q.p25 === 'number' ? negZeroSafe(q.p25, 2) : undefined,
          p90: typeof q.p10 === 'number' ? negZeroSafe(q.p10, 2) : undefined,
          p95: typeof q.p05 === 'number' ? negZeroSafe(q.p05, 2) : undefined,
          p975: typeof q.p025 === 'number' ? negZeroSafe(q.p025, 2) : undefined,
        }
      }
      return out
    }

    const revTiming = s.timing
      ? {
          ...s.timing,
          mean_time_a_s: s.timing.mean_time_b_s,
          mean_time_b_s: s.timing.mean_time_a_s,
          mean_delta_t_s: negZeroSafe(s.timing.mean_delta_t_s, 2),
          central_80_margin_interval_s: [
            negZeroSafe(s.timing.central_80_margin_interval_s[1], 2),
            negZeroSafe(s.timing.central_80_margin_interval_s[0], 2),
          ] as [number, number],
        }
      : s.timing

    const revProbs = s.probabilities
      ? {
          ...s.probabilities,
          win_a: s.probabilities.win_b,
          win_b: s.probabilities.win_a,
        }
      : s.probabilities

    const revTimeAccounting = negateAccounting(s.time_accounting)
    const revAppliedInputs = {
      ...inp,
      team_a: teamB,
      team_b: teamA,
      ...(inp.seconds_accounting ? { seconds_accounting: negateAccounting(inp.seconds_accounting) } : {}),
    }

    const out: Record<string, any> = {
      ...s,
      applied_inputs: revAppliedInputs,
      timing: revTiming,
      probabilities: revProbs,
      time_accounting: revTimeAccounting,
    }
    if ('team_a' in s) out.team_a = teamB
    if ('team_b' in s) out.team_b = teamA
    return out
  }

  const attr = s.attribution_7_component ?? {}
  const negatedAttr: Record<string, number> = {}
  for (const [k, v] of Object.entries(attr)) {
    negatedAttr[k] = typeof v === 'number' ? negZeroSafe(v, 2) : 0
  }
  if (typeof attr.technical_reliability_advantage === 'number') {
    negatedAttr.technical_reliability_advantage = negZeroSafe(attr.technical_reliability_advantage, 4)
  }

  const jf = s.joint_finisher_conditioning ?? {}
  const reversedJf = {
    ...jf,
    mean_delta_t_s: jf.mean_delta_t_s != null ? negZeroSafe(jf.mean_delta_t_s, 2) : null,
    p10_delta_t_s: jf.p90_delta_t_s != null ? negZeroSafe(jf.p90_delta_t_s, 2) : null,
    p50_delta_t_s: jf.p50_delta_t_s != null ? negZeroSafe(jf.p50_delta_t_s, 2) : null,
    p90_delta_t_s: jf.p10_delta_t_s != null ? negZeroSafe(jf.p10_delta_t_s, 2) : null,
    mean_time_a_s: jf.mean_time_b_s ?? null,
    mean_time_b_s: jf.mean_time_a_s ?? null,
  }

  return {
    ...s,
    scenario_id: `${s.mode}__${s.team_b}__vs__${s.team_a}__tws_${s.tws_kt}`,
    team_a: s.team_b,
    team_b: s.team_a,
    win_probability_a: s.win_probability_b,
    win_probability_b: s.win_probability_a,
    joint_finisher_conditioning: reversedJf,
    status_breakdown: s.status_breakdown
      ? {
          [s.team_b]: s.status_breakdown[s.team_b],
          [s.team_a]: s.status_breakdown[s.team_a],
        }
      : undefined,
    attribution_7_component: negatedAttr,
  }
}

function isAllowedLoopbackHost(hostHeader: string | undefined): boolean {
  if (!hostHeader) return true
  const hostname = hostHeader.split(':')[0].toLowerCase()
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]' || hostname === '::1'
}

function isAllowedOrigin(originHeader: string | undefined): boolean {
  if (!originHeader) return true
  try {
    const parsed = new URL(originHeader)
    const h = parsed.hostname.toLowerCase()
    return h === 'localhost' || h === '127.0.0.1' || h === '[::1]' || h === '::1'
  } catch {
    return false
  }
}

function isAllowedLoopbackPeer(remoteAddress: string | undefined): boolean {
  if (!remoteAddress) return true
  const clean = remoteAddress.replace(/^::ffff:/, '').toLowerCase()
  return clean === '127.0.0.1' || clean === '::1' || clean === 'localhost'
}

let activeInferences = 0
const MAX_CONCURRENT_INFERENCES = 1
const MAX_QUEUED_INFERENCES = 4
const inferenceQueue: Array<() => void> = []

function acquireInferenceSlot(): Promise<() => void> {
  return new Promise((resolve, reject) => {
    if (activeInferences < MAX_CONCURRENT_INFERENCES) {
      activeInferences++
      resolve(() => releaseInferenceSlot())
    } else if (inferenceQueue.length < MAX_QUEUED_INFERENCES) {
      inferenceQueue.push(() => {
        activeInferences++
        resolve(() => releaseInferenceSlot())
      })
    } else {
      reject(new Error('Inference queue depth exceeded (max 4 queued)'))
    }
  })
}

function releaseInferenceSlot() {
  activeInferences = Math.max(0, activeInferences - 1)
  if (inferenceQueue.length > 0 && activeInferences < MAX_CONCURRENT_INFERENCES) {
    const next = inferenceQueue.shift()
    if (next) next()
  }
}

function runPythonSimulatorAsync(
  pythonExec: string,
  workspaceRoot: string,
  payload: Record<string, any>,
  timeoutMs = 15000,
): Promise<{ status: number | null; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const child = spawn(
      pythonExec,
      ['-m', 'pipeline.kinematic_ml.simulator', '--json', JSON.stringify(payload)],
      {
        cwd: workspaceRoot,
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
      },
    )
    let stdout = ''
    let stderr = ''
    let settled = false
    const maxOutputBytes = 1024 * 1024 // 1 MiB limit

    const timer = setTimeout(() => {
      if (!settled) {
        settled = true
        child.kill()
        resolve({ status: 124, stdout, stderr: stderr || 'Simulation timed out' })
      }
    }, timeoutMs)

    child.stdout.on('data', (chunk: Buffer) => {
      if (stdout.length + chunk.length > maxOutputBytes) {
        if (!settled) {
          settled = true
          clearTimeout(timer)
          child.kill()
          resolve({ status: 1, stdout: '', stderr: 'Simulation output exceeded 1 MiB maximum' })
        }
      } else {
        stdout += chunk.toString('utf-8')
      }
    })
    child.stderr.on('data', (chunk: Buffer) => {
      if (stderr.length + chunk.length > maxOutputBytes) {
        if (!settled) {
          settled = true
          clearTimeout(timer)
          child.kill()
          resolve({ status: 1, stdout: '', stderr: 'Simulation output exceeded 1 MiB maximum' })
        }
      } else {
        stderr += chunk.toString('utf-8')
      }
    })
    child.on('error', (err) => {
      if (!settled) {
        settled = true
        clearTimeout(timer)
        resolve({ status: 1, stdout, stderr: err.message })
      }
    })
    child.on('close', (code) => {
      if (!settled) {
        settled = true
        clearTimeout(timer)
        resolve({ status: code, stdout, stderr })
      }
    })
  })
}


const MANDATORY_ARTIFACT_PAIRS: ReadonlyArray<readonly [string, string]> = [
  ['weights_pt', 'weights_pt_sha256'],
  ['weights_npz', 'weights_npz_sha256'],
  ['model_json', 'model_json_sha256'],
  ['empirical_polar_json', 'empirical_polar_sha256'],
  ['spline_polar_json', 'spline_polar_sha256'],
  ['maneuver_model_json', 'maneuver_model_sha256'],
  ['start_model_json', 'start_model_sha256'],
  ['route_templates_json', 'route_templates_sha256'],
  ['residual_blocks_npz', 'residual_blocks_sha256'],
  ['scenarios_catalog', 'scenarios_catalog_sha256'],
]

const AC37_CANONICAL_TEAMS = new Set([
  'ac37:ETNZ',
  'ac37:INEOS',
  'ac37:LUNA_ROSSA',
  'ac37:AMERICAN_MAGIC',
  'ac37:ALINGHI',
  'ac37:ORIENT_EXPRESS',
])

const AC37_DISPLAY_ALIASES: Record<string, string> = {
  ETNZ: 'ac37:ETNZ',
  NZL: 'ac37:ETNZ',
  'EMIRATES TEAM NEW ZEALAND': 'ac37:ETNZ',
  INEOS: 'ac37:INEOS',
  GBR: 'ac37:INEOS',
  GB1: 'ac37:INEOS',
  'INEOS BRITANNIA': 'ac37:INEOS',
  LUNA_ROSSA: 'ac37:LUNA_ROSSA',
  ITA: 'ac37:LUNA_ROSSA',
  'LUNA ROSSA PRADA PIRELLI': 'ac37:LUNA_ROSSA',
  AMERICAN_MAGIC: 'ac37:AMERICAN_MAGIC',
  USA: 'ac37:AMERICAN_MAGIC',
  'NYYC AMERICAN MAGIC': 'ac37:AMERICAN_MAGIC',
  ALINGHI: 'ac37:ALINGHI',
  SUI: 'ac37:ALINGHI',
  'ALINGHI RED BULL RACING': 'ac37:ALINGHI',
  ORIENT_EXPRESS: 'ac37:ORIENT_EXPRESS',
  FRA: 'ac37:ORIENT_EXPRESS',
  'ORIENT EXPRESS RACING TEAM': 'ac37:ORIENT_EXPRESS',
}

const ALLOWED_SIMULATE_TOP_KEYS = new Set([
  'schema_version',
  'model_id',
  'team_a',
  'team_b',
  'tws_kt',
  'twd_deg',
  'course_id',
  'mode',
  'rule_adjustments',
  'course',
  'environment',
  'purpose',
  'n_sims',
  'trial_count',
  'seed',
  'scenario_policy_id',
])

const ALLOWED_SIMULATE_ENV_KEYS = new Set([
  'kind',
  'tws_kt',
  'tws_mps',
  'wind_from_deg',
  'twd_deg',
])

const PURPOSE_DEFAULT_TRIALS: Record<string, number> = {
  preview: 2000,
  standard: 10000,
  evaluation: 20000,
}

function sha256Buffer(buf: Buffer): string {
  return createHash('sha256').update(buf).digest('hex')
}

function isPathContained(baseDir: string, targetPath: string): boolean {
  const rel = path.relative(path.resolve(baseDir), path.resolve(targetPath))
  return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel))
}

function resolveArtifactContained(relPath: string, bundleDir: string, workspaceRoot: string): string {
  if (!relPath || typeof relPath !== 'string' || path.isAbsolute(relPath)) {
    throw new Error(`Invalid non-relative artifact path: ${String(relPath)}`)
  }
  const fromBundle = path.resolve(bundleDir, relPath)
  const fromRoot = path.resolve(workspaceRoot, relPath)
  const resolved = existsSync(fromBundle) ? fromBundle : fromRoot
  if (!isPathContained(workspaceRoot, resolved)) {
    throw new Error(`Artifact path escapes workspace root: ${relPath}`)
  }
  if (!isPathContained(bundleDir, resolved)) {
    throw new Error(`Artifact path escapes candidate bundle directory: ${relPath}`)
  }
  if (!existsSync(resolved)) {
    throw new Error(`Mandatory artifact file does not exist: ${relPath}`)
  }
  return resolved
}

function normalizeDeg360(deg: number): number {
  const mod = ((deg % 360.0) + 360.0) % 360.0
  return Object.is(mod, -0) || mod === 360.0 ? 0.0 : mod
}

function resolveAc37TeamIdentity(rawTeam: string): string {
  const trimmed = rawTeam.trim()
  if (AC37_CANONICAL_TEAMS.has(trimmed)) return trimmed
  const mapped = AC37_DISPLAY_ALIASES[trimmed.toUpperCase()]
  if (mapped && AC37_CANONICAL_TEAMS.has(mapped)) return mapped
  throw new Error(`Unsupported AC37 competitor identity: '${rawTeam}'`)
}

function validateCatalogScenarios(scenarios: any[], expectedModelId: string): void {
  for (let i = 0; i < scenarios.length; i++) {
    const s = scenarios[i]
    if (!s || typeof s !== 'object') {
      throw new Error(`Catalog scenario[${i}] is not an object`)
    }
    if (s.schema_version !== 'kinematic-race-sim-2') continue
    if (s.model_id !== expectedModelId) {
      throw new Error(
        `Catalog scenario[${i}] model_id '${String(s.model_id)}' does not match manifest candidate_id '${expectedModelId}'`,
      )
    }
    if (s.status === 'available') {
      const probs = s.probabilities
      if (
        !probs ||
        typeof probs.win_a !== 'number' ||
        typeof probs.win_b !== 'number' ||
        !Number.isFinite(probs.win_a) ||
        !Number.isFinite(probs.win_b) ||
        probs.win_a < 0 ||
        probs.win_a > 1 ||
        probs.win_b < 0 ||
        probs.win_b > 1
      ) {
        throw new Error(`Catalog scenario[${i}] has invalid probabilities`)
      }
      if ((s.probability_scope || 'completion_assumed_on_water') === 'completion_assumed_on_water') {
        if (probs.no_winner != null || Math.abs(probs.win_a + probs.win_b - 1.0) > 1e-3) {
          throw new Error(`Catalog scenario[${i}] probability sum invariant violated`)
        }
      }
      const timing = s.timing
      if (
        !timing ||
        typeof timing.mean_delta_t_s !== 'number' ||
        !Number.isFinite(timing.mean_delta_t_s) ||
        !Array.isArray(timing.central_80_margin_interval_s) ||
        timing.central_80_margin_interval_s.length !== 2
      ) {
        throw new Error(`Catalog scenario[${i}] has invalid timing fields`)
      }
    }
  }
}

async function loadCombinedCatalog(workspaceRoot: string): Promise<Record<string, any> | null> {
  const ac75Dir = path.join(workspaceRoot, '.forecast', 'ac75_learning')
  const ac75PointerPath = path.join(ac75Dir, 'latest_candidate.json')
  const legacyPointerPath = path.join(workspaceRoot, '.forecast', 'kinematic_ml', 'latest_candidate.json')

  let ac75Catalog: Record<string, any> | null = null
  if (existsSync(ac75PointerPath)) {
    const ptr = JSON.parse(await readFile(ac75PointerPath, 'utf-8'))
    if (!ptr?.manifest_path || typeof ptr.manifest_path !== 'string') {
      throw new Error('Candidate pointer missing manifest_path')
    }
    const manPath = path.resolve(workspaceRoot, ptr.manifest_path)
    if (!isPathContained(ac75Dir, manPath) || !isPathContained(workspaceRoot, manPath)) {
      throw new Error(`Candidate manifest path escapes .forecast/ac75_learning: ${ptr.manifest_path}`)
    }
    if (!existsSync(manPath)) {
      throw new Error(`Candidate manifest file missing: ${ptr.manifest_path}`)
    }
    const manBytes = await readFile(manPath)
    if (!ptr.manifest_sha256 || typeof ptr.manifest_sha256 !== 'string') {
      throw new Error('Candidate pointer missing manifest_sha256')
    }
    const actualManHash = sha256Buffer(manBytes)
    if (actualManHash !== ptr.manifest_sha256) {
      throw new Error(
        `Candidate manifest SHA-256 mismatch: expected ${ptr.manifest_sha256}, got ${actualManHash}`,
      )
    }

    const manifest = JSON.parse(manBytes.toString('utf-8'))
    if (manifest.schema_version !== 'ac75-model-1') {
      throw new Error(`Unsupported manifest schema_version: ${String(manifest.schema_version)}`)
    }
    const candidateId = manifest.candidate_id
    if (!candidateId || typeof candidateId !== 'string') {
      throw new Error('Manifest missing valid candidate_id')
    }
    if (ptr.candidate_id && ptr.candidate_id !== candidateId) {
      throw new Error(`Candidate ID mismatch between pointer (${ptr.candidate_id}) and manifest (${candidateId})`)
    }

    const artifacts = manifest.artifacts
    if (!artifacts || typeof artifacts !== 'object') {
      throw new Error('Manifest missing artifacts mapping')
    }

    const bundleDir = path.dirname(manPath)
    let resolvedCatPath = ''
    for (const [pathKey, hashKey] of MANDATORY_ARTIFACT_PAIRS) {
      const rel = artifacts[pathKey]
      const expectedHash = artifacts[hashKey]
      if (!rel || typeof rel !== 'string') {
        throw new Error(`Manifest missing mandatory artifact path: ${pathKey}`)
      }
      if (!expectedHash || typeof expectedHash !== 'string') {
        throw new Error(`Manifest missing mandatory SHA-256 hash: ${hashKey}`)
      }
      const resolvedArt = resolveArtifactContained(rel, bundleDir, workspaceRoot)
      const actualHash = sha256Buffer(await readFile(resolvedArt))
      if (actualHash !== expectedHash) {
        throw new Error(
          `Artifact SHA-256 mismatch for ${pathKey}: expected ${expectedHash}, got ${actualHash}`,
        )
      }
      if (pathKey === 'scenarios_catalog') {
        resolvedCatPath = resolvedArt
      }
    }

    const parsed = JSON.parse(await readFile(resolvedCatPath, 'utf-8'))
    if (Array.isArray(parsed)) {
      validateCatalogScenarios(parsed, candidateId)
      ac75Catalog = {
        schema_version: 'ac75-catalog-2',
        created_at: manifest.created_at || new Date().toISOString(),
        model_id: candidateId,
        model_status: manifest.status || 'experimental',
        status_notice: manifest.status_notice || '',
        total_scenarios: parsed.length,
        available_teams: manifest.available_teams || [],
        available_modes: [
          { id: 'ac75_learned_v2', label: 'AC75 Learned Simulator (v2)', description: '' },
          { id: 'barcelona_2024_empirical', label: 'Empirical Barcelona 2024 AC75 (v1)', description: '' },
          { id: 'barcelona_2024_empirical_with_ac38_rules', label: 'Empirical + AC38 Rule Adjustments (v1)', description: '' },
        ],
        default_sliders: {},
        courses: [],
        scenarios: parsed,
      }
    } else if (parsed && typeof parsed === 'object') {
      if (parsed.schema_version !== 'ac75-catalog-2') {
        throw new Error(`Unsupported catalog schema_version: ${String(parsed.schema_version)}`)
      }
      if (parsed.model_id !== candidateId) {
        throw new Error(`Catalog model_id '${String(parsed.model_id)}' !== manifest '${candidateId}'`)
      }
      const scenList = Array.isArray(parsed.scenarios) ? parsed.scenarios : []
      validateCatalogScenarios(scenList, candidateId)
      ac75Catalog = parsed
    } else {
      throw new Error('Scenarios catalog must be an object or array')
    }
  }

  let legacyCatalog: Record<string, any> | null = null
  if (existsSync(legacyPointerPath)) {
    const pointer = JSON.parse(await readFile(legacyPointerPath, 'utf-8'))
    const legacyPath = path.resolve(workspaceRoot, pointer.candidate_path)
    if (existsSync(legacyPath)) {
      legacyCatalog = JSON.parse(await readFile(legacyPath, 'utf-8'))
    }
  }

  if (ac75Catalog && legacyCatalog) {
    const combinedScenarios = [...(ac75Catalog.scenarios || []), ...(legacyCatalog.scenarios || [])]
    const combinedTeams = Array.from(
      new Set([...(ac75Catalog.available_teams || []), ...(legacyCatalog.available_teams || [])]),
    )
    return {
      ...ac75Catalog,
      available_teams: combinedTeams,
      total_scenarios: combinedScenarios.length,
      scenarios: combinedScenarios,
    }
  }

  return ac75Catalog || legacyCatalog
}

export function createKinematicMiddleware(workspaceRoot: string) {
  return async (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    const url = req.url || ''
    const pathname = url.split(/[?#]/, 1)[0]

    const reply = (status: number, body: string, contentType = 'application/json; charset=utf-8') => {
      const bytes = Buffer.from(body)
      res.writeHead(status, {
        'Content-Type': contentType,
        'Content-Length': bytes.length,
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
      })
      res.end(bytes)
    }

    if (pathname.startsWith('/api/kinematic/')) {
      if (!isAllowedLoopbackHost(req.headers.host) || !isAllowedLoopbackPeer(req.socket.remoteAddress)) {
        reply(403, JSON.stringify({ status: 'forbidden', error: 'Loopback host and peer required' }))
        return
      }
      if (req.method === 'POST' && !isAllowedOrigin(req.headers.origin)) {
        reply(403, JSON.stringify({ status: 'forbidden', error: 'Same-origin required' }))
        return
      }
    }

    // 1. Get staged candidate catalog
    if (pathname === '/api/kinematic/catalog' && req.method === 'GET') {
      try {
        const combined = await loadCombinedCatalog(workspaceRoot)
        if (!combined) {
          reply(404, JSON.stringify({ error: 'No staged kinematic candidate found' }))
          return
        }
        reply(200, JSON.stringify(combined))
        return
      } catch (err: any) {
        reply(500, JSON.stringify({ error: err.message || 'Failed to read catalog' }))
        return
      }
    }

    // 2. Direct simulation request or scenario query
    if (pathname === '/api/kinematic/simulate' && req.method === 'POST') {
      const chunks: Buffer[] = []
      let totalBytes = 0
      let payloadTooLarge = false

      req.on('data', (chunk: Buffer) => {
        totalBytes += chunk.length
        if (totalBytes > 2048) {
          payloadTooLarge = true
        } else {
          chunks.push(chunk)
        }
      })

      req.on('end', async () => {
        if (payloadTooLarge) {
          reply(413, JSON.stringify({
            status: 'unsupported_request',
            error: 'Scenario request exceeds 2 KiB maximum payload limit.',
          }))
          return
        }

        let body: Record<string, any>
        try {
          const bodyStr = Buffer.concat(chunks).toString('utf-8')
          const parsedBody = JSON.parse(bodyStr || '{}')
          if (!parsedBody || typeof parsedBody !== 'object' || Array.isArray(parsedBody)) {
            reply(400, JSON.stringify({ error: 'Request body must be a JSON object' }))
            return
          }
          body = parsedBody
        } catch (err: any) {
          reply(400, JSON.stringify({ error: err.message || 'Invalid JSON body' }))
          return
        }

        let catalog: Record<string, any> | null
        try {
          catalog = await loadCombinedCatalog(workspaceRoot)
        } catch (catErr: any) {
          reply(500, JSON.stringify({ error: catErr.message || 'Candidate integrity verification failed' }))
          return
        }

        try {
          const unknownTop = Object.keys(body).filter((k) => !ALLOWED_SIMULATE_TOP_KEYS.has(k))
          if (unknownTop.length > 0) {
            reply(422, JSON.stringify({
              status: 'unsupported_request',
              error: `Unknown request fields not allowed: ${unknownTop.join(', ')}`,
            }))
            return
          }

          const {
            team_a,
            team_b,
            tws_kt,
            twd_deg,
            course_id = 'barcelona_lvc_4leg',
            mode = 'ac75_learned_v2',
            rule_adjustments,
            course,
            environment,
          } = body

          if (environment !== undefined && (!environment || typeof environment !== 'object' || Array.isArray(environment))) {
            reply(422, JSON.stringify({ status: 'unsupported_request', error: 'environment must be a JSON object' }))
            return
          }
          if (environment) {
            const unknownEnv = Object.keys(environment).filter((k) => !ALLOWED_SIMULATE_ENV_KEYS.has(k))
            if (unknownEnv.length > 0) {
              reply(422, JSON.stringify({
                status: 'unsupported_request',
                error: `Unknown environment fields not allowed: ${unknownEnv.join(', ')}`,
              }))
              return
            }
            if (environment.kind != null && environment.kind !== 'fixed_wind') {
              reply(422, JSON.stringify({ status: 'unsupported_request', error: `Unsupported environment kind: ${String(environment.kind)}` }))
              return
            }
          }

          if (!team_a || !team_b || typeof team_a !== 'string' || typeof team_b !== 'string' || team_a === team_b) {
            reply(422, JSON.stringify({
              status: 'unsupported_request',
              error: 'Unsupported mode, competitor pair, or wind speed out of range [6, 24] kt.',
            }))
            return
          }

          // Reject contradictory wind speed values
          if (tws_kt != null && environment?.tws_kt != null && Math.abs(Number(tws_kt) - Number(environment.tws_kt)) > 1e-6) {
            reply(422, JSON.stringify({ status: 'unsupported_request', error: 'Contradictory tws_kt values between top-level and environment.' }))
            return
          }
          const ktSource = environment?.tws_kt != null ? Number(environment.tws_kt) : (tws_kt != null ? Number(tws_kt) : NaN)
          const hasMps = environment?.tws_mps != null
          const mpsSource = hasMps ? Number(environment.tws_mps) : NaN
          if (hasMps && !Number.isFinite(mpsSource)) {
            reply(422, JSON.stringify({ status: 'unsupported_request', error: 'Invalid environment.tws_mps value.' }))
            return
          }
          if (!hasMps && !Number.isFinite(ktSource)) {
            reply(422, JSON.stringify({ status: 'unsupported_request', error: 'Missing finite wind speed (tws_kt or tws_mps).' }))
            return
          }
          const effectiveTwsMps = hasMps ? mpsSource : ktSource * (1852.0 / 3600.0)
          const effectiveTwsKt = hasMps ? mpsSource * (3600.0 / 1852.0) : ktSource
          if (hasMps && Number.isFinite(ktSource) && Math.abs(mpsSource - ktSource * (1852.0 / 3600.0)) > 1e-4) {
            reply(422, JSON.stringify({ status: 'unsupported_request', error: 'Contradictory tws_mps and tws_kt values.' }))
            return
          }

          if (!Number.isFinite(effectiveTwsKt) || !Number.isFinite(effectiveTwsMps) || effectiveTwsKt < 6.0 || effectiveTwsKt > 24.0) {
            reply(422, JSON.stringify({
              status: 'unsupported_request',
              error: 'Unsupported mode, competitor pair, or wind speed out of range [6, 24] kt.',
            }))
            return
          }

          // Reject contradictory wind directions across top-level twd_deg, env.twd_deg, env.wind_from_deg
          const rawDirs = [environment?.wind_from_deg, environment?.twd_deg, twd_deg].filter((v) => v != null)
          const normDirs: number[] = []
          for (const dRaw of rawDirs) {
            const dNum = Number(dRaw)
            if (!Number.isFinite(dNum)) {
              reply(422, JSON.stringify({ status: 'unsupported_request', error: 'Wind direction must be finite.' }))
              return
            }
            normDirs.push(normalizeDeg360(dNum))
          }
          for (let i = 1; i < normDirs.length; i++) {
            const angDiff = Math.abs(((normDirs[0] - normDirs[i] + 540.0) % 360.0) - 180.0)
            if (angDiff > 1e-4) {
              reply(422, JSON.stringify({ status: 'unsupported_request', error: 'Contradictory wind direction fields.' }))
              return
            }
          }
          const canonicalTwdDeg = normDirs.length > 0 ? normDirs[0] : 180.0

          const availableModes: string[] = Array.from(
            new Set([
              ...(catalog?.available_modes?.map((m: any) => (typeof m === 'string' ? m : m.id)) || []),
              'ac75_learned_v2',
              'ac75_learned_v1',
              'barcelona_2024_ac75_learned',
              'barcelona_2024_empirical',
              'barcelona_2024_empirical_with_ac38_rules',
            ]),
          )

          if (!availableModes.includes(mode)) {
            reply(422, JSON.stringify({
              status: 'unsupported_request',
              error: 'Unsupported mode, competitor pair, or wind speed out of range [6, 24] kt.',
            }))
            return
          }

          const isV2Mode =
            mode === 'ac75_learned_v2' ||
            mode === 'ac75_learned_v1' ||
            mode === 'barcelona_2024_ac75_learned' ||
            body.schema_version === 'kinematic-race-sim-2' ||
            body.schema_version === 'ac75-scenario-request-1'

          const purpose = body.purpose != null ? String(body.purpose).trim() : 'preview'
          if (!Object.prototype.hasOwnProperty.call(PURPOSE_DEFAULT_TRIALS, purpose)) {
            reply(422, JSON.stringify({
              status: 'unsupported_request',
              error: `Unsupported purpose '${purpose}'; expected preview, standard, or evaluation.`,
            }))
            return
          }

          if (body.trial_count != null && body.n_sims != null && Number(body.trial_count) !== Number(body.n_sims)) {
            reply(422, JSON.stringify({ status: 'unsupported_request', error: 'Contradictory trial_count and n_sims values.' }))
            return
          }
          const rawTrialCount = body.trial_count ?? body.n_sims
          const effectiveTrialCount = rawTrialCount != null ? Number(rawTrialCount) : PURPOSE_DEFAULT_TRIALS[purpose]
          if (!Number.isInteger(effectiveTrialCount) || effectiveTrialCount <= 0 || effectiveTrialCount > 100000) {
            reply(422, JSON.stringify({ status: 'unsupported_request', error: 'trial_count must be a positive integer <= 100000.' }))
            return
          }

          const effectiveSeed = body.seed != null ? Number(body.seed) : (isV2Mode ? 2027 : 42)
          if (!Number.isInteger(effectiveSeed)) {
            reply(422, JSON.stringify({ status: 'unsupported_request', error: 'seed must be an integer.' }))
            return
          }
          const effectivePolicyId =
            body.scenario_policy_id != null ? String(body.scenario_policy_id).trim() : 'training_observed_routes_v1'

          let canonTeamA = team_a
          let canonTeamB = team_b
          if (isV2Mode) {
            if (!catalog?.model_id) {
              reply(404, JSON.stringify({ error: 'No staged AC75 learned candidate available' }))
              return
            }
            if (body.model_id != null && String(body.model_id).trim() !== catalog.model_id) {
              reply(422, JSON.stringify({
                status: 'unsupported_request',
                error: `Requested model_id '${String(body.model_id)}' does not match pinned installed model '${catalog.model_id}'.`,
              }))
              return
            }
            try {
              canonTeamA = resolveAc37TeamIdentity(team_a)
              canonTeamB = resolveAc37TeamIdentity(team_b)
            } catch (idErr: any) {
              reply(422, JSON.stringify({ status: 'unsupported_request', error: idErr.message }))
              return
            }
            if (canonTeamA === canonTeamB) {
              reply(422, JSON.stringify({
                status: 'unsupported_request',
                error: `Competitor teams must resolve to distinct identities: ${canonTeamA} vs ${canonTeamB}.`,
              }))
              return
            }

            const pinnedModelId = String(catalog.model_id)
            const v2Scenarios = (catalog.scenarios || []).filter(
              (s: any) => s.schema_version === 'kinematic-race-sim-2',
            )
            const targetTwsMps = Object.is(effectiveTwsMps, -0) ? 0 : effectiveTwsMps

            const matchesScenario = (s: any, reqTeamA: string, reqTeamB: string): boolean => {
              const inp = s.applied_inputs
              if (!inp || !inp.environment || inp.environment.tws_mps == null) return false
              if (s.model_id !== pinnedModelId) return false
              if (inp.team_a !== reqTeamA || inp.team_b !== reqTeamB) return false
              if ((inp.course_id || 'barcelona_lvc_4leg') !== course_id) return false
              const cachedTws = Number(inp.environment.tws_mps)
              if (cachedTws !== targetTwsMps) return false
              const cachedTwdRaw = inp.environment.twd_deg ?? inp.environment.wind_from_deg ?? 180.0
              if (normalizeDeg360(Number(cachedTwdRaw)) !== canonicalTwdDeg) return false
              if ((inp.purpose || 'preview') !== purpose) return false
              if (Number(inp.trial_count ?? 2000) !== effectiveTrialCount) return false
              if (Number(inp.seed ?? 2027) !== effectiveSeed) return false
              if (inp.scenario_policy_id != null && String(inp.scenario_policy_id) !== effectivePolicyId) return false
              return true
            }

            const directV2 = v2Scenarios.find((s: any) => matchesScenario(s, canonTeamA, canonTeamB))
            if (directV2) {
              reply(200, JSON.stringify(directV2))
              return
            }

            const reverseV2 = v2Scenarios.find((s: any) => matchesScenario(s, canonTeamB, canonTeamA))
            if (reverseV2) {
              reply(200, JSON.stringify(reverseCatalogScenario(reverseV2)))
              return
            }
          }

          const isDefaultRules =
            !rule_adjustments ||
            ((rule_adjustments.battery_power_offset_kt === undefined || rule_adjustments.battery_power_offset_kt === 0) &&
              (rule_adjustments.cyclor_power_boost_kt === undefined ||
                rule_adjustments.cyclor_power_boost_kt === 0 ||
                (mode === 'barcelona_2024_empirical_with_ac38_rules' && rule_adjustments.cyclor_power_boost_kt === 0.25)) &&
              (rule_adjustments.maneuver_loss_multiplier === undefined ||
                rule_adjustments.maneuver_loss_multiplier === 1 ||
                (mode === 'barcelona_2024_empirical_with_ac38_rules' && rule_adjustments.maneuver_loss_multiplier === 0.95)) &&
              (rule_adjustments.foil_span_factor === undefined ||
                rule_adjustments.foil_span_factor === 1 ||
                rule_adjustments.foil_span_limit_factor === undefined ||
                rule_adjustments.foil_span_limit_factor === 1 ||
                (mode === 'barcelona_2024_empirical_with_ac38_rules' && rule_adjustments.foil_span_limit_factor === 1.05)))
          const isDefaultCourse = !course || course.preset_id === 'barcelona_2024_lvc'

          if (catalog && !isV2Mode && isDefaultRules && isDefaultCourse) {
            const directMatch = (catalog.scenarios || []).find(
              (s: any) =>
                s.schema_version !== 'kinematic-race-sim-2' &&
                s.mode === mode &&
                s.team_a === team_a &&
                s.team_b === team_b &&
                Math.abs(s.tws_kt - effectiveTwsKt) < 1e-9,
            )
            if (directMatch) {
              reply(200, JSON.stringify(directMatch))
              return
            }

            const reverseMatch = (catalog.scenarios || []).find(
              (s: any) =>
                s.schema_version !== 'kinematic-race-sim-2' &&
                s.mode === mode &&
                s.team_a === team_b &&
                s.team_b === team_a &&
                Math.abs(s.tws_kt - effectiveTwsKt) < 1e-9,
            )
            if (reverseMatch) {
              reply(200, JSON.stringify(reverseCatalogScenario(reverseMatch)))
              return
            }
          }

          const payload = {
            ...(isV2Mode && catalog?.model_id ? { model_id: catalog.model_id } : {}),
            team_a: canonTeamA,
            team_b: canonTeamB,
            tws_kt: effectiveTwsKt,
            twd_deg: canonicalTwdDeg,
            course_id,
            environment: { tws_mps: effectiveTwsMps, twd_deg: canonicalTwdDeg },
            mode,
            course,
            rule_adjustments,
            purpose,
            trial_count: effectiveTrialCount,
            n_sims: effectiveTrialCount,
            seed: effectiveSeed,
            scenario_policy_id: effectivePolicyId,
          }

          const localPython = path.join(
            workspaceRoot,
            '.venv',
            process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
          )
          const pythonExec = process.env.REGATTA_PYTHON || (existsSync(localPython) ? localPython : 'python')

          let releaseSlot: (() => void) | null = null
          try {
            releaseSlot = await acquireInferenceSlot()
          } catch (qErr: any) {
            reply(503, JSON.stringify({
              status: 'service_unavailable',
              error: qErr.message || 'Inference queue full (max 4 queued)',
            }))
            return
          }

          let proc: { status: number | null; stdout: string; stderr: string }
          try {
            proc = await runPythonSimulatorAsync(pythonExec, workspaceRoot, payload, 15000)
          } finally {
            if (releaseSlot) releaseSlot()
          }

          if (proc.status === 0 && proc.stdout) {
            try {
              const simOutput = JSON.parse(proc.stdout.trim())
              reply(200, JSON.stringify(simOutput))
              return
            } catch {
              reply(500, JSON.stringify({ error: 'Failed to parse simulator JSON output' }))
              return
            }
          }

          const errMsg = proc.stderr || proc.stdout || 'Python simulation process failed'
          let parsedError = errMsg
          try {
            const errObj = JSON.parse(errMsg)
            parsedError = errObj.error || errMsg
          } catch {
            // Ignore non-JSON stderr formatting
          }

          reply(422, JSON.stringify({
            status: 'unsupported_request',
            error: parsedError,
          }))
          return
        } catch (err: any) {
          reply(400, JSON.stringify({ error: err.message || 'Invalid JSON body' }))
          return
        }
      })
      return
    }

    next()
  }
}
