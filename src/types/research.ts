export interface SpeedScores {
  sample_count: number
  rmse_kt: number | null
  mae_kt: number | null
  bias_kt: number | null
}

export interface DayScores {
  days: number
  mean_rmse_kt: number | null
  mean_mae_kt: number | null
}

export interface PairedDifference {
  mean_delta_kt: number | null
  day_count: number
  interval_95: [number, number] | null
  interval_scope?: string
}

export interface ResearchComparison {
  status?: string
  split?: string
  sample_weighted?: Record<string, SpeedScores>
  day_equal: Record<string, DayScores>
  paired_day_differences?: Record<string, PairedDifference>
  paired_local_linear_minus_kernel_rmse?: PairedDifference
  missing_or_unmatched_count?: number
  scope?: string
}

export interface WindDiscrepancy {
  team_code: string
  tack: string
  sample_count: number
  day_count: number
  median_speed_difference_kt: number
  median_direction_difference_deg: number
  direction_discrepancies_above_60deg: number
}

export interface PolarExperiments {
  schema_version: string
  status: string
  reason?: string
  scope: string
  cohort: { sample_count: number; days: number; races: number }
  model_comparison?: { leave_one_day_out: ResearchComparison; chronological: ResearchComparison }
  wind_comparison?: {
    official_discrepancy: { by_team_tack: WindDiscrepancy[]; interpretation: string }
    peer_discrepancy: { by_team_tack: WindDiscrepancy[]; interpretation: string }
    peer_supported_samples: number
    leave_one_day_out: ResearchComparison
    chronological: ResearchComparison
    scope: string
  }
  environment_ablation?: {
    feature_blocks: Record<
      string,
      { leave_one_day_out: ResearchComparison; chronological: ResearchComparison }
    >
    coverage: { race_id: string; sample_count: number; available_counts: Record<string, number> }[]
    wave_period_definition: string
    thermal_definition: string
    interpretation: string
  }
}

export interface WindScores {
  brier: number
  log_loss: number
  circular_crps_deg: number
}

export interface WindForecastModel {
  schema_version: string
  status: string
  availability_basis: string
  counts: { races: number; context_days: number; scored_targets: number; censored_targets: number }
  validation: Record<
    string,
    {
      day_equal: WindScores
      sample_weighted: WindScores
      scored_days: number
      scored_targets: number
    }
  >
  target: { definition: string; horizon_s: number; threshold_deg: number }
  limitations: string[]
}

export interface RaceWindForecast {
  schema_version: string
  availability_basis: string
  unavailable_prediction_count: number
  training_days?: number
  reference_model: string
  predictions: {
    timestamp_ms: number
    target_timestamp_ms: number
    current_twd_deg: number
    methods: Record<string, { probability_shift_ge_5deg: number; center_twd_deg: number }>
    target_status: string
  }[]
}

export interface TimingSummary {
  schema_version: string
  scope: string
  counts: Record<string, number>
}

export interface TimingHorizon {
  horizon_s: number
  observed_duration_s: number
  coverage_s: number
  right_censored: boolean
  censor_reason: string | null
  progress_deficit_m: number | null
  polar_reference_deficit_m: number | null
}

export interface TimingTurn {
  timestamp_ms: number
  type: string
  leg: number
  cost_quality: string
  cost_reason?: string
  review_status: string
  horizons: TimingHorizon[]
  recovery?: { right_censored: boolean; recovery_s: number | null; speed_regime: string }
}

export interface TimingResearch {
  schema_version: string
  scope: string
  caveats: string[]
  boats: {
    boat_id: string
    team_code: string
    ledger: {
      quality: string
      reason?: string | null
      complete_finish?: boolean
      accounted_elapsed_s?: number
      reconciliation_error_s?: number
      components: { kind: string; leg: number | null; elapsed_s: number }[]
      peer_comparison?: {
        total_difference_s: number
        peer_ids: string[]
        components: { kind: string; leg: number | null; difference_s: number }[]
      } | null
    }
    phases: { quality: string; active_elapsed_s?: number; seconds: Record<string, number> | null }
    turns: TimingTurn[]
    detector_evaluation: { status: string; precision: number | null; recall: number | null }
  }[]
}
