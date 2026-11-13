import { useEffect, useState } from 'react'
import { loadAc38Forecast, loadPredictionIndex } from '../../engine/predictionCatalog'
import type { Ac38Forecast } from '../../types/prediction'

const pct = (v: number | null | undefined) => (v == null ? 'Unavailable' : `${(v * 100).toFixed(1)}%`)

function Ac38MatchupResults({ forecast, teamA, teamB, scenarioId }: {
  forecast: Ac38Forecast
  teamA: string
  teamB: string
  scenarioId: string
}) {
  const { forecast: body, uncertainty, header, structural_sensitivities } = forecast
  const p1A = body.pairwise_single_match[teamA]?.[teamB] ?? null
  const p1B = p1A == null ? null : 1 - p1A
  const p9A = body.series_best_of_9[teamA]?.[teamB] ?? null
  const p13A = body.series_best_of_13[teamA]?.[teamB] ?? null
  const mcSe = uncertainty.monte_carlo.pairwise_single_match_mc_se[teamA]?.[teamB] ?? null
  const sens = structural_sensitivities.find((s) => s.scenario_id === scenarioId) ?? structural_sensitivities[0]

  return (
    <main className="simulator-results-panel" aria-label="AC38 Forecast Output">
      <div className="matchup-headline-card">
        <div className="matchup-teams-display">
          <div className="team-box">
            <span className="team-code">ac38:{teamA}</span>
            <span className="team-win-prob">{pct(p1A)}</span>
            <small style={{ color: '#94a3b8' }}>Single Match Win Prob</small>
          </div>
          <div className="matchup-vs">
            <div>VS</div>
            {mcSe != null && (
              <div style={{ color: '#94a3b8', fontSize: '0.72rem', marginTop: '0.2rem' }}>
                MC SE: ±{(mcSe * 100).toFixed(2)} pp
              </div>
            )}
          </div>
          <div className="team-box">
            <span className="team-code">ac38:{teamB}</span>
            <span className="team-win-prob">{pct(p1B)}</span>
            <small style={{ color: '#94a3b8' }}>Single Match Win Prob</small>
          </div>
        </div>
        <div className="win-prob-bar-track" aria-hidden="true">
          <div className="win-prob-bar-fill-a" style={{ width: `${(p1A ?? 0.5) * 100}%` }} />
          <div className="win-prob-bar-fill-b" style={{ width: `${(p1B ?? 0.5) * 100}%` }} />
        </div>
      </div>

      <div className="joint-conditioning-card">
        <div className="joint-card-title">AC38 Series &amp; Tournament Context ({header.status.replaceAll('_', ' ')})</div>
        <div className="joint-metrics-row">
          <div className="joint-metric">
            <span className="joint-metric-label">Best of 9 ({teamA})</span>
            <span className="joint-metric-value">{pct(p9A)}</span>
          </div>
          <div className="joint-metric">
            <span className="joint-metric-label">Best of 13 ({teamA})</span>
            <span className="joint-metric-value">{pct(p13A)}</span>
          </div>
          <div className="joint-metric">
            <span className="joint-metric-label">Exp Fleet Pos ({teamA} / {teamB})</span>
            <span className="joint-metric-value">
              {body.expected_fleet_position[teamA].toFixed(2)} / {body.expected_fleet_position[teamB].toFixed(2)}
            </span>
          </div>
          <div className="joint-metric">
            <span className="joint-metric-label">Cup Bounds · {sens.label}</span>
            <span className="joint-metric-value">
              {teamA}: {pct(sens.trophy_rule_bounds[teamA].lower)}–{pct(sens.trophy_rule_bounds[teamA].upper)} · {teamB}: {pct(sens.trophy_rule_bounds[teamB].lower)}–{pct(sens.trophy_rule_bounds[teamB].upper)}
            </span>
          </div>
        </div>
        <small>
          Cutoff: {header.issuance_cutoff_utc} · {header.conditioning}
        </small>
      </div>

      <div className="attribution-card">
        <h3>Physical Breakdown Status</h3>
        <p style={{ margin: '0.25rem 0 0', fontSize: '0.88rem', color: '#94a3b8' }}>
          AC38 simulated race times, manoeuvre-time breakdowns, and wind-response adjustments are unavailable until a separately validated AC38 physical model supports them. Switch to &quot;AC37 historical simulation&quot; above to inspect AC37 kinematic race times and manoeuvre breakdowns.
        </p>
      </div>
    </main>
  )
}

export function Ac38SimulatorMode() {
  const [forecast, setForecast] = useState<Ac38Forecast | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [teamA, setTeamA] = useState('ETNZ')
  const [teamB, setTeamB] = useState('LUNA_ROSSA')
  const [scenarioId, setScenarioId] = useState('residual_scale_1x')

  useEffect(() => {
    const controller = new AbortController()
    void loadPredictionIndex(controller.signal)
      .then((idx) => {
        if (!idx.ac38_forecast_path) throw new Error('No published AC38 forecast in prediction index.')
        return loadAc38Forecast(idx.ac38_forecast_path, controller.signal)
      })
      .then((doc) => {
        if (controller.signal.aborted) return
        setForecast(doc)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setError(err instanceof Error ? err.message : 'Unable to load AC38 forecast artifact.')
        setLoading(false)
      })
    return () => controller.abort()
  }, [])

  if (loading) return <div className="simulator-loading">Loading published AC38 forecast model...</div>
  if (error || !forecast) return <div className="simulator-error">AC38 forecast mode unavailable: {error ?? 'Not published.'}</div>

  return (
    <div className="simulator-grid">
      <aside className="simulator-controls-panel" aria-label="AC38 Forecast Controls">
        <div className="control-section">
          <h3>AC38 Competitors</h3>
          <div className="form-row">
            <label htmlFor="ac38-team-a-select">Entry A</label>
            <select id="ac38-team-a-select" className="form-select" value={teamA} onChange={(e) => {
              const next = e.target.value
              if (next === teamB) setTeamB(teamA)
              setTeamA(next)
            }}>
              {forecast.teams.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.campaign_team_id})</option>)}
            </select>
          </div>
          <div className="form-row">
            <label htmlFor="ac38-team-b-select">Entry B</label>
            <select id="ac38-team-b-select" className="form-select" value={teamB} onChange={(e) => {
              const next = e.target.value
              if (next === teamA) setTeamA(teamB)
              setTeamB(next)
            }}>
              {forecast.teams.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.campaign_team_id})</option>)}
            </select>
          </div>
        </div>
        <div className="control-section">
          <h3>Cup Sensitivity View</h3>
          <div className="form-row">
            <label htmlFor="ac38-scenario-select">Structural / Reliability Assumption</label>
            <select id="ac38-scenario-select" className="form-select" value={scenarioId} onChange={(e) => setScenarioId(e.target.value)}>
              {forecast.structural_sensitivities.map((s) => (
                <option key={s.scenario_id} value={s.scenario_id}>{s.label}</option>
              ))}
            </select>
          </div>
          <small style={{ color: '#94a3b8' }}>
            Static-deployable published forecast ({forecast.header.selected_transfer_candidate.replaceAll('_', ' ')} transfer, telemetry retained: {String(forecast.header.telemetry_retained)}, κ={forecast.header.scale_kappa}, wind response off).
          </small>
        </div>
      </aside>
      <Ac38MatchupResults forecast={forecast} teamA={teamA} teamB={teamB} scenarioId={scenarioId} />
    </div>
  )
}
