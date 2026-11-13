import type {
  AnyKinematicScenario,
  KinematicCatalog,
  KinematicScenario,
  KinematicScenarioV2,
} from '../types/kinematic'
import { isKinematicScenarioV2 } from '../types/kinematic'

function negZeroSafe(n: number, decimals = 2): number {
  const val = Number((-n).toFixed(decimals))
  return Object.is(val, -0) ? 0 : val
}

function negateV2Accounting(acct: Record<string, any> | undefined): Record<string, any> | undefined {
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

export function reverseKinematicScenario(s: KinematicScenario): KinematicScenario
export function reverseKinematicScenario(s: KinematicScenarioV2): KinematicScenarioV2
export function reverseKinematicScenario(s: AnyKinematicScenario): AnyKinematicScenario
export function reverseKinematicScenario(s: AnyKinematicScenario): AnyKinematicScenario {
  if (isKinematicScenarioV2(s)) {
    const inp = s.applied_inputs
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

    return {
      ...s,
      applied_inputs: {
        ...inp,
        team_a: inp.team_b,
        team_b: inp.team_a,
        ...(inp.seconds_accounting
          ? { seconds_accounting: negateV2Accounting(inp.seconds_accounting) as any }
          : {}),
      },
      timing: revTiming,
      probabilities: revProbs,
      time_accounting: negateV2Accounting(s.time_accounting),
    }
  }

  const attr = s.attribution_7_component ?? {}
  const negatedAttr: Record<string, number> = {}
  for (const [k, v] of Object.entries(attr)) {
    negatedAttr[k] = typeof v === 'number' ? negZeroSafe(v, 2) : 0
  }
  if (typeof attr.technical_reliability_advantage === 'number') {
    negatedAttr.technical_reliability_advantage = negZeroSafe(attr.technical_reliability_advantage, 4)
  }

  const jf = s.joint_finisher_conditioning
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
    team_a: s.team_a && s.team_b ? s.team_b : s.team_a,
    team_b: s.team_a && s.team_b ? s.team_a : s.team_b,
    win_probability_a: s.win_probability_b,
    win_probability_b: s.win_probability_a,
    joint_finisher_conditioning: reversedJf,
    status_breakdown: s.status_breakdown
      ? {
          [s.team_b]: s.status_breakdown[s.team_b],
          [s.team_a]: s.status_breakdown[s.team_a],
        }
      : s.status_breakdown,
    attribution_7_component: negatedAttr,
  }
}

function normalizeCatalogPayload(raw: any): KinematicCatalog {
  if (Array.isArray(raw)) {
    return {
      schema_version: 'ac75-catalog-2',
      created_at: new Date().toISOString(),
      model_status: 'experimental',
      status_notice:
        'Status: Experimental learned simulator. Fitted on authentic 2024 AC75 telemetry archive.',
      total_scenarios: raw.length,
      available_teams: [
        'ac37:ETNZ',
        'ac37:INEOS',
        'ac37:LUNA_ROSSA',
        'ac37:AMERICAN_MAGIC',
        'ac37:ALINGHI',
        'ac37:ORIENT_EXPRESS',
      ],
      available_modes: [
        {
          id: 'ac75_learned_v2',
          label: 'AC75 Learned Simulator (v2)',
          description: 'Causal AC37 telemetry learned simulator',
        },
      ],
      default_sliders: {},
      courses: [],
      scenarios: raw,
    }
  }
  return raw as KinematicCatalog
}

export async function loadKinematicCatalog(signal?: AbortSignal): Promise<KinematicCatalog> {
  try {
    const response = await fetch('/api/kinematic/catalog', {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
      signal,
    })
    if (response.ok) {
      const data = await response.json()
      return normalizeCatalogPayload(data)
    }
  } catch {
    // Fall back to static catalog path
  }

  const fallbackResp = await fetch('/data/kinematic/catalog.json', {
    headers: { Accept: 'application/json' },
    cache: 'no-store',
    signal,
  })
  if (!fallbackResp.ok) {
    throw new Error(`Failed to load kinematic catalog: HTTP ${fallbackResp.status}`)
  }
  const fallbackData = await fallbackResp.json()
  return normalizeCatalogPayload(fallbackData)
}

