import { useState } from 'react'
import type { Ac38Forecast } from '../../types/prediction'

const pct = (v: number | null | undefined) => (v == null ? 'Unavailable' : `${(v * 100).toFixed(1)}%`)

interface Props {
  forecast: Ac38Forecast | null
  error: string | null
}

function MatchupExplorer({ forecast }: { forecast: Ac38Forecast }) {
  const teams = forecast.teams
  const [teamA, setTeamA] = useState(teams[0]?.id ?? 'ETNZ')
  const [teamB, setTeamB] = useState(teams[1]?.id ?? 'LUNA_ROSSA')

  const p1 = forecast.forecast.pairwise_single_match[teamA]?.[teamB] ?? null
  const p9 = forecast.forecast.series_best_of_9[teamA]?.[teamB] ?? null
  const p13 = forecast.forecast.series_best_of_13[teamA]?.[teamB] ?? null
  const se = forecast.uncertainty.monte_carlo.pairwise_single_match_mc_se[teamA]?.[teamB] ?? null

  return (
    <div className="ac38-subcard">
      <h4>Pairwise Match &amp; Series Explorer (One Model)</h4>
      <div className="ac38-matchup-controls">
        <label>
          Team A
          <select aria-label="AC38 Matchup Team A" value={teamA} onChange={(e) => {
            const next = e.target.value
            if (next === teamB) setTeamB(teamA)
            setTeamA(next)
          }}>
            {teams.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.id})</option>)}
          </select>
        </label>
        <label>
          Team B
          <select aria-label="AC38 Matchup Team B" value={teamB} onChange={(e) => {
            const next = e.target.value
            if (next === teamA) setTeamA(teamB)
            setTeamB(next)
          }}>
            {teams.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.id})</option>)}
          </select>
        </label>
      </div>
      <div className="ac38-kpi-row">
        <div className="ac38-kpi">
          <span>Single Match ({teamA} win)</span>
          <strong>{pct(p1)}</strong>
          <small>MC SE: {se == null ? '—' : `±${(se * 100).toFixed(2)} pp`}</small>
        </div>
        <div className="ac38-kpi">
          <span>Best of 9 (First to 5)</span>
          <strong>{pct(p9)}</strong>
          <small>{teamB}: {pct(p9 == null ? null : 1 - p9)}</small>
        </div>
        <div className="ac38-kpi">
          <span>Best of 13 (First to 7 · Cup Match)</span>
          <strong>{pct(p13)}</strong>
          <small>{teamB}: {pct(p13 == null ? null : 1 - p13)}</small>
        </div>
      </div>
    </div>
  )
}

