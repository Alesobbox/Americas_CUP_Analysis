import type { AnalysisDetail, AnalysisIndex, AnalysisIndexRace } from '../types/analysis'

const finite = (value: unknown) => typeof value === 'number' && Number.isFinite(value)
const finiteOrNull = (value: unknown) => value === null || finite(value)
const nonnegative = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0
const count = (value: unknown) => nonnegative(value) && Number.isInteger(value)
const string = (value: unknown) => typeof value === 'string' && value.length > 0
const legList = (value: unknown): value is number[] =>
  Array.isArray(value) &&
  value.every((leg) => count(leg) && leg > 0) &&
  new Set(value).size === value.length
const performanceIds = [
  'upwind_vmg',
  'downwind_vmg',
  'upwind_speed',
  'downwind_speed',
  'tack_retention',
  'gybe_retention',
]

/** Optional additions retain compatibility with existing historical-2 exports. */
export function validateAnalysisEnhancements(detail: AnalysisDetail): void {
  for (const boat of detail.boats) {
    const performance = boat.performance
    if (
      performance &&
      (performance.schema_version !== '1.0' ||
        !string(performance.method_version) ||
        !finiteOrNull(performance.overall_index) ||
        performance.baseline_index !== 100 ||
        !Array.isArray(performance.notes) ||
        performance.notes.some((note) => !string(note)) ||
        !Array.isArray(performance.dimensions) ||
        performance.dimensions.length !== 6 ||
        new Set(performance.dimensions.map((dimension) => dimension.id)).size !== 6 ||
        performance.dimensions.some(
          (dimension) =>
            !string(dimension.id) ||
            !string(dimension.label) ||
            !performanceIds.includes(dimension.id) ||
            !finiteOrNull(dimension.index) ||
            !finiteOrNull(dimension.value) ||
            !finiteOrNull(dimension.peer_mean) ||
            dimension.unit !== (dimension.id.endsWith('_retention') ? '%' : 'kt') ||
            !count(dimension.peer_count) ||
            !count(dimension.sample_count) ||
            !nonnegative(dimension.coverage_s) ||
            dimension.higher_is_better !== true ||
            !legList(dimension.matched_legs) ||
            !string(dimension.quality) ||
            !string(dimension.formula) ||
            !string(dimension.denominator) ||
            !string(dimension.source)
        ))
    ) {
      throw new Error('Boat performance has an unsupported format')
    }
    if (performance) {
      const boatIds = new Set(detail.boats.map((entry) => entry.id))
      const invalid = () => {
        throw new Error('Boat performance evidence has an unsupported format')
      }
      for (const dimension of performance.dimensions) {
        if (
          (dimension.index !== null && dimension.index < 0) ||
          (dimension.excluded_legs &&
            (!Array.isArray(dimension.excluded_legs) ||
              dimension.excluded_legs.some(
                (entry) => !count(entry.leg) || entry.leg === 0 || !string(entry.reason)
              )))
        )
          invalid()
        if (dimension.leg_evidence !== undefined) {
          if (
            !Array.isArray(dimension.leg_evidence) ||
            !legList(dimension.leg_evidence.map((entry) => entry.leg)) ||
            dimension.leg_evidence.length !== dimension.matched_legs.length ||
            dimension.leg_evidence.some(
              (entry, index) =>
                entry.leg !== dimension.matched_legs[index] ||
                !nonnegative(entry.index) ||
                !nonnegative(entry.value) ||
                !nonnegative(entry.peer_mean) ||
                entry.peer_mean === 0 ||
                !count(entry.peer_count) ||
                entry.peer_count === 0 ||
                !count(entry.sample_count) ||
                entry.sample_count === 0 ||
                !nonnegative(entry.coverage_s) ||
                !Array.isArray(entry.peer_ids) ||
                entry.peer_ids.length !== entry.peer_count ||
                new Set(entry.peer_ids).size !== entry.peer_count ||
                entry.peer_ids.some((id) => id === boat.id || !boatIds.has(id)) ||
                ((entry.start_ms !== undefined || entry.end_ms !== undefined) &&
                  (!nonnegative(entry.start_ms) ||
                    !nonnegative(entry.end_ms) ||
                    entry.end_ms! <= entry.start_ms!)) ||
                (entry.peers !== undefined &&
                  (!Array.isArray(entry.peers) ||
                    entry.peers.length !== entry.peer_count ||
                    new Set(entry.peers.map((peer) => peer.id)).size !== entry.peer_count ||
                    entry.peers.some(
                      (peer) =>
                        !entry.peer_ids.includes(peer.id) ||
                        !string(peer.team_code) ||
                        !string(peer.team_name) ||
                        !nonnegative(peer.value) ||
                        !nonnegative(peer.coverage_s) ||
                        !count(peer.sample_count) ||
                        peer.sample_count === 0 ||
                        !nonnegative(peer.start_ms) ||
                        !nonnegative(peer.end_ms) ||
                        peer.end_ms <= peer.start_ms ||
                        !string(peer.quality)
                    ))) ||
                (entry.excluded_peers !== undefined &&
                  (!Array.isArray(entry.excluded_peers) ||
                    entry.excluded_peers.some(
                      (peer) =>
                        peer.id === boat.id ||
                        !boatIds.has(peer.id) ||
                        entry.peer_ids.includes(peer.id) ||
                        !string(peer.team_code) ||
                        !string(peer.reason)
                    ))) ||
                (entry.events !== undefined &&
                  (!Array.isArray(entry.events) ||
                    entry.events.some(
                      (event) =>
                        !nonnegative(event.timestamp_ms) ||
                        !nonnegative(event.entry_speed_kt) ||
                        event.entry_speed_kt === 0 ||
                        !nonnegative(event.minimum_speed_kt) ||
                        event.minimum_speed_kt > event.entry_speed_kt ||
                        !nonnegative(event.retention_pct) ||
                        !nonnegative(event.window_start_ms) ||
                        !nonnegative(event.window_end_ms) ||
                        event.window_end_ms <= event.window_start_ms ||
                        event.timestamp_ms < event.window_start_ms ||
                        event.timestamp_ms > event.window_end_ms
                    )))
            )
          )
            invalid()
        }
      }
      const scope = performance.scope
      if (
        scope &&
        (!legList(scope.expected_legs) ||
          !legList(scope.matched_legs) ||
          scope.expected_leg_count !== scope.expected_legs.length ||
          scope.matched_leg_count !== scope.matched_legs.length ||
          scope.matched_legs.some((leg) => !scope.expected_legs.includes(leg)) ||
          !count(scope.min_peer_count) ||
          !nonnegative(scope.covered_s) ||
          !Array.isArray(scope.excluded_legs) ||
          scope.excluded_legs.length + scope.matched_legs.length !== scope.expected_legs.length ||
          new Set(scope.excluded_legs.map((entry) => entry.leg)).size !==
            scope.excluded_legs.length ||
          scope.excluded_legs.some(
            (entry) =>
              !scope.expected_legs.includes(entry.leg) ||
              scope.matched_legs.includes(entry.leg) ||
              !string(entry.reason)
          ))
      )
        invalid()
    }
    if (
      boat.debrief &&
      (boat.debrief.schema_version !== '1.0' ||
        !string(boat.debrief.method_version) ||
        !Array.isArray(boat.debrief.items) ||
        boat.debrief.items.some(
          (item) =>
            !string(item.id) ||
            !string(item.title) ||
            !string(item.detail) ||
            !nonnegative(item.timestamp_ms) ||
            !nonnegative(item.value) ||
            !string(item.unit) ||
            !string(item.source) ||
            !string(item.quality) ||
            !['leg_deficit', 'manoeuvre_loss'].includes(item.kind)
        ))
    ) {
      throw new Error('Team debrief has an unsupported format')
    }
  }
  const tactical = detail.tactical_insights
  if (
    tactical &&
    (tactical.schema_version !== '1.0' ||
      !string(tactical.method_version) ||
      tactical.race_id !== detail.race.id ||
      !string(tactical.source) ||
      !string(tactical.availability_basis) ||
      !nonnegative(tactical.window_s) ||
      !nonnegative(tactical.projection_horizon_s) ||
      !nonnegative(tactical.snapshot_interval_ms) ||
      tactical.snapshot_interval_ms === 0 ||
      !nonnegative(tactical.max_snapshot_age_ms) ||
      !Array.isArray(tactical.snapshots) ||
      tactical.snapshots.some(
        (snapshot, index) =>
          !nonnegative(snapshot.timestamp_ms) ||
          !nonnegative(snapshot.window_start_ms) ||
          !nonnegative(snapshot.window_end_ms) ||
          snapshot.window_start_ms > snapshot.window_end_ms ||
          snapshot.window_end_ms > snapshot.timestamp_ms ||
          (index > 0 && tactical.snapshots[index - 1].timestamp_ms >= snapshot.timestamp_ms) ||
          !nonnegative(snapshot.coverage_s) ||
          !count(snapshot.sample_count) ||
          !string(snapshot.source) ||
          !['derived', 'unavailable'].includes(snapshot.quality) ||
          !nonnegative(snapshot.speed_coverage_s) ||
          !count(snapshot.speed_sample_count) ||
          !['derived', 'unavailable'].includes(snapshot.speed_quality) ||
          !(snapshot.speed_reason === null || string(snapshot.speed_reason)) ||
          !finiteOrNull(snapshot.direction_change_deg) ||
          !finiteOrNull(snapshot.direction_rate_deg_per_min) ||
          !finiteOrNull(snapshot.speed_change_kt) ||
          !finiteOrNull(snapshot.projection_change_deg) ||
          !string(snapshot.projection_reason) ||
          !Array.isArray(snapshot.insights) ||
          snapshot.insights.some(
            (insight) =>
              !string(insight.id) ||
              !string(insight.title) ||
              !string(insight.detail) ||
              !string(insight.quality) ||
              !string(insight.source) ||
              !string(insight.kind)
          )
      ))
  ) {
    throw new Error('Tactical insights have an unsupported format')
  }
  const validBootstrap = (
    interval:
      | { value: number; ci_low_kt: number; ci_high_kt: number; bootstrap_se_kt: number }
      | null
      | undefined
  ) =>
    interval == null ||
    (finite(interval.value) &&
      finite(interval.ci_low_kt) &&
      finite(interval.ci_high_kt) &&
      nonnegative(interval.bootstrap_se_kt) &&
      interval.ci_low_kt <= interval.value + 1e-6 &&
      interval.value <= interval.ci_high_kt + 1e-6)
  for (const boat of detail.boats) {
    if (boat.polar) {
      const p = boat.polar
      if (
        p.schema_version !== '1.0' ||
        !string(p.method_version) ||
        !['derived', 'unavailable'].includes(p.quality) ||
        !count(p.steady_sample_count) ||
        !nonnegative(p.steady_coverage_s) ||
        !validBootstrap(p.sog_residual_kt) ||
        !validBootstrap(p.wind_vmg_residual_kt)
      ) {
        throw new Error('Boat polar residuals have an unsupported format')
      }
    }
  }
  const polar = detail.polar_analysis
  if (
    polar &&
    (polar.schema_version !== '1.0' ||
      !string(polar.method_version) ||
      polar.race_id !== detail.race.id ||
      !['derived', 'unavailable'].includes(polar.quality) ||
      !Array.isArray(polar.caveats))
  ) {
    throw new Error('Observed polar analysis has an unsupported format')
  }
}