export async function requestKinematicSimulation(
  team_a: string,
  team_b: string,
  tws_kt: number,
  mode: string,
  rule_adjustments?: Record<string, number>,
  signal?: AbortSignal,
  extra?: { course_id?: string; twd_deg?: number },
): Promise<AnyKinematicScenario> {
  const course_id = extra?.course_id || 'barcelona_lvc_4leg'
  const twd_deg = extra?.twd_deg ?? 180.0
  let response: Response | null = null
  try {
    response = await fetch('/api/kinematic/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        team_a,
        team_b,
        tws_kt,
        twd_deg,
        course_id,
        mode,
        rule_adjustments,
      }),
      signal,
    })
  } catch {
    // Network error: will attempt static fallback below
  }

  if (response) {
    if (response.ok) {
      return await response.json()
    }
    if (response.status === 422 || response.status === 413) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.error || `Unsupported simulation request (HTTP ${response.status})`)
    }
    if (response.status !== 404 && response.status !== 405) {
      throw new Error(`Simulation failed: HTTP ${response.status}`)
    }
  }

  // Fallback for static demo preview mode without middleware backend
  const catalog = await loadKinematicCatalog(signal)
  const isV2Mode =
    mode === 'ac75_learned_v2' || mode === 'ac75_learned_v1' || mode === 'barcelona_2024_ac75_learned'

  if (isV2Mode) {
    const targetMps = tws_kt * (1852.0 / 3600.0)
    const targetTwd = (((twd_deg % 360) + 360) % 360)
    const v2List = catalog.scenarios.filter(isKinematicScenarioV2)
    const isExactV2Match = (s: any, reqTeamA: string, reqTeamB: string) => {
      const sTwdRaw = s.applied_inputs.environment.twd_deg ?? 180
      const sTwd = (((Number(sTwdRaw) % 360) + 360) % 360)
      return (
        s.applied_inputs.team_a === reqTeamA &&
        s.applied_inputs.team_b === reqTeamB &&
        (s.applied_inputs.course_id || 'barcelona_lvc_4leg') === course_id &&
        Math.abs(Number(s.applied_inputs.environment.tws_mps) - targetMps) < 1e-9 &&
        Math.abs(sTwd - targetTwd) < 1e-9 &&
        (s.applied_inputs.purpose || 'preview') === 'preview' &&
        Number(s.applied_inputs.trial_count ?? 2000) === 2000 &&
        Number(s.applied_inputs.seed ?? 2027) === 2027
      )
    }
    const directV2 = v2List.find((s) => isExactV2Match(s, team_a, team_b))
    if (directV2) {
      return directV2
    }
    const reverseV2 = v2List.find((s) => isExactV2Match(s, team_b, team_a))
    if (reverseV2) {
      return reverseKinematicScenario(reverseV2)
    }
  }

  const v1List = catalog.scenarios.filter((s): s is KinematicScenario => !isKinematicScenarioV2(s))
  const directMatch = v1List.find(
    (s) => s.mode === mode && s.team_a === team_a && s.team_b === team_b && Math.abs(s.tws_kt - tws_kt) < 1e-4,
  )
  if (directMatch) {
    return directMatch
  }

  const reverseMatch = v1List.find(
    (s) => s.mode === mode && s.team_a === team_b && s.team_b === team_a && Math.abs(s.tws_kt - tws_kt) < 1e-4,
  )
  if (reverseMatch) {
    return reverseKinematicScenario(reverseMatch)
  }

  throw new Error(`No pre-computed scenario found for ${team_a} vs ${team_b} at ${tws_kt} kt in static preview mode.`)
}
