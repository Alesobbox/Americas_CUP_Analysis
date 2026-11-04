import type { BoatScaleMode, Competitor, TrailColor, TrailLength, TrailScope } from '../../types/replay'
import './boat-course-controls.css'

export function BoatCourseControls(p: {
  boats: Competitor[]; selectedId: string | null; comparisonId: string | null; onComparison: (id: string) => void
  scaleMode: BoatScaleMode; onScaleMode: (value: BoatScaleMode) => void
  trailScope: TrailScope; onTrailScope: (value: TrailScope) => void
  trailLength: TrailLength; onTrailLength: (value: TrailLength) => void
  trailColor: TrailColor; onTrailColor: (value: TrailColor) => void
  showVmgLabels: boolean; onShowVmgLabels: (value: boolean) => void
  highlightComparison: boolean; onHighlightComparison: (value: boolean) => void
}) {
  const primary = p.boats.find((boat) => boat.id === p.selectedId)
  return <div className="boat-course-controls" aria-label="Boat visibility and trails">
    <div className="boat-course-options">
      <label>Boat size<select aria-label="Course boat size" value={p.scaleMode} onChange={(event) => p.onScaleMode(event.target.value as BoatScaleMode)}><option value="enhanced">Easy to see</option><option value="true">True metric scale</option></select></label>
      <label>Trails<select aria-label="Trail visibility" value={p.trailLength === 'off' ? 'none' : p.trailScope} onChange={(event) => { const scope = event.target.value as TrailScope; p.onTrailScope(scope); if (scope !== 'none' && p.trailLength === 'off') p.onTrailLength('30s') }}><option value="all">All boats</option><option value="highlighted">Highlighted boats</option><option value="none">No trails</option></select></label>
      <label title="VMG trail colour uses its magnitude; VMG labels retain the signed course-axis value.">Trail colour<select aria-label="Course trail colour" value={p.trailColor} onChange={(event) => p.onTrailColor(event.target.value as TrailColor)}><option value="team">Team</option><option value="speed">Speed</option><option value="vmg">VMG</option></select></label>
      <label className="course-checkbox" title="Signed VMG along the fixed course axis, from replay telemetry."><input type="checkbox" checked={p.showVmgLabels} onChange={(event) => p.onShowVmgLabels(event.target.checked)} />VMG labels</label>
    </div>
    <div className="course-display-summary"><span className="course-highlight-primary"><i style={{ background: primary?.color }} /><strong>A</strong> {primary?.team_code ?? 'Choose a boat'}</span><span className="course-display-note">{p.scaleMode === 'enhanced' ? 'Boat symbols enlarged for visibility.' : 'Hulls shown at true metric scale.'}</span><details className="course-trail-details"><summary>Trail settings &amp; boat B</summary><div className="course-highlight-controls"><label>Trail length<select aria-label="Course trail length" value={p.trailLength} onChange={(event) => p.onTrailLength(event.target.value as TrailLength)}><option value="off">Off</option><option value="10s">10 seconds</option><option value="30s">30 seconds</option><option value="60s">60 seconds</option><option value="leg">Current leg</option><option value="race">Whole race</option></select></label><label className="course-checkbox"><input type="checkbox" checked={p.highlightComparison} onChange={(event) => p.onHighlightComparison(event.target.checked)} />Highlight B</label><select aria-label="Highlighted comparison boat" value={p.comparisonId ?? ''} onChange={(event) => { p.onComparison(event.target.value); p.onHighlightComparison(true) }}><option value="" disabled>Choose boat B</option>{p.boats.map((boat) => <option key={boat.id} value={boat.id}>{boat.team_code}</option>)}</select><span className="course-display-note">Select a boat or its label to highlight A. Highlight B here or choose it in Compare.</span></div></details></div>
  </div>
}
