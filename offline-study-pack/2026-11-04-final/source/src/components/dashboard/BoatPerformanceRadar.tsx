import { useId, useState } from 'react'
import type { AnalysisDetailBoat, PerformanceDimension, PerformanceLegEvidence } from '../../types/analysis'
import { evidenceText } from '../../utils/evidenceText'

const available = (value: number | null | undefined): value is number => typeof value === 'number' && Number.isFinite(value)
const display = (value: number | null | undefined, unit = '', digits = 1) => available(value) ? value.toFixed(digits) + (unit ? ' ' + unit : '') : 'Unavailable'
const difference = (value: number | null | undefined) => available(value) ? value - 100 : null
const differenceLabel = (value: number | null | undefined) => {
  const delta = difference(value)
  return delta === null ? 'Unavailable' : `${delta > 0 ? '+' : delta < 0 ? '−' : ''}${Math.abs(delta).toFixed(1)}%`
}
const exact = (value: number | null | undefined) => available(value) ? String(value) : 'Unavailable'
const ids = ['upwind_vmg', 'downwind_vmg', 'upwind_speed', 'downwind_speed', 'tack_retention', 'gybe_retention']
const labels: Record<string, string> = { upwind_vmg: 'Upwind course VMG', downwind_vmg: 'Downwind course VMG', upwind_speed: 'Upwind speed', downwind_speed: 'Downwind speed', tack_retention: 'Tack retention', gybe_retention: 'Gybe retention' }
const labelFor = (dimension: PerformanceDimension) => labels[dimension.id] ?? dimension.label
export interface PerformanceReview { raceId: string; boatId: string; leg: number; start_ms: number; end_ms: number }

/** Select exported values; aggregating metrics remains Python's responsibility. */
export function performanceView(dimension: PerformanceDimension, scope: string) {
  if (scope === 'all') return dimension
  const leg = dimension.leg_evidence?.find((entry) => entry.leg === Number(scope))
  return leg ? { ...dimension, ...leg, matched_legs: [leg.leg], reason: undefined } : {
    ...dimension, index: null, value: null, peer_mean: null, peer_count: 0, coverage_s: 0, sample_count: 0,
    matched_legs: [], quality: 'unavailable', reason: dimension.excluded_legs?.find((entry) => entry.leg === Number(scope))?.reason
      ?? 'No qualifying comparison for this axis on leg ' + scope + '.',
  }
}

/** Drawing geometry only: a stable full-range domain for every boat in the race. */
export function performanceChartMaximum(boats: AnalysisDetailBoat[]) {
  const scores = boats.flatMap((boat) => boat.performance?.dimensions.flatMap((dimension) =>
    [dimension.index, ...(dimension.leg_evidence?.map((entry) => entry.index) ?? [])]) ?? []).filter(available)
  return Math.max(150, Math.ceil(Math.max(150, ...scores) / 25) * 25)
}

