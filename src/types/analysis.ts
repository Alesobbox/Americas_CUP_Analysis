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

export interface AnalysisIndex {
  schema_version: '2.0'
  races: AnalysisIndexRace[]
  histories: AnalysisHistory[]
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
  source_coverage?: Record<string, { first_ms: number | null; last_ms: number | null; count: number; gaps: Array<[number, number]> }>
}

export interface AnalysisWind {
  source: string
  baseline_twd_deg: number | null
  sample_count: number
  shift_min_deg: number | null
  shift_max_deg: number | null
  timeline: Array<{ timestamp: number; shift_deg: number; tws_kt: number }>
  fleet_timeline?: Array<{ timestamp: number; active_boats: number; spread_deg: number }>
  boat_exposure?: Array<{ team_code: string; sample_count: number; median_local_minus_official_deg: number | null }>
}

export interface AnalysisPair {
  boat_a: string
  boat_b: string
  legs: Array<{ leg: number; sample_count: number; median_spatial_m: number | null; median_lateral_m: number | null }>
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
  race: { id: string; name: string; date: string; boat_class: string; race_type: string; gun_time_ms: number; result_provenance?: string; limitations?: string[] }
  definitions: Record<string, MetricDefinition>
  boats: AnalysisDetailBoat[]
  wind: AnalysisWind
  pairs: AnalysisPair[]
  event_feed?: AnalysisEventFeed
  limitations?: string[]
}
