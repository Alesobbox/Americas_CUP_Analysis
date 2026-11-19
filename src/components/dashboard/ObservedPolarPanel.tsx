import { useState } from 'react'
import type {
  AnalysisDetail,
  AnalysisDetailBoat,
  ArchivePolarModel,
  BoatPolarObservedBin,
  PolarBootstrapInterval,
  PolarBracketCurve,
  PolarTackContrast,
} from '../../types/analysis'
import { evidenceText } from '../../utils/evidenceText'

function formatSigned(value: number | null | undefined, digits = 2, unit = ' kt') {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'Unavailable'
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}${Math.abs(value).toFixed(digits)}${unit}`
}

function formatBootstrapCi(interval: PolarBootstrapInterval | null | undefined) {
  if (!interval) return 'Unavailable'
  return `${formatSigned(interval.value, 2, ' kt')} [${formatSigned(interval.ci_low_kt, 2, '')}, ${formatSigned(interval.ci_high_kt, 2, '')}]`
}

function formatTackContrast(contrast: PolarTackContrast | null | undefined) {
  if (!contrast) return 'Unavailable'
  return `${formatSigned(contrast.contrast_kt, 3, ' kt')} [${formatSigned(contrast.ci_low_kt, 3, '')}, ${formatSigned(contrast.ci_high_kt, 3, '')}]`
}

function PolarCurveChart({
  bracket,
  mode,
  observedBins = [],
  boatLabel,
}: {
  bracket: PolarBracketCurve | undefined
  mode: 'upwind' | 'downwind'
  observedBins?: BoatPolarObservedBin[]
  boatLabel?: string
}) {
  if (!bracket || bracket.points.length === 0) {
    return (
      <p className="analysis-empty">
        Insufficient steady-state support in this wind bracket to render the conditional polar
        curve.
      </p>
    )
  }

  const pts = bracket.points
  const filteredBins = observedBins.filter(
    (entry) =>
      entry.tws_bin_kt >= bracket.tws_min_kt - 1.0 && entry.tws_bin_kt <= bracket.tws_max_kt + 1.0
  )

  const minTwa = Math.min(...pts.map((p) => p.twa_deg), ...filteredBins.map((b) => b.twa_bin_deg))
  const maxTwa = Math.max(...pts.map((p) => p.twa_deg), ...filteredBins.map((b) => b.twa_bin_deg))
  const allSpeeds = [
    ...pts.flatMap((p) => [p.mean_sog_kt, p.p50_sog_kt, p.p90_sog_kt]),
    ...filteredBins.map((b) => b.sog_mean_kt),
  ]
  const rawMinSpd = Math.min(...allSpeeds)
  const rawMaxSpd = Math.max(...allSpeeds)
  const minSpd = Math.max(0, Math.floor((rawMinSpd - 2) / 5) * 5)
  const maxSpd = Math.ceil((rawMaxSpd + 2) / 5) * 5
  const twaSpan = Math.max(10, maxTwa - minTwa)
  const spdSpan = Math.max(5, maxSpd - minSpd)

  const W = 640
  const H = 260
  const padL = 52
  const padR = 20
  const padT = 18
  const padB = 38
  const plotW = W - padL - padR
  const plotH = H - padT - padB

  const sx = (twa: number) => padL + ((twa - minTwa) / twaSpan) * plotW
  const sy = (sog: number) => padT + (1 - (sog - minSpd) / spdSpan) * plotH

  const pathFor = (accessor: (p: (typeof pts)[number]) => number) =>
    pts
      .map(
        (p, idx) =>
          `${idx === 0 ? 'M' : 'L'} ${sx(p.twa_deg).toFixed(1)} ${sy(accessor(p)).toFixed(1)}`
      )
      .join(' ')

  const yTicks = Array.from({ length: 5 }, (_, i) => minSpd + (spdSpan * i) / 4)
  const xStep = mode === 'upwind' ? 10 : 15
  const xStart = Math.ceil(minTwa / xStep) * xStep
  const xTicks: number[] = []
  for (let v = xStart; v <= maxTwa + 0.1; v += xStep) xTicks.push(v)

  return (
    <div className="polar-chart-card">
      <div className="polar-legend" aria-label="Polar curve legend">
        <span>
          <i className="polar-swatch p90" />
          Observed p90 (upper conditional percentile)
        </span>
        <span>
          <i className="polar-swatch p50" />
          Conditional median (p50)
        </span>
        <span>
          <i className="polar-swatch mean" />
          Conditional mean SOG
        </span>
        {filteredBins.length > 0 && (
          <>
            <span>
              <i className="polar-swatch port" />
              {boatLabel ?? 'Boat'} Port bins
            </span>
            <span>
              <i className="polar-swatch stbd" />
              {boatLabel ?? 'Boat'} Stbd bins
            </span>
          </>
        )}
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="polar-svg-chart"
        role="img"
        aria-label={`Observed ground-speed polar for ${mode} sailing in ${bracket.label}`}
      >
        {yTicks.map((tick) => (
          <g key={`y-${tick}`}>
            <line
              x1={padL}
              y1={sy(tick)}
              x2={W - padR}
              y2={sy(tick)}
              stroke="#e2e8f0"
              strokeWidth="1"
            />
            <text x={padL - 8} y={sy(tick) + 4} textAnchor="end" fill="#475569" fontSize="11">
              {tick.toFixed(0)} kt
            </text>
          </g>
        ))}
        {xTicks.map((tick) => (
          <g key={`x-${tick}`}>
            <line
              x1={sx(tick)}
              y1={padT}
              x2={sx(tick)}
              y2={H - padB}
              stroke="#f1f5f9"
              strokeWidth="1"
            />
            <text x={sx(tick)} y={H - padB + 16} textAnchor="middle" fill="#475569" fontSize="11">
              {tick.toFixed(0)}°
            </text>
          </g>
        ))}
        <line
          x1={padL}
          y1={H - padB}
          x2={W - padR}
          y2={H - padB}
          stroke="#94a3b8"
          strokeWidth="1"
        />
        <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="#94a3b8" strokeWidth="1" />
        <text x={W / 2} y={H - 4} textAnchor="middle" fill="#475569" fontSize="11">
          |TRUE WIND ANGLE| (DEGREES) · REF TWS {bracket.tws_ref_kt.toFixed(1)} KT
        </text>
        <path
          d={pathFor((p) => p.p90_sog_kt)}
          fill="none"
          stroke="#0f766e"
          strokeWidth="2"
          strokeDasharray="6 4"
        />
        <path
          d={pathFor((p) => p.mean_sog_kt)}
          fill="none"
          stroke="#334155"
          strokeWidth="1.75"
          strokeDasharray="2 3"
        />
        <path d={pathFor((p) => p.p50_sog_kt)} fill="none" stroke="#1a73e8" strokeWidth="2.75" />
        {filteredBins.map((bin, idx) =>
          bin.tack === 'PORT' ? (
            <circle
              key={`bin-${idx}`}
              cx={sx(bin.twa_bin_deg)}
              cy={sy(bin.sog_mean_kt)}
              r={Math.min(7, 3 + Math.sqrt(bin.sample_count) * 0.4)}
              fill="#c2410c"
              fillOpacity="0.82"
              stroke="#ffffff"
              strokeWidth="1"
            >
              <title>
                {`PORT |TWA| ${bin.twa_bin_deg}° · TWS ${bin.tws_bin_kt} kt: ${bin.sog_mean_kt} kt (pred ${bin.predicted_sog_kt} kt, n=${bin.sample_count}s)`}
              </title>
            </circle>
          ) : (
            <rect
              key={`bin-${idx}`}
              x={sx(bin.twa_bin_deg) - 3.5}
              y={sy(bin.sog_mean_kt) - 3.5}
              width="7"
              height="7"
              rx="1.5"
              fill="#0369a1"
              fillOpacity="0.82"
              stroke="#ffffff"
              strokeWidth="1"
            >
              <title>
                {`STARBOARD |TWA| ${bin.twa_bin_deg}° · TWS ${bin.tws_bin_kt} kt: ${bin.sog_mean_kt} kt (pred ${bin.predicted_sog_kt} kt, n=${bin.sample_count}s)`}
              </title>
            </rect>
          )
        )}
      </svg>
    </div>
  )
}

export function RaceObservedPolarSection({
  detail,
  boat,
  onSelectBoat,
}: {
  detail: AnalysisDetail
  boat: AnalysisDetailBoat
  onSelectBoat?: (id: string) => void
}) {
  const polar = detail.polar_analysis
  const [mode, setMode] = useState<'upwind' | 'downwind'>('upwind')
  const [bracketId, setBracketId] = useState('')

  if (!polar) return null

  const availableModes = (['upwind', 'downwind'] as const).filter(
    (m) => (polar.brackets[m]?.length ?? 0) > 0
  )
  const effectiveMode: 'upwind' | 'downwind' = availableModes.includes(mode)
    ? mode
    : (availableModes[0] ?? 'upwind')
  const brackets = polar.brackets[effectiveMode] ?? []
  const effectiveBracket = brackets.find((entry) => entry.id === bracketId) ?? brackets[0]

  const boatPolar = boat.polar
  const validation = polar.validation_summary

  return (
    <section className="analysis-section" aria-label="Observed ground-speed polar">
      <div className="analysis-section-heading">
        <div>
          <span className="eyebrow">OBSERVED GROUND-SPEED POLAR</span>
          <h4>Observed polar &amp; conditional residuals</h4>
        </div>
        <span className="analysis-method-tag">
          {polar.method_version} · SOG includes surface current
        </span>
      </div>

      <p className="analysis-provenance-note">
        Observed ground-speed polar fit over steady-state 1 Hz completed legs (excludes manoeuvres,
        gate turns, and &lt;60 m traffic). SOG includes surface current, and conditional residuals
        also include tactics, traffic, sea state, and wind-measurement error—they cannot isolate
        crew or flight-control skill. The 90th percentile (p90) is an observed upper conditional
        percentile, not a proven optimal target. Tack is modeled as a fixed effect, with leg-cluster
        bootstrap confidence intervals.
      </p>

      {polar.quality === 'unavailable' ? (
        <p className="analysis-empty">
          {evidenceText(
            polar.reason || 'Steady-state telemetry unavailable for an observed ground-speed polar.'
          )}
        </p>
      ) : (
        <>
          {boatPolar && boatPolar.quality === 'derived' ? (
            <div className="analysis-metric-grid">
              <article className="analysis-metric">
                <span className="analysis-metric-label">Day-grouped SOG residual</span>
                <strong>{formatSigned(boatPolar.lodo_sog_residual_kt, 2)}</strong>
                <span className="analysis-metric-meta">
                  95% bootstrap CI{' '}
                  {boatPolar.sog_residual_kt
                    ? `[${formatSigned(boatPolar.sog_residual_kt.ci_low_kt, 2, '')}, ${formatSigned(boatPolar.sog_residual_kt.ci_high_kt, 2, '')}] kt`
                    : 'Unavailable'}
                </span>
                <small>
                  LORO {formatSigned(boatPolar.loro_sog_residual_kt, 2)} ·{' '}
                  {boatPolar.steady_coverage_s.toFixed(0)} s steady
                </small>
              </article>
              <article className="analysis-metric">
                <span className="analysis-metric-label">Conditional wind-VMG residual</span>
                <strong>{formatSigned(boatPolar.wind_vmg_residual_kt?.value ?? null, 2)}</strong>
                <span className="analysis-metric-meta">
                  {boatPolar.wind_vmg_residual_kt
                    ? `95% bootstrap CI [${formatSigned(boatPolar.wind_vmg_residual_kt.ci_low_kt, 2, '')}, ${formatSigned(boatPolar.wind_vmg_residual_kt.ci_high_kt, 2, '')}] kt`
                    : 'Unavailable'}
                </span>
                <small>Relative to conditional expected wind-VMG(TWS, |TWA|, tack)</small>
              </article>
              <article className="analysis-metric">
                <span className="analysis-metric-label">Share ≥ observed p90</span>
                <strong>
                  {boatPolar.above_p90_share !== null
                    ? `${(boatPolar.above_p90_share * 100).toFixed(1)}%`
                    : 'Unavailable'}
                </strong>
                <span className="analysis-metric-meta">Observed upper conditional percentile</span>
                <small>Not a proven optimal target or hydro limit</small>
              </article>
              <article className="analysis-metric">
                <span className="analysis-metric-label">Steady coverage &amp; traffic</span>
                <strong>{boatPolar.steady_coverage_s.toFixed(0)} s</strong>
                <span className="analysis-metric-meta">
                  {boatPolar.leg_cluster_count} leg clusters ·{' '}
                  {boatPolar.traffic_excluded_s.toFixed(0)} s &lt;60 m excluded
                </span>
                <small>
                  {validation?.lodo_sog_rmse_kt !== undefined
                    ? `Race Day-Grouped RMSE ${validation.lodo_sog_rmse_kt.toFixed(2)} kt`
                    : 'In-race diagnostic fit'}
                </small>
              </article>
            </div>
          ) : (
            boatPolar && (
              <p className="analysis-provenance-note">
                {boat.team_code}: {evidenceText(boatPolar.reason || 'Unavailable for this boat.')}
              </p>
            )
          )}

          {availableModes.length > 0 && (
            <div className="analysis-subsection">
              <div className="analysis-controls">
                <label>
                  LEG MODE
                  <select
                    aria-label="Polar leg mode"
                    value={effectiveMode}
                    onChange={(event) => {
                      setMode(event.target.value as 'upwind' | 'downwind')
                      setBracketId('')
                    }}
                  >
                    {availableModes.map((m) => (
                      <option key={m} value={m}>
                        {m === 'upwind' ? 'Upwind (odd legs)' : 'Downwind (even legs)'}
                      </option>
                    ))}
                  </select>
                </label>
                {brackets.length > 0 && (
                  <label>
                    WIND BRACKET
                    <select
                      aria-label="Polar wind bracket"
                      value={effectiveBracket?.id ?? ''}
                      onChange={(event) => setBracketId(event.target.value)}
                    >
                      {brackets.map((entry) => (
                        <option key={entry.id} value={entry.id}>
                          {entry.label}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>

              <PolarCurveChart
                bracket={effectiveBracket}
                mode={effectiveMode}
                observedBins={boatPolar?.observed_bins?.[effectiveMode] ?? []}
                boatLabel={boat.team_code}
              />
            </div>
          )}

          <div className="analysis-subsection">
            <h5>Fleet conditional residuals in this race</h5>
            <div className="analysis-table-wrap">
              <table className="analysis-table" aria-label="Observed ground-speed polar residuals">
                <thead>
                  <tr>
                    <th>BOAT</th>
                    <th>STEADY</th>
                    <th>DAY-GROUPED SOG RESIDUAL (95% BOOTSTRAP CI)</th>
                    <th>LORO SOG RESIDUAL</th>
                    <th>WIND-VMG RESIDUAL (95% BOOTSTRAP CI)</th>
                    <th>PORT / STBD</th>
                    <th>≥ OBS. P90</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.boats.map((entry) => {
                    const p = entry.polar
                    const selected = entry.id === boat.id
                    return (
                      <tr key={entry.id} className={selected ? 'polar-row-selected' : undefined}>
                        <td>
                          {onSelectBoat ? (
                            <button
                              type="button"
                              className="analysis-team-select"
                              onClick={() => onSelectBoat(entry.id)}
                            >
                              <i style={{ backgroundColor: entry.color }} />
                              {entry.team_code}
                            </button>
                          ) : (
                            entry.team_code
                          )}
                        </td>
                        <td>{p ? `${p.steady_coverage_s.toFixed(0)} s` : '—'}</td>
                        <td>
                          {p && p.quality === 'derived' && p.sog_residual_kt
                            ? formatBootstrapCi(p.sog_residual_kt)
                            : evidenceText(p?.reason || 'Unavailable')}
                        </td>
                        <td>
                          {p && p.quality === 'derived'
                            ? formatSigned(p.loro_sog_residual_kt, 2)
                            : '—'}
                        </td>
                        <td>
                          {p && p.quality === 'derived' && p.wind_vmg_residual_kt
                            ? formatBootstrapCi(p.wind_vmg_residual_kt)
                            : '—'}
                        </td>
                        <td>
                          {p && p.quality === 'derived'
                            ? `${formatSigned(p.port_sog_residual_kt, 2, '')} / ${formatSigned(p.starboard_sog_residual_kt, 2, '')} kt`
                            : '—'}
                        </td>
                        <td>
                          {p && p.above_p90_share !== null
                            ? `${(p.above_p90_share * 100).toFixed(1)}%`
                            : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </section>
  )
}

export function ArchiveObservedPolarSection({
  polarModel,
  selectedTeam,
}: {
  polarModel?: ArchivePolarModel
  selectedTeam?: string
}) {
  const [mode, setMode] = useState<'upwind' | 'downwind'>('upwind')
  const [bracketId, setBracketId] = useState('')

  if (!polarModel) return null

  const availableModes = (['upwind', 'downwind'] as const).filter(
    (m) => (polarModel.curves[m]?.length ?? 0) > 0
  )
  const effectiveMode: 'upwind' | 'downwind' = availableModes.includes(mode)
    ? mode
    : (availableModes[0] ?? 'upwind')
  const curves = polarModel.curves[effectiveMode] ?? []
  const effectiveCurve = curves.find((entry) => entry.id === bracketId) ?? curves[0]
  const valRows = [
    polarModel.validation.baseline_mode_only,
    polarModel.validation.leave_one_race_out,
    polarModel.validation.leave_one_day_out,
  ]

  return (
    <section className="analysis-section" aria-label="Archive observed ground-speed polar">
      <div className="analysis-section-heading">
        <div>
          <span className="eyebrow">ARCHIVE OBSERVED GROUND-SPEED POLAR</span>
          <h4>Cross-session ground-speed polar &amp; residual validation</h4>
        </div>
        <span className="analysis-method-tag">
          {polarModel.method_version} · {polarModel.counts.eligible_races} races ·{' '}
          {polarModel.counts.distinct_days} days · {polarModel.counts.steady_coverage_s.toFixed(0)}{' '}
          s steady
        </span>
      </div>

      <p className="analysis-provenance-note">
        Observed ground-speed polar trained across {polarModel.counts.eligible_races} races and{' '}
        {polarModel.counts.distinct_days} racing days ({polarModel.counts.boat_leg_clusters}{' '}
        boat-leg clusters). SOG includes surface current; conditional residuals include tactics,
        traffic, sea state, and wind-measurement error and cannot isolate crew or flight-control
        skill. The 90th percentile is an observed upper conditional percentile, not a proven optimal
        target.
      </p>

      <div className="analysis-subsection">
        <h5>Day-grouped vs. Leave-One-Race-Out validation</h5>
        <div className="analysis-table-wrap">
          <table className="analysis-table" aria-label="Polar cross-validation comparison">
            <thead>
              <tr>
                <th>VALIDATION REGIME</th>
                <th>FOLDS</th>
                <th>SOG RMSE</th>
                <th>SOG MAE</th>
                <th>SOG R²</th>
                <th>WIND-VMG RMSE</th>
                <th>P50 COV</th>
                <th>P90 COV</th>
              </tr>
            </thead>
            <tbody>
              {valRows.map((row) => (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td>{row.folds}</td>
                  <td>{row.sog_rmse_kt.toFixed(3)} kt</td>
                  <td>{row.sog_mae_kt.toFixed(3)} kt</td>
                  <td>{row.sog_r2.toFixed(3)}</td>
                  <td>{row.vmg_rmse_kt.toFixed(3)} kt</td>
                  <td>{(row.p50_empirical_coverage * 100).toFixed(1)}%</td>
                  <td>{(row.p90_empirical_coverage * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="analysis-subsection">
        <h5>Two-category fixed effect for tack (Starboard − Port)</h5>
        <div className="analysis-metric-grid">
          <article className="analysis-metric">
            <span className="analysis-metric-label">Upwind tack fixed effect</span>
            <strong>
              {formatSigned(polarModel.tack_fixed_effect.upwind?.contrast_kt ?? null, 3)}
            </strong>
            <span className="analysis-metric-meta">
              95% bootstrap CI: {formatTackContrast(polarModel.tack_fixed_effect.upwind)}
            </span>
            <small>Adjusted for bivariate (TWS, |TWA|) surface</small>
          </article>
          <article className="analysis-metric">
            <span className="analysis-metric-label">Downwind tack fixed effect</span>
            <strong>
              {formatSigned(polarModel.tack_fixed_effect.downwind?.contrast_kt ?? null, 3)}
            </strong>
            <span className="analysis-metric-meta">
              95% bootstrap CI: {formatTackContrast(polarModel.tack_fixed_effect.downwind)}
            </span>
            <small>Adjusted for bivariate (TWS, |TWA|) surface</small>
          </article>
          <article className="analysis-metric">
            <span className="analysis-metric-label">Overall tack fixed effect</span>
            <strong>
              {formatSigned(polarModel.tack_fixed_effect.overall?.contrast_kt ?? null, 3)}
            </strong>
            <span className="analysis-metric-meta">
              95% bootstrap CI: {formatTackContrast(polarModel.tack_fixed_effect.overall)}
            </span>
            <small>
              {polarModel.tack_fixed_effect.bootstrap_draws} leg-cluster bootstrap draws
            </small>
          </article>
        </div>
      </div>

      <div className="analysis-subsection">
        <h5>Archive team conditional residuals (leg-cluster bootstrap confidence intervals)</h5>
        <div className="analysis-table-wrap">
          <table className="analysis-table" aria-label="Archive team polar residuals">
            <thead>
              <tr>
                <th>TEAM</th>
                <th>RACES / CLUSTERS</th>
                <th>STEADY</th>
                <th>DAY-GROUPED SOG RESIDUAL (95% BOOTSTRAP CI)</th>
                <th>LORO RESIDUAL (95% CI)</th>
                <th>WIND-VMG RESIDUAL (95% CI)</th>
                <th>UP / DOWN</th>
                <th>≥ OBS. P90</th>
              </tr>
            </thead>
            <tbody>
              {polarModel.team_residuals.map((row) => (
                <tr
                  key={row.team_code}
                  className={row.team_code === selectedTeam ? 'polar-row-selected' : undefined}
                >
                  <td>{row.team_code}</td>
                  <td>
                    {row.race_count} / {row.leg_cluster_count}
                  </td>
                  <td>{row.steady_coverage_s.toFixed(0)} s</td>
                  <td>{formatBootstrapCi(row.lodo_sog_residual_kt)}</td>
                  <td>{formatBootstrapCi(row.loro_sog_residual_kt)}</td>
                  <td>{formatBootstrapCi(row.wind_vmg_residual_kt)}</td>
                  <td>
                    {formatSigned(row.upwind_sog_residual_kt, 2, '')} /{' '}
                    {formatSigned(row.downwind_sog_residual_kt, 2, '')} kt
                  </td>
                  <td>
                    {row.above_p90_share !== null
                      ? `${(row.above_p90_share * 100).toFixed(1)}%`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {availableModes.length > 0 && (
        <div className="analysis-subsection">
          <h5>Observed ground-speed polar curves by TWS bracket</h5>
          <div className="analysis-controls">
            <label>
              LEG MODE
              <select
                aria-label="Archive polar leg mode"
                value={effectiveMode}
                onChange={(event) => {
                  setMode(event.target.value as 'upwind' | 'downwind')
                  setBracketId('')
                }}
              >
                {availableModes.map((m) => (
                  <option key={m} value={m}>
                    {m === 'upwind' ? 'Upwind (odd legs)' : 'Downwind (even legs)'}
                  </option>
                ))}
              </select>
            </label>
            <label>
              TWS BRACKET
              <select
                aria-label="Archive polar TWS bracket"
                value={effectiveCurve?.id ?? ''}
                onChange={(event) => setBracketId(event.target.value)}
              >
                {curves.map((entry) => (
                  <option key={entry.id} value={entry.id}>
                    {entry.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <PolarCurveChart bracket={effectiveCurve} mode={effectiveMode} />
        </div>
      )}
    </section>
  )
}
