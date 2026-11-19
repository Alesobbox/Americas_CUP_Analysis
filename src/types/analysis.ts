export type MetricQuality = 'derived' | 'reconstructed' | 'official' | 'unavailable' | 'partial'

export interface AnalysisMetric {
  value: number | null
  unit: string
  quality: MetricQuality
  coverage_s: number | null
  sample_count?: number
  reason?: string
}

export type MetricMap = Record<string, AnalysisMetric>

export interface MetricDefinition {
  label: string
  unit: string
  formula: string
  window: string
  denominator: string
  source: string
  display: string
}

export interface AnalysisIndexBoat {
  id: string
  team_code: string
  team_name: string
  color: string
  classification: string
  official_rank: number | null
  official_elapsed_s: number | null
  metrics: MetricMap
}

export interface AnalysisIndexRace {
  id: string
  name: string
  date: string
  boat_class: string
  race_type: string
  analysis_file: string
  boat_count: number
  boats: AnalysisIndexBoat[]
  result_provenance?: string
  limitations?: string[]
}

export interface HistoryObservation {
  race_id: string
  date: string
  classification: string
  official_rank: number | null
  metrics: MetricMap
  start?: {
    crossing_time_ms: number | null
    delta_to_gun_s: number | null
    crossing_order: number | null
    ocs: boolean
  }
  legs?: Array<{
    leg: number
    complete?: boolean
    elapsed_s: AnalysisMetric
    course_vmg_kt: AnalysisMetric
    wind_vmg_kt: AnalysisMetric
    distance_m: AnalysisMetric
  }>
}

export interface HistoryMetricSummary {
  median: number
  min: number
  max: number
  count: number
}

export interface HistoryManoeuvreSummary {
  event_count: number
  race_count: number
  origin_races?: Record<string, number>
  loss_p10_kt: number | null
  loss_median_kt: number | null
  loss_p90_kt: number | null
  recovery_median_s: number | null
  unrecovered_count: number
}

export interface AnalysisHistory {
  team_code: string
  boat_class: string
  race_type: string
  race_count: number
  observations: HistoryObservation[]
  summary: Record<string, HistoryMetricSummary>
  leg_summary?: Record<string, Record<string, HistoryMetricSummary>>
  manoeuvre_summary?: Record<string, HistoryManoeuvreSummary>
}

export interface PolarBootstrapInterval {
  value: number
  ci_low_kt: number
  ci_high_kt: number
  bootstrap_se_kt: number
  unit?: string
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
}

export interface PolarValidationMetrics {
  label: string
  folds: number
  sog_rmse_kt: number
  sog_mae_kt: number
  sog_r2: number
  vmg_rmse_kt: number
  vmg_mae_kt: number
  vmg_r2: number
  p50_pinball_loss_kt: number
  p90_pinball_loss_kt: number
  p50_empirical_coverage: number
  p90_empirical_coverage: number
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
  schema_version: '1.0'
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
  schema_version: '1.0'
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
}

export interface ArchivePolarModel {
  schema_version: '1.0'
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
  }
  team_residuals: ArchiveTeamPolarResidual[]
  curves: {
    upwind: PolarBracketCurve[]
    downwind: PolarBracketCurve[]
  }
}

export interface AnalysisIndex {
  schema_version: '2.0'
  races: AnalysisIndexRace[]
  histories: AnalysisHistory[]
  polar_model?: ArchivePolarModel
}

export interface AnalysisStart {
  crossing_time_ms: number | null
  crossing_order: number | null
  ocs: boolean
  gun: { metrics: MetricMap }
}

export interface AnalysisGate {
  leg: number
  crossing_time_ms: number | null
  mark_chosen: string | null
  side: string | null
  source: string
  approach_20s_distance_m: number | null
  approach_angle_deg: number | null
  entry_speed_kt: number | null
  exit_speed_kt: number | null
  rounding_time_s: number | null
  rounding_reason: string | null
  split_to_leader_s: number | null
  checkpoint_rank?: number | null
  split_change_s?: number | null
  rank_change?: number | null
}

export interface AnalysisLeg {
  leg: number
  start_ms: number
  end_ms: number
  metrics: MetricMap
  gate: AnalysisGate | null
  twa_bins_s?: Record<string, number>
}

export interface AnalysisManoeuvre {
  type: string
  timestamp: number
  leg: number | null
  position: { x: number; y: number } | null
  entry_speed_kt: number | null
  min_speed_kt: number | null
  speed_loss_kt: number | null
  recovery_time_s: number | null
  acceleration_kt_s?: number | null
  quality: string
}

export interface AnalysisDetailBoat extends AnalysisIndexBoat {
  start: AnalysisStart
  legs: AnalysisLeg[]
  manoeuvres: AnalysisManoeuvre[]
  gates: AnalysisGate[]
  boundary_periods?: Array<{ start_ms: number; end_ms: number }>
  source_conflicts?: string[]
  source_coverage?: Record<
    string,
    {
      first_ms: number | null
      last_ms: number | null
      count: number
      gaps: Array<[number, number]>
    }
  >
  performance?: BoatPerformance
  debrief?: TeamDebriefReport
  polar?: BoatPolarResidual
}

