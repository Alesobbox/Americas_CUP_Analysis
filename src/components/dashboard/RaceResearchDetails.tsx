import { useState } from 'react'
import type { RaceWindForecast, TimingResearch, TimingTurn } from '../../types/research'
import { evidenceText } from '../../utils/evidenceText'
import { formatMetric, formatPercent, formatSigned } from './polarPresentation'

function elapsed(timestamp: number, gunMs: number) {
  const seconds = Math.round((timestamp - gunMs) / 1000)
  return `${seconds < 0 ? '−' : '+'}${Math.floor(Math.abs(seconds) / 60)}:${String(Math.abs(seconds) % 60).padStart(2, '0')}`
}

function horizonValue(turn: TimingTurn, horizon: number, polar = false) {
  const result = turn.horizons.find((row) => row.horizon_s === horizon)
  if (!result) return turn.cost_reason ?? 'Unavailable'
  if (result.right_censored)
    return `Censored: ${(result.censor_reason ?? 'incomplete support').replaceAll('_', ' ')}`
  return formatSigned(polar ? result.polar_reference_deficit_m : result.progress_deficit_m, 1, ' m')
}

export function RaceTimingResearch({
  report,
  boatId,
  gunMs,
  onReview,
}: {
  report?: TimingResearch
  boatId: string
  gunMs: number
  onReview?: (timestamp: number) => void
}) {
  const [horizon, setHorizon] = useState(20)
  const row = report?.boats.find((boat) => boat.boat_id === boatId)
  if (!row) return null
  const comparison = row.ledger.peer_comparison
  return (
    <>
      <div className="analysis-subsection">
        <h5>Exact checkpoint timing ledger</h5>
        <p className="analysis-provenance-note">
          Start delay plus consecutive leg durations accounts for gun-to-endpoint elapsed time. The
          same peer set is used for every comparison component. These seconds describe timing; they
          do not identify a tactical or crew cause.
        </p>
        <div className="analysis-table-wrap">
          <table className="analysis-table" aria-label="Exact timing ledger">
            <thead>
              <tr>
                <th>COMPONENT</th>
                <th>OBSERVED TIME</th>
                <th>DIFFERENCE FROM PEERS</th>
              </tr>
            </thead>
            <tbody>
              {row.ledger.components.map((component, index) => (
                <tr key={`${component.kind}:${component.leg}`}>
                  <td>
                    {component.kind === 'start_delay' ? 'Start delay' : `Leg ${component.leg}`}
                  </td>
                  <td>{formatMetric(component.elapsed_s, 3, ' s')}</td>
                  <td>{formatSigned(comparison?.components[index]?.difference_s, 3, ' s')}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th>Accounted elapsed</th>
                <td>{formatMetric(row.ledger.accounted_elapsed_s, 3, ' s')}</td>
                <td>{formatSigned(comparison?.total_difference_s, 3, ' s')}</td>
              </tr>
            </tfoot>
          </table>
        </div>
        <p className="analysis-micro-note">
          {row.ledger.complete_finish
            ? 'Complete calculated finish.'
            : evidenceText(row.ledger.reason ?? 'Incomplete timing evidence.')}{' '}
          Reconciliation difference: {formatMetric(row.ledger.reconciliation_error_s, 6, ' s')}.{' '}
          Recorded and calculated checkpoints are not independently verified official
          classifications.
        </p>
      </div>
      <details className="analysis-subsection">
        <summary>Non-overlapping phase accounting</summary>
        <p className="analysis-provenance-note">
          Missing coverage takes priority, followed by gate approaches, turns and other sailing.
          Each second belongs to one phase. Other sailing is not a certified steady-state regime.
        </p>
        <div className="research-phase-list">
          {Object.entries(row.phases.seconds ?? {}).map(([phase, seconds]) => (
            <span key={phase}>
              <strong>{phase.replaceAll('_', ' ')}</strong>
              {formatMetric(seconds, 3, ' s')}
            </span>
          ))}
        </div>
      </details>
      <details className="analysis-subsection">
        <summary>
          Geometry-selected turns and reference distance deficits ({row.turns.length} candidates)
        </summary>
        <p className="analysis-provenance-note">
          Turns are selected without a minimum speed-loss threshold. Distances compare observed
          progress with a pre-turn continuation over a stated horizon. They are not causal seconds
          lost. Polar alternatives query supported pre-turn conditions only, using a model trained
          without this day.
        </p>
        <p className="analysis-micro-note">
          Detector precision and recall:{' '}
          {row.detector_evaluation.status === 'insufficient_reviewed_labels'
            ? 'Unavailable until candidate and background windows receive independent review.'
            : `${formatPercent(row.detector_evaluation.precision)} / ${formatPercent(row.detector_evaluation.recall)} in reviewed windows.`}{' '}
          Speed collapse candidates are not verified touchdowns.
        </p>
        <label className="research-horizon">
          Reference horizon{' '}
          <select
            aria-label="Manoeuvre reference horizon"
            value={horizon}
            onChange={(event) => setHorizon(Number(event.target.value))}
          >
            {[10, 20, 30].map((seconds) => (
              <option key={seconds} value={seconds}>
                {seconds} seconds
              </option>
            ))}
          </select>
        </label>
        <div className="analysis-table-wrap research-event-table">
          <table className="analysis-table" aria-label="Turn reference progress deficits">
            <thead>
              <tr>
                <th>TIME / TYPE</th>
                <th>LEG</th>
                <th>OBSERVED REFERENCE DEFICIT</th>
                <th>HELD-OUT POLAR ALTERNATIVE</th>
                <th>RECOVERY</th>
                <th>REVIEW</th>
              </tr>
            </thead>
            <tbody>
              {row.turns.map((turn) => (
                <tr key={turn.timestamp_ms}>
                  <td>
                    {onReview ? (
                      <button
                        type="button"
                        className="analysis-table-link"
                        onClick={() => onReview(turn.timestamp_ms)}
                      >
                        {elapsed(turn.timestamp_ms, gunMs)} · {turn.type}
                      </button>
                    ) : (
                      `${elapsed(turn.timestamp_ms, gunMs)} · ${turn.type}`
                    )}
                  </td>
                  <td>{turn.leg}</td>
                  <td>{horizonValue(turn, horizon)}</td>
                  <td>{horizonValue(turn, horizon, true)}</td>
                  <td>
                    {turn.recovery?.right_censored
                      ? 'Censored'
                      : formatMetric(turn.recovery?.recovery_s, 2, ' s')}
                  </td>
                  <td>{turn.review_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  )
}

export function RaceWindResearch({ report, gunMs }: { report?: RaceWindForecast; gunMs: number }) {
  const [selected, setSelected] = useState('')
  if (!report) return null
  const prediction =
    report.predictions.find((row) => String(row.timestamp_ms) === selected) ?? report.predictions[0]
  return (
    <details className="analysis-subsection">
      <summary>Recorded-time wind-shift forecasts</summary>
      <p className="analysis-provenance-note">
        Probability of at least a 5° endpoint change after three minutes, fitted on completed
        prior-day observations. The forecast list is retrospective; historical live delivery times
        are unverified. Selecting a forecast does not change its training data.
      </p>
      {!prediction ? (
        <p className="analysis-empty">No forecast was eligible from earlier-day training data.</p>
      ) : (
        <>
          <label className="research-horizon">
            Forecast issued at{' '}
            <select
              aria-label="Research wind forecast timestamp"
              value={prediction.timestamp_ms}
              onChange={(event) => setSelected(event.target.value)}
            >
              {report.predictions.map((row) => (
                <option key={row.timestamp_ms} value={row.timestamp_ms}>
                  {elapsed(row.timestamp_ms, gunMs)}
                </option>
              ))}
            </select>
          </label>
          <div className="analysis-table-wrap">
            <table
              className="analysis-table"
              aria-label="Recorded-time wind forecast probabilities"
            >
              <thead>
                <tr>
                  <th>MODEL</th>
                  <th>SHIFT PROBABILITY</th>
                  <th>CENTRAL DIRECTION</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(prediction.methods).map(([method, values]) => (
                  <tr key={method}>
                    <td>{method.replaceAll('_', ' ')}</td>
                    <td>{formatPercent(values.probability_shift_ge_5deg)}</td>
                    <td>{formatMetric(values.center_twd_deg, 1, '°')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="analysis-micro-note">
            Target at {elapsed(prediction.target_timestamp_ms, gunMs)}.{' '}
            {prediction.target_status === 'censored'
              ? 'Future target is censored in the recorded source.'
              : 'Endpoint target is recorded.'}{' '}
            Training uses {report.training_days ?? 'unavailable'} earlier days.
          </p>
        </>
      )}
    </details>
  )
}
