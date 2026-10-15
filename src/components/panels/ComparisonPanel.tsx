import { compareBoats } from '../../engine/analytics'
import type { Competitor, ReplayFrame, ReplayManifest } from '../../types/replay'

export function ComparisonPanel({ replay, frame, primary, secondaryId, onSecondary }: { replay: ReplayManifest; frame: ReplayFrame; primary: Competitor; secondaryId: string | null; onSecondary: (id: string) => void }) {
  const picker = <label>Comparison boat B <select aria-label="Compare with" value={secondaryId ?? ''} onChange={(event) => onSecondary(event.target.value)}><option value="" disabled>Choose boat B</option>{replay.competitors.map((boat) => <option value={boat.id} key={boat.id}>{boat.team_code} · {boat.team_name}</option>)}</select></label>
  const secondary = replay.competitors.find((boat) => boat.id === secondaryId)
  if (!secondary || secondary.id === primary.id || !frame.boats[primary.id] || !frame.boats[secondary.id]) return <section aria-label="Head to head comparison" className="panel-block">{picker}<p>{secondary?.id === primary.id ? 'A and B are the same boat. Choose a different B to compare.' : 'Comparison unavailable: choose B with telemetry.'}</p></section>
  const metrics = compareBoats(frame.boats[primary.id], frame.boats[secondary.id], replay.course.axis_deg)
  return <section aria-label="Head to head comparison" className="panel-block">
    <div className="panel-title"><span className="eyebrow">HEAD TO HEAD</span><span className="panel-caption">B − A</span></div>
    <div className="compare-pickers"><div><span>A</span><strong style={{ color: primary.color }}>{primary.team_code}</strong></div>{picker}</div>
    <dl className="comparison-grid"><div><dt>SEPARATION</dt><dd>{metrics.separationM.toFixed(0)}<small>m</small></dd></div><div><dt>RACE PROGRESS B−A</dt><dd>{metrics.progressDeltaM >= 0 ? '+' : ''}{metrics.progressDeltaM.toFixed(0)}<small>m</small></dd></div><div><dt>ALONG CURRENT LEG</dt><dd>{metrics.alongLegM >= 0 ? '+' : ''}{metrics.alongLegM.toFixed(0)}<small>m</small></dd></div><div><dt>LATERAL OFFSET</dt><dd>{metrics.lateralM >= 0 ? '+' : ''}{metrics.lateralM.toFixed(0)}<small>m</small></dd></div><div><dt>SOG B−A</dt><dd>{metrics.speedDeltaKt >= 0 ? '+' : ''}{metrics.speedDeltaKt.toFixed(1)}<small>kt</small></dd></div><div><dt>VMG B−A</dt><dd>{metrics.vmgDeltaKt >= 0 ? '+' : ''}{metrics.vmgDeltaKt.toFixed(1)}<small>kt</small></dd></div><div><dt>CLOSURE</dt><dd>{metrics.closureMps >= 0 ? '+' : ''}{metrics.closureMps.toFixed(1)}<small>m/s</small></dd></div></dl>
    <p className="micro-note">Positive closure means the boats are approaching. Along-leg offset follows A’s current leg; race progress is cumulative.</p>
  </section>
}