export async function loadAnalysisIndex(signal?: AbortSignal): Promise<AnalysisIndex> {
  const response = await fetch('/data/analysis/index.json', { signal })
  if (!response.ok) throw new Error(`Analysis archive is unavailable (${response.status})`)
  if (!response.headers.get('content-type')?.includes('json'))
    throw new Error('Analysis archive did not return JSON')
  const index = (await response.json()) as AnalysisIndex
  if (
    index.schema_version !== '2.0' ||
    !Array.isArray(index.races) ||
    !Array.isArray(index.histories) ||
    (index.polar_model &&
      (index.polar_model.schema_version !== '1.0' ||
        !string(index.polar_model.method_version) ||
        !Array.isArray(index.polar_model.team_residuals) ||
        !index.polar_model.validation?.leave_one_day_out ||
        !index.polar_model.validation?.leave_one_race_out))
  ) {
    throw new Error('Analysis archive has an unsupported format')
  }
  return index
}

export async function loadAnalysisDetail(
  race: Pick<AnalysisIndexRace, 'id' | 'analysis_file'>,
  signal?: AbortSignal
): Promise<AnalysisDetail> {
  if (!/^analysis\/[a-zA-Z0-9_-]+\.json$/.test(race.analysis_file)) {
    throw new Error('Detailed analysis is unavailable for this race')
  }
  const response = await fetch(`/data/${race.analysis_file}`, { signal })
  if (!response.ok) throw new Error(`Detailed analysis is unavailable (${response.status})`)
  if (!response.headers.get('content-type')?.includes('json'))
    throw new Error('Detailed analysis did not return JSON')
  const detail = (await response.json()) as AnalysisDetail
  if (
    detail.schema_version !== '2.0' ||
    detail.race?.id !== race.id ||
    !Array.isArray(detail.boats) ||
    !detail.definitions
  ) {
    throw new Error('Detailed analysis does not match the selected race')
  }
  if (
    detail.event_feed &&
    (detail.event_feed.schema_version !== '1.0' ||
      !Array.isArray(detail.event_feed.events) ||
      detail.event_feed.events.some(
        (event) =>
          !event.id ||
          !Number.isFinite(event.timestamp_ms) ||
          !event.type ||
          !event.source ||
          !event.quality
      ))
  ) {
    throw new Error('Analysis event feed has an unsupported format')
  }
  validateAnalysisEnhancements(detail)
  return detail
}
