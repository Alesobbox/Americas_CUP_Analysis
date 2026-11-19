import type { MetricDefinition } from './analysis'

export interface PolarBootstrapInterval {
  value: number
  ci_low_kt: number
  ci_high_kt: number
  bootstrap_se_kt: number
  unit?: string
  scope?: string
  valid_draws?: number
}

export interface PolarCurvePoint {
  twa_deg: number
  mean_sog_kt: number
  p50_sog_kt: number
  p90_sog_kt: number
  mean_wind_vmg_kt: number
  p50_wind_vmg_kt: number
  p90_wind_vmg_kt: number
  effective_coverage_s: number
  support_clusters: number
}

export interface PolarBracketCurve {
  id: string
  label: string
  tws_min_kt: number
  tws_max_kt: number
  tws_ref_kt: number
  points: PolarCurvePoint[]
}

export interface PolarTackContrast {
  contrast_kt: number
  ci_low_kt: number
  ci_high_kt: number
  bootstrap_se_kt: number
  coverage_s: number
}

export interface PolarTackFixedEffect {
  specification: string
  bootstrap_draws: number
  upwind: PolarTackContrast | null
  downwind: PolarTackContrast | null
  overall: PolarTackContrast | null
  resampling_unit?: string
  uncertainty_scope?: string
}

export interface PolarValidationMetrics {
  label: string
  folds: number
  sog_rmse_kt?: number
  sog_mae_kt?: number
  sog_r2?: number
  vmg_rmse_kt?: number
  vmg_mae_kt?: number
  vmg_r2?: number
  p50_pinball_loss_kt?: number
  p90_pinball_loss_kt?: number
  p50_empirical_coverage?: number
  p90_empirical_coverage?: number
  target?: string
  status?: string
  evaluated_sample_count?: number
  excluded_sample_count?: number
  kind?: string
  group?: string
  mean_residual_kt?: number | null
}

export interface BoatPolarObservedBin {
  tack: 'PORT' | 'STARBOARD'
  tws_bin_kt: number
  twa_bin_deg: number
  sog_mean_kt: number
  sog_p90_kt: number
  wind_vmg_mean_kt: number
  predicted_sog_kt: number
  sample_count: number
}

export interface BoatPolarResidual {
  schema_version: '1.0' | '2.0'
  method_version: string
  quality: 'derived' | 'unavailable'
  reason: string | null
  evaluation_scope: string
  steady_sample_count: number
  steady_coverage_s: number
  leg_cluster_count: number
  mean_observed_sog_kt?: number
  mean_predicted_sog_kt?: number
  mean_observed_wind_vmg_kt?: number
  mean_predicted_wind_vmg_kt?: number
  sog_residual_kt: PolarBootstrapInterval | null
  wind_vmg_residual_kt: PolarBootstrapInterval | null
  loro_sog_residual_kt: number | null
  lodo_sog_residual_kt: number | null
  in_sample_sog_residual_kt?: number | null
  upwind_sog_residual_kt?: number | null
  downwind_sog_residual_kt?: number | null
  port_sog_residual_kt?: number | null
  starboard_sog_residual_kt?: number | null
  above_p90_share: number | null
  bootstrap_draws?: number
  traffic_excluded_s: number
  observed_bins: {
    upwind: BoatPolarObservedBin[]
    downwind: BoatPolarObservedBin[]
  }
}

export interface RacePolarAnalysis {
  schema_version: '1.0' | '2.0'
  method_version: string
  race_id: string
  quality: 'derived' | 'unavailable'
  reason: string | null
  evaluation_scope: string
  caveats: string[]
  definitions: Record<string, Omit<MetricDefinition, 'display'>>
  validation_summary: {
    race_cell_count: number
    race_steady_coverage_s: number
    loro_sog_rmse_kt?: number
    lodo_sog_rmse_kt?: number
    loro_sog_mae_kt?: number
    lodo_sog_mae_kt?: number
    in_sample_sog_rmse_kt?: number
    tack_fixed_effect: PolarTackFixedEffect
  } | null
  brackets: {
    upwind: PolarBracketCurve[]
    downwind: PolarBracketCurve[]
  }
}

export interface ArchiveTeamPolarResidual {
  team_code: string
  race_count: number
  leg_cluster_count: number
  steady_coverage_s: number
  lodo_sog_residual_kt: PolarBootstrapInterval | null
  loro_sog_residual_kt: PolarBootstrapInterval | null
  in_sample_sog_residual_kt: PolarBootstrapInterval | null
  wind_vmg_residual_kt: PolarBootstrapInterval | null
  upwind_sog_residual_kt: number | null
  downwind_sog_residual_kt: number | null
  port_sog_residual_kt: number | null
  starboard_sog_residual_kt: number | null
  above_p90_share: number | null
  bootstrap_draws: number
  peer_relative_residual_kt?: PolarBootstrapInterval | null
  race_block_sensitivity_kt?: PolarBootstrapInterval | null
}

export interface ArchivePolarModel {
  schema_version: '1.0' | '2.0'
  method_version: string
  evaluation_scope: string
  steady_state_filter: {
    sample_cadence_hz: number
    min_sog_kt: number
    max_sog_kt: number
    min_tws_kt: number
    max_tws_kt: number
    upwind_abs_twa_deg: [number, number]
    downwind_abs_twa_deg: [number, number]
    manoeuvre_exclusion_s: number
    gate_exclusion_s: number
    max_turn_rate_deg_s: number
    min_competitor_separation_m: number
  }
  caveats: string[]
  definitions: Record<string, Omit<MetricDefinition, 'display'>>
  counts: {
    eligible_races: number
    excluded_races: number
    distinct_days: number
    boat_leg_clusters: number
    steady_coverage_s: number
    steady_cells: number
  }
  tack_fixed_effect: PolarTackFixedEffect
  validation: {
    baseline_mode_only: PolarValidationMetrics
    leave_one_race_out: PolarValidationMetrics
    leave_one_day_out: PolarValidationMetrics
    chronological?: PolarValidationMetrics
    by_group?: PolarValidationMetrics[]
    calibration_status?: string
  }
  team_residuals: ArchiveTeamPolarResidual[]
  curves: {
    upwind: PolarBracketCurve[]
    downwind: PolarBracketCurve[]
  }
}
