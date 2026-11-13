import type { Ac38Forecast, Ac38RuleBound } from '../types/prediction'

const SHA256_RE = /^[a-f0-9]{64}$/
const PRIVATE_POSTERIOR_KEYS = new Set([
  'active_conditionals',
  'posterior_grid',
  'grid_axes',
  'weights_normalized',
  'z_grid',
  'h_grid',
])

function assertNoPrivatePosteriorKeys(value: unknown): void {
  const stack: unknown[] = [value]
  while (stack.length > 0) {
    const node = stack.pop()
    if (Array.isArray(node)) {
      for (const item of node) stack.push(item)
    } else if (node && typeof node === 'object') {
      for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
        if (PRIVATE_POSTERIOR_KEYS.has(k)) {
          fail(`private posterior field "${k}" leaked into public artifact`)
        }
        stack.push(v)
      }
    }
  }
}

function fail(message: string): never {
  throw new Error(`Invalid AC38 forecast: ${message}`)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function requireBool(cond: boolean, message: string): void {
  if (!cond) fail(message)
}

function isFiniteNum(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function isProb(value: unknown): value is number {
  return isFiniteNum(value) && value >= 0 && value <= 1
}

function validateSha(value: unknown, label: string): void {
  requireBool(typeof value === 'string' && SHA256_RE.test(value), `${label} must be 64-char sha256`)
}

function validateHeader(header: unknown): Record<string, unknown> {
  if (!isRecord(header)) fail('missing header')
  requireBool(header.schema_version === 'ac38-forecast-1', 'unsupported schema_version')
  requireBool(header.experimental === true, 'experimental flag must be true')
  requireBool(
    header.status === 'experimental_conditional' || header.status === 'experimental_rule_bounds',
    'invalid header status',
  )
  requireBool(typeof header.issuance_cutoff_utc === 'string' && Number.isFinite(Date.parse(header.issuance_cutoff_utc)), 'invalid issuance_cutoff_utc')
  requireBool(typeof header.conditioning === 'string' && header.conditioning.trim().length > 0, 'missing conditioning')
  validateSha(header.model_ref, 'model_ref')
  validateSha(header.transfer_posterior_sha256, 'transfer_posterior_sha256')
  validateSha(header.eligibility_ledger_sha256, 'eligibility_ledger_sha256')
  validateSha(header.inventory_sha256, 'inventory_sha256')
  validateSha(header.backtest_report_sha256, 'backtest_report_sha256')
  requireBool(Number.isInteger(header.trials) && (header.trials as number) > 0, 'invalid trial count')
  requireBool(Number.isInteger(header.seed), 'invalid seed')
  requireBool(header.scale_kappa === 1, 'scale_kappa must be 1')
  requireBool(
    header.selected_transfer_candidate === 'results_only' || header.selected_transfer_candidate === 'results_plus_telemetry',
    'invalid selected_transfer_candidate',
  )
  requireBool(typeof header.telemetry_retained === 'boolean', 'telemetry_retained must be a boolean')
  return header
}

function validatePairwiseMatrix(matrix: unknown, teamIds: string[], label: string): void {
  if (!isRecord(matrix)) fail(`missing pairwise matrix ${label}`)
  for (const ti of teamIds) {
    const row = matrix[ti]
    if (!isRecord(row)) fail(`missing row ${ti} in ${label}`)
    requireBool(row[ti] === null, `${label} diagonal for ${ti} must be null`)
    for (const tj of teamIds) {
      if (ti === tj) continue
      const p = row[tj]
      const q = (matrix[tj] as Record<string, unknown> | undefined)?.[ti]
      requireBool(isProb(p) && isProb(q), `${label} off-diagonal probability invalid for ${ti} vs ${tj}`)
      requireBool(Math.abs((p as number) + (q as number) - 1) <= 1e-4, `${label} complementarity violated for ${ti} vs ${tj}`)
    }
  }
}

function validateBoundsMap(bounds: unknown, teamIds: string[], label: string): Record<string, Ac38RuleBound> {
  if (!isRecord(bounds)) fail(`missing bounds map ${label}`)
  let lowerSum = 0
  let upperSum = 0
  for (const id of teamIds) {
    const b = bounds[id]
    if (!isRecord(b) || !isProb(b.lower) || !isProb(b.upper) || b.lower > b.upper + 1e-12) {
      fail(`invalid bounds for ${id} in ${label}`)
    }
    lowerSum += b.lower
    upperSum += b.upper
  }
  requireBool(lowerSum <= 1 + 1e-3 && upperSum >= 1 - 1e-3, `incoherent trophy bounds sum in ${label}`)
  return bounds as Record<string, Ac38RuleBound>
}

function validateRulesSection(rules: unknown, header: Record<string, unknown>): number {
  if (!isRecord(rules)) fail('missing rules')
  const trials = header.trials as number
  const resolved = rules.resolved_trials
  const unresolved = rules.unresolved_trials
  requireBool(
    Number.isInteger(resolved) && Number.isInteger(unresolved) && (resolved as number) >= 0 && (unresolved as number) >= 0 && (resolved as number) + (unresolved as number) === trials,
    'resolved + unresolved trials mismatch',
  )
  requireBool(
    header.status === ((unresolved as number) > 0 ? 'experimental_rule_bounds' : 'experimental_conditional'),
    'status disagrees with unresolved_trials',
  )
  requireBool(
    isProb(rules.resolved_fraction) && isProb(rules.unresolved_fraction)
    && Math.abs((rules.resolved_fraction as number) - (resolved as number) / trials) <= 1e-5
    && Math.abs((rules.unresolved_fraction as number) - (unresolved as number) / trials) <= 1e-5,
    'resolved/unresolved fractions mismatch',
  )
  if (isRecord(rules.first_unresolved_stage_counts)) {
    const sum = Object.values(rules.first_unresolved_stage_counts).reduce<number>((acc, v) => acc + (Number.isInteger(v) ? (v as number) : -999999), 0)
    requireBool(sum === unresolved, 'first_unresolved_stage_counts do not sum to unresolved_trials')
  }
  return unresolved as number
}

function validateForecastSection(forecast: unknown, teamIds: string[], unresolvedTrials: number): void {
  if (!isRecord(forecast)) fail('missing forecast section')
  validatePairwiseMatrix(forecast.pairwise_single_match, teamIds, 'pairwise_single_match')
  validatePairwiseMatrix(forecast.series_best_of_9, teamIds, 'series_best_of_9')
  validatePairwiseMatrix(forecast.series_best_of_13, teamIds, 'series_best_of_13')

  if (!isRecord(forecast.expected_fleet_position) || !isRecord(forecast.fleet_position_distribution)) {
    fail('missing fleet rank fields')
  }
  let fleetSum = 0
  for (const id of teamIds) {
    const expPos = forecast.expected_fleet_position[id]
    const dist = forecast.fleet_position_distribution[id]
    requireBool(isFiniteNum(expPos) && expPos >= 1 && expPos <= 7, `invalid expected_fleet_position for ${id}`)
    requireBool(Array.isArray(dist) && dist.length === 7 && dist.every(isProb), `invalid fleet distribution for ${id}`)
    const rowSum = (dist as number[]).reduce((a, b) => a + b, 0)
    requireBool(Math.abs(rowSum - 1) <= 1e-3, `fleet distribution must sum to 1 for ${id}`)
    fleetSum += expPos as number
  }
  requireBool(Math.abs(fleetSum - 28) <= 2e-2, 'expected fleet positions must sum to 28')

  if (!isRecord(forecast.advancement_probabilities)) fail('missing advancement_probabilities')
  const advLimits: Array<[string, number]> = [
    ['round_robin_top3', 3.005],
    ['repechage_1_win', 1.005],
    ['repechage_2_win', 1.005],
    ['semifinal', 4.005],
    ['semifinal_1_win', 1.005],
    ['semifinal_2_win', 1.005],
    ['challenger_final_win', 1.005],
  ]
  for (const [key, maxSum] of advLimits) {
    const map = forecast.advancement_probabilities[key]
    if (!isRecord(map)) fail(`missing advancement map ${key}`)
    let sum = 0
    for (const id of teamIds) {
      requireBool(isProb(map[id]), `invalid probability for ${id} in ${key}`)
      sum += map[id] as number
    }
    requireBool(sum <= maxSum, `advancement probability sum exceeded for ${key}`)
  }

  validateBoundsMap(forecast.trophy_rule_bounds, teamIds, 'trophy_rule_bounds')
  if (!isRecord(forecast.trophy_probabilities)) fail('missing trophy_probabilities')
  if (unresolvedTrials > 0) {
    for (const id of teamIds) {
      requireBool(forecast.trophy_probabilities[id] === null, 'unresolved Cup point estimate must be null')
    }
  } else {
    let probSum = 0
    for (const id of teamIds) {
      requireBool(isProb(forecast.trophy_probabilities[id]), `invalid trophy probability for ${id}`)
      probSum += forecast.trophy_probabilities[id] as number
    }
    requireBool(Math.abs(probSum - 1) <= 1e-3, 'trophy probabilities must sum to 1')
  }
}

function validateQuantileBand(band: unknown, label: string): void {
  if (!isRecord(band) || !isProb(band.p05) || !isProb(band.p50) || !isProb(band.p95)) {
    fail(`invalid nested interval quantiles in ${label}`)
  }
  requireBool(band.p05 <= band.p50 && band.p50 <= band.p95, `invalid nested interval ordering in ${label}`)
}

function validateSensitivitiesAndUncertainty(doc: Record<string, unknown>, teamIds: string[]): void {
  const sens = doc.structural_sensitivities
  requireBool(Array.isArray(sens) && sens.length > 0, 'missing structural_sensitivities')
  const seenIds = new Set<string>()
  const seenSpecs = new Set<string>()
  for (const item of sens as unknown[]) {
    if (!isRecord(item) || typeof item.scenario_id !== 'string' || !item.scenario_id || seenIds.has(item.scenario_id)) {
      fail('duplicate or invalid structural sensitivity scenario_id')
    }
    seenIds.add(item.scenario_id)
    requireBool(
      Number.isInteger(item.trials) && (item.trials as number) > 0
      && Number.isInteger(item.resolved_trials) && (item.resolved_trials as number) >= 0
      && Number.isInteger(item.unresolved_trials) && (item.unresolved_trials as number) >= 0
      && (item.resolved_trials as number) + (item.unresolved_trials as number) === (item.trials as number),
      `invalid trial counts in ${item.scenario_id}`,
    )
    requireBool(isFiniteNum(item.residual_scale), `invalid residual_scale in ${item.scenario_id}`)
    const failProb = item.failure_probability ?? 0
    requireBool(isProb(failProb), `invalid failure_probability in ${item.scenario_id}`)
    const specKey = [
      (item.residual_scale as number).toFixed(6),
      Boolean(item.zero_transfer),
      String(item.mapping_policy),
      String(item.evidence_scope),
      item.conditional_on_completed !== false,
      (failProb as number).toFixed(6),
    ].join('|')
    requireBool(!seenSpecs.has(specKey), `duplicated scenario configuration in ${item.scenario_id}`)
    seenSpecs.add(specKey)
    validateBoundsMap(item.trophy_rule_bounds, teamIds, item.scenario_id)
  }

  const unc = doc.uncertainty
  if (!isRecord(unc) || !isRecord(unc.monte_carlo) || !isRecord(unc.posterior_nested_intervals) || !isRecord(unc.transfer_parameter_summary)) {
    fail('missing uncertainty breakdowns')
  }
  const mc = unc.monte_carlo
  requireBool(isProb(mc.worst_case_95_half_width), 'invalid MC half-width')
  if (!isRecord(mc.actual_mc_se_by_team)) fail('missing actual_mc_se_by_team')
  for (const id of teamIds) {
    const entry = mc.actual_mc_se_by_team[id]
    if (!isRecord(entry) || !isFiniteNum(entry.lower) || entry.lower < 0 || !isFiniteNum(entry.upper) || entry.upper < 0) {
      fail(`invalid actual_mc_se_by_team for ${id}`)
    }
  }
  if (!isRecord(mc.pairwise_single_match_mc_se)) fail('missing pairwise_single_match_mc_se')
  for (const ti of teamIds) {
    const row = mc.pairwise_single_match_mc_se[ti]
    if (!isRecord(row)) fail(`missing pairwise_single_match_mc_se row for ${ti}`)
    requireBool(row[ti] === null, `pairwise_single_match_mc_se diagonal for ${ti} must be null`)
    for (const tj of teamIds) {
      if (ti === tj) continue
      const v = row[tj]
      requireBool(isFiniteNum(v) && v >= 0, `invalid pairwise_single_match_mc_se for ${ti} vs ${tj}`)
    }
  }

  const nested = unc.posterior_nested_intervals
  requireBool(typeof nested.converged_within_0_5pp === 'boolean', 'invalid converged_within_0_5pp flag')
  requireBool(isFiniteNum(nested.stabilization_target_pp) && nested.stabilization_target_pp > 0, 'invalid stabilization_target_pp')
  requireBool(Number.isInteger(nested.computation_cap_trials) && (nested.computation_cap_trials as number) >= 1, 'invalid computation_cap_trials')
  if (!isRecord(nested.intervals_by_team)) fail('missing posterior_nested_intervals.intervals_by_team')
  for (const id of teamIds) {
    const entry = nested.intervals_by_team[id]
    if (!isRecord(entry)) fail(`missing nested interval entry for ${id}`)
    validateQuantileBand(entry.lower_p05_p95, `${id}.lower_p05_p95`)
    validateQuantileBand(entry.upper_p05_p95, `${id}.upper_p05_p95`)
  }

  const tps = unc.transfer_parameter_summary
  for (const key of ['beta_percentiles', 'tau_percentiles', 'rho_percentiles']) {
    const q = tps[key]
    if (!isRecord(q) || !isFiniteNum(q.p05) || !isFiniteNum(q.p50) || !isFiniteNum(q.p95) || q.p05 > q.p50 || q.p50 > q.p95) {
      fail(`invalid percentiles for ${key}`)
    }
  }
}

function asAc38Forecast(_value: unknown): asserts _value is Ac38Forecast {
  // Narrowed after runtime invariant checks above.
}

export function parseAc38Forecast(value: unknown): Ac38Forecast {
  if (!isRecord(value)) fail('payload must be an object')
  assertNoPrivatePosteriorKeys(value)
  const header = validateHeader(value.header)
  if (!Array.isArray(value.teams) || value.teams.length !== 7) fail('expected 7 AC38 teams')
  const teamIds = value.teams.map((t) => {
    if (!isRecord(t) || typeof t.id !== 'string' || typeof t.campaign_team_id !== 'string') fail('invalid team descriptor')
    requireBool(t.campaign_team_id === `ac38:${t.id}`, `campaign_team_id must be cycle-scoped for ${t.id}`)
    return t.id
  })
  requireBool(new Set(teamIds).size === 7, 'duplicate team IDs')
  const unresolvedTrials = validateRulesSection(value.rules, header)
  validateForecastSection(value.forecast, teamIds, unresolvedTrials)
  validateSensitivitiesAndUncertainty(value, teamIds)
  asAc38Forecast(value)
  return value
}
