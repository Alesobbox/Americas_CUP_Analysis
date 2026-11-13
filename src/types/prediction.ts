export type ForecastStatus = 'available' | 'estimated' | 'gate_ambiguous' | 'unavailable'

export interface PredictionReference {
  model_ref?: string
  source_manifest_hash?: string
  scenario_hash?: string
}

export interface PredictionRaceReference extends PredictionReference {
  boat_ids?: string[]
  replay_boat_ids?: string[]
}

export interface PredictionPreset extends PredictionReference {
  id: string
  path?: string
  tws_kt: number
  direction_offset_deg: number
  scope: 'pre_race'
  status?: ForecastStatus
  reason?: string
}

export interface PredictionIndex {
  schema_version: 'prediction-index-1'
  source_manifest_hash?: string
  source_manifest_path?: string
  evidence_manifest_hash?: string
  evidence_manifest_path?: string
  races: Array<PredictionRaceReference & { race_id: string; path: string; presets?: PredictionPreset[] }>
  cup_path: string
  ac38_forecast_path?: string
}

export interface PredictionHeader extends PredictionReference {
  schema_version: 'prediction-1'
  race_id: string
  boat_ids: string[]
  replay_boat_ids?: string[]
  scheduled_entries?: Array<{ id: string; team_code: string; team_name: string }>
  boat_class: string
  model_ref: string
  source_manifest_hash: string
  scenario_hash: string
  status_dictionary: ForecastStatus[]
  method_and_assumption_refs: string[]
  train_cutoff_ms?: number
  scope?: string
  max_state_age_ms?: number
  conditions?: { tws_kt?: number; direction_offset_deg?: number }
}

export interface PreRacePrediction {
  status: ForecastStatus
  reason?: string
  expected_position_by_boat: Record<string, number | null>
  nonfinish_score: 'N' | number
}

export interface RacePrediction {
  header: PredictionHeader
  pre_race: PreRacePrediction
  live: {
    state_timestamps_ms: number[]
    published_at_ms: number[]
    progress_band: Array<string | number | null>
    win_prob_by_boat: Record<string, Array<number | null>>
    no_finisher_prob: Array<number | null>
    status_code: Array<number | ForecastStatus>
    reason_code?: Array<string | null>
    source_age_ms_by_boat: Record<string, Array<number | null>>
    position_uncertainty_summary_by_boat: Record<string, unknown[]>
    quality_code_by_boat: Record<string, Array<string | number | null>>
    numerical_error: Array<number | null>
  }
}

export interface CupScenarioRecord {
  scenario_id: string
  scenario: { rho: number; sigma_multiplier: number; match_concentration: number; hazard_multiplier: number }
  trials: number; seed: number; input_hash: string; model_ref: string | null; source_manifest_hash: string
  status: string; resolved_trials: number; unresolved_trials: number; resolved_fraction: number; unresolved_fraction: number
  resolved_win_counts: Record<string, number>
  first_unresolved_stage_counts: Record<string, number>
  overlapping_reason_counts: Record<string, number>
  reason_count_policy: string
  rule_bounds: Record<string, { lower: number; upper: number }>
  probabilities: Record<string, number | null>
  numerical_error: { worst_case_95_half_width: number; scope: string }
  unresolved_reasons: string[]; assumptions: string[]
}

export interface CupScenarioAnalysis {
  schema_version: 'cup-scenarios-1'
  baseline_scenario_id: string
  model_lineage: { model_ref?: string; training_before_day?: string; training_cutoff_ms?: number; selection_policy?: string; strength_method?: string; source_manifest_hash?: string }
  mapping_provenance: { policy: string; teams: Array<{ team_id: string; observed: boolean; source_entries: Array<{ entry_id: string; effect: number }>; mapped_strength: number | null }> }
  build_budget: { trials_per_scenario: number; scenario_count: number; seed: number; profile: string; common_random_numbers: boolean; randomization_policy?: string }
  simulation_inputs: { mapped_strength: Record<string, number>; rules: Record<string, unknown>; pooled_scale: number; failure_probability: number; conditional_on_completed_scored_races: boolean }
  conditioning: Record<string, string>
  records: CupScenarioRecord[]
  extrema_by_team: Record<string, { lower_scenario_ids: string[]; upper_scenario_ids: string[] }>
  refinement_policy: { method: string; status: string; reason: string }
}

export interface CupPrediction {
  header: { schema_version: 'cup-1'; boat_class: 'AC75'; method_version?: string; source_manifest_hash?: string; model_ref?: string; scenario_hash?: string; method_and_assumption_refs?: string[] }
  status: ForecastStatus
  reason?: string
  unresolved_reasons?: string[]
  teams: Array<{ id: string; name: string }>
  scenario_envelope_by_team?: Record<string, { lower: number; upper: number } | null> | null
  rule_bounds_by_team?: Record<string, { lower: number; upper: number } | null> | null
  evaluated_scenarios?: string[]
  probabilities?: Record<string, number | null>
  win_prob_by_team?: Record<string, number | null>
  scenario_analysis?: CupScenarioAnalysis
}

export interface Ac38RuleBound {
  lower: number
  upper: number
}

export interface Ac38Quantiles {
  p05: number
  p50: number
  p95: number
}

