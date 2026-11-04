import { useMemo, useState } from 'react'
import { getStandings } from '../../engine/analytics'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'

interface RaceStatusLeaderboardProps {
  replay: ReplayManifest
  frame: ReplayFrame
  selectedId: string | null
  onSelectBoat: (id: string) => void
}

function formatCountdown(deltaGunMs: number): string {
  const absSec = Math.floor(Math.abs(deltaGunMs) / 1000)
  const mm = Math.floor(absSec / 60)
  const ss = absSec % 60
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

export function RaceStatusLeaderboard({
  replay,
  frame,
  selectedId,
  onSelectBoat,
}: RaceStatusLeaderboardProps) {
  const [courseLayersOpen, setCourseLayersOpen] = useState(false)
  const standings = useMemo(() => getStandings(replay, frame), [replay, frame])

  const leader = standings.find((entry) => entry.rank === 1)
  const runnerUp = standings.find((entry) => entry.rank === 2)
  const totalLegs = Math.max(0, (replay.course.sequences?.length ?? 1) - 1)
  const isPreStart = frame.timestamp < replay.chronology.gun_time
  const activeLeg = isPreStart ? 0 : leader?.frame.leg ?? 0
  const leadMargin = runnerUp?.gapS !== null && runnerUp?.gapS !== undefined && Number.isFinite(runnerUp.gapS)
    ? `+${formatCountdown(runnerUp.gapS * 1000)}${runnerUp.gapIsEstimate ? ' est.' : ''}`
    : 'Unavailable'

  // Countdown or start in clock
  const startInStr = useMemo(() => {
    const deltaGunMs = replay.chronology.gun_time - frame.timestamp
    if (deltaGunMs > 0) {
      return formatCountdown(deltaGunMs)
    }
    return '00:00'
  }, [frame.timestamp, replay.chronology.gun_time])

  const racePhaseText = isPreStart ? 'Pre-start' : frame.timestamp >= replay.chronology.window_end ? 'Replay end' : 'Racing'

  return (
    <aside className="race-status-leaderboard-card" aria-label="Fleet Leaderboard">
      {/* 1. Header with Status & Leg count */}
      <div className="card-header leaderboard-header">
        <div className="header-status-left">
          <strong className="panel-title">Fleet</strong>
          <span className="live-status-dot" />
          <span className="phase-text">{racePhaseText}</span>
        </div>
        <div className="header-leg-right">
          <span className="leg-badge">Leg {activeLeg} / {totalLegs}</span>
        </div>
      </div>

      {/* 2. Top 3 Summary KPI Cards */}
      <div className="leaderboard-kpi-row">
        {/* Card 1: Distance to finish */}
        <div className="kpi-mini-card">
          <span className="kpi-mini-label">Distance to finish</span>
            <strong className="kpi-mini-val" title="A course-route remaining-distance metric is not exported">Unavailable</strong>
        </div>

        {/* Card 2: Leader */}
        <div className="kpi-mini-card">
          <span className="kpi-mini-label">Leader</span>
          <div className="kpi-leader-badge">
            <span
              className="leader-color-bar"
              style={{ backgroundColor: leader?.competitor.color ?? '#64748b' }}
            />
            <strong className="kpi-mini-val leader-name">
              {leader?.competitor.team_code ?? 'Unavailable'}
            </strong>
          </div>
        </div>

        {/* Card 3: Start in */}
        <div className="kpi-mini-card">
          <span className="kpi-mini-label">{isPreStart ? 'Start in' : 'Lead Margin'}</span>
          <strong className="kpi-mini-val timer-val" title="While racing, the time gap is an estimate: progress difference in metres divided by leader speed in m/s. Finished gaps use timing calculated from race telemetry.">
              {isPreStart ? startInStr : leadMargin}
          </strong>
        </div>
      </div>

      {/* 3. Fleet Leaderboard Table */}
      <div className="fleet-table-container">
        <table className="fleet-table" role="table">
          <thead>
            <tr>
              <th className="th-rank">#</th>
              <th className="th-boat">Boat</th>
              <th className="th-sog">SOG</th>
              <th className="th-vmg">VMG</th>
              <th className="th-twa">TWA</th>
              <th className="th-tws">TWS</th>
            </tr>
          </thead>
          <tbody>
            {standings.map((entry) => {
              const isSelected = entry.competitor.id === selectedId
              const boatState = entry.frame
              const rankNum = entry.rank ?? '—'

              return (
                <tr
                  key={entry.competitor.id}
                  className={`fleet-table-row ${isSelected ? 'selected' : ''}`}
                  onClick={() => onSelectBoat(entry.competitor.id)}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onSelectBoat(entry.competitor.id)
                    }
                  }}
                >
                  <td className="td-rank">{rankNum}</td>
                  <td className="td-boat">
                    <div className="boat-cell-flex">
                      <span
                        className="boat-color-badge"
                        style={{ backgroundColor: entry.competitor.color }}
                      />
                      <span className="boat-code-text">{entry.competitor.team_code}</span>
                    </div>
                  </td>
                  <td className="td-sog">{boatState.sog.toFixed(1)} kt</td>
                  <td className={`td-vmg ${boatState.vmg < 0 ? 'neg' : ''}`}>
                    {boatState.vmg.toFixed(1)} kt
                  </td>
                  <td className="td-twa">{Math.round(boatState.twa)}°</td>
                  <td className="td-tws">{boatState.tws.toFixed(1)} kt</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* 4. Bottom Collapsible: Course & layers */}
      <div className="course-layers-collapse">
        <button
          type="button"
          className="collapse-trigger-btn"
          onClick={() => setCourseLayersOpen((prev) => !prev)}
          aria-expanded={courseLayersOpen}
        >
          <span className="chevron-icon">{courseLayersOpen ? '▾' : '▸'}</span>
          <span>Course & layers</span>
        </button>
        {courseLayersOpen && (
          <div className="collapse-content-drawer">
            <div className="layer-row">
              <span>Race Corridor Boundaries</span>
              <span className="layer-tag">ACTIVE</span>
            </div>
            <div className="layer-row">
              <span>Dynamic Marks (RM1-RM8)</span>
              <span className="layer-tag">ACTIVE</span>
            </div>
            <div className="layer-row">
              <span>Official wind direction arrows</span>
              <span className="layer-tag">REPLAY</span>
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
