import { evidenceText } from '../../utils/evidenceText'
import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { loadAnalysisDetail, loadAnalysisIndex } from '../../engine/analysisCatalog'
import { BoatPerformanceRadar } from '../dashboard/BoatPerformanceRadar'
import { TeamDebrief } from '../dashboard/TeamDebrief'
import type {
  AnalysisDetail,
  AnalysisIndex,
  AnalysisIndexRace,
  AnalysisMetric,
  MetricDefinition,
  MetricMap,
} from '../../types/analysis'

interface Props {
  currentRaceId: string
  replayRaceIds: string[]
  onOpenReplay: (raceId: string, timestamp?: number, boatId?: string, intervalEnd?: number) => void
  onClose: () => void
  inline?: boolean
  selectedBoatId?: string | null
  onSelectBoat?: (id: string) => void
  comparisonId?: string | null
  onSelectComparison?: (id: string) => void
  onSelectRace?: (id: string) => void
}

function labelFor(id: string, definitions?: Record<string, MetricDefinition>) {
  return evidenceText(
    definitions?.[id]?.label ||
      id.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
  )
}

function raceTypeLabel(value: string) {
  if (value === 'RACE_TYPE_FLEET') return 'Fleet race'
  if (value === 'RACE_TYPE_MATCH') return 'Match race'
  return value
    .replace(/^RACE_TYPE_/, '')
    .replace(/_/g, ' ')
    .toLowerCase()
}

function classificationLabel(value: string) {
  return value.startsWith('RANK_') ? 'Finished' : value.replace(/_/g, ' ')
}

function withUnit(value: number | null, unit: string, digits = 1) {
  return value === null || !Number.isFinite(value)
    ? 'Unavailable'
    : `${number(value, digits)} ${unit}`
}

function signedSeconds(value: number | null) {
  if (value === null || !Number.isFinite(value)) return 'Unavailable'
  return `${value > 0 ? '+' : ''}${number(value, 2)} s`
}

function historyLegValue(value: AnalysisMetric | undefined) {
  return value ? metricValue(value) : 'Unavailable'
}

function historyLegEvidence(value: AnalysisMetric | undefined) {
  if (!value) return undefined
  return `${evidenceText(value.quality)}${value.coverage_s === null ? '' : ` · ${number(value.coverage_s, 0)} s covered`}${value.reason ? ` · ${evidenceText(value.reason)}` : ''}`
}

function HistoryLegCell({ value }: { value: AnalysisMetric | undefined }) {
  const evidence = historyLegEvidence(value)
  return (
    <td>
      <span>{historyLegValue(value)}</span>
      {evidence && <small className="analysis-leg-evidence">{evidence}</small>}
    </td>
  )
}

const historicalLegMetrics: Array<[string, string, string]> = [
  ['elapsed_s', 'Leg time', 's'],
  ['course_vmg_kt', 'Leg-directed course VMG', 'kt'],
  ['wind_vmg_kt', 'Wind-relative VMG', 'kt'],
  ['distance_m', 'Distance sailed', 'm'],
]

function number(value: number, maximumFractionDigits = 1) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(value)
}

function metricValue(metric: AnalysisMetric) {
  if (metric.value === null || !Number.isFinite(metric.value)) return '—'
  return `${number(metric.value, Math.abs(metric.value) < 10 ? 2 : 1)}${metric.unit ? ` ${metric.unit}` : ''}`
}