export interface Ac38ForecastHeader {
  schema_version: 'ac38-forecast-1'
  status: 'experimental_conditional' | 'experimental_rule_bounds'
  experimental: true
  generated_at_utc: string
  issuance_cutoff_utc: string
  conditioning: string
  model_ref: string
  transfer_posterior_sha256: string
  eligibility_ledger_sha256: string
  inventory_sha256: string
  backtest_report_sha256: string
  seed: number
  trials: number
  selected_transfer_candidate: 'results_only' | 'results_plus_telemetry'
  telemetry_retained: boolean
  scale_kappa: number
  applied_ac75_updates: string[]
  update_ess: number
}

export interface Ac38TeamCoverage {
  team_id: string
  campaign_team_id: string
  team_name: string
  observed: boolean
  basis: string
  source_entries: Array<{ entry_id: string; effect: number }>
  mapped_ac40_mean: number | null
  mapped_ac40_sd: number | null
}

export interface Ac38RuleSource {
  title?: string
  doc_code?: string
  version?: string
  effective_date?: string | null
  url: string
  status?: string
  sha256?: string
}

export interface Ac38SensitivityRecord {
  scenario_id: string
  label: string
  category: string
  residual_scale: number
  zero_transfer: boolean
  mapping_policy: string
  evidence_scope: string
  failure_probability: number
  conditional_on_completed: boolean
  trials: number
  resolved_trials: number
  unresolved_trials: number
  unresolved_fraction: number
  expected_fleet_position: Record<string, number>
  trophy_rule_bounds: Record<string, Ac38RuleBound>
  actual_mc_se_by_team: Record<string, Ac38RuleBound>
}

export interface Ac38BacktestMetricSummary {
  n_obs: number
  n_groups: number
  mean_log_loss: number
  grouped_mean_log_loss: number
  grouped_se_log_loss: number
  mean_brier: number
  grouped_se_brier: number
  coverage_50: number | null
  coverage_90: number | null
  calibration: {
    slope: number
    intercept: number
    mean_pred: number
    mean_obs: number
    bins: Array<{ range: [number, number]; count: number; mean_pred: number; mean_obs: number }>
  }
}

export interface Ac38Forecast {
  header: Ac38ForecastHeader
  teams: Array<{ id: string; campaign_team_id: string; name: string; role: string }>
  entrant_coverage: {
    default_mapping_policy: string
    evidence_scope: string
    ac38_races_included: string[]
    ac38_anchored_races: string[]
    ac38_reconstructed_races: string[]
    ac38_excluded_observations: Array<Record<string, unknown>>
    teams: Ac38TeamCoverage[]
    assumptions: string[]
  }
  rules: {
    tie_policy: string
    sources: Ac38RuleSource[]
    unresolved_clauses: string[]
    resolved_trials: number
    unresolved_trials: number
    resolved_fraction: number
    unresolved_fraction: number
    first_unresolved_stage_counts: Record<string, number>
    overlapping_reason_counts: Record<string, number>
    unresolved_reasons: string[]
  }
  forecast: {
    pairwise_single_match: Record<string, Record<string, number | null>>
    series_best_of_9: Record<string, Record<string, number | null>>
    series_best_of_13: Record<string, Record<string, number | null>>
    expected_fleet_position: Record<string, number>
    fleet_position_distribution: Record<string, number[]>
    advancement_probabilities: {
      round_robin_top3: Record<string, number>
      repechage_1_win: Record<string, number>
      repechage_2_win: Record<string, number>
      semifinal: Record<string, number>
      semifinal_1_win: Record<string, number>
      semifinal_2_win: Record<string, number>
      challenger_final_win: Record<string, number>
    }
    trophy_probabilities: Record<string, number | null>
    trophy_rule_bounds: Record<string, Ac38RuleBound>
  }
  uncertainty: {
    monte_carlo: {
      trials: number
      seed: number
      worst_case_95_half_width: number
      actual_mc_se_by_team: Record<string, Ac38RuleBound>
      pairwise_single_match_mc_se: Record<string, Record<string, number | null>>
    }
    posterior_nested_intervals: {
      policy: string
      quantiles: string
      stabilization_target_pp: number
      computation_cap_trials: number
      converged_within_0_5pp: boolean
      final_max_endpoint_delta: number
      reason: string
      refinement_history: Array<{
        outer_worlds: number
        inner_trials_per_world: number
        total_trials: number
        max_endpoint_delta_vs_prev: number | null
        within_0_5pp: boolean
      }>
      intervals_by_team: Record<string, { lower_p05_p95: Ac38Quantiles; upper_p05_p95: Ac38Quantiles }>
    }
    transfer_parameter_summary: {
      beta_percentiles: Ac38Quantiles
      tau_percentiles: Ac38Quantiles
      rho_percentiles: Ac38Quantiles
      prior_sensitivity: Record<string, unknown>
    }
  }
  structural_sensitivities: Ac38SensitivityRecord[]
  historical_evaluation: {
    selection_rule: string
    selected_candidate: 'results_only' | 'results_plus_telemetry'
    telemetry_retained: boolean
    accuracy_claim: string
    ac40_chronological: Record<string, unknown>
    ac75_chronological: Record<string, unknown>
    ac75_loto: Record<string, unknown>
  }
}
