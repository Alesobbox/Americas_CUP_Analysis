export type Point = [number, number]

export interface BorderPoint {
  x: number
  y: number
}

export type BoatClass = 'AC40' | 'AC75' | 'UNKNOWN'
export type BoatScaleMode = 'true' | 'enhanced'
export type ViewMode = 'map' | 'grid'

export interface ClassEvidence {
  description: string
  confidence: 'CONFIRMED' | 'INFERRED' | 'UNKNOWN'
  source: string
}

export interface SafetyBorders {
  platform_border: BorderPoint[]
  keep_clear_border: BorderPoint[]
}

export interface VirtualContactIncident {
  id: string
  boat_a: string
  boat_b: string
  start_ms: number
  end_ms: number
  duration_ms: number
  peak_ms: number
  min_center_distance_m: number
  peak_overlap_m2?: number
  peak_overlap_m?: number
  boat_a_id?: string
  boat_b_id?: string
  boat_a_code?: string
  boat_b_code?: string
  start_frame_idx?: number
  end_frame_idx?: number
  type?: string
}

export interface CourseMark {
  name: string
  target: Point
  asset_id?: string
  code?: string
  role?: string
}

export interface GateSequence {
  leg: number
  port_mark: string
  starboard_mark: string
  gate_type: 'START' | 'TOP' | 'BOTTOM' | 'FINISH'
}

export interface ReplayCourse {
  axis_deg: number
  length_m: number
  origin: { lat: number; lon: number }
  projection: { k_lat: number; k_lon: number }
  boundaries: { race: Point[]; safety: Point[] }
  boundary_timeline?: Array<{ t: number; race: Point[]; safety: Point[] }>
  marks: Record<string, CourseMark>
  safety_borders?: SafetyBorders
  sequences?: GateSequence[]
  start_marks?: { port: string; starboard: string }
}

export interface WindSample {
  t: number
  twd: number
  tws: number
}

export interface Competitor {
  id: string
  team_code: string
  team_name: string
  short_name?: string
  country?: string
  color: string
  classification: string
  start: {
    crossing_time: number
    delta_to_gun_s: number
    ocs: boolean
    chosen_side: 'PORT' | 'STARBOARD'
  }
  gates: GateCrossing[]
  manoeuvres: Manoeuvre[]
  summary: {
    finish_rank: number
    elapsed_s: number
    distance_sailed_m: number
    tack_count: number
    gybe_count: number
    avg_speed_kt: number
    avg_vmg_kt: number
  }
}

export interface GateCrossing {
  leg: number
  crossing_time: number
  mark_chosen: string
  side: 'PORT' | 'STARBOARD'
}

export interface Manoeuvre {
  type: 'TACK' | 'GYBE'
  timestamp: number
  entry_speed_kt: number
  min_speed_kt: number
  speed_loss_kt: number
  recovery_time_s: number
}

export interface BoatTelemetry {
  x: number[]
  y: number[]
  heading: number[]
  cog: number[]
  sog: number[]
  vmg: number[]
  twa: number[]
  twd: number[]
  tws: number[]
  progress_m: number[]
  leg: number[]
}

export interface BoatFrame {
  id: string
  x: number
  y: number
  heading: number
  cog: number
  sog: number
  vmg: number
  twa: number
  twd: number
  tws: number
  progress_m: number
  leg: number
}

export interface ReplayFrame {
  timestamp: number
  index: number
  fraction: number
  boats: Record<string, BoatFrame>
  marks: Record<string, { x: number; y: number }>
}

export interface ReplayData {
  id: string
  name: string
  venue: string
  date: string
  event_edition: string
  boat_class: BoatClass
  class_evidence: ClassEvidence
  safety_borders?: SafetyBorders
  virtual_contact_incidents: VirtualContactIncident[]
  course: ReplayCourse
  wind: {
    reference_twd_deg: number
    reference_tws_kt: number
    timeline: WindSample[]
  }
  chronology: {
    gun_time: number
    window_start: number
    window_end: number
  }
  competitors: Competitor[]
  telemetry: {
    timestamps: number[]
    boats: Record<string, BoatTelemetry>
    marks: Record<string, { x: number[]; y: number[] }>
  }
  provenance?: {
    source_records: number
    sample_interval_ms: number
    measured_streams: string[]
    derived_fields: Record<string, string>
  }
}

export interface ReplayManifest extends Omit<
  ReplayData,
  'event_edition' | 'boat_class' | 'class_evidence' | 'virtual_contact_incidents'
> {
  event_edition?: string
  boat_class?: BoatClass
  class_evidence?: ClassEvidence
  safety_borders?: SafetyBorders
  virtual_contact_incidents?: VirtualContactIncident[]
}

export type PlaybackSpeed = 0.25 | 0.5 | 1 | 2 | 4 | 8
export type CameraMode = 'north' | 'course'
export type FollowMode = 'course' | 'fleet' | 'boat'
export type TrailLength = 'off' | '10s' | '30s' | '60s' | 'leg' | 'race'
export type TrailColor = 'team' | 'speed' | 'vmg'
export type TrailScope = 'all' | 'highlighted' | 'none'