export interface PerformanceLegExclusion {
  leg: number
  reason: string
}

export interface PerformancePeerEvidence {
  id: string
  team_code: string
  team_name: string
  value: number
  coverage_s: number
  sample_count: number
  start_ms: number
  end_ms: number
  quality: string
}

export interface PerformanceLegEvidence {
  leg: number
  value: number
  peer_mean: number
  index: number
  peer_count: number
  peer_ids: string[]
  coverage_s: number
  sample_count: number
  start_ms?: number
  end_ms?: number
  quality?: string
  peers?: PerformancePeerEvidence[]
  excluded_peers?: Array<{ id: string; team_code: string; reason: string }>
  events?: Array<{
    timestamp_ms: number
    entry_speed_kt: number
    minimum_speed_kt: number
    retention_pct: number
    window_start_ms: number
    window_end_ms: number
  }>
}

export interface PerformanceDimension {
  id: string
  label: string
  index: number | null
  value: number | null
  peer_mean: number | null
  unit: 'kt' | '%'
  peer_count: number
  higher_is_better: boolean
  coverage_s: number
  sample_count: number
  matched_legs: number[]
  leg_evidence?: PerformanceLegEvidence[]
  excluded_legs?: PerformanceLegExclusion[]
  quality: string
  formula: string
  denominator: string
  source: string
  reason?: string
}

export interface BoatPerformance {
  schema_version: '1.0'
  method_version: string
  overall_index: number | null
  baseline_index: number
  notes: string[]
  reason?: string
  dimensions: PerformanceDimension[]
  scope?: {
    expected_legs: number[]
    matched_legs: number[]
    expected_leg_count: number
    matched_leg_count: number
    min_peer_count: number
    covered_s: number
    excluded_legs: PerformanceLegExclusion[]
  }
}

export interface TeamDebriefReport {
  schema_version: '1.0'
  method_version: string
  items: Array<{
    id: string
    title: string
    detail: string
    timestamp_ms: number
    value: number
    unit: string
    quality: string
    source: string
    kind: 'leg_deficit' | 'manoeuvre_loss'
    leg?: number
    peer_count?: number
  }>
}

export interface TacticalSnapshot {
  timestamp_ms: number
  window_start_ms: number
  window_end_ms: number
  coverage_s: number
  sample_count: number
  quality: 'derived' | 'unavailable'
  source: string
  reason?: string
  direction_change_deg: number | null
  direction_rate_deg_per_min: number | null
  speed_change_kt: number | null
  speed_coverage_s: number
  speed_sample_count: number
  speed_quality: 'derived' | 'unavailable'
  speed_reason: string | null
  projection_change_deg: number | null
  projection_reason: string
  insights: Array<{
    id: string
    title: string
    detail: string
    quality: string
    source: string
    kind: string
  }>
}

export interface TacticalInsights {
  schema_version: '1.0'
  method_version: string
  race_id: string
  source: string
  snapshot_interval_ms: number
  max_snapshot_age_ms: number
  window_s: number
  projection_horizon_s: number
  availability_basis: string
  reason?: string
  definitions?: Record<string, Omit<MetricDefinition, 'display'>>
  source_provenance?: Record<string, unknown>
  snapshots: TacticalSnapshot[]
}

export interface AnalysisWind {
  source: string
  baseline_twd_deg: number | null
  sample_count: number
  shift_min_deg: number | null
  shift_max_deg: number | null
  timeline: Array<{ timestamp: number; shift_deg: number; tws_kt: number }>
  fleet_timeline?: Array<{ timestamp: number; active_boats: number; spread_deg: number }>
  boat_exposure?: Array<{
    team_code: string
    sample_count: number
    median_local_minus_official_deg: number | null
  }>
}

export interface AnalysisPair {
  boat_a: string
  boat_b: string
  legs: Array<{
    leg: number
    sample_count: number
    median_spatial_m: number | null
    median_lateral_m: number | null
  }>
}

export interface AnalysisEvent {
  id: string
  timestamp_ms: number
  type: 'gun' | 'start' | 'gate' | 'finish' | 'tack' | 'gybe' | 'wind_shift'
  boat_id?: string
  label: string
  source: string
  quality: string
  unavailable_reason?: string
}

export interface AnalysisEventFeed {
  schema_version: '1.0'
  method_version: string
  events: AnalysisEvent[]
}

export interface AnalysisDetail {
  schema_version: '2.0'
  method_version: string
  race: {
    id: string
    name: string
    date: string
    boat_class: string
    race_type: string
    gun_time_ms: number
    result_provenance?: string
    limitations?: string[]
  }
  definitions: Record<string, MetricDefinition>
  boats: AnalysisDetailBoat[]
  wind: AnalysisWind
  pairs: AnalysisPair[]
  event_feed?: AnalysisEventFeed
  tactical_insights?: TacticalInsights
  polar_analysis?: RacePolarAnalysis
  limitations?: string[]
}
