export interface KinematicAttribution {
  pre_start_positioning_s?: number
  upwind_vmg_s?: number
  downwind_vmg_s?: number
  tack_execution_s?: number
  gybe_execution_s?: number
  boundary_avoidance_s?: number
  technical_reliability_advantage?: number
}

export interface KinematicStatusDetail {
  finished_rate: number
  dns_rate: number
  dnf_exogenous_rate: number
  ocs_dsq_rate: number
}

export interface KinematicJointFinisherConditioning {
  both_finished_count: number
  both_finished_fraction: number
  mean_delta_t_s: number | null
  p10_delta_t_s: number | null
  p50_delta_t_s: number | null
  p90_delta_t_s: number | null
  mean_time_a_s?: number | null
  mean_time_b_s?: number | null
  scope: string
}

export interface KinematicScenario {
  schema_version: string
  team_a: string
  team_b: string
  tws_kt: number
  course_length_m: number
  n_sims: number
  mode: string
  win_probability_a: number
  win_probability_b: number
  no_winner_probability?: number
  joint_finisher_conditioning: KinematicJointFinisherConditioning
  status_breakdown: Record<string, KinematicStatusDetail>
  attribution_7_component: KinematicAttribution
  rule_adjustments?: {
    cyclor_power_boost_kt?: number
    maneuver_loss_multiplier?: number
    foil_span_limit_factor?: number
  }
}

export interface KinematicCatalogMode {
  id: string
  label: string
  description: string
}

export interface KinematicCatalogSlider {
  default: number
  min: number
  max: number
  step: number
  unit: string
}

export interface KinematicCatalogCourse {
  preset_id?: string
  course_id?: string
  name?: string
  label?: string
  venue?: string
  course_axis_deg?: number
  course_length_m?: number
  leg_length_m?: number
  leg_count?: number
  default_wind_speed_kt?: number
}

export interface KinematicScenarioV2 {
  schema_version: 'kinematic-race-sim-2'
  scenario_id: string
  model_id: string
  status: 'available' | 'unavailable' | 'unsupported'
  probability_scope: string
  applied_inputs: {
    team_a: string
    team_b: string
    course_id?: string
    course?: Record<string, any>
    environment: { tws_mps: number; twd_deg: number }
    purpose: string
    trial_count: number
    seed: number
    seconds_accounting?: {
      straight_delta_s: number
      maneuver_delta_s: number
      start_delta_s: number
      total_mean_delta_s: number
      margin_mc_se_s?: number
    }
    variance_attribution?: Record<string, any>
  }
  timing?: {
    mean_time_a_s: number
    mean_time_b_s: number
    mean_delta_t_s: number
    central_80_margin_interval_s: [number, number]
  } | null
  probabilities?: {
    win_a: number
    win_b: number
    no_winner?: number | null
    mc_error?: number | null
  } | null
  time_accounting?: Record<string, any>
  trial_counts?: { scheduled?: number; requested?: number; completed: number; unresolved?: number }
  reason_codes?: string[]
}

export type AnyKinematicScenario = KinematicScenario | KinematicScenarioV2

export interface KinematicCatalog {
  schema_version: string
  created_at: string
  model_id?: string
  model_status: 'validated' | 'experimental'
  selected_motion_candidate?: string
  status_notice: string
  total_scenarios: number
  available_teams: string[]
  available_modes: KinematicCatalogMode[]
  default_sliders: Record<string, KinematicCatalogSlider>
  courses: KinematicCatalogCourse[]
  scenarios: AnyKinematicScenario[]
}

export function isKinematicScenarioV2(s: unknown): s is KinematicScenarioV2 {
  return typeof s === 'object' && s !== null && (s as any).schema_version === 'kinematic-race-sim-2'
}
