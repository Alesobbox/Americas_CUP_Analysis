import { useState } from 'react'
import type { AnalysisDetail, AnalysisDetailBoat } from '../../types/analysis'
import { evidenceText } from '../../utils/evidenceText'
import { formatSigned, formatBootstrapCi } from './polarPresentation'
import { PolarCurveChart } from './PolarCurveChart'

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
        percentile, not a proven optimal target. Tack is modeled as a fixed effect.
        {polar.schema_version === '2.0'
          ? ' Residuals use individual accepted observations. Boat intervals resample legs within this race, conditional on the fitted out-of-day reference; they do not include full model uncertainty. Curves are descriptive full-archive fits.'
          : ' Legacy polar-1 curves and validation describe aggregated cell means; regenerate polar-2 for sample-level results.'}
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
