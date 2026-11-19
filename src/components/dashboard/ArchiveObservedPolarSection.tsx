import { useState } from 'react'
import type { ArchivePolarModel } from '../../types/analysis'
import {
  formatSigned,
  formatBootstrapCi,
  formatTackContrast,
  formatMetric,
  formatPercent,
} from './polarPresentation'
import { PolarDayDiagnostics } from './PolarDayDiagnostics'
import { PolarCurveChart } from './PolarCurveChart'

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
    ...(polarModel.validation.chronological ? [polarModel.validation.chronological] : []),
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

      <p className="analysis-provenance-note">
        {polarModel.schema_version === '2.0'
          ? 'Scores and quantiles use individual accepted 1 Hz observations. Curves below are descriptive fits to the full archive; validation predicts excluded days or races. Earlier-day evaluation uses strictly older days. Day-block intervals refit the estimator and remain few-day sensitivity bounds.'
          : 'Legacy polar-1 output: scores and fitted quantiles describe weighted cell means. Regenerate polar-2 to evaluate individual 1 Hz observations.'}
      </p>
      <div className="analysis-subsection">
        <h5>Day-grouped, race-held-out and chronological validation</h5>
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
                <th>EVALUATED / EXCLUDED</th>
              </tr>
            </thead>
            <tbody>
              {valRows.map((row) => (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td>{row.folds}</td>
                  <td>{formatMetric(row.sog_rmse_kt, 3, ' kt')}</td>
                  <td>{formatMetric(row.sog_mae_kt, 3, ' kt')}</td>
                  <td>{formatMetric(row.sog_r2, 3)}</td>
                  <td>{formatMetric(row.vmg_rmse_kt, 3, ' kt')}</td>
                  <td>{formatPercent(row.p50_empirical_coverage)}</td>
                  <td>{formatPercent(row.p90_empirical_coverage)}</td>
                  <td>
                    {row.evaluated_sample_count ?? 'Legacy'} /{' '}
                    {row.excluded_sample_count ?? 'Legacy'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <PolarDayDiagnostics rows={polarModel.validation.by_group} />
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
              {polarModel.tack_fixed_effect.bootstrap_draws}{' '}
              {polarModel.tack_fixed_effect.resampling_unit ?? 'legacy leg'}-block estimator refits
            </small>
          </article>
        </div>
      </div>

      <div className="analysis-subsection">
        <h5>Archive team residuals and peer-relative comparisons</h5>
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
                <th>PEER-RELATIVE RESIDUAL</th>
                <th>RACE-BLOCK SENSITIVITY</th>
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
                  <td>{formatBootstrapCi(row.peer_relative_residual_kt)}</td>
                  <td>{formatBootstrapCi(row.race_block_sensitivity_kt)}</td>
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
          <h5>Descriptive full-archive polar curves by wind bracket</h5>
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
