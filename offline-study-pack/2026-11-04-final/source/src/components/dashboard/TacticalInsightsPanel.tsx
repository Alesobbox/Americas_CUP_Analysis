import { evidenceText } from '../../utils/evidenceText'
import type { AnalysisDetail, TacticalInsights, TacticalSnapshot } from '../../types/analysis'

export function selectTacticalSnapshot(series: TacticalInsights | undefined, raceId: string, playhead: number): { snapshot: TacticalSnapshot | null; reason?: string } {
  if (!series || series.race_id !== raceId) return { snapshot: null, reason: 'Tactical insights are unavailable for this race.' }
  if (!Number.isFinite(playhead)) return { snapshot: null, reason: 'Replay time is unavailable.' }
  if (!series.snapshots.length && series.reason) return { snapshot: null, reason: series.reason }
  let low = 0, high = series.snapshots.length - 1, selected = -1
  while (low <= high) {
    const middle = Math.floor((low + high) / 2)
    if (series.snapshots[middle].timestamp_ms <= playhead) { selected = middle; low = middle + 1 }
    else high = middle - 1
  }
  if (selected < 0) return { snapshot: null, reason: 'No recorded tactical window has been reached at this playhead.' }
  const snapshot = series.snapshots[selected]
  if (playhead - snapshot.timestamp_ms > series.max_snapshot_age_ms || snapshot.window_end_ms > playhead) {
    return { snapshot: null, reason: 'Tactical window is stale at this playhead; no current insight is available.' }
  }
  return { snapshot }
}

export function TacticalInsightsPanel({ detail, raceId, playhead, embedded = false }: {
  detail: AnalysisDetail | null
  raceId: string
  playhead: number
  embedded?: boolean
}) {
  const series = detail?.race.id === raceId ? detail.tactical_insights : undefined
  const { snapshot, reason } = selectTacticalSnapshot(series, raceId, playhead)
  return <section className={`tactical-insights-panel${embedded ? ' embedded' : ' dashboard-workspace'}`} aria-label="Tactical insights" data-race-id={raceId} data-as-of={snapshot?.timestamp_ms ?? ''}>
    <div className="workspace-heading"><h2>Tactical insights</h2><span className="insight-status">RECORDED WIND</span></div>
    {!snapshot && <p className="insight-unavailable">{evidenceText(reason)}</p>}
    {snapshot && <>
      <p className="insight-evidence">As of {new Date(snapshot.timestamp_ms).toISOString().slice(11, 19)} UTC · direction window: {snapshot.coverage_s.toFixed(0)} s covered · {snapshot.sample_count} direction samples · {evidenceText(snapshot.quality)}</p>
      {snapshot.reason && <p className="insight-unavailable">{evidenceText(snapshot.reason)}</p>}
      <p className="insight-evidence">Speed window: {snapshot.speed_coverage_s.toFixed(0)} s covered · {snapshot.speed_sample_count} speed samples · {evidenceText(snapshot.speed_quality)}</p>
      {snapshot.speed_reason && <p className="insight-unavailable">{evidenceText(snapshot.speed_reason)}</p>}
      <div className="tactical-insight-grid">{snapshot.insights.map((insight) => <article className="tactical-insight" key={insight.id} data-insight-kind={insight.kind}>
        <h3>{evidenceText(insight.title)}</h3><p>{evidenceText(insight.detail)}</p><small>{evidenceText(insight.quality)} · {evidenceText(insight.source)}</small>
      </article>)}</div>
      <p className="insight-evidence">{evidenceText(snapshot.projection_reason)}</p>
      <details className="insight-provenance"><summary>Insight evidence and limits</summary><p>{evidenceText(series?.source)} · {series?.window_s} s lookback · {series?.projection_horizon_s} s projection horizon.</p><p>{evidenceText(series?.availability_basis)}</p><p>Observation window: {new Date(snapshot.window_start_ms).toISOString()} to {new Date(snapshot.window_end_ms).toISOString()}. Method: {series?.method_version}.</p>{Object.entries(series?.definitions ?? {}).map(([id, definition]) => <div key={id}><p><strong>{definition.label} ({definition.unit})</strong> · {evidenceText(definition.formula)}</p><p>Window: {evidenceText(definition.window)} · Denominator: {evidenceText(definition.denominator)} · Source: {evidenceText(definition.source)}</p></div>)}</details>
    </>}
  </section>
}
