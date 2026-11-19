import type { PolarValidationMetrics } from '../../types/analysis'
import { formatMetric, formatPercent, formatSigned } from './polarPresentation'

export function PolarDayDiagnostics({ rows }: { rows?: PolarValidationMetrics[] }) {
  if (!rows?.length) return null
  return (
    <details className="analysis-subsection">
      <summary>Coverage and error by day, wind range and leg mode</summary>
      <p className="analysis-provenance-note">
        Each group uses held-out-day predictions for individual accepted 1 Hz observations.
        Unsupported predictions stay excluded. Coverage is diagnostic; eight days cannot establish a
        guarantee for future days or every subgroup.
      </p>
      <div className="analysis-table-wrap">
        <table className="analysis-table" aria-label="Polar day and subgroup diagnostics">
          <thead>
            <tr>
              <th>GROUP</th>
              <th>VALUE</th>
              <th>EVALUATED / EXCLUDED</th>
              <th>SOG RMSE</th>
              <th>MEAN RESIDUAL</th>
              <th>P90 COVERAGE</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.kind}:${row.group}`}>
                <td>{row.kind === 'tws' ? 'Wind, kt' : row.kind}</td>
                <td>{row.group}</td>
                <td>
                  {row.evaluated_sample_count ?? 'Unavailable'} /{' '}
                  {row.excluded_sample_count ?? 'Unavailable'}
                </td>
                <td>{formatMetric(row.sog_rmse_kt, 3, ' kt')}</td>
                <td>{formatSigned(row.mean_residual_kt, 3)}</td>
                <td>{formatPercent(row.p90_empirical_coverage)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