function elapsed(seconds: number | null) {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return '—'
  const whole = Math.floor(seconds)
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`
}

function raceClock(timestamp: number | null, gunTime: number) {
  if (timestamp === null || !Number.isFinite(timestamp)) return '—'
  const delta = Math.round((timestamp - gunTime) / 1000)
  const absolute = Math.abs(delta)
  return `${delta < 0 ? '−' : '+'}${Math.floor(absolute / 60)}:${String(absolute % 60).padStart(2, '0')}`
}

function MetricCards({
  metrics,
  definitions,
}: {
  metrics: MetricMap
  definitions?: Record<string, MetricDefinition>
}) {
  const entries = Object.entries(metrics)
  if (!entries.length)
    return <p className="analysis-empty">No comparable metrics were exported for this section.</p>
  return (
    <div className="analysis-metric-grid">
      {entries.map(([id, metric]) => (
        <article
          className={`analysis-metric ${metric.value === null ? 'unavailable' : ''}`}
          key={id}
        >
          <span className="analysis-metric-label">{labelFor(id, definitions)}</span>
          <strong>{metricValue(metric)}</strong>
          <span className="analysis-metric-meta">
            {evidenceText(metric.quality)}
            {metric.coverage_s !== null ? ` · ${number(metric.coverage_s, 0)} s covered` : ''}
            {metric.sample_count !== undefined && metric.unit !== 'events'
              ? ` · ${metric.sample_count} events`
              : ''}
          </span>
          {(metric.reason || metric.value === null) && (
            <small>{evidenceText(metric.reason || 'Not available from this race record')}</small>
          )}
        </article>
      ))}
    </div>
  )
}

function ReplayButton({
  raceId,
  timestamp,
  replayRaceIds,
  onOpenReplay,
  children,
}: {
  raceId: string
  timestamp?: number
  replayRaceIds: string[]
  onOpenReplay: Props['onOpenReplay']
  children: string
}) {
  const available = replayRaceIds.includes(raceId)
  return (
    <button
      type="button"
      className="analysis-replay-link"
      disabled={!available}
      title={available ? undefined : 'Replay unavailable for this race'}
      onClick={() => onOpenReplay(raceId, timestamp)}
    >
      {available ? children : 'Replay unavailable'}
    </button>
  )
}

function WindPlot({
  timeline,
  ariaLabel = 'Official wind direction shift over the race',
  axisLabel = 'SHIFT FROM BASELINE, DEGREES',
}: {
  timeline: Array<{ timestamp: number; shift_deg: number }>
  ariaLabel?: string
  axisLabel?: string
}) {
  if (timeline.length < 2)
    return <p className="analysis-empty">No wind shift timeline is available.</p>
  const values = timeline.map((point) => point.shift_deg)
  const minimum = Math.min(...values, 0)
  const maximum = Math.max(...values, 0)
  const range = Math.max(1, maximum - minimum)
  const first = timeline[0].timestamp
  const duration = Math.max(1, timeline[timeline.length - 1].timestamp - first)
  const points = timeline
    .map(
      (point) =>
        `${((point.timestamp - first) / duration) * 800},${((maximum - point.shift_deg) / range) * 100}`
    )
    .join(' ')
  const zeroY = (maximum / range) * 100
  return (
    <div className="analysis-wind-plot">
      <svg role="img" aria-label={ariaLabel} viewBox="0 0 800 100" preserveAspectRatio="none">
        <line x1="0" x2="800" y1={zeroY} y2={zeroY} className="wind-zero" />
        <polyline points={points} />
      </svg>
      <div>
        <span>RACE START</span>
        <span>{axisLabel}</span>
        <span>RACE END</span>
      </div>
    </div>
  )
}

function GateTable({
  boat,
  raceId,
  gunTime,
  replayRaceIds,
  onOpenReplay,
}: {
  boat: AnalysisDetail['boats'][number]
  raceId: string
  gunTime: number
  replayRaceIds: string[]
  onOpenReplay: Props['onOpenReplay']
}) {
  if (!boat.gates.length) return null
  return (
    <section className="analysis-section">
      <div className="analysis-section-heading">
        <h4>Mark approaches and roundings</h4>
        <span>{boat.gates.length} gate crossings · shared checkpoint changes</span>
      </div>
      <div className="analysis-table-wrap">
        <table className="analysis-table">
          <thead>
            <tr>
              <th>LEG</th>
              <th>TIME</th>
              <th>MARK / SIDE</th>
              <th>20 S APPROACH</th>
              <th>ANGLE</th>
              <th>ENTRY / EXIT</th>
              <th>ROUNDING</th>
              <th>RANK</th>
              <th>LEADER SPLIT</th>
              <th>CHANGE</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {boat.gates.map((gate, index) => (
              <tr key={`${gate.leg}-${index}`}>
                <td>{gate.leg}</td>
                <td>{raceClock(gate.crossing_time_ms, gunTime)}</td>
                <td>
                  {gate.mark_chosen || '—'} / {gate.side || '—'}
                </td>
                <td>{withUnit(gate.approach_20s_distance_m, 'm')}</td>
                <td>{withUnit(gate.approach_angle_deg, '°')}</td>
                <td>
                  {withUnit(gate.entry_speed_kt, 'kt')} / {withUnit(gate.exit_speed_kt, 'kt')}
                </td>
                <td title={evidenceText(gate.rounding_reason) || undefined}>
                  {gate.rounding_time_s === null
                    ? evidenceText(gate.rounding_reason) || 'Unavailable'
                    : `${number(gate.rounding_time_s)} s`}
                </td>
                <td>{gate.checkpoint_rank ?? '—'}</td>
                <td>{withUnit(gate.split_to_leader_s, 's')}</td>
                <td>
                  {gate.split_change_s == null
                    ? '—'
                    : `${withUnit(gate.split_change_s, 's')}${gate.rank_change == null ? '' : ` · rank ${gate.rank_change > 0 ? '+' : ''}${gate.rank_change}`}`}
                </td>
                <td>
                  {gate.crossing_time_ms !== null && (
                    <ReplayButton
                      raceId={raceId}
                      timestamp={gate.crossing_time_ms}
                      replayRaceIds={replayRaceIds}
                      onOpenReplay={onOpenReplay}
                    >
                      Replay ↗
                    </ReplayButton>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function RaceView({
  index,
  race,
  detail,
  detailLoading,
  detailError,
  selectedBoatId,
  onSelectRace,
  onSelectBoat,
  replayRaceIds,
  onOpenReplay,
  comparisonId: externalComparisonId,
  onSelectComparison,
}: {
  index: AnalysisIndex
  race: AnalysisIndexRace | undefined
  detail: AnalysisDetail | null
  detailLoading: boolean
  detailError: string | null
  selectedBoatId: string | null
  onSelectRace: (id: string) => void
  onSelectBoat: (id: string) => void
  replayRaceIds: string[]
  onOpenReplay: Props['onOpenReplay']
  comparisonId?: string | null
  onSelectComparison?: (id: string) => void
}) {
  const [localComparisonId, setLocalComparisonId] = useState<string | null>(null)
  const comparisonId = externalComparisonId === undefined ? localComparisonId : externalComparisonId
  const setComparisonId = onSelectComparison ?? setLocalComparisonId
  if (!race) return <p className="analysis-empty">No races are present in the analysis archive.</p>
  const boat =
    detail?.boats.find((candidate) => candidate.id === selectedBoatId) ?? detail?.boats[0]
  const comparison =
    detail?.boats.find((candidate) => candidate.id === comparisonId && candidate.id !== boat?.id) ??
    (externalComparisonId === undefined
      ? detail?.boats.find((candidate) => candidate.id !== boat?.id)
      : undefined)
  const pair = detail?.pairs.find(
    (candidate) =>
      (candidate.boat_a === boat?.team_code && candidate.boat_b === comparison?.team_code) ||
      (candidate.boat_b === boat?.team_code && candidate.boat_a === comparison?.team_code)
  )
  const sorted = [...race.boats].sort(
    (a, b) => (a.official_rank ?? Infinity) - (b.official_rank ?? Infinity)
  )
  return (
    <div className="analysis-content">
      <div className="analysis-controls">
        <label>
          RACE{' '}
          <select value={race.id} onChange={(event) => onSelectRace(event.target.value)}>
            {index.races.map((entry) => (
              <option value={entry.id} key={entry.id}>
                {entry.date} · {entry.name}
              </option>
            ))}
          </select>
        </label>
        <ReplayButton raceId={race.id} replayRaceIds={replayRaceIds} onOpenReplay={onOpenReplay}>
          Open race replay ↗
        </ReplayButton>
      </div>
      <div className="analysis-race-heading">
        <div>
          <span className="eyebrow">
            {race.boat_class} · {raceTypeLabel(race.race_type)}
          </span>
          <h3>{race.name}</h3>
          <p>
            {race.date} · {race.boat_count} boats
          </p>
        </div>
        <span className="analysis-method-tag">EXPORTED ANALYSIS</span>
      </div>
      <p className="analysis-provenance-note">
        {evidenceText(
          race.result_provenance ||
            'Classification, rank and elapsed time are calculated from source race records; they have not been independently verified as official results.'
        )}
      </p>
      {!!race.limitations?.length && (
        <details className="analysis-limitations">
          <summary>Source limitations ({race.limitations.length})</summary>
          {race.limitations.map((limitation) => (
            <p className="analysis-provenance-note" key={limitation}>
              {evidenceText(limitation)}
            </p>
          ))}
        </details>
      )}
      <section className="analysis-section">
        <div className="analysis-section-heading">
          <h4>Classification</h4>
          <span>Source-based result · select a boat for detail</span>
        </div>
        <div className="analysis-table-wrap">
          <table className="analysis-table">
            <thead>
              <tr>
                <th>POS</th>
                <th>TEAM</th>
                <th>STATUS</th>
                <th>ELAPSED</th>
                <th>ANALYSIS</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((entry) => (
                <tr key={entry.id} className={entry.id === boat?.id ? 'selected' : ''}>
                  <td>{entry.official_rank ?? '—'}</td>
                  <td>
                    <button
                      type="button"
                      className="analysis-team-select"
                      onClick={() => onSelectBoat(entry.id)}
                    >
                      <i style={{ backgroundColor: entry.color }} />
                      {entry.team_code}
                      <small>{entry.team_name}</small>
                    </button>
                  </td>
                  <td>{classificationLabel(entry.classification)}</td>
                  <td>{elapsed(entry.official_elapsed_s)}</td>
                  <td>
                    {Object.values(entry.metrics).filter((metric) => metric.value !== null).length}{' '}
                    metrics
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {detailLoading && (
        <p className="analysis-state" role="status">
          Loading detailed analysis…
        </p>
      )}
      {detailError && (
        <p className="analysis-state error" role="alert">
          {detailError}
        </p>
      )}
      {detail && boat && (
        <>
          <div className="analysis-boat-heading">
            <div>
              <span className="eyebrow">BOAT REPORT</span>
              <h3>
                <i style={{ backgroundColor: boat.color }} />
                {boat.team_name}
              </h3>
            </div>
            <span>{classificationLabel(boat.classification)}</span>
          </div>
          <BoatPerformanceRadar
            key={race.id + ':' + boat.id}
            boat={boat}
            raceId={race.id}
            boats={detail.boats}
            replayAvailable={replayRaceIds.includes(race.id)}
            onReviewLeg={(review) => {
              onSelectBoat(review.boatId)
              onOpenReplay(review.raceId, review.start_ms, review.boatId, review.end_ms)
            }}
          />
          <TeamDebrief
            boat={boat}
            raceId={race.id}
            replayAvailable={replayRaceIds.includes(race.id)}
            onOpenReplay={onOpenReplay}
          />
          <section className="analysis-section">
            <div className="analysis-section-heading">
              <h4>Race metrics</h4>
              <span>Calculated over the stated coverage</span>
            </div>
            <MetricCards metrics={boat.metrics} definitions={detail.definitions} />
          </section>
          <section className="analysis-section">
            <div className="analysis-section-heading">
              <h4>Start</h4>
              <span>Gun-relative measurements and crossing order</span>
            </div>
            <p className="analysis-inline-facts">
              Crossing {raceClock(boat.start.crossing_time_ms, detail.race.gun_time_ms)}{' '}
              <span>·</span> Order {boat.start.crossing_order ?? '—'} <span>·</span>{' '}
              {boat.start.ocs ? 'OCS' : 'No OCS recorded'}
            </p>
            {boat.source_conflicts?.map((conflict) => (
              <p className="analysis-conflict" key={conflict}>
                Source conflict: {evidenceText(conflict)}
              </p>
            ))}
            <MetricCards metrics={boat.start.gun.metrics} definitions={detail.definitions} />
          </section>
          {boat.legs.length > 0 && (
            <section className="analysis-section">
              <div className="analysis-section-heading">
                <h4>Leg performance</h4>
                <span>Race clock relative to the gun</span>
              </div>
              <div className="analysis-leg-list">
                {boat.legs.map((leg) => (
                  <article className="analysis-leg" key={`${leg.leg}-${leg.start_ms}`}>
                    <div className="analysis-leg-head">
                      <strong>LEG {leg.leg}</strong>
                      <span>
                        {raceClock(leg.start_ms, detail.race.gun_time_ms)} to{' '}
                        {raceClock(leg.end_ms, detail.race.gun_time_ms)}
                      </span>
                      <ReplayButton
                        raceId={race.id}
                        timestamp={leg.start_ms}
                        replayRaceIds={replayRaceIds}
                        onOpenReplay={onOpenReplay}
                      >
                        View leg ↗
                      </ReplayButton>
                    </div>
                    <MetricCards metrics={leg.metrics} definitions={detail.definitions} />
                    {leg.twa_bins_s && (
                      <div className="analysis-twa-bins">
                        <strong>ABSOLUTE TWA DISTRIBUTION</strong>
                        {Object.entries(leg.twa_bins_s).map(([bin, seconds]) => (
                          <span key={bin}>
                            {bin}: {number(seconds, 0)} s
                          </span>
                        ))}
                      </div>
                    )}
                    {leg.gate && (
                      <p className="analysis-inline-facts">
                        Gate {leg.gate.mark_chosen || '—'} · {leg.gate.side || '—'} · Split{' '}
                        {leg.gate.split_to_leader_s === null
                          ? '—'
                          : `${number(leg.gate.split_to_leader_s)} s`}
                      </p>
                    )}
                  </article>
                ))}
              </div>
            </section>
          )}
          <GateTable
            boat={boat}
            raceId={race.id}
            gunTime={detail.race.gun_time_ms}
            replayRaceIds={replayRaceIds}
            onOpenReplay={onOpenReplay}
          />
          {boat.manoeuvres.length > 0 && (
            <section className="analysis-section">
              <div className="analysis-section-heading">
                <h4>Manoeuvres</h4>
                <span>{boat.manoeuvres.length} recorded</span>
              </div>
              <div className="analysis-table-wrap">
                <table className="analysis-table">
                  <thead>
                    <tr>
                      <th>TIME</th>
                      <th>TYPE</th>
                      <th>LEG</th>
                      <th>SPEED LOSS</th>
                      <th>RECOVERY</th>
                      <th>ACCELERATION</th>
                      <th>QUALITY</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {boat.manoeuvres.map((manoeuvre, index) => (
                      <tr key={`${manoeuvre.timestamp}-${index}`}>
                        <td>{raceClock(manoeuvre.timestamp, detail.race.gun_time_ms)}</td>
                        <td>{manoeuvre.type}</td>
                        <td>{manoeuvre.leg ?? '—'}</td>
                        <td>
                          {manoeuvre.speed_loss_kt === null
                            ? '—'
                            : `${number(manoeuvre.speed_loss_kt)} kt`}
                        </td>
                        <td>
                          {manoeuvre.recovery_time_s === null
                            ? '—'
                            : `${number(manoeuvre.recovery_time_s)} s`}
                        </td>
                        <td>
                          {manoeuvre.acceleration_kt_s == null
                            ? '—'
                            : `${number(manoeuvre.acceleration_kt_s, 2)} kt/s`}
                        </td>
                        <td>{evidenceText(manoeuvre.quality)}</td>
                        <td>
                          <ReplayButton
                            raceId={race.id}
                            timestamp={manoeuvre.timestamp}
                            replayRaceIds={replayRaceIds}
                            onOpenReplay={onOpenReplay}
                          >
                            Replay ↗
                          </ReplayButton>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          <section className="analysis-section">
            <div className="analysis-section-heading">
              <h4>Course position</h4>
              <span>Active race boundary · layline only with a defensible target</span>
            </div>
            <MetricCards
              metrics={Object.fromEntries(
                Object.entries(boat.metrics).filter(
                  ([id]) => id.startsWith('boundary_') || id.startsWith('layline_')
                )
              )}
              definitions={detail.definitions}
            />
            {boat.boundary_periods && boat.boundary_periods.length > 0 && (
              <div className="analysis-subsection">
                <h5>Outside-boundary periods</h5>
                <div className="analysis-boundary-periods">
                  {boat.boundary_periods.map((period, index) => (
                    <div key={`${period.start_ms}-${index}`}>
                      <span>
                        {raceClock(period.start_ms, detail.race.gun_time_ms)} to{' '}
                        {raceClock(period.end_ms, detail.race.gun_time_ms)} ·{' '}
                        {number((period.end_ms - period.start_ms) / 1000)} s
                      </span>
                      <ReplayButton
                        raceId={race.id}
                        timestamp={period.start_ms}
                        replayRaceIds={replayRaceIds}
                        onOpenReplay={onOpenReplay}
                      >
                        Replay ↗
                      </ReplayButton>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
          <section className="analysis-section">
            <div className="analysis-section-heading">
              <h4>Wind shifts</h4>
              <span>{evidenceText(detail.wind.source)}</span>
            </div>
            <div className="analysis-wind-facts">
              <span>
                BASELINE <strong>{withUnit(detail.wind.baseline_twd_deg, '°', 1)}</strong>
              </span>
              <span>
                SHIFT RANGE{' '}
                <strong>
                  {withUnit(detail.wind.shift_min_deg, '°', 1)} to{' '}
                  {withUnit(detail.wind.shift_max_deg, '°', 1)}
                </strong>
              </span>
              <span>
                SAMPLES <strong>{detail.wind.sample_count}</strong>
              </span>
            </div>
            <WindPlot timeline={detail.wind.timeline} />
            {detail.wind.fleet_timeline && detail.wind.fleet_timeline.length > 0 && (
              <div className="analysis-subsection">
                <h5>Local wind spread across active boats</h5>
                <WindPlot
                  timeline={detail.wind.fleet_timeline.map((sample) => ({
                    timestamp: sample.timestamp,
                    shift_deg: sample.spread_deg,
                  }))}
                  ariaLabel="Local wind direction spread across active boats over the race"
                  axisLabel="FLEET SPREAD, DEGREES"
                />
                <p>
                  Only active boats with time-aligned local wind samples contribute to each point.
                </p>
              </div>
            )}
            {detail.wind.boat_exposure && detail.wind.boat_exposure.length > 0 && (
              <div className="analysis-subsection">
                <h5>Local versus official direction</h5>
                <div className="analysis-table-wrap">
                  <table className="analysis-table">
                    <thead>
                      <tr>
                        <th>TEAM</th>
                        <th>ALIGNED SAMPLES</th>
                        <th>MEDIAN LOCAL MINUS OFFICIAL</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.wind.boat_exposure.map((exposure) => (
                        <tr key={exposure.team_code}>
                          <td>{exposure.team_code}</td>
                          <td>{exposure.sample_count}</td>
                          <td>{withUnit(exposure.median_local_minus_official_deg, '°', 1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            <p className="analysis-micro-note">
              Direction shifts are relative to the stated official wind baseline. They describe
              conditions, not proof of a tactical gain.
            </p>
          </section>
          {comparison && (
            <section className="analysis-section">
              <div className="analysis-section-heading">
                <h4>Head to head</h4>
                <label>
                  COMPARE WITH{' '}
                  <select
                    value={comparison.id}
                    onChange={(event) => setComparisonId(event.target.value)}
                  >
                    {detail.boats
                      .filter((candidate) => candidate.id !== boat.id)
                      .map((candidate) => (
                        <option value={candidate.id} key={candidate.id}>
                          {candidate.team_code}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
              <p className="analysis-inline-facts">
                {boat.team_code} and {comparison.team_code} · same race only. Separation is physical
                distance, not a time or progress gap.
              </p>
              <div className="analysis-table-wrap">
                <table className="analysis-table">
                  <thead>
                    <tr>
                      <th>METRIC</th>
                      <th>{boat.team_code}</th>
                      <th>{comparison.team_code}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(boat.metrics)
                      .filter(([id]) => comparison.metrics[id])
                      .map(([id, metric]) => (
                        <tr key={id}>
                          <td>{labelFor(id, detail.definitions)}</td>
                          <td>{metricValue(metric)}</td>
                          <td>{metricValue(comparison.metrics[id])}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              {pair ? (
                <div className="analysis-subsection">
                  <h5>Separation by leg</h5>
                  <div className="analysis-table-wrap">
                    <table className="analysis-table">
                      <thead>
                        <tr>
                          <th>LEG</th>
                          <th>OVERLAP SAMPLES</th>
                          <th>MEDIAN SPATIAL</th>
                          <th>MEDIAN LATERAL</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pair.legs.map((leg) => (
                          <tr key={leg.leg}>
                            <td>{leg.leg}</td>
                            <td>{leg.sample_count}</td>
                            <td>{withUnit(leg.median_spatial_m, 'm')}</td>
                            <td>{withUnit(leg.median_lateral_m, 'm')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <p className="analysis-inline-facts">
                  No common active-leg separation samples were exported for this pair.
                </p>
              )}
            </section>
          )}
          <details className="analysis-definitions">
            <summary>Definitions, coverage and provenance</summary>
            <p>
              These values describe the exported analysis. The quality and coverage shown on each
              metric indicate the available evidence. An unavailable value is not treated as zero.
            </p>
            <div className="analysis-definition-list">
              {Object.entries(detail.definitions).map(([id, definition]) => (
                <div key={id}>
                  <strong>{evidenceText(definition.label)}</strong>
                  <span>
                    {definition.unit} · {evidenceText(definition.source)}
                  </span>
                  <p>{evidenceText(definition.formula)}</p>
                  <p>
                    Window: {evidenceText(definition.window)} · Denominator:{' '}
                    {evidenceText(definition.denominator)}
                  </p>
                </div>
              ))}
            </div>
            {boat.source_coverage && (
              <>
                <h5>Source stream coverage for {boat.team_code}</h5>
                <div className="analysis-table-wrap">
                  <table className="analysis-table">
                    <thead>
                      <tr>
                        <th>STREAM</th>
                        <th>SAMPLES</th>
                        <th>REPORTED GAPS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(boat.source_coverage).map(([stream, coverage]) => (
                        <tr key={stream}>
                          <td>{stream.toUpperCase()}</td>
                          <td>{coverage.count}</td>
                          <td>{coverage.gaps.length}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
            <small>Method version: {detail.method_version}</small>
          </details>
          {comparison && (
            <LegComparison boat={boat} comparison={comparison} definitions={detail.definitions} />
          )}
        </>
      )}
    </div>
  )
}

function LegComparison({
  boat,
  comparison,
  definitions,
}: {
  boat: AnalysisDetail['boats'][number]
  comparison: AnalysisDetail['boats'][number]
  definitions: Record<string, MetricDefinition>
}) {
  const fields = ['elapsed_s', 'course_vmg_kt', 'wind_vmg_kt', 'distance_m'] as const
  return (
    <section className="analysis-section">
      <div className="analysis-section-heading">
        <h4>Leg by leg comparison</h4>
        <span>
          {boat.team_code} / {comparison.team_code} · same race
        </span>
      </div>
      <div className="analysis-table-wrap">
        <table className="analysis-table">
          <thead>
            <tr>
              <th>LEG</th>
              <th>MEASURE</th>
              <th>{boat.team_code}</th>
              <th>{comparison.team_code}</th>
            </tr>
          </thead>
          <tbody>
            {boat.legs.flatMap((leg, index) =>
              fields.map((id) => (
                <tr key={`${leg.leg}-${id}`}>
                  <td>{leg.leg}</td>
                  <td>{labelFor(id, definitions)}</td>
                  <td>{leg.metrics[id] ? metricValue(leg.metrics[id]) : '—'}</td>
                  <td>
                    {comparison.legs[index]?.metrics[id]
                      ? metricValue(comparison.legs[index].metrics[id])
                      : '—'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function HistoryView({
  index,
  replayRaceIds,
  onOpenReplay,
  onSelectRace,
}: {
  index: AnalysisIndex
  replayRaceIds: string[]
  onOpenReplay: Props['onOpenReplay']
  onSelectRace: (id: string) => void
}) {
  const [cohort, setCohort] = useState('')
  const [team, setTeam] = useState('')
  const [selectedLeg, setSelectedLeg] = useState('')
  const [selectedLegMetric, setSelectedLegMetric] = useState('elapsed_s')
  const cohorts = [
    ...new Set(index.histories.map((history) => `${history.boat_class}|${history.race_type}`)),
  ]
  const effectiveCohort = cohorts.includes(cohort) ? cohort : cohorts[0]
  const matching = index.histories.filter(
    (history) => `${history.boat_class}|${history.race_type}` === effectiveCohort
  )
  const history = matching.find((entry) => entry.team_code === team) ?? matching[0]
  const [metricId, setMetricId] = useState('')
  const metricIds = history ? Object.keys(history.summary) : []
  const effectiveMetricId = metricIds.includes(metricId) ? metricId : metricIds[0]
  const summary = effectiveMetricId ? history?.summary[effectiveMetricId] : undefined
  const sampleMetric = history?.observations.find(
    (observation) => observation.metrics[effectiveMetricId]
  )?.metrics[effectiveMetricId]
  if (!history)
    return <p className="analysis-empty">No team observations are available in this archive.</p>
  const raceNames = new Map(index.races.map((race) => [race.id, race.name]))
  const sorted = [...history.observations].sort((a, b) => a.date.localeCompare(b.date))
  const allTeamObservations = index.histories
    .filter((entry) => entry.team_code === history.team_code)
    .flatMap((entry) =>
      entry.observations.map((observation) => ({
        ...observation,
        raceType: entry.race_type,
        boatClass: entry.boat_class,
      }))
    )
    .sort((a, b) => a.date.localeCompare(b.date))
  const legNumbers = [
    ...new Set([
      ...Object.keys(history.leg_summary || {}).map(Number),
      ...sorted.flatMap((observation) => (observation.legs || []).map((leg) => leg.leg)),
    ]),
  ]
    .filter(Number.isFinite)
    .sort((a, b) => a - b)
  const effectiveLeg = legNumbers.includes(Number(selectedLeg))
    ? Number(selectedLeg)
    : legNumbers[0]
  const legSummary = history.leg_summary?.[String(effectiveLeg)] || {}
  const legMetricOptions = historicalLegMetrics.filter(([id]) => legSummary[id])
  const effectiveLegMetric = legMetricOptions.some(([id]) => id === selectedLegMetric)
    ? selectedLegMetric
    : legMetricOptions[0]?.[0]
  const selectedLegSummary = effectiveLegMetric ? legSummary[effectiveLegMetric] : undefined
  return (
    <div className="analysis-content">
      <section className="analysis-section">
        <div className="analysis-section-heading">
          <h4>Race coverage</h4>
          <span>
            {index.races.length} races ·{' '}
            {index.races.reduce((sum, race) => sum + race.boat_count, 0)} boat-race entries
          </span>
        </div>
        <div className="analysis-archive-list">
          {index.races.map((race) => (
            <article key={race.id}>
              <div>
                <strong>{race.name}</strong>
                <span>
                  {race.date} · {race.boat_class} · {raceTypeLabel(race.race_type)} ·{' '}
                  {race.boat_count} boats
                </span>
              </div>
              <button type="button" onClick={() => onSelectRace(race.id)}>
                Analyze →
              </button>
            </article>
          ))}
        </div>
      </section>
      <div className="analysis-controls">
        <label>
          COMPARABLE RACES{' '}
          <select
            value={effectiveCohort}
            onChange={(event) => {
              setCohort(event.target.value)
              setTeam('')
              setMetricId('')
            }}
          >
            {cohorts.map((entry) => {
              const [boatClass, raceType] = entry.split('|')
              return (
                <option value={entry} key={entry}>
                  {boatClass} · {raceTypeLabel(raceType)}
                </option>
              )
            })}
          </select>
        </label>
        <span className="analysis-cohort-note">
          Performance values are summarized within boat class and race type.
        </span>
      </div>
      <div className="analysis-team-tabs" role="group" aria-label="Choose team">
        {matching.map((entry) => (
          <button
            type="button"
            key={entry.team_code}
            className={entry.team_code === history.team_code ? 'active' : ''}
            onClick={() => {
              setTeam(entry.team_code)
              setMetricId('')
            }}
          >
            {entry.team_code}
            <small>
              {entry.race_count} {entry.race_count === 1 ? 'race' : 'races'}
            </small>
          </button>
        ))}
      </div>
      <div className="analysis-race-heading">
        <div>
          <span className="eyebrow">HISTORICAL VIEW</span>
          <h3>{history.team_code}</h3>
          <p>
            {history.boat_class} · {raceTypeLabel(history.race_type)} · {history.race_count}{' '}
            {history.race_count === 1 ? 'race' : 'races'}
          </p>
        </div>
      </div>
      {summary && (
        <section className="analysis-section">
          <div className="analysis-section-heading">
            <h4>{history.race_count === 1 ? 'Single observation' : 'Across comparable races'}</h4>
            <label>
              METRIC{' '}
              <select
                value={effectiveMetricId}
                onChange={(event) => setMetricId(event.target.value)}
              >
                {metricIds.map((id) => (
                  <option value={id} key={id}>
                    {labelFor(id)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="analysis-history-summary">
            <div>
              <span>{history.race_count === 1 ? 'OBSERVED VALUE' : 'MEDIAN'}</span>
              <strong>
                {number(summary.median, 2)} {sampleMetric?.unit || ''}
              </strong>
            </div>
            <div>
              <span>{history.race_count === 1 ? 'COMPARISON' : 'RANGE'}</span>
              <strong>
                {history.race_count === 1
                  ? 'One race only'
                  : `${number(summary.min, 2)}–${number(summary.max, 2)} ${sampleMetric?.unit || ''}`}
              </strong>
            </div>
            <div>
              <span>WITH DATA</span>
              <strong>
                {summary.count} / {history.race_count}
              </strong>
            </div>
          </div>
          <p className="analysis-micro-note">
            {history.race_count === 1
              ? 'A single race cannot establish a trend.'
              : 'Only races with an available value contribute to the median and range.'}{' '}
            Open a race to inspect its definition and coverage.
          </p>
        </section>
      )}
      <section className="analysis-section">
        <div className="analysis-section-heading">
          <h4>Race record</h4>
          <span>Chronological · source-based results</span>
        </div>
        <div className="analysis-table-wrap">
          <table className="analysis-table">
            <thead>
              <tr>
                <th>DATE</th>
                <th>RACE</th>
                <th>RESULT</th>
                <th>{effectiveMetricId ? labelFor(effectiveMetricId) : 'METRIC'}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((observation) => (
                <tr key={`${observation.race_id}-${observation.date}`}>
                  <td>{observation.date}</td>
                  <td>
                    <button
                      className="analysis-table-link"
                      type="button"
                      onClick={() => onSelectRace(observation.race_id)}
                    >
                      {raceNames.get(observation.race_id) || observation.race_id}
                    </button>
                  </td>
                  <td>
                    {observation.official_rank !== null
                      ? `#${observation.official_rank}`
                      : classificationLabel(observation.classification)}
                  </td>
                  <td
                    title={
                      effectiveMetricId
                        ? evidenceText(observation.metrics[effectiveMetricId]?.reason)
                        : undefined
                    }
                  >
                    {effectiveMetricId && observation.metrics[effectiveMetricId]
                      ? metricValue(observation.metrics[effectiveMetricId])
                      : '—'}
                  </td>
                  <td>
                    <ReplayButton
                      raceId={observation.race_id}
                      replayRaceIds={replayRaceIds}
                      onOpenReplay={onOpenReplay}
                    >
                      Replay ↗
                    </ReplayButton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {sorted.some((observation) => observation.start) && (
        <section className="analysis-section">
          <div className="analysis-section-heading">
            <h4>Start outcomes</h4>
            <span>Calculated crossings · OCS stays distinct from order</span>
          </div>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>RACE</th>
                  <th>TO GUN</th>
                  <th>CROSSING ORDER</th>
                  <th>START STATUS</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((observation) => (
                  <tr key={observation.race_id}>
                    <td>
                      <button
                        className="analysis-table-link"
                        type="button"
                        onClick={() => onSelectRace(observation.race_id)}
                      >
                        {raceNames.get(observation.race_id) || observation.race_id}
                      </button>
                    </td>
                    <td>{signedSeconds(observation.start?.delta_to_gun_s ?? null)}</td>
                    <td>{observation.start?.crossing_order ?? '—'}</td>
                    <td>
                      {observation.start?.ocs
                        ? 'OCS'
                        : observation.start?.crossing_time_ms == null
                          ? 'No crossing'
                          : 'Crossing calculated'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {legNumbers.length > 0 && (
        <section className="analysis-section">
          <div className="analysis-section-heading">
            <h4>Leg performance</h4>
            <label>
              LEG{' '}
              <select
                value={effectiveLeg}
                onChange={(event) => {
                  setSelectedLeg(event.target.value)
                  setSelectedLegMetric('elapsed_s')
                }}
              >
                {legNumbers.map((leg) => (
                  <option value={leg} key={leg}>
                    Leg {leg}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {selectedLegSummary && (
            <div className="analysis-history-leg-summary">
              <label>
                EXPORTED SUMMARY{' '}
                <select
                  value={effectiveLegMetric}
                  onChange={(event) => setSelectedLegMetric(event.target.value)}
                >
                  {legMetricOptions.map(([id, label]) => (
                    <option value={id} key={id}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <div>
                <span>
                  {history.race_count === 1 ? 'OBSERVED VALUE' : 'MEDIAN'}{' '}
                  <strong>
                    {withUnit(
                      selectedLegSummary.median,
                      historicalLegMetrics.find(([id]) => id === effectiveLegMetric)?.[2] || ''
                    )}
                  </strong>
                </span>
                <span>
                  {history.race_count === 1 ? 'SINGLE RACE' : 'RANGE'}{' '}
                  <strong>
                    {history.race_count === 1
                      ? 'No trend'
                      : `${number(selectedLegSummary.min, 2)}–${number(selectedLegSummary.max, 2)} ${historicalLegMetrics.find(([id]) => id === effectiveLegMetric)?.[2] || ''}`}
                  </strong>
                </span>
                <span>
                  WITH DATA{' '}
                  <strong>
                    {selectedLegSummary.count} / {history.race_count}
                  </strong>
                </span>
              </div>
            </div>
          )}
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>RACE</th>
                  <th>LEG TIME</th>
                  <th>COURSE VMG</th>
                  <th>WIND VMG</th>
                  <th>DISTANCE</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((observation) => {
                  const leg = observation.legs?.find((candidate) => candidate.leg === effectiveLeg)
                  return (
                    <tr key={observation.race_id}>
                      <td>
                        <button
                          className="analysis-table-link"
                          type="button"
                          onClick={() => onSelectRace(observation.race_id)}
                        >
                          {raceNames.get(observation.race_id) || observation.race_id}
                        </button>
                      </td>
                      <HistoryLegCell value={leg?.elapsed_s} />
                      <HistoryLegCell value={leg?.course_vmg_kt} />
                      <HistoryLegCell value={leg?.wind_vmg_kt} />
                      <HistoryLegCell value={leg?.distance_m} />
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="analysis-micro-note">
            Leg summaries include only exported available values for this boat class and race type.
            Each value shows its quality and coverage; select a race for definitions.
          </p>
        </section>
      )}
      {history.manoeuvre_summary && (
        <section className="analysis-section">
          <div className="analysis-section-heading">
            <h4>Manoeuvre distributions</h4>
            <span>
              Events from {history.race_count} {history.race_count === 1 ? 'race' : 'races'} · tacks
              and gybes separate
            </span>
          </div>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>TYPE</th>
                  <th>EVENTS / RACES</th>
                  <th>LOSS P10</th>
                  <th>MEDIAN LOSS</th>
                  <th>LOSS P90</th>
                  <th>MEDIAN RECOVERY</th>
                  <th>UNRECOVERED</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(history.manoeuvre_summary).map(([type, summary]) => (
                  <tr key={type}>
                    <td>{type}</td>
                    <td>
                      {summary.event_count} / {summary.race_count}
                      {summary.origin_races && (
                        <small className="analysis-origin-races">
                          {Object.entries(summary.origin_races)
                            .map(
                              ([raceId, count]) => `${raceNames.get(raceId) || raceId}: ${count}`
                            )
                            .join(' · ')}
                        </small>
                      )}
                    </td>
                    <td>{withUnit(summary.loss_p10_kt, 'kt')}</td>
                    <td>{withUnit(summary.loss_median_kt, 'kt')}</td>
                    <td>{withUnit(summary.loss_p90_kt, 'kt')}</td>
                    <td>{withUnit(summary.recovery_median_s, 's')}</td>
                    <td>{summary.unrecovered_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="analysis-micro-note">
            Percentiles describe recorded events, with event and originating-race counts shown. An
            unrecovered event does not contribute a zero-second recovery.
          </p>
        </section>
      )}
      {allTeamObservations.length > history.observations.length && (
        <section className="analysis-section">
          <div className="analysis-section-heading">
            <h4>All races for {history.team_code}</h4>
            <span>Different race types stay separate in the summary above</span>
          </div>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>DATE</th>
                  <th>RACE</th>
                  <th>FORMAT</th>
                  <th>RESULT</th>
                </tr>
              </thead>
              <tbody>
                {allTeamObservations.map((observation) => (
                  <tr key={`${observation.race_id}-${observation.date}`}>
                    <td>{observation.date}</td>
                    <td>
                      <button
                        className="analysis-table-link"
                        type="button"
                        onClick={() => onSelectRace(observation.race_id)}
                      >
                        {raceNames.get(observation.race_id) || observation.race_id}
                      </button>
                    </td>
                    <td>
                      {observation.boatClass} · {raceTypeLabel(observation.raceType)}
                    </td>
                    <td>
                      {observation.official_rank !== null
                        ? `#${observation.official_rank}`
                        : classificationLabel(observation.classification)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

export function AnalysisModal({
  currentRaceId,
  replayRaceIds,
  onOpenReplay,
  onClose,
  inline = false,
  selectedBoatId,
  onSelectBoat,
  comparisonId,
  onSelectComparison,
  onSelectRace,
}: Props) {
  const viewId = useId()
  const [mode, setMode] = useState<'race' | 'history'>('race')
  const [index, setIndex] = useState<AnalysisIndex | null>(null)
  const [indexError, setIndexError] = useState<string | null>(null)
  const [raceId, setRaceId] = useState(currentRaceId)
  const [boatId, setBoatId] = useState<string | null>(null)
  const [detail, setDetail] = useState<AnalysisDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const detailCache = useRef(new Map<string, AnalysisDetail>())

  useEffect(() => {
    setRaceId(currentRaceId)
    setBoatId(null)
  }, [currentRaceId])

  useEffect(() => {
    const controller = new AbortController()
    loadAnalysisIndex(controller.signal)
      .then(setIndex)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted)
          setIndexError(
            reason instanceof Error ? reason.message : 'Analysis archive could not be loaded'
          )
      })
    return () => controller.abort()
  }, [])

  const selectedRace = useMemo(
    () => index?.races.find((race) => race.id === raceId) ?? index?.races[0],
    [index, raceId]
  )
  useEffect(() => {
    if (!selectedRace || mode !== 'race') return
    const cached = detailCache.current.get(selectedRace.id)
    if (cached) {
      setDetail(cached)
      setDetailLoading(false)
      setDetailError(null)
      return
    }
    const controller = new AbortController()
    setDetail(null)
    setDetailError(null)
    setDetailLoading(true)
    loadAnalysisDetail(selectedRace, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return
        detailCache.current.set(selectedRace.id, value)
        setDetail(value)
        setDetailLoading(false)
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        setDetailError(
          reason instanceof Error ? reason.message : 'Detailed analysis could not be loaded'
        )
        setDetailLoading(false)
      })
    return () => controller.abort()
  }, [selectedRace, mode])

  useEffect(() => {
    if (inline) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, inline])

  const chooseRace = (id: string) => {
    setRaceId(id)
    setBoatId(null)
    setMode('race')
    onSelectRace?.(id)
  }
  const chooseBoat = (id: string) => {
    setBoatId(id)
    onSelectBoat?.(id)
  }
  const content = (
    <div
      className={`analysis-modal${inline ? ' dashboard-inline-analysis' : ' modal'}`}
      role={inline ? 'region' : 'dialog'}
      aria-modal={inline ? undefined : true}
      aria-label="Race analysis and historical view"
    >
      <div className="modal-head analysis-page-heading">
        <div>
          {inline ? <h1>Race analysis</h1> : <h2>Race analysis</h2>}
          <p>Review the race. Follow the evidence.</p>
        </div>
        {!inline && (
          <button type="button" onClick={onClose} aria-label="Close analysis">
            ×
          </button>
        )}
      </div>
      <div
        className="analysis-main-tabs"
        role="tablist"
        aria-label="Analysis view"
        onKeyDown={(event) => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
          event.preventDefault()
          const next =
            event.key === 'Home'
              ? 'race'
              : event.key === 'End'
                ? 'history'
                : mode === 'race'
                  ? 'history'
                  : 'race'
          setMode(next)
          event.currentTarget
            .querySelector<HTMLButtonElement>(`[data-analysis-mode="${next}"]`)
            ?.focus()
        }}
      >
        <button
          id={viewId + '-race'}
          data-analysis-mode="race"
          type="button"
          role="tab"
          aria-controls={viewId + '-panel'}
          aria-selected={mode === 'race'}
          tabIndex={mode === 'race' ? 0 : -1}
          className={mode === 'race' ? 'active' : ''}
          onClick={() => setMode('race')}
        >
          Race report
        </button>
        <button
          id={viewId + '-history'}
          data-analysis-mode="history"
          type="button"
          role="tab"
          aria-controls={viewId + '-panel'}
          aria-selected={mode === 'history'}
          tabIndex={mode === 'history' ? 0 : -1}
          className={mode === 'history' ? 'active' : ''}
          onClick={() => setMode('history')}
        >
          Historical view
        </button>
      </div>
      {!index && !indexError && (
        <p className="analysis-state" role="status">
          Loading analysis archive…
        </p>
      )}
      {indexError && (
        <div className="analysis-state error" role="alert">
          <strong>Analysis unavailable</strong>
          <p>{indexError}</p>
          <p>Race replay remains available from the Races menu.</p>
        </div>
      )}
      {index && (
        <div role="tabpanel" id={viewId + '-panel'} aria-labelledby={viewId + '-' + mode}>
          {mode === 'race' ? (
            <RaceView
              index={index}
              race={selectedRace}
              detail={detail?.race.id === selectedRace?.id ? detail : null}
              detailLoading={detailLoading}
              detailError={detailError}
              selectedBoatId={selectedBoatId ?? boatId}
              comparisonId={comparisonId}
              onSelectComparison={onSelectComparison}
              onSelectRace={chooseRace}
              onSelectBoat={chooseBoat}
              replayRaceIds={replayRaceIds}
              onOpenReplay={onOpenReplay}
            />
          ) : (
            <HistoryView
              index={index}
              replayRaceIds={replayRaceIds}
              onOpenReplay={onOpenReplay}
              onSelectRace={chooseRace}
            />
          )}
        </div>
      )}
    </div>
  )
  return inline ? (
    content
  ) : (
    <div
      className="modal-shade"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      {content}
    </div>
  )
}
