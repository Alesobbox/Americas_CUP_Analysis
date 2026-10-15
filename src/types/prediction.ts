export type ForecastStatus = 'available' | 'estimated' | 'gate_ambiguous' | 'unavailable'

export interface PredictionReference {
  model_ref?: string
  source_manifest_hash?: string
  scenario_hash?: string
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
  races: Array<PredictionReference & { race_id: string; path: string; presets?: PredictionPreset[] }>
  cup_path: string
}

export interface PredictionHeader extends PredictionReference {
  schema_version: 'prediction-1'
  race_id: string
  boat_ids: string[]
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

export interface CupPrediction {
  header: { schema_version: 'cup-1'; boat_class: 'AC75'; source_manifest_hash?: string; model_ref?: string; scenario_hash?: string; method_and_assumption_refs?: string[] }
  status: ForecastStatus
  reason?: string
  teams: Array<{ id: string; name: string }>
  scenario_envelope_by_team?: Record<string, { lower: number; upper: number } | null>
  rule_bounds_by_team?: Record<string, { lower: number; upper: number } | null>
  evaluated_scenarios?: string[]
}
