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
  races: Array<PredictionRaceReference & { race_id: string; path: string; presets?: PredictionPreset[] }>
  cup_path: string
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