export function BoatPerformanceRadar({ boat, raceId = '', boats = [], replayAvailable = false, onReviewLeg }: {
  boat: AnalysisDetailBoat; raceId?: string; boats?: AnalysisDetailBoat[]; replayAvailable?: boolean
  onReviewLeg?: (review: PerformanceReview) => void
}) {
  const titleId = useId(), descriptionId = useId(), evidenceId = useId()
  const context = raceId + ':' + boat.id
  const [selection, setSelection] = useState({ context, axis: 'upwind_vmg', scope: 'all' })
  const current = selection.context === context ? selection : { context, axis: 'upwind_vmg', scope: 'all' }
  const selectAxis = (axis: string) => setSelection({ ...current, context, axis })
  const performance = boat.performance
  if (!performance) return <section className="analysis-section" aria-label="Boat performance"><div className="analysis-section-heading"><h4>Boat performance</h4></div><p className="analysis-empty">Peer-relative performance is unavailable in this export.</p></section>
  const dimensions = [...performance.dimensions].sort((a, b) => ids.indexOf(a.id) - ids.indexOf(b.id))
  const selected = dimensions.find((dimension) => dimension.id === current.axis) ?? dimensions[0]
  const views = dimensions.map((dimension) => performanceView(dimension, current.scope))
  const selectedView = performanceView(selected, current.scope)
  const legEvidence = (selected.leg_evidence ?? []).filter((entry) => current.scope === 'all' || entry.leg === Number(current.scope))
  const expectedLegs = performance.scope?.expected_legs ?? boat.legs?.map((leg) => leg.leg) ?? []
  const matchedLegs = performance.scope?.matched_legs ?? [...new Set(dimensions.slice(0, 2).flatMap((dimension) => dimension.matched_legs))]
  const maximum = performanceChartMaximum(boats.length ? boats : [boat])
  // Shared drawing domain for differences; no historical metric is aggregated here.
  const differenceScores = (boats.length ? boats : [boat]).flatMap((entry) => entry.performance?.dimensions.flatMap((dimension) => [dimension.index, ...(dimension.leg_evidence?.map((leg) => leg.index) ?? [])]) ?? []).filter(available)
  const differenceExtent = Math.max(10, Math.ceil(Math.max(0, ...differenceScores.map((score) => Math.abs(score - 100))) / 10) * 10)
  const center = 180, radius = 108
  const position = (index: number, score: number, extra = 0) => {
    const angle = index / dimensions.length * Math.PI * 2 - Math.PI / 2
    const length = radius * Math.max(0, score) / maximum + extra
    return { x: center + Math.cos(angle) * length, y: center + Math.sin(angle) * length }
  }
  const points = views.map((dimension, index) => available(dimension.index) ? position(index, dimension.index) : null)
  const complete = points.length >= 3 && points.every((point) => point !== null)
  const detailScores = [selectedView.index, ...legEvidence.map((entry) => entry.index)].filter(available)
  const detailMinimum = Math.floor(Math.min(95, ...detailScores) / 5) * 5
  const detailMaximum = Math.ceil(Math.max(105, ...detailScores) / 5) * 5
  const detailX = (score: number) => 35 + (score - detailMinimum) / (detailMaximum - detailMinimum) * 330
  const review = (entry: PerformanceLegEvidence) => {
    const leg = boat.legs?.find((candidate) => candidate.leg === entry.leg)
    const start = entry.start_ms ?? leg?.start_ms, end = entry.end_ms ?? leg?.end_ms
    return available(start) && available(end) && end > start ? { raceId, boatId: boat.id, leg: entry.leg, start_ms: start, end_ms: end } : null
  }
  return <section className="analysis-section performance-inspector" aria-label="Boat performance" data-performance-context={context}>
    <div className="analysis-section-heading"><h4>Boat performance</h4><span>100 = other eligible boats’ mean</span></div>
    <p className="analysis-inline-facts">{boat.team_code} · retrospective observed values on matching completed legs. These indexes describe this comparison, not intrinsic yacht or crew ability.</p>
    <div className="performance-inspector-controls"><label>Leg scope <select aria-label="Performance leg scope" value={current.scope} onChange={(event) => setSelection({ ...current, context, scope: event.target.value })}><option value="all">All comparable legs</option>{expectedLegs.map((leg) => <option key={leg} value={leg}>Leg {leg}</option>)}</select></label><p role="status">{matchedLegs.length} of {expectedLegs.length} course legs compared{performance.scope ? ' · at least ' + performance.scope.min_peer_count + ' peers per supported comparison · ' + performance.scope.covered_s.toFixed(3) + ' source-covered seconds' : ''}. {current.scope === 'all' ? 'Equal-weight matched-leg indexes.' : 'Showing comparable leg ' + current.scope + ' values.'}</p></div>
    {!!performance.scope?.excluded_legs.length && <details className="performance-scope-limits"><summary>Excluded course legs ({performance.scope.excluded_legs.length})</summary><ul>{performance.scope.excluded_legs.map((entry) => <li key={entry.leg}>Leg {entry.leg}: {evidenceText(entry.reason)}</li>)}</ul></details>}
    <div className="performance-comparison-heading"><h5>{boat.team_code} against the other boats</h5><p>Each difference compares this boat with the eligible others on matching completed legs.</p></div>
    <div className="performance-comparison-legend" role="group" aria-label="Performance comparison legend"><span><i className="performance-selected-key" aria-hidden="true" /><strong>{boat.team_code}</strong><span>selected boat</span></span><span><i className="performance-peer-key" aria-hidden="true" /><span>Other boats’ mean</span><strong>100</strong></span></div>
    <div className="performance-axis-controls" role="group" aria-label="Inspect a performance dimension">{dimensions.map((dimension, index) => {
      const delta = difference(views[index].index)
      const position = delta === null ? 50 : 50 + delta / differenceExtent * 50
      return <button type="button" key={dimension.id} aria-label={'Inspect ' + labelFor(dimension)} aria-pressed={selected.id === dimension.id} aria-controls={evidenceId} data-axis-id={dimension.id} onClick={() => selectAxis(dimension.id)}>
        <span className="performance-difference-label">{labelFor(dimension)}</span><strong className="performance-difference-value" data-index-difference={delta ?? ''}>{differenceLabel(views[index].index)}</strong>
        <span className="performance-difference-track" aria-hidden="true">{delta !== null && <i style={{ left: `${Math.min(50, position)}%`, width: `${Math.abs(position - 50)}%` }} />}{delta !== null && <b style={{ left: `${position}%` }} />}</span>
        <span className="performance-difference-context">{delta === null ? 'No comparable value' : delta === 0 ? 'Equal to the other boats’ mean' : `${delta > 0 ? 'Above' : 'Below'} the other boats’ mean`}</span><span className="performance-difference-index">Index {display(views[index].index)}</span>
      </button>
    })}</div>
    <p className="performance-difference-scale">Difference scale −{differenceExtent}% to +{differenceExtent}%, shared across this race. The centre is the other boats’ mean. Select a row for its exact values and leg evidence.</p>
    <div className="performance-radar-layout">
      <div className="performance-radar-figure">
        <svg className="performance-radar" viewBox="0 0 360 360" role="img" aria-labelledby={titleId + ' ' + descriptionId} data-chart-maximum={maximum}>
          <title id={titleId}>{boat.team_code + " boat performance relative to other boats"}</title><desc id={descriptionId}>Circular graph with shared race scale zero to {maximum}. Dashed circle: peer baseline 100. Solid blue profile: the selected boat. Activate a dimension using the difference controls to inspect exact exported evidence. Missing dimensions leave gaps.</desc>
          {[50, 100, maximum].map((score) => <g key={score}><circle cx={center} cy={center} r={radius * score / maximum} className={score === 100 ? 'radar-baseline' : 'radar-ring'} /><text x={center + 5} y={center - radius * score / maximum + 12} className="radar-tick">{score}</text></g>)}
          {dimensions.map((dimension, index) => { const edge = position(index, maximum); const label = position(index, maximum, 35); return <g key={dimension.id} className={dimension.id === selected.id ? 'performance-axis-selected' : ''} onClick={() => selectAxis(dimension.id)}><line x1={center} y1={center} x2={edge.x} y2={edge.y} className="radar-axis" /><text x={label.x} y={label.y} textAnchor="middle" dominantBaseline="middle" className="radar-label">{labelFor(dimension).replace(' course', '')}</text></g> })}
          {complete && <polygon points={points.map((point) => point!.x + ',' + point!.y).join(' ')} className="radar-fill" />}
          {points.map((point, index) => { const next = points[(index + 1) % points.length]; return point && <g key={dimensions[index].id} onClick={() => selectAxis(dimensions[index].id)} className="performance-chart-point">{next && <line x1={point.x} y1={point.y} x2={next.x} y2={next.y} className="radar-score-line" />}<circle cx={point.x} cy={point.y} r={13} className="performance-point-target" /><circle cx={point.x} cy={point.y} r={dimensions[index].id === selected.id ? 6 : 4} className="radar-score-point" data-score={views[index].index ?? ''}><title>{labelFor(dimensions[index]) + ": " + display(views[index].index)}</title></circle>{dimensions[index].id === selected.id && <text x={Math.abs(point.x - center) < 1 ? point.x - 14 : point.x + (point.x > center ? -10 : 10)} y={point.y - 12} textAnchor={Math.abs(point.x - center) < 1 || point.x > center ? "end" : "start"} className="performance-active-score">{display(views[index].index)}</text>}</g> })}
        </svg>
        <p className="analysis-micro-note">Shared race chart scale 0–{maximum}; all exported scores fit. Baseline 100. Missing or out-of-scope dimensions remain gaps.</p>

        <p className="performance-overall">Heuristic profile summary <strong>{current.scope === 'all' ? display(performance.overall_index) : 'Not applicable to a single leg'}</strong></p><p className="analysis-micro-note">Equal weights across six correlated dimensions; supported scope can cover only part of a race. This is not a validated ability score.</p>{performance.reason && <p className="analysis-micro-note">{evidenceText(performance.reason)}</p>}
      </div>
      <div className="analysis-table-wrap performance-evidence"><table className="analysis-table" aria-label="Boat performance evidence"><thead><tr><th>DIMENSION</th><th>INDEX</th><th>VS OTHERS</th><th>BOAT</th><th>OTHERS’ MEAN</th><th>PEERS</th><th>COVERAGE / OBSERVATIONS</th><th>MATCHED LEGS</th></tr></thead><tbody>{views.map((dimension) => <tr key={dimension.id} className={dimension.id === selected.id ? 'performance-evidence-selected' : ''}><td><button type="button" className="performance-row-select" onClick={() => selectAxis(dimension.id)}>{labelFor(dimension)}</button><small>{evidenceText(dimension.quality)}{dimension.reason ? ' · ' + evidenceText(dimension.reason) : ''}</small></td><td>{display(dimension.index)}</td><td className="performance-evidence-difference">{differenceLabel(dimension.index)}</td><td>{display(dimension.value, dimension.unit, 3)}</td><td>{display(dimension.peer_mean, dimension.unit, 3)}</td><td>{dimension.peer_count}</td><td>{dimension.coverage_s.toFixed(3)} s / {dimension.sample_count} {dimension.unit === '%' ? 'events' : 'legs'}</td><td>{dimension.matched_legs.length ? dimension.matched_legs.join(', ') : '—'}</td></tr>)}</tbody></table></div>
    </div>
    <section className="performance-pinned-evidence" id={evidenceId} aria-label="Pinned performance evidence" data-inspect-axis={selected.id} data-inspect-leg={current.scope} data-exported-index={selectedView.index ?? ''}>
      <h5>{labelFor(selected)} · {current.scope === 'all' ? 'all comparable legs' : 'leg ' + current.scope}</h5>
      {available(selectedView.index) ? <><p className="performance-selected-reading">{boat.team_code} is <strong>{differenceLabel(selectedView.index)}</strong> versus the other boats’ mean · exported index {display(selectedView.index)} · own value {display(selectedView.value, selected.unit, 3)} · other-boats mean {display(selectedView.peer_mean, selected.unit, 3)}</p><svg className="performance-detail-plot" viewBox="0 0 400 76" role="img" aria-label={labelFor(selected) + ' focused index detail'} data-domain-minimum={detailMinimum} data-domain-maximum={detailMaximum}><line x1="35" x2="365" y1="38" y2="38" /><line x1={detailX(100)} x2={detailX(100)} y1="20" y2="54" className="performance-detail-baseline" /><text x="35" y="70">{detailMinimum}</text><text x={detailX(100)} y="14" textAnchor="middle">100 · peers</text><text x="365" y="70" textAnchor="end">{detailMaximum}</text><circle cx={detailX(selectedView.index)} cy="38" r="6" className="performance-focused-score" data-focused-score={selectedView.index} /><text x={detailX(selectedView.index)} y="58" textAnchor="middle">{display(selectedView.index)}</text></svg></> : <p className="analysis-empty">{evidenceText(selectedView.reason) || 'No supported value in this scope.'}</p>}
      <p className="analysis-micro-note">The aggregate is the mean of the exported per-leg ratios below. Dividing the two aggregate raw means can give a different result. Decimal detail shows arithmetic, not measurement certainty.</p>
      <details><summary>Full exported arithmetic</summary><dl className="performance-exact-values"><dt>Index</dt><dd>{exact(selectedView.index)}</dd><dt>Boat value ({selected.unit})</dt><dd>{exact(selectedView.value)}</dd><dt>Other-boats mean ({selected.unit})</dt><dd>{exact(selectedView.peer_mean)}</dd></dl></details>
      {!legEvidence.length && <p className="analysis-empty">No per-leg evidence is available for this axis and scope.</p>}
      {legEvidence.map((entry) => { const interval = review(entry); return <details className="performance-leg-evidence" key={entry.leg}><summary>Leg {entry.leg} · index {display(entry.index)} · {entry.peer_count} peers · {entry.coverage_s.toFixed(3)} s covered</summary><p>Exact exported calculation: 100 × {exact(entry.value)} / {exact(entry.peer_mean)} = {exact(entry.index)}. {entry.sample_count} {selected.unit === '%' ? 'qualifying events' : 'completed leg'}.</p><p>Own interval: {interval ? new Date(interval.start_ms).toISOString() + ' to ' + new Date(interval.end_ms).toISOString() : 'unavailable'}.</p><button type="button" className="analysis-replay-link" disabled={!replayAvailable || !interval || !onReviewLeg} data-performance-race={raceId} data-performance-boat={boat.id} data-performance-start={interval?.start_ms} data-performance-end={interval?.end_ms} onClick={() => { if (interval) onReviewLeg?.(interval) }}>Review leg {entry.leg} in replay</button><div className="analysis-table-wrap"><table className="analysis-table" aria-label={'Leg ' + entry.leg + ' peer evidence'}><thead><tr><th>PEER</th><th>EXPORTED VALUE</th><th>COVERAGE</th><th>OBSERVATIONS</th><th>INTERVAL</th></tr></thead><tbody>{entry.peer_ids.map((peerId) => { const peer = entry.peers?.find((candidate) => candidate.id === peerId); const identity = boats.find((candidate) => candidate.id === peerId); return <tr key={peerId}><td>{peer?.team_code ?? identity?.team_code ?? peerId}<small>{peer?.team_name ?? identity?.team_name}</small></td><td>{peer ? exact(peer.value) + ' ' + selected.unit : 'Not included in legacy evidence'}</td><td>{peer ? peer.coverage_s.toFixed(3) + ' s · ' + evidenceText(peer.quality) : 'Unavailable'}</td><td>{peer?.sample_count ?? 'Unavailable'}</td><td>{peer ? new Date(peer.start_ms).toISOString().slice(11, 23) + '–' + new Date(peer.end_ms).toISOString().slice(11, 23) + ' UTC' : 'Unavailable'}</td></tr> })}</tbody></table></div>{!!entry.excluded_peers?.length && <ul>{entry.excluded_peers.map((peer) => <li key={peer.id}>{peer.team_code}: excluded · {evidenceText(peer.reason)}</li>)}</ul>}{!!entry.events?.length && <div className="analysis-table-wrap"><table className="analysis-table" aria-label={'Leg ' + entry.leg + ' qualifying manoeuvres'}><thead><tr><th>EVENT UTC</th><th>ENTRY SOG</th><th>MINIMUM SOG</th><th>RETENTION</th></tr></thead><tbody>{entry.events.map((event, index) => <tr key={String(event.timestamp_ms) + ':' + index}><td>{new Date(event.timestamp_ms).toISOString().slice(11, 23)}</td><td>{event.entry_speed_kt} kt</td><td>{event.minimum_speed_kt} kt</td><td>{exact(event.retention_pct)} %</td></tr>)}</tbody></table></div>}</details> })}
    </section>
    <details className="analysis-definitions"><summary>Performance formulas and comparison limits</summary>{performance.notes.map((note) => <p key={note}>{evidenceText(note)}</p>)}{dimensions.map((dimension) => <div key={dimension.id}><h5>{labelFor(dimension)}</h5><p>{evidenceText(dimension.formula)}</p><p>Denominator: {evidenceText(dimension.denominator)}</p><p>Source: {evidenceText(dimension.source)}</p></div>)}<small>Method: {performance.method_version}</small></details>
  </section>
}

