import { useEffect, useRef, useState } from 'react'
import type { AnyKinematicScenario, KinematicCatalog, KinematicCatalogCourse } from '../../types/kinematic'
import { isKinematicScenarioV2 } from '../../types/kinematic'
import { loadKinematicCatalog, requestKinematicSimulation } from '../../engine/kinematicCatalog'
import { Ac38SimulatorMode } from './Ac38SimulatorMode'
import './simulator.css'

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return 'N/A'
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${String(s).padStart(2, '0')}s`
}

const DEFAULT_COURSES: KinematicCatalogCourse[] = [
  { course_id: 'barcelona_lvc_4leg', label: 'Barcelona 4-Leg Match (1500m)' },
  { course_id: 'barcelona_6leg_1500m', label: 'Barcelona 6-Leg Match (1500m)' },
  { course_id: 'barcelona_6leg_1852m', label: 'Barcelona 6-Leg Championship (1.0 nm)' },
  { course_id: 'barcelona_8leg_1852m', label: 'Barcelona 8-Leg Long Course (1.0 nm)' },
]

export function SimulatorWorkspace() {
  const [catalog, setCatalog] = useState<KinematicCatalog | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [teamA, setTeamA] = useState('ac37:ETNZ')
  const [teamB, setTeamB] = useState('ac37:INEOS')
  const [twsKt, setTwsKt] = useState(11.66)
  const [twdDeg, setTwdDeg] = useState(180.0)
  const [courseId, setCourseId] = useState('barcelona_lvc_4leg')
  const [mode, setMode] = useState('ac75_learned_v2')
  const [simDomain, setSimDomain] = useState<'ac37_historical' | 'ac38_forecast'>('ac37_historical')

  // Sliders for AC38 Rule adjustments
  const [batteryPowerOffset, setBatteryPowerOffset] = useState(0.0)
  const [maneuverLossMultiplier, setManeuverLossMultiplier] = useState(1.0)
  const [foilSpanFactor, setFoilSpanFactor] = useState(1.0)

  const [activeScenario, setActiveScenario] = useState<AnyKinematicScenario | null>(null)
  const [simulating, setSimulating] = useState(false)
  const simAbortRef = useRef<AbortController | null>(null)
  const requestSequenceRef = useRef<number>(0)

  // 1. Initial catalog load
  useEffect(() => {
    const controller = new AbortController()
    loadKinematicCatalog(controller.signal)
      .then((cat) => {
        setCatalog(cat)
        setLoading(false)
        const scenarios = Array.isArray(cat.scenarios) ? cat.scenarios : []
        const firstV2 = scenarios.find(isKinematicScenarioV2)
        if (firstV2) {
          setMode('ac75_learned_v2')
          setTeamA(firstV2.applied_inputs.team_a)
          setTeamB(firstV2.applied_inputs.team_b)
          if (firstV2.applied_inputs.course_id) {
            setCourseId(firstV2.applied_inputs.course_id)
          }
          const env = firstV2.applied_inputs.environment
          if (env) {
            if (env.tws_mps != null) {
              setTwsKt(Number((env.tws_mps * (3600 / 1852)).toFixed(1)))
            }
            if (env.twd_deg != null) {
              setTwdDeg(Number(env.twd_deg))
            }
          }
          setActiveScenario(firstV2)
        } else {
          setMode('barcelona_2024_empirical')
          setTeamA('ETNZ')
          setTeamB('GB1')
          const defaultV1 =
            scenarios.find(
              (s) =>
                !isKinematicScenarioV2(s) &&
                s.team_a === 'ETNZ' &&
                s.team_b === 'GB1' &&
                s.mode === 'barcelona_2024_empirical'
            ) || scenarios[0]
          setActiveScenario(defaultV1 || null)
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(err.message || 'Failed to load simulator catalog')
          setLoading(false)
        }
      })
    return () => controller.abort()
  }, [])

  // 2. Run simulation on parameter changes
  const runSimulation = () => {
    const seq = ++requestSequenceRef.current
    if (simAbortRef.current) {
      simAbortRef.current.abort()
    }
    const controller = new AbortController()
    simAbortRef.current = controller
    setSimulating(true)

    const ruleAdjustments =
      mode === 'barcelona_2024_empirical_with_ac38_rules'
        ? {
            cyclor_power_boost_kt: batteryPowerOffset,
            maneuver_loss_multiplier: maneuverLossMultiplier,
            foil_span_limit_factor: foilSpanFactor,
          }
        : undefined

    requestKinematicSimulation(
      teamA,
      teamB,
      twsKt,
      mode,
      ruleAdjustments,
      controller.signal,
      { course_id: courseId, twd_deg: twdDeg }
    )
      .then((res) => {
        if (seq === requestSequenceRef.current && !controller.signal.aborted) {
          setActiveScenario(res)
          setError(null)
          setSimulating(false)
        }
      })
      .catch((err) => {
        if (seq === requestSequenceRef.current && !controller.signal.aborted) {
          console.error('Simulation error:', err)
          setError(err.message || 'Simulation failed')
          setSimulating(false)
        }
      })
  }

  const resetSliders = () => {
    setBatteryPowerOffset(0.0)
    setManeuverLossMultiplier(1.0)
    setFoilSpanFactor(1.0)
  }

  const isStale = (() => {
    if (!activeScenario) return false
    if (isKinematicScenarioV2(activeScenario)) {
      const inp = activeScenario.applied_inputs
      if (!inp) return false
      if (inp.team_a !== teamA || inp.team_b !== teamB) return true
      if ((inp.course_id || 'barcelona_lvc_4leg') !== courseId) return true
      const env = inp.environment
      if (env) {
        if (env.tws_mps != null) {
          const scenarioTwsKt = Number((env.tws_mps * (3600 / 1852)).toFixed(1))
          if (Math.abs(scenarioTwsKt - twsKt) > 0.15) return true
        }
        if (env.twd_deg != null && Math.abs(Number(env.twd_deg) - twdDeg) > 0.5) {
          return true
        }
      }
      return false
    } else {
      if (activeScenario.team_a !== teamA || activeScenario.team_b !== teamB) return true
      if (Math.abs((activeScenario.tws_kt ?? 0) - twsKt) > 0.15) return true
      if (activeScenario.mode !== mode) return true
      return false
    }
  })()

  const teams = catalog?.available_teams || [
    'ac37:ETNZ',
    'ac37:INEOS',
    'ac37:LUNA_ROSSA',
    'ac37:AMERICAN_MAGIC',
    'ac37:ALINGHI',
    'ac37:ORIENT_EXPRESS',
  ]
  const courses =
    catalog?.courses && catalog.courses.length > 0 ? catalog.courses : DEFAULT_COURSES
  const modelStatus = catalog?.model_status || 'experimental'

  const v2Scenario =
    activeScenario && isKinematicScenarioV2(activeScenario) ? activeScenario : null
  const v2Accounting =
    v2Scenario?.applied_inputs?.seconds_accounting || v2Scenario?.time_accounting || null
  const v2Variance = v2Scenario?.applied_inputs?.variance_attribution || null

  return (
    <section className="simulator-workspace" aria-label="Kinematic Match Simulator">
      <div className="simulator-header">
        <div className="simulator-title-group">
          <h2>AC75 Kinematic Match Simulator</h2>
          <p className="simulator-subtitle">
            AC37 Telemetry-Learned Performance Simulator with paired residual bootstrap, observed leg routes, and right-censored maneuver durations.
          </p>
        </div>
        <div>
          <span className={`simulator-status-badge ${modelStatus}`}>
            STATUS: {modelStatus.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="simulator-mode-bar" role="tablist" aria-label="Simulator mode selector">
        <button
          type="button"
          role="tab"
          aria-selected={simDomain === 'ac37_historical'}
          className={`simulator-mode-tab ${simDomain === 'ac37_historical' ? 'is-active' : ''}`}
          onClick={() => setSimDomain('ac37_historical')}
        >
          AC37 historical simulation
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={simDomain === 'ac38_forecast'}
          className={`simulator-mode-tab ${simDomain === 'ac38_forecast' ? 'is-active' : ''}`}
          onClick={() => setSimDomain('ac38_forecast')}
        >
          AC38 forecast
        </button>
      </div>

      {simDomain === 'ac38_forecast' ? (
        <Ac38SimulatorMode />
      ) : (
        <>
          <div className="simulator-notice-callout">
            <strong>Notice:</strong>{' '}
            {catalog?.status_notice ||
              'AC37 Learned Simulator (kinematic-race-sim-2) uses archive-fitted polar/neural speed ratios, observed route templates, and disjoint seconds accounting.'}
          </div>

          {loading && <div className="simulator-loading">Loading staged kinematic catalog...</div>}
          {error && <div className="simulator-error">Error: {error}</div>}

          {!loading && (
        <div className="simulator-grid">
          {/* Controls Column */}
          <aside className="simulator-controls-panel" aria-label="Simulator Controls">
            <div className="control-section">
              <h3>Match Competitors</h3>
              <div className="form-row">
                <label htmlFor="team-a-select">Port Entry (Team A)</label>
                <select
                  id="team-a-select"
                  className="form-select"
                  value={teamA}
                  onChange={(e) => {
                    const nextA = e.target.value
                    if (nextA === teamB) {
                      setTeamB(teamA)
                    }
                    setTeamA(nextA)
                  }}
                >
                  {teams.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-row">
                <label htmlFor="team-b-select">Starboard Entry (Team B)</label>
                <select
                  id="team-b-select"
                  className="form-select"
                  value={teamB}
                  onChange={(e) => {
                    const nextB = e.target.value
                    if (nextB === teamA) {
                      setTeamA(teamB)
                    }
                    setTeamB(nextB)
                  }}
                >
                  {teams.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="control-section">
              <h3>Simulation Mode &amp; Course</h3>
              <div className="form-row">
                <label htmlFor="mode-select">Model Family</label>
                <select
                  id="mode-select"
                  className="form-select"
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                >
                  <option value="ac75_learned_v2">AC75 Learned Simulator (v2)</option>
                  <option value="barcelona_2024_empirical">Empirical Barcelona 2024 AC75 (v1)</option>
                  <option value="barcelona_2024_empirical_with_ac38_rules">
                    Empirical + AC38 Rule Adjustments (v1)
                  </option>
                </select>
              </div>

              {mode === 'ac75_learned_v2' && (
                <div className="form-row">
                  <label htmlFor="course-select">Course Preset</label>
                  <select
                    id="course-select"
                    className="form-select"
                    value={courseId}
                    onChange={(e) => setCourseId(e.target.value)}
                  >
                    {courses.map((c) => {
                      const cid = c.course_id || c.preset_id || 'barcelona_lvc_4leg'
                      const clabel = c.label || c.name || cid
                      return (
                        <option key={cid} value={cid}>
                          {clabel}
                        </option>
                      )
                    })}
                  </select>
                </div>
              )}
            </div>

            <div className="control-section">
              <h3>Environmental Conditions</h3>
              <div className="slider-container">
                <div className="slider-header">
                  <span>True Wind Speed (TWS)</span>
                  <span className="slider-val">{twsKt.toFixed(1)} kt</span>
                </div>
                <input
                  type="range"
                  className="slider-input"
                  min="7.5"
                  max="20.0"
                  step="0.5"
                  value={twsKt}
                  onChange={(e) => setTwsKt(parseFloat(e.target.value))}
                />
              </div>

              {mode === 'ac75_learned_v2' && (
                <div className="slider-container">
                  <div className="slider-header">
                    <span>True Wind Direction (TWD)</span>
                    <span className="slider-val">{twdDeg.toFixed(0)}°</span>
                  </div>
                  <input
                    type="range"
                    className="slider-input"
                    min="0"
                    max="355"
                    step="5"
                    value={twdDeg}
                    onChange={(e) => setTwdDeg(parseFloat(e.target.value))}
                  />
                </div>
              )}
            </div>

            {mode === 'barcelona_2024_empirical_with_ac38_rules' && (
              <div className="control-section">
                <h3>AC38 Rule Parameters</h3>

                <div className="slider-container">
                  <div className="slider-header">
                    <span>Battery / Cyclor Power Offset</span>
                    <span className="slider-val">
                      {batteryPowerOffset > 0
                        ? `+${batteryPowerOffset.toFixed(1)}`
                        : batteryPowerOffset.toFixed(1)}{' '}
                      kt
                    </span>
                  </div>
                  <input
                    type="range"
                    className="slider-input"
                    min="-1.0"
                    max="1.0"
                    step="0.1"
                    value={batteryPowerOffset}
                    onChange={(e) => setBatteryPowerOffset(parseFloat(e.target.value))}
                  />
                </div>

                <div className="slider-container">
                  <div className="slider-header">
                    <span>Maneuver Loss Multiplier</span>
                    <span className="slider-val">{maneuverLossMultiplier.toFixed(2)}x</span>
                  </div>
                  <input
                    type="range"
                    className="slider-input"
                    min="0.80"
                    max="1.20"
                    step="0.05"
                    value={maneuverLossMultiplier}
                    onChange={(e) => setManeuverLossMultiplier(parseFloat(e.target.value))}
                  />
                </div>

                <div className="slider-container">
                  <div className="slider-header">
                    <span>Foil Span Limit Factor</span>
                    <span className="slider-val">{foilSpanFactor.toFixed(2)}x</span>
                  </div>
                  <input
                    type="range"
                    className="slider-input"
                    min="0.95"
                    max="1.10"
                    step="0.01"
                    value={foilSpanFactor}
                    onChange={(e) => setFoilSpanFactor(parseFloat(e.target.value))}
                  />
                </div>

                <button type="button" className="simulator-reset-btn" onClick={resetSliders}>
                  Reset Parameters
                </button>
              </div>
            )}

            <button
              type="button"
              className="popover-footer-btn"
              style={{ marginTop: '0.5rem', width: '100%' }}
              onClick={runSimulation}
              disabled={simulating}
            >
              {simulating ? 'Running Monte Carlo...' : 'Run Simulation'}
            </button>
          </aside>

          {/* Results Column */}
          <main className={`simulator-results-panel ${isStale ? 'stale-results' : ''}`} aria-label="Simulation Output">
            {isStale && (
              <output className="simulator-stale-notice" data-testid="stale-notice">
                <strong>Inputs Changed:</strong> Displayed simulation reflects previous parameters. Click &quot;Run Simulation&quot; to compute exact outcomes.
              </output>
            )}
            {v2Scenario && (
              <>
                {v2Scenario.status !== 'available' ? (
                  <div className="simulator-error" data-testid="unavailable-scenario-banner">
                    <strong>Scenario Unavailable:</strong>{' '}
                    {(v2Scenario.reason_codes || []).join(', ') ||
                      'Insufficient telemetry support for requested conditions.'}
                  </div>
                ) : (
                  <>
                    <div className="matchup-headline-card">
                      <div className="matchup-teams-display">
                        <div className="team-box">
                          <span className="team-code">{v2Scenario.applied_inputs.team_a}</span>
                          <span className="team-win-prob">
                            {((v2Scenario.probabilities?.win_a ?? 0) * 100).toFixed(1)}%
                          </span>
                          <small style={{ color: '#94a3b8' }}>Port Entry</small>
                        </div>

                        <div className="matchup-vs">
                          <div>VS</div>
                          {v2Scenario.probabilities?.mc_error != null && (
                            <div style={{ color: '#94a3b8', fontSize: '0.72rem', marginTop: '0.2rem' }}>
                              MC SE: ±{(v2Scenario.probabilities.mc_error * 100).toFixed(1)}%
                            </div>
                          )}
                          {(v2Scenario.probabilities?.no_winner ?? 0) > 0 && (
                            <div style={{ color: '#ef4444', fontSize: '0.72rem', marginTop: '0.2rem' }}>
                              No finish:{' '}
                              {((v2Scenario.probabilities?.no_winner ?? 0) * 100).toFixed(1)}%
                            </div>
                          )}
                        </div>

                        <div className="team-box">
                          <span className="team-code">{v2Scenario.applied_inputs.team_b}</span>
                          <span className="team-win-prob">
                            {((v2Scenario.probabilities?.win_b ?? 0) * 100).toFixed(1)}%
                          </span>
                          <small style={{ color: '#94a3b8' }}>Starboard Entry</small>
                        </div>
                      </div>

                      <div className="win-prob-bar-track" aria-hidden="true">
                        <div
                          className="win-prob-bar-fill-a"
                          style={{ width: `${(v2Scenario.probabilities?.win_a ?? 0) * 100}%` }}
                        />
                        <div
                          className="win-prob-bar-fill-b"
                          style={{ width: `${(v2Scenario.probabilities?.win_b ?? 0) * 100}%` }}
                        />
                      </div>
                    </div>

                    {/* V2 Timing & Central 80% Simulated Margin Interval */}
                    <div className="joint-conditioning-card">
                      <div className="joint-card-title">
                        Simulated Race Times &amp; Central 80% Simulated Margin Interval
                      </div>
                      <div className="joint-metrics-row">
                        <div className="joint-metric">
                          <span className="joint-metric-label">
                            {v2Scenario.applied_inputs.team_a} Sim Time
                          </span>
                          <span className="joint-metric-value">
                            {formatDuration(v2Scenario.timing?.mean_time_a_s)}
                          </span>
                        </div>

                        <div className="joint-metric">
                          <span className="joint-metric-label">
                            {v2Scenario.applied_inputs.team_b} Sim Time
                          </span>
                          <span className="joint-metric-value">
                            {formatDuration(v2Scenario.timing?.mean_time_b_s)}
                          </span>
                        </div>

                        <div className="joint-metric">
                          <span className="joint-metric-label">Expected ΔT (Tb - Ta)</span>
                          <span className="joint-metric-value">
                            {v2Scenario.timing?.mean_delta_t_s != null
                              ? `${v2Scenario.timing.mean_delta_t_s > 0 ? '+' : ''}${v2Scenario.timing.mean_delta_t_s.toFixed(1)}s`
                              : 'N/A'}
                          </span>
                        </div>

                        <div className="joint-metric">
                          <span className="joint-metric-label">
                            Central 80% simulated margin interval
                          </span>
                          <span className="joint-metric-value">
                            {v2Scenario.timing?.central_80_margin_interval_s != null
                              ? `[${v2Scenario.timing.central_80_margin_interval_s[0].toFixed(1)}s, ${v2Scenario.timing.central_80_margin_interval_s[1].toFixed(1)}s]`
                              : 'N/A'}
                          </span>
                        </div>
                      </div>
                      <small>
                        {v2Scenario.probability_scope === 'completion_assumed_on_water'
                          ? '* Probabilities and timing are conditioned on on-water completion (no_winner = null; ties split 0.5/0.5).'
                          : '* Timing metrics are evaluated across completed trials.'}
                      </small>
                    </div>

                    {/* Disjoint Seconds Accounting */}
                    <div className="attribution-card">
                      <h3>Disjoint Seconds Accounting (Straight + Maneuver + Start = Total ΔT)</h3>
                      <table className="attribution-table">
                        <thead>
                          <tr>
                            <th>Disjoint Phase</th>
                            <th>Advantage To</th>
                            <th>Signed ΔT Contribution (Tb - Ta)</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>Straight-Line Sailing</td>
                            <td>
                              {(v2Accounting?.straight_delta_s ?? 0) >= 0
                                ? v2Scenario.applied_inputs.team_a
                                : v2Scenario.applied_inputs.team_b}
                            </td>
                            <td
                              className={`attr-val ${(v2Accounting?.straight_delta_s ?? 0) >= 0 ? 'positive' : 'negative'}`}
                            >
                              {(v2Accounting?.straight_delta_s ?? 0).toFixed(2)}s
                            </td>
                          </tr>
                          <tr>
                            <td>Maneuver Execution (Tacks &amp; Gybes)</td>
                            <td>
                              {(v2Accounting?.maneuver_delta_s ?? 0) >= 0
                                ? v2Scenario.applied_inputs.team_a
                                : v2Scenario.applied_inputs.team_b}
                            </td>
                            <td
                              className={`attr-val ${(v2Accounting?.maneuver_delta_s ?? 0) >= 0 ? 'positive' : 'negative'}`}
                            >
                              {(v2Accounting?.maneuver_delta_s ?? 0).toFixed(2)}s
                            </td>
                          </tr>
                          <tr>
                            <td>Start Box Entry &amp; Acceleration</td>
                            <td>
                              {(v2Accounting?.start_delta_s ?? 0) >= 0
                                ? v2Scenario.applied_inputs.team_a
                                : v2Scenario.applied_inputs.team_b}
                            </td>
                            <td
                              className={`attr-val ${(v2Accounting?.start_delta_s ?? 0) >= 0 ? 'positive' : 'negative'}`}
                            >
                              {(v2Accounting?.start_delta_s ?? 0).toFixed(2)}s
                            </td>
                          </tr>
                          <tr>
                            <td>
                              <strong>Total Mean ΔT</strong>
                            </td>
                            <td>
                              {(v2Accounting?.total_mean_delta_s ?? 0) >= 0
                                ? v2Scenario.applied_inputs.team_a
                                : v2Scenario.applied_inputs.team_b}
                            </td>
                            <td
                              className={`attr-val ${(v2Accounting?.total_mean_delta_s ?? 0) >= 0 ? 'positive' : 'negative'}`}
                            >
                              <strong>
                                {(v2Accounting?.total_mean_delta_s ?? 0).toFixed(2)}s
                              </strong>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    {/* Variance Attribution Ledger */}
                    <div className="attribution-card">
                      <h3>Variance Attribution &amp; Provenance Ledger</h3>
                      <table className="status-table">
                        <thead>
                          <tr>
                            <th>Component</th>
                            <th>Method / Value</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>Serial Execution Variation</td>
                            <td>
                              {v2Variance?.serial_execution_variation ||
                                '30-second empirical block residual bootstrap'}
                            </td>
                          </tr>
                          <tr>
                            <td>Shared Conditions Variation</td>
                            <td>
                              {v2Variance?.shared_conditions_variation ||
                                'Contemporaneous paired-boat residual correlation'}
                            </td>
                          </tr>
                          <tr>
                            <td>Paired Residual Blocks / Correlation</td>
                            <td>
                              {v2Variance?.empirical_paired_block_count ?? 0} blocks (r ={' '}
                              {(v2Variance?.empirical_cross_boat_correlation ?? 0.5).toFixed(3)})
                            </td>
                          </tr>
                          <tr>
                            <td>Model ID / Scenario ID</td>
                            <td>
                              <code>{v2Scenario.model_id}</code> /{' '}
                              <code>{v2Scenario.scenario_id}</code>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </>
            )}

            {activeScenario && !isKinematicScenarioV2(activeScenario) && (
              <>
                <div className="matchup-headline-card">
                  <div className="matchup-teams-display">
                    <div className="team-box">
                      <span className="team-code">{activeScenario.team_a}</span>
                      <span className="team-win-prob">
                        {(activeScenario.win_probability_a * 100).toFixed(1)}%
                      </span>
                      <small style={{ color: '#94a3b8' }}>Port Entry</small>
                    </div>

                    <div className="matchup-vs">
                      <div>VS</div>
                      {(activeScenario.no_winner_probability ?? 0) > 0 && (
                        <div style={{ color: '#ef4444', fontSize: '0.72rem', marginTop: '0.2rem' }}>
                          No finish: {((activeScenario.no_winner_probability ?? 0) * 100).toFixed(1)}%
                        </div>
                      )}
                    </div>

                    <div className="team-box">
                      <span className="team-code">{activeScenario.team_b}</span>
                      <span className="team-win-prob">
                        {(activeScenario.win_probability_b * 100).toFixed(1)}%
                      </span>
                      <small style={{ color: '#94a3b8' }}>Starboard Entry</small>
                    </div>
                  </div>

                  <div className="win-prob-bar-track" aria-hidden="true">
                    <div
                      className="win-prob-bar-fill-a"
                      style={{ width: `${activeScenario.win_probability_a * 100}%` }}
                    />
                    <div
                      className="win-prob-bar-fill-b"
                      style={{ width: `${activeScenario.win_probability_b * 100}%` }}
                    />
                  </div>
                </div>

                {/* Joint Finisher Conditioning Card */}
                <div className="joint-conditioning-card">
                  <div className="joint-card-title">
                    Joint-Finisher Conditioning &amp; Simulation Times
                  </div>
                  <div className="joint-metrics-row">
                    <div className="joint-metric">
                      <span className="joint-metric-label">Joint Completion Rate</span>
                      <span className="joint-metric-value">
                        {(activeScenario.joint_finisher_conditioning.both_finished_fraction * 100).toFixed(1)}%
                      </span>
                    </div>

                    {activeScenario.joint_finisher_conditioning.mean_time_a_s != null && (
                      <div className="joint-metric">
                        <span className="joint-metric-label">{activeScenario.team_a} Sim Time</span>
                        <span className="joint-metric-value">
                          {formatDuration(activeScenario.joint_finisher_conditioning.mean_time_a_s)}
                        </span>
                      </div>
                    )}

                    {activeScenario.joint_finisher_conditioning.mean_time_b_s != null && (
                      <div className="joint-metric">
                        <span className="joint-metric-label">{activeScenario.team_b} Sim Time</span>
                        <span className="joint-metric-value">
                          {formatDuration(activeScenario.joint_finisher_conditioning.mean_time_b_s)}
                        </span>
                      </div>
                    )}

                    <div className="joint-metric">
                      <span className="joint-metric-label">Expected ΔT (Tb - Ta)</span>
                      <span className="joint-metric-value">
                        {activeScenario.joint_finisher_conditioning.mean_delta_t_s != null
                          ? `${activeScenario.joint_finisher_conditioning.mean_delta_t_s > 0 ? '+' : ''}${activeScenario.joint_finisher_conditioning.mean_delta_t_s}s`
                          : 'N/A'}
                      </span>
                    </div>

                    <div className="joint-metric">
                      <span className="joint-metric-label">
                        Central 80% simulated margin interval
                      </span>
                      <span className="joint-metric-value">
                        {activeScenario.joint_finisher_conditioning.p10_delta_t_s != null
                          ? `[${activeScenario.joint_finisher_conditioning.p10_delta_t_s}s, ${activeScenario.joint_finisher_conditioning.p90_delta_t_s}s]`
                          : 'N/A'}
                      </span>
                    </div>
                  </div>
                  <small>
                    * Delta T and attribution values are evaluated strictly conditional on both boats completing the race. DNF runs are excluded from time deltas.
                  </small>
                </div>

                {/* 7-Component Counterfactual Attribution */}
                <div className="attribution-card">
                  <h3>7-Component Additive Performance Attribution</h3>
                  <table className="attribution-table">
                    <thead>
                      <tr>
                        <th>Phase / Factor</th>
                        <th>Advantage To</th>
                        <th>Margin Contribution</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeScenario.attribution_7_component && (
                        <>
                          <tr>
                            <td>Pre-Start Positioning</td>
                            <td>
                              {(activeScenario.attribution_7_component.pre_start_positioning_s || 0) >= 0
                                ? activeScenario.team_a
                                : activeScenario.team_b}
                            </td>
                            <td
                              className={`attr-val ${(activeScenario.attribution_7_component.pre_start_positioning_s || 0) >= 0 ? 'positive' : 'negative'}`}
                            >
                              {Math.abs(
                                activeScenario.attribution_7_component.pre_start_positioning_s || 0
                              ).toFixed(2)}
                              s
                            </td>
                          </tr>
                          <tr>
                            <td>Upwind Straight-Line VMG</td>
                            <td>
                              {(activeScenario.attribution_7_component.upwind_vmg_s || 0) >= 0
                                ? activeScenario.team_a
                                : activeScenario.team_b}
                            </td>
                            <td
                              className={`attr-val ${(activeScenario.attribution_7_component.upwind_vmg_s || 0) >= 0 ? 'positive' : 'negative'}`}
                            >
                              {Math.abs(activeScenario.attribution_7_component.upwind_vmg_s || 0).toFixed(2)}s
                            </td>
                          </tr>
                          <tr>
                            <td>Downwind Straight-Line VMG</td>
                            <td>
                              {(activeScenario.attribution_7_component.downwind_vmg_s || 0) >= 0
                                ? activeScenario.team_a
                                : activeScenario.team_b}
                            </td>
                            <td
                              className={`attr-val ${(activeScenario.attribution_7_component.downwind_vmg_s || 0) >= 0 ? 'positive' : 'negative'}`}
                            >
                              {Math.abs(
                                activeScenario.attribution_7_component.downwind_vmg_s || 0
                              ).toFixed(2)}
                              s
                            </td>
                          </tr>
                          <tr>
                            <td>Tack Count &amp; Execution Loss</td>
                            <td>
                              {(activeScenario.attribution_7_component.tack_execution_s || 0) >= 0
                                ? activeScenario.team_a
                                : activeScenario.team_b}
                            </td>
                            <td
                              className={`attr-val ${(activeScenario.attribution_7_component.tack_execution_s || 0) >= 0 ? 'positive' : 'negative'}`}
                            >
                              {Math.abs(
                                activeScenario.attribution_7_component.tack_execution_s || 0
                              ).toFixed(2)}
                              s
                            </td>
                          </tr>
                          <tr>
                            <td>Gybe Count &amp; Execution Loss</td>
                            <td>
                              {(activeScenario.attribution_7_component.gybe_execution_s || 0) >= 0
                                ? activeScenario.team_a
                                : activeScenario.team_b}
                            </td>
                            <td
                              className={`attr-val ${(activeScenario.attribution_7_component.gybe_execution_s || 0) >= 0 ? 'positive' : 'negative'}`}
                            >
                              {Math.abs(
                                activeScenario.attribution_7_component.gybe_execution_s || 0
                              ).toFixed(2)}
                              s
                            </td>
                          </tr>
                          <tr>
                            <td>Boundary Penalty Avoidance</td>
                            <td>
                              {(activeScenario.attribution_7_component.boundary_avoidance_s || 0) >= 0
                                ? activeScenario.team_a
                                : activeScenario.team_b}
                            </td>
                            <td
                              className={`attr-val ${(activeScenario.attribution_7_component.boundary_avoidance_s || 0) >= 0 ? 'positive' : 'negative'}`}
                            >
                              {Math.abs(
                                activeScenario.attribution_7_component.boundary_avoidance_s || 0
                              ).toFixed(2)}
                              s
                            </td>
                          </tr>
                          <tr>
                            <td>Technical / Exogenous Reliability Advantage</td>
                            <td>
                              {(activeScenario.attribution_7_component.technical_reliability_advantage ||
                                0) >= 0
                                ? activeScenario.team_a
                                : activeScenario.team_b}
                            </td>
                            <td className="attr-val">
                              {(
                                (activeScenario.attribution_7_component
                                  .technical_reliability_advantage || 0) * 100
                              ).toFixed(2)}
                              %
                            </td>
                          </tr>
                        </>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Status Breakdown Table */}
                <div className="attribution-card">
                  <h3>Categorical Outcome Breakdown</h3>
                  <table className="status-table">
                    <thead>
                      <tr>
                        <th>Team</th>
                        <th>Finished</th>
                        <th>DNS</th>
                        <th>DNF (Exogenous)</th>
                        <th>OCS / DSQ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(activeScenario.status_breakdown || {}).map(([t, s]) => (
                        <tr key={t}>
                          <td>
                            <strong>{t}</strong>
                          </td>
                          <td>{(s.finished_rate * 100).toFixed(1)}%</td>
                          <td>{(s.dns_rate * 100).toFixed(1)}%</td>
                          <td>{(s.dnf_exogenous_rate * 100).toFixed(1)}%</td>
                          <td>{(s.ocs_dsq_rate * 100).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </main>
        </div>
          )}
        </>
      )}
    </section>
  )
}
