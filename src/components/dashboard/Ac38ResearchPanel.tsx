import type { AnalysisIndex, AnalysisDetail } from '../../types/analysis'
import type { PolarExperiments, ResearchComparison, WindForecastModel } from '../../types/research'
import { formatMetric, formatSigned } from './polarPresentation'
import { RaceTimingResearch, RaceWindResearch } from './RaceResearchDetails'
import './ac38-research.css'

const MODEL_LABELS: Record<string, string> = {
  kernel: 'Gaussian kernel',
  local_linear: 'Local linear',
  onboard: 'Onboard wind',
  official: 'Official wind asset',
  peer_consensus: 'Nearby boat consensus',
  baseline: 'Wind and angle baseline',
  baseline_plus_currents: '+ Model currents',
  baseline_plus_waves: '+ Model waves',
  baseline_plus_temperatures: '+ Temperatures',
  event_climatology: 'Past event frequency',
  probabilistic_persistence: 'Probabilistic persistence',
  local_angle_ar: 'Local angle autoregression',
}

export function researchModelLabel(name: string) {
  return MODEL_LABELS[name] ?? name.replaceAll('_', ' ')
}

function ComparisonTable({ title, report }: { title: string; report?: ResearchComparison }) {
  if (!report) return null
  if (Object.keys(report.day_equal).length === 0)
    return <p className="analysis-empty">{title}: no common eligible evaluation days.</p>
  return (
    <div className="analysis-subsection">
      <h5>{title}</h5>
      <div className="analysis-table-wrap">
        <table className="analysis-table" aria-label={title}>
          <thead>
            <tr>
              <th>MODEL</th>
              <th>DAYS</th>
              <th>DAY-EQUAL RMSE</th>
              <th>SAMPLE RMSE</th>
              <th>ACCEPTED SAMPLES</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(report.day_equal).map(([name, score]) => (
              <tr key={name}>
                <td>{researchModelLabel(name)}</td>
                <td>{score.days}</td>
                <td>{formatMetric(score.mean_rmse_kt, 3, ' kt')}</td>
                <td>{formatMetric(report.sample_weighted?.[name]?.rmse_kt, 3, ' kt')}</td>
                <td>{report.sample_weighted?.[name]?.sample_count ?? 'Unavailable'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {report.missing_or_unmatched_count !== undefined && (
        <p className="analysis-micro-note">
          {report.missing_or_unmatched_count.toLocaleString()} observations have missing or
          unmatched inputs. Every compared model uses the same accepted rows.
        </p>
      )}
      {report.paired_local_linear_minus_kernel_rmse && (
        <p className="analysis-micro-note">
          Local linear minus kernel day-equal RMSE:{' '}
          {formatSigned(report.paired_local_linear_minus_kernel_rmse.mean_delta_kt, 3)}. Negative
          favours local linear. Few-day sensitivity remains in the report.
        </p>
      )}
    </div>
  )
}

function WindForecastScores({ model }: { model?: WindForecastModel }) {
  if (!model) return null
  return (
    <details className="analysis-subsection" open>
      <summary>Three-minute wind-shift benchmark</summary>
      <p className="analysis-provenance-note">
        Predicts whether direction changes at least 5° at the 180-second endpoint. Models train on
        completed earlier-day targets. Lower Brier, log loss and circular CRPS are better. Recorded
        timestamps do not verify when information arrived live.
      </p>
      <div className="analysis-table-wrap">
        <table className="analysis-table" aria-label="Wind shift forecast scores">
          <thead>
            <tr>
              <th>MODEL</th>
              <th>DAYS / TARGETS</th>
              <th>DAY-EQUAL BRIER</th>
              <th>DAY-EQUAL LOG LOSS</th>
              <th>CIRCULAR CRPS</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(model.validation).map(([name, score]) => (
              <tr key={name}>
                <td>{researchModelLabel(name)}</td>
                <td>
                  {score.scored_days} / {score.scored_targets}
                </td>
                <td>{formatMetric(score.day_equal.brier, 4)}</td>
                <td>{formatMetric(score.day_equal.log_loss, 4)}</td>
                <td>{formatMetric(score.day_equal.circular_crps_deg, 3, '°')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="analysis-micro-note">
        {model.counts.censored_targets} endpoint targets are censored. Predictions remain
        experimental.
      </p>
    </details>
  )
}

function EnvironmentResults({ report }: { report?: PolarExperiments['environment_ablation'] }) {
  if (!report) return null
  return (
    <details className="analysis-subsection">
      <summary>Environmental additions and usable coverage</summary>
      <p className="analysis-provenance-note">
        Historical model fields describe coarse environmental context. One-second sampling does not
        increase their native resolution. A negative comparison does not rule out a physical effect.
        Water speed adjustments use vector subtraction.
      </p>
      {Object.entries(report.feature_blocks).map(([name, result]) => (
        <ComparisonTable
          key={name}
          title={`${researchModelLabel(name)}: held-out days`}
          report={result.leave_one_day_out}
        />
      ))}
      <div className="analysis-table-wrap">
        <table className="analysis-table" aria-label="Environmental sample coverage">
          <thead>
            <tr>
              <th>SESSION</th>
              <th>ACCEPTED</th>
              <th>CURRENT U / V MATCHES</th>
              <th>WAVE HEIGHT MATCHES</th>
              <th>AIR / WATER MATCHES</th>
            </tr>
          </thead>
          <tbody>
            {report.coverage.map((row) => (
              <tr key={row.race_id}>
                <td>{row.race_id}</td>
                <td>{row.sample_count}</td>
                <td>
                  {row.available_counts.current_u_mps ?? 'Unavailable'} /{' '}
                  {row.available_counts.current_v_mps ?? 'Unavailable'}
                </td>
                <td>{row.available_counts.wave_height_m ?? 'Unavailable'}</td>
                <td>
                  {row.available_counts.air_temperature_c ?? 'Unavailable'} /{' '}
                  {row.available_counts.water_temperature_c ?? 'Unavailable'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="analysis-micro-note">
        Wave period is energy period, not peak period. Air minus modeled water temperature is a
        stability covariate, not air density.
      </p>
    </details>
  )
}

function WindAgreementResults({ report }: { report?: PolarExperiments['wind_comparison'] }) {
  if (!report) return null
  return (
    <details className="analysis-subsection">
      <summary>Onboard, official and nearby-peer wind agreement</summary>
      <p className="analysis-provenance-note">
        Nearby consensus excludes the target boat. Disagreement combines sensor processing, spatial
        gradients and wakes; it does not identify sensor accuracy. Large direction discrepancies
        stay counted. {report.peer_supported_samples.toLocaleString()} accepted observations have
        nearby peer support.
      </p>
      <ComparisonTable
        title="Wind sources on identical held-out-day observations"
        report={report.leave_one_day_out}
      />
      <div className="analysis-table-wrap">
        <table className="analysis-table" aria-label="Onboard minus official wind agreement">
          <thead>
            <tr>
              <th>TEAM / TACK</th>
              <th>DAYS / PAIRS</th>
              <th>MEDIAN SPEED DIFFERENCE</th>
              <th>MEDIAN ANGLE DIFFERENCE</th>
              <th>OVER 60°</th>
            </tr>
          </thead>
          <tbody>
            {report.official_discrepancy.by_team_tack.map((row) => (
              <tr key={`${row.team_code}:${row.tack}`}>
                <td>
                  {row.team_code} / {row.tack}
                </td>
                <td>
                  {row.day_count} / {row.sample_count}
                </td>
                <td>{formatSigned(row.median_speed_difference_kt, 3)}</td>
                <td>{formatSigned(row.median_direction_difference_deg, 2, '°')}</td>
                <td>{row.direction_discrepancies_above_60deg}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

function ResearchDownloads({
  polar,
  wind,
  timing,
}: {
  polar: boolean
  wind: boolean
  timing: boolean
}) {
  return (
    <nav className="research-downloads" aria-label="AC38 research downloads">
      {polar && (
        <a href="/data/research/polar_experiments.json" download>
          Download polar, wind agreement and environment report
        </a>
      )}
      {wind && (
        <a href="/data/research/wind_forecast.json" download>
          Download wind forecast report
        </a>
      )}
      {timing && (
        <a href="/data/research/timing_summary.json" download>
          Download timing summary
        </a>
      )}
    </nav>
  )
}

export function ArchiveAc38ResearchSection({ index }: { index: AnalysisIndex }) {
  const report = index.polar_research
  if (!report && !index.wind_forecast_model && !index.timing_research) return null
  return (
    <section className="analysis-section" aria-label="AC38 research experiments">
      <div className="analysis-section-heading">
        <h4>AC38 research comparisons</h4>
        <span>Observed samples · explicit held-out days</span>
      </div>
      {report && (
        <p className="analysis-provenance-note">
          {report.cohort.sample_count.toLocaleString()} accepted observations across{' '}
          {report.cohort.races} sessions and {report.cohort.days} days. These comparisons test
          conditional ground speed. No foil-state labels or future-day coverage guarantees are
          established.
        </p>
      )}
      <ComparisonTable
        title="Tuned surfaces: retrospective held-out days"
        report={report?.model_comparison?.leave_one_day_out}
      />
      <ComparisonTable
        title="Tuned surfaces: earlier days predict later days"
        report={report?.model_comparison?.chronological}
      />
      <WindAgreementResults report={report?.wind_comparison} />
      <EnvironmentResults report={report?.environment_ablation} />
      <WindForecastScores model={index.wind_forecast_model} />
      {index.timing_research && (
        <p className="analysis-micro-note">
          Exact checkpoint and disjoint-phase accounting is available in individual boat reports.
          Turn candidates remain subject to manual review.
        </p>
      )}
      <ResearchDownloads
        polar={Boolean(report)}
        wind={Boolean(index.wind_forecast_model)}
        timing={Boolean(index.timing_research)}
      />
    </section>
  )
}

export function RaceAc38ResearchSection({
  detail,
  boatId,
  onReview,
}: {
  detail: AnalysisDetail
  boatId: string
  onReview?: (timestamp: number) => void
}) {
  if (!detail.timing_research && !detail.wind_forecast) return null
  return (
    <section className="analysis-section" aria-label="AC38 timing and wind research">
      <div className="analysis-section-heading">
        <h4>Timing, manoeuvres and wind research</h4>
        <span>Retrospective evidence</span>
      </div>
      <RaceTimingResearch
        report={detail.timing_research}
        boatId={boatId}
        gunMs={detail.race.gun_time_ms}
        onReview={onReview}
      />
      <RaceWindResearch report={detail.wind_forecast} gunMs={detail.race.gun_time_ms} />
      <a
        className="analysis-table-link"
        href={`/data/analysis/${encodeURIComponent(detail.race.id)}.json`}
        download
      >
        Download this session’s complete evidence
      </a>
    </section>
  )
}
