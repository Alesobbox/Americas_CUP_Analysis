export type CanonicalChannel = 'currents' | 'waves' | 'air_temperature' | 'water_temperature'

export interface ChannelProvenance {
  channel: CanonicalChannel
  provider: string
  provider_id: string
  dataset: string
  dataset_version: string
  variables: string[]
  native_spatial_support: Record<string, unknown>
  native_temporal_support: string
  averaging_bounds: Record<string, unknown>
  depth_m: number | null
  temperature_convention: string | null
  units: Record<string, string>
  mask_handling: string
  interpolation: string
  quality_status: 'available' | 'partial' | 'fallback' | 'unavailable' | 'excluded'
  request_spec: Record<string, unknown>
  returned_coordinates: Record<string, unknown>
  retrieval_time_utc: string
  raw_subset_sha256: string
  metadata_sha256: string
  valid_time_bounds: Record<string, unknown>
  initialization_time_utc: string
  availability_time_utc: string
  product_classification:
    'retrospective_reanalysis' | 'archived_forecast' | 'climatological_scenario'
  missingness: { missing_count: number; total_count: number }
  fallback_used: boolean
  fallback_reason: string | null
  distance_to_wet_cell_m?: unknown
}

export interface EnvironmentSeriesV2 {
  time_ms: number[]
  current_u_mps: Array<number | null>
  current_v_mps: Array<number | null>
  current_speed_mps: Array<number | null>
  current_dir_towards_deg: Array<number | null>
  wave_height_m: Array<number | null>
  wave_period_s: Array<number | null>
  wave_dir_from_deg: Array<number | null>
  air_temperature_c: Array<number | null>
  water_temperature_c: Array<number | null>
}

export interface RaceEnvironmentV2 {
  schema_version: 'environment-2'
  registry_version: string
  race_id: string
  context: string
  bundle_sha256: string
  bundle_relpath: string
  boats_relpath: string | null
  location: {
    latitude: number
    longitude: number
    bbox: Record<string, unknown>
  }
  window: {
    window_start_ms: number
    window_end_ms: number
    start_utc: string
    end_utc: string
  }
  channels: Record<CanonicalChannel, ChannelProvenance>
  course_centre: EnvironmentSeriesV2
}

export interface EnvironmentSourceV1 {
  provider: 'Open-Meteo'
  product: 'historical_model'
  request_url: string
  response_sha256: string
  retrieved_at: string
  grid_location: { latitude: number; longitude: number }
  response_file: string
}

export interface RaceEnvironmentV1 {
  schema_version: 'environment-1'
  context: 'historical_replay_only'
  race_id: string
  requested_location: { latitude: number; longitude: number }
  units: {
    air_temperature_c: '°C'
    wave_height_m: 'm'
    water_temperature_c: '°C'
    time_ms: 'Unix milliseconds UTC'
  }
  hourly: {
    time_ms: number[]
    air_temperature_c: Array<number | null>
    wave_height_m: Array<number | null>
    water_temperature_c: Array<number | null>
  }
  sources: Partial<Record<'air' | 'marine', EnvironmentSourceV1>>
  errors: Partial<Record<'air' | 'marine', string>>
}

export type RaceEnvironment = RaceEnvironmentV1 | RaceEnvironmentV2

export type EnvironmentField =
  | 'current_speed_mps'
  | 'current_dir_towards_deg'
  | 'wave_height_m'
  | 'wave_period_s'
  | 'wave_dir_from_deg'
  | 'air_temperature_c'
  | 'water_temperature_c'

export interface EnvironmentalReading {
  text: string
  title: string
  modeled: boolean
}

export interface ProviderLink {
  label: string
  url: string
}
