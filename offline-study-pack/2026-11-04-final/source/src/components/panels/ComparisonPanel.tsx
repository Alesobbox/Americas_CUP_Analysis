import { compareBoats } from '../../engine/analytics'
import type { Competitor, ReplayFrame, ReplayManifest } from '../../types/replay'

export function ComparisonPanel({ replay, frame, primary, secondaryId, onSecondary, onPrimary }: { replay: ReplayManifest; frame: ReplayFrame; primary: Competitor; secondaryId: string | null; onSecondary: (id: string) => void; onPrimary?: (id: string) => void }) {
  const secondary = replay.competitors.find((boat) => boat.id === secondaryId)
  const options = replay.competitors.map((boat) => <option value={boat.id} key={boat.id}>{boat.team_code} · {boat.team_name}</option>)
  const selectors = <div className="compare-pickers"><div className="compare-boat-identity"><span className="compare-boat-letter">A</span><label>Primary boat A<select aria-label="Primary boat A" value={primary.id} onChange={(event) => onPrimary?.(event.target.value)}>{options}</select></label><i style={{ background: primary.color }} /></div><div className="compare-boat-identity"><span className="compare-boat-letter">B</span><label>Comparison boat B<select aria-label="Compare with" value={secondaryId ?? ''} onChange={(event) => onSecondary(event.target.value)}><option value="" disabled>Choose boat B</option>{options}</select></label><i style={{ background: secondary?.color ?? 'var(--border-subtle)' }} /></div></div>
  if (!secondary || secondary.id === primary.id || !frame.boats[primary.id] || !frame.boats[secondary.id]) return <section aria-label="Head to head comparison" className="panel-block compare-panel">{selectors}<p className="comparison-empty">{secondary?.id === primary.id ? 'A and B are the same boat. Choose a different B to compare.' : 'Comparison unavailable: choose B with telemetry.'}</p></section>
  const a = frame.boats[primary.id], b = frame.boats[secondary.id]
  const metrics = compareBoats(a, b, replay.course.axis_deg)
  const signed = (value: number, digits = 0) => Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${value.toFixed(digits)}` : 'Unavailable'
  const value = (number: number) => Number.isFinite(number) ? number.toFixed(1) : 'Unavailable'
  return <section aria-label="Head to head comparison" className="panel-block compare-panel">
    {selectors}
    <table className="compare-values" aria-label="Boat measurements at the playhead"><thead><tr><th>{primary.team_code}</th><th>Measurement</th><th>{secondary.team_code}</th><th>B − A</th></tr></thead><tbody><tr><td>{value(a.sog)}</td><th>Speed <small>kt</small></th><td>{value(b.sog)}</td><td>{signed(metrics.speedDeltaKt, 1)}</td></tr><tr><td>{value(a.vmg)}</td><th>VMG <small>kt</small></th><td>{value(b.vmg)}</td><td>{signed(metrics.vmgDeltaKt, 1)}</td></tr></tbody></table>
    <div className="pairwise-heading"><h3>Between the boats</h3><span>Signed offsets: B − A</span></div>
    <dl className="comparison-grid"><div><dt>SEPARATION</dt><dd>{metrics.separationM.toFixed(0)}<small>m</small></dd></div><div><dt>RACE PROGRESS B−A</dt><dd>{signed(metrics.progressDeltaM)}<small>m</small></dd></div><div><dt>ALONG CURRENT LEG</dt><dd>{signed(metrics.alongLegM)}<small>m</small></dd></div><div><dt>LATERAL OFFSET</dt><dd>{signed(metrics.lateralM)}<small>m</small></dd></div><div><dt>CLOSURE</dt><dd>{signed(metrics.closureMps, 1)}<small>m/s</small></dd></div></dl>
    <p className="micro-note">Positive closure means the boats are approaching. Along-leg offset follows A’s current leg; race progress is cumulative. Changing A preserves your explicit B selection.</p>
  </section>
}
