import { evidenceText } from '../../utils/evidenceText'
import type { AnalysisDetailBoat } from '../../types/analysis'

export function TeamDebrief({
  boat,
  raceId,
  replayAvailable,
  onOpenReplay,
}: {
  boat: AnalysisDetailBoat
  raceId: string
  replayAvailable: boolean
  onOpenReplay: (raceId: string, timestamp?: number) => void
}) {
  return (
    <section className="analysis-section team-debrief" aria-label="Team debrief">
      <div className="analysis-section-heading">
        <h4>Team debrief</h4>
        <span>Evidence-linked review queue</span>
      </div>
      <p className="analysis-inline-facts">
        Retrospective review priorities from recorded performance. Each item opens the supporting
        replay moment.
      </p>
      {!boat.debrief && (
        <p className="analysis-empty">Team debrief is unavailable in this export.</p>
      )}
      {boat.debrief && !boat.debrief.items.length && (
        <p className="analysis-empty">
          No supported review priorities were exported for this boat.
        </p>
      )}
      <div className="debrief-items">
        {boat.debrief?.items.map((item) => (
          <article className="debrief-item" key={item.id}>
            <div className="analysis-section-heading">
              <h5>{evidenceText(item.title)}</h5>
              <strong>
                {item.value.toFixed(1)} {item.unit}
              </strong>
            </div>
            <p>{evidenceText(item.detail)}</p>
            <small>
              {evidenceText(item.quality)} · {evidenceText(item.source)}
              {item.peer_count === undefined ? '' : ` · ${item.peer_count} peers`} ·{' '}
              {new Date(item.timestamp_ms).toISOString().slice(11, 19)} UTC
            </small>
            <button
              type="button"
              className="analysis-replay-link"
              disabled={!replayAvailable}
              onClick={() => onOpenReplay(raceId, item.timestamp_ms)}
              data-review-timestamp={item.timestamp_ms}
            >
              {replayAvailable ? 'Review in replay ↗' : 'Replay unavailable'}
            </button>
          </article>
        ))}
      </div>
      {boat.debrief && (
        <small className="analysis-micro-note">
          Method: {boat.debrief.method_version}. Priorities identify observations for review; they
          do not establish the cause of a loss.
        </small>
      )}
    </section>
  )
}