function CoverageAndAssumptions({ forecast }: { forecast: Ac38Forecast }) {
  const { entrant_coverage } = forecast
  return (
    <div className="ac38-two-col">
      <div className="ac38-subcard">
        <h4>Entrant Coverage ({entrant_coverage.ac38_races_included.length} AC38 Races · Policy: {entrant_coverage.default_mapping_policy.replaceAll('_', ' ')})</h4>
        <p className="ac38-small-note">
          Anchored full results: {entrant_coverage.ac38_anchored_races.length} · Telemetry reconstructed: {entrant_coverage.ac38_reconstructed_races.length} · Excluded: {entrant_coverage.ac38_excluded_observations.length}
        </p>
        <div className="workspace-table-wrap">
          <table className="ac38-table" aria-label="AC38 entrant coverage">
            <thead>
              <tr><th>Team</th><th>Campaign</th><th>Basis</th><th>Mapped AC40</th></tr>
            </thead>
            <tbody>
              {entrant_coverage.teams.map((t) => (
                <tr key={t.team_id}>
                  <th>{t.team_id}</th>
                  <td>{t.campaign_team_id}</td>
                  <td>{t.basis.replaceAll('_', ' ')}</td>
                  <td>{t.mapped_ac40_mean == null ? 'Population prior' : `${t.mapped_ac40_mean.toFixed(2)} ± ${(t.mapped_ac40_sd ?? 0).toFixed(2)}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="ac38-subcard">
        <h4>Main Model Assumptions &amp; Conditioning</h4>
        <ul className="ac38-assumptions">
          {entrant_coverage.assumptions.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </div>
    </div>
  )
}

function TournamentOutcomeTable({ forecast }: { forecast: Ac38Forecast }) {
  const { teams, rules, forecast: body, uncertainty } = forecast
  const adv = body.advancement_probabilities
  return (
    <div className="ac38-subcard">
      <h4>Tournament Progression, Fleet Ranking &amp; Cup Bounds</h4>
      <p className="ac38-small-note">
        Resolved trials: {rules.resolved_trials.toLocaleString('en-US')} · Unresolved rule branches: {rules.unresolved_trials.toLocaleString('en-US')} ({pct(rules.unresolved_fraction)}) · MC 95% half-width ≤ ±{(uncertainty.monte_carlo.worst_case_95_half_width * 100).toFixed(2)} pp
      </p>
      <div className="workspace-table-wrap">
        <table className="ac38-table" aria-label="AC38 unified tournament forecast">
          <thead>
            <tr>
              <th>Team</th>
              <th>Exp Fleet Pos</th>
              <th>RR Top 3</th>
              <th>Semifinal</th>
              <th>Challenger Win</th>
              <th>Cup Rule Bounds</th>
              <th>MC SE (L / U)</th>
            </tr>
          </thead>
          <tbody>
            {teams.map((team) => {
              const b = body.trophy_rule_bounds[team.id]
              const mc = uncertainty.monte_carlo.actual_mc_se_by_team[team.id]
              return (
                <tr key={team.id}>
                  <th>{team.name} ({team.id})</th>
                  <td>{body.expected_fleet_position[team.id].toFixed(2)}</td>
                  <td>{pct(adv.round_robin_top3[team.id])}</td>
                  <td>{pct(adv.semifinal[team.id])}</td>
                  <td>{pct(adv.challenger_final_win[team.id])}</td>
                  <td>{pct(b.lower)}–{pct(b.upper)}</td>
                  <td>±{(mc.lower * 100).toFixed(2)} / ±{(mc.upper * 100).toFixed(2)} pp</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function UncertaintyAndSensitivityDetails({ forecast }: { forecast: Ac38Forecast }) {
  const [sensTeam, setSensTeam] = useState('ETNZ')
  const { teams, rules, uncertainty, structural_sensitivities, historical_evaluation } = forecast
  const nested = uncertainty.posterior_nested_intervals
  const tps = uncertainty.transfer_parameter_summary

  return (
    <>
      <details className="ac38-details">
        <summary>Posterior Uncertainty &amp; Nested Simulation Intervals ({nested.converged_within_0_5pp ? 'Stabilized' : 'Computation Cap Reached'})</summary>
        <p className="ac38-small-note">
          Transfer posterior (κ=1): β median {tps.beta_percentiles.p50.toFixed(2)} [{tps.beta_percentiles.p05.toFixed(2)}, {tps.beta_percentiles.p95.toFixed(2)}] ·
          τ median {tps.tau_percentiles.p50.toFixed(2)} [{tps.tau_percentiles.p05.toFixed(2)}, {tps.tau_percentiles.p95.toFixed(2)}] ·
          ρ median {tps.rho_percentiles.p50.toFixed(2)} [{tps.rho_percentiles.p05.toFixed(2)}, {tps.rho_percentiles.p95.toFixed(2)}].
        </p>
        <p className="ac38-small-note">{nested.reason}</p>
        <div className="workspace-table-wrap">
          <table className="ac38-table" aria-label="AC38 nested posterior intervals">
            <thead>
              <tr><th>Team</th><th>Lower 5th–95th</th><th>Upper 5th–95th</th></tr>
            </thead>
            <tbody>
              {teams.map((t) => {
                const iv = nested.intervals_by_team[t.id]
                return (
                  <tr key={t.id}>
                    <th>{t.id}</th>
                    <td>{pct(iv.lower_p05_p95.p05)}–{pct(iv.lower_p05_p95.p95)}</td>
                    <td>{pct(iv.upper_p05_p95.p05)}–{pct(iv.upper_p05_p95.p95)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </details>

      <details className="ac38-details">
        <summary>Structural, Crew Mapping, Evidence &amp; Reliability Sensitivities ({structural_sensitivities.length} Scenarios)</summary>
        <label className="ac38-inline-select">
          Inspect team bounds
          <select aria-label="Sensitivity team" value={sensTeam} onChange={(e) => setSensTeam(e.target.value)}>
            {teams.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.id})</option>)}
          </select>
        </label>
        <div className="workspace-table-wrap">
          <table className="ac38-table" aria-label="AC38 structural sensitivities">
            <thead>
              <tr><th>Scenario</th><th>Residual</th><th>Zero β</th><th>Failure q</th><th>Exp Pos ({sensTeam})</th><th>Cup Bounds ({sensTeam})</th></tr>
            </thead>
            <tbody>
              {structural_sensitivities.map((s) => (
                <tr key={s.scenario_id}>
                  <th>{s.label}</th>
                  <td>{s.residual_scale}x</td>
                  <td>{s.zero_transfer ? 'Yes' : 'No'}</td>
                  <td>{pct(s.failure_probability)}</td>
                  <td>{s.expected_fleet_position[sensTeam].toFixed(2)}</td>
                  <td>{pct(s.trophy_rule_bounds[sensTeam].lower)}–{pct(s.trophy_rule_bounds[sensTeam].upper)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <details className="ac38-details">
        <summary>Unresolved Governing Rules &amp; Historical Backtest Summary</summary>
        <p className="ac38-small-note">{historical_evaluation.accuracy_claim}</p>
        {rules.unresolved_clauses.length > 0 && (
          <ul className="ac38-assumptions">
            {rules.unresolved_clauses.map((c) => <li key={c}>{c}</li>)}
          </ul>
        )}
        <p className="ac38-small-note">
          Noticeboard &amp; Rules sources: {rules.sources.map((s) => `${s.version ?? s.doc_code ?? s.title ?? 'Unknown rule source'} (${s.effective_date ?? 'undated'})`).join(' · ')}
        </p>
      </details>
    </>
  )
}

export function Ac38ForecastPanel({ forecast, error }: Props) {
  if (error) {
    return (
      <section className="ac38-forecast-section" aria-label="AC38 Unified Forecast">
        <output className="forecast-unavailable">AC38 forecast unavailable: {error}</output>
      </section>
    )
  }
  if (!forecast) return null
  const { header } = forecast

  return (
    <section className="ac38-forecast-section" aria-label="AC38 Unified Forecast">
      <div className="ac38-header-row">
        <span className="ac38-badge">Experimental</span>
        <span className="ac38-meta">Status: {header.status.replaceAll('_', ' ')}</span>
        <span className="ac38-meta">Data cutoff: {header.issuance_cutoff_utc}</span>
        <span className="ac38-meta">Trials: {header.trials.toLocaleString('en-US')} (seed {header.seed})</span>
        <span className="ac38-meta">
          Model: {header.selected_transfer_candidate.replaceAll('_', ' ')} (telemetry {header.telemetry_retained ? 'retained' : 'not retained'}, κ={header.scale_kappa})
        </span>
      </div>
      <h3>AC38 Challenger Selection &amp; America’s Cup Forecast (from AC40 Evidence)</h3>
      <p className="ac38-conditioning">{header.conditioning}</p>
      <CoverageAndAssumptions forecast={forecast} />
      <MatchupExplorer forecast={forecast} />
      <TournamentOutcomeTable forecast={forecast} />
      <UncertaintyAndSensitivityDetails forecast={forecast} />
    </section>
  )
}
