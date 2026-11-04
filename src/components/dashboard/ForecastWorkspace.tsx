import { useEffect, useRef, useState } from 'react'
import { checkpointStatus, findExactPreset, loadCupPrediction, loadPredictionIndex, loadRacePrediction, selectForecastCheckpoint } from '../../engine/predictionCatalog'
import type { CupPrediction, PredictionIndex, RacePrediction } from '../../types/prediction'
import type { ReplayManifest } from '../../types/replay'
import { loadScenarioService, prepareScenario, type ScenarioService } from '../../engine/forecastScenarios'
import { evidenceText } from '../../utils/evidenceText'
import './forecast.css'
import './cupEvidence.css'

const percent = (value: number) => `${(value * 100).toFixed(1)}%`
const reasonText = (reason: string | undefined, fallback: string) => evidenceText(reason?.replaceAll('_', ' ') || fallback)
const failure = (error: unknown) => error instanceof Error ? error.message : 'Forecast data could not be loaded.'
const forecastBoats = (prediction: RacePrediction | null, replay: ReplayManifest) => prediction?.header.scheduled_entries?.map((entry) => replay.competitors.find((boat) => boat.id === entry.id) ?? entry) ?? replay.competitors

interface Props {
  replay: ReplayManifest
  playhead: number
  selectedId: string | null
  onSelectBoat: (id: string) => void
  onSeek: (time: number) => void
  playing: boolean
  onToggle: () => void
}

export function LiveForecastCard({ prediction, error, playhead, replay, selectedId }: Pick<Props, 'playhead' | 'replay' | 'selectedId'> & { prediction: RacePrediction | null; error: string | null }) {
  const checkpoint = prediction ? selectForecastCheckpoint(prediction, playhead) : null
  const index = checkpoint?.index ?? null
  const status = prediction && index !== null ? checkpointStatus(prediction, index) : null
  const available = status === 'available' || status === 'estimated'
  const reason = error ?? checkpoint?.reason ?? (prediction && index !== null ? prediction.live.reason_code?.[index] : null)
  const numericalError = prediction && index !== null ? prediction.live.numerical_error[index] : null
  return <article className="forecast-card" aria-labelledby="live-forecast-title">
    <div className="forecast-card-heading"><span className="forecast-scope">Current race · AC40</span><span className={`forecast-status ${available ? 'forecast-status-ready' : ''}`}>{available ? status === 'estimated' ? 'Estimated state' : 'Available' : 'Unavailable'}</span></div>
    <h3 id="live-forecast-title">Win this race at the playhead</h3>
    <p>Chance of being the first valid on-water finisher, using information published by this time.</p>
    {!available && <p role="status" className="forecast-unavailable">{reasonText(reason ?? undefined, prediction ? 'The current state does not support a complete fleet forecast.' : 'Loading the race forecast…')}</p>}
    <div className="workspace-table-wrap"><table><thead><tr><th>Boat</th><th>Win probability</th><th>State age</th></tr></thead><tbody>{forecastBoats(prediction, replay).map((boat) => {
      const value = available && prediction && index !== null ? prediction.live.win_prob_by_boat[boat.id][index] : null
      const age = prediction && index !== null ? prediction.live.source_age_ms_by_boat[boat.id][index] : null
      return <tr key={boat.id} aria-selected={boat.id === selectedId}><th scope="row">{boat.team_code}</th><td><span className="forecast-probability">{value == null ? '—' : <><span className="forecast-probability-track" aria-hidden="true"><span style={{ width: `${value * 100}%` }} /></span><span>{percent(value)}</span></>}</span></td><td>{age == null ? '—' : `${(age / 1000).toFixed(1)} s`}</td></tr>
    })}</tbody></table></div>
    {available && prediction && index !== null && <p className="forecast-footnote">State: {new Date(prediction.live.state_timestamps_ms[index]).toISOString().slice(11, 19)} UTC · published: {new Date(prediction.live.published_at_ms[index]).toISOString().slice(11, 19)} UTC.{numericalError !== null && <> Monte Carlo precision: ±{(numericalError * 100).toFixed(2)} percentage points; model uncertainty is separate.</>}</p>}
    {prediction && <details><summary>Method and evidence</summary><p>Model: {prediction.header.model_ref}. {evidenceText(prediction.header.method_and_assumption_refs.join(' · '))}</p><p className="forecast-hash">Input: {prediction.header.source_manifest_hash}<br />Scenario: {prediction.header.scenario_hash}</p></details>}
  </article>
}

export function PreRaceForecastCard({ prediction, rosterPrediction, error, replay, selectedId, children, stateLabel }: Pick<Props, 'replay' | 'selectedId'> & { prediction: RacePrediction | null; rosterPrediction?: RacePrediction | null; error: string | null; children?: React.ReactNode; stateLabel?: string }) {
  const available = prediction && ['available', 'estimated'].includes(prediction.pre_race.status) && !error
  const roster = prediction ?? rosterPrediction ?? null
  return <article className="forecast-card" aria-labelledby="pre-forecast-title">
    <div className="forecast-card-heading"><span className="forecast-scope">Before the start · AC40</span><span className={`forecast-status ${available ? 'forecast-status-ready' : ''}`}>{stateLabel ?? (available ? 'Available' : 'Unavailable')}</span></div>
    <h3 id="pre-forecast-title">Expected finishing position</h3>
    <p>Expected position · nonfinish scored N ({roster?.header.boat_ids.length ?? replay.competitors.length}). Uses the scheduled opponents and the selected conditions.</p>
    {children}
    {!available && <p role="status" className="forecast-unavailable">{reasonText(error ?? prediction?.pre_race.reason, prediction ? 'Audited completion and outcome evidence is required for an unconditional expected position.' : 'Loading the pre-race forecast…')}</p>}
    <div className="workspace-table-wrap"><table><thead><tr><th>Boat</th><th>Expected position</th></tr></thead><tbody>{forecastBoats(roster, replay).map((boat) => {
      const value = available ? prediction.pre_race.expected_position_by_boat[boat.id] : null
      return <tr key={boat.id} aria-selected={boat.id === selectedId}><th scope="row">{boat.team_code}</th><td>{value == null ? '—' : value.toFixed(2)}</td></tr>
    })}</tbody></table></div>
    {available && <p className="forecast-footnote">These positions include noncompletion and do not have to sum to the usual rank total.</p>}
  </article>
}

export function CupForecastCard({ prediction, error }: { prediction: CupPrediction | null; error: string | null }) {
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null)
  const available = prediction && ['available', 'estimated'].includes(prediction.status) && !error
  const reasons = prediction?.unresolved_reasons?.length ? prediction.unresolved_reasons : prediction?.reason ? [prediction.reason] : []
  const evidence = available ? prediction.scenario_analysis : undefined
  const selected = evidence?.records.find((scenario) => scenario.scenario_id === selectedScenarioId)
    ?? evidence?.records.find((scenario) => scenario.scenario_id === evidence.baseline_scenario_id)
  const rangeText = (range: { lower: number; upper: number } | null | undefined) => range ? `${percent(range.lower)}–${percent(range.upper)}` : '—'
  return <article className="forecast-card" aria-labelledby="cup-forecast-title">
    <div className="forecast-card-heading"><span className="forecast-scope">America’s Cup 2027 · AC75</span><span className={`forecast-status ${available ? 'forecast-status-ready' : ''}`}>{available ? 'Scenario envelope' : 'Unavailable'}</span></div>
    <h3 id="cup-forecast-title">Win the whole America’s Cup</h3>
    <p>Includes Challenger selection and the final Match against the Defender.</p>
    {!available && <p role="status" className="forecast-unavailable">{error || (prediction ? 'Cup probabilities are not ready: event rules and the AC40-to-AC75 model still need verification.' : 'Loading the America’s Cup scenarios…')}</p>}
    {!available && reasons.length > 0 && <details><summary>Why this is unavailable</summary><ul>{reasons.map((reason, index) => <li key={index}>{reasonText(reason, '')}</li>)}</ul></details>}
    {evidence && selected && <div className="cup-scenario-control"><label>Cup scenario <select aria-label="Cup scenario" value={selected.scenario_id} onChange={(event) => setSelectedScenarioId(event.target.value)}>{evidence.records.map((scenario) => <option key={scenario.scenario_id} value={scenario.scenario_id}>Loading {scenario.scenario.rho} · residual multiplier {scenario.scenario.sigma_multiplier}{scenario.scenario_id === evidence.baseline_scenario_id ? ' · baseline' : ''}</option>)}</select></label><p className="cup-scenario-counts">{selected.resolved_trials.toLocaleString('en-US')} resolved · {selected.unresolved_trials.toLocaleString('en-US')} unresolved of {selected.trials.toLocaleString('en-US')} trials</p><p>Monte Carlo half-width: ±{(selected.numerical_error.worst_case_95_half_width * 100).toFixed(2)} pp (integration only). Structural uncertainty remains in the bounds.</p></div>}
    {prediction && <div className="workspace-table-wrap"><table aria-label="Cup team bounds"><thead><tr><th>Team</th>{prediction.rule_bounds_by_team && <th>Baseline assumptions: rule bounds</th>}<th>All tested assumptions: outer envelope<span className="cup-range-scale">0–100% scale</span></th>{selected && <th>Selected scenario: rule bounds</th>}</tr></thead><tbody>{prediction.teams.map((team) => {
      const range = available ? prediction.scenario_envelope_by_team?.[team.id] : null
      const rules = available ? prediction.rule_bounds_by_team?.[team.id] : null
      return <tr key={team.id}><th scope="row">{team.name}</th>{prediction.rule_bounds_by_team && <td>{rangeText(rules)}</td>}<td><span className="cup-bound-value">{rangeText(range)}{range && <span className="cup-bound-track" aria-hidden="true"><span style={{ left: `${range.lower * 100}%`, width: `${(range.upper - range.lower) * 100}%` }} /></span>}</span></td>{selected && <td>{rangeText(selected.rule_bounds[team.id])}</td>}</tr>
    })}</tbody></table></div>}
    {available && <p className="forecast-footnote">The outer envelope combines tested transfer assumptions and unresolved rule paths; these are not calibrated AC75 confidence intervals. Each team has a marginal range, so endpoints need not sum to 100%. A loading is an assumption, not a fitted cross-class correlation.</p>}
    {prediction && evidence && selected && <>
      <details className="cup-evidence"><summary>Scenario sensitivity and evidence</summary>
        <p>Baseline: {evidence.baseline_scenario_id}. Scenario weights are unspecified; no midpoint or resolved-only point estimate is reported.</p>
        <div className="workspace-table-wrap"><table aria-label="Cup scenario sensitivity"><thead><tr><th>Scenario</th><th>AC40 loading</th><th>Residual multiplier</th><th>Resolved paths</th><th>Rule-unresolved paths</th><th>MC half-width</th></tr></thead><tbody>{evidence.records.map((scenario) => <tr key={scenario.scenario_id}><th scope="row">{scenario.scenario_id}</th><td>{scenario.scenario.rho}</td><td>{scenario.scenario.sigma_multiplier}</td><td>{scenario.resolved_trials.toLocaleString('en-US')}</td><td>{scenario.unresolved_trials.toLocaleString('en-US')}</td><td>±{(scenario.numerical_error.worst_case_95_half_width * 100).toFixed(2)} pp</td></tr>)}</tbody></table></div>
        <h4>First unresolved stage</h4><p>Mutually exclusive counts for the selected scenario; their sum equals its unresolved paths.</p><ul>{Object.entries(selected.first_unresolved_stage_counts).map(([stage, count]) => <li key={stage}>{reasonText(stage, '')}: {count.toLocaleString('en-US')}</li>)}</ul>
        <h4>Overlapping reasons</h4><p>One path may appear in multiple reasons. These counts must not be added.</p><ul>{Object.entries(selected.overlapping_reason_counts).map(([reason, count]) => <li key={reason}>{reason} ({count.toLocaleString('en-US')})</li>)}</ul>
        <h4>Pinned strength model</h4><p className="cup-model-reference">{evidence.model_lineage.model_ref ? <a href={`/data/predictions/models/${evidence.model_lineage.model_ref}.json`} download>{evidence.model_lineage.model_ref}</a> : 'Model reference unavailable'} · training before {evidence.model_lineage.training_before_day ?? 'unavailable'}.</p><p>{evidenceText(evidence.model_lineage.selection_policy)}</p>
        <h4>Conditioning and limits</h4><ul>{Object.entries(evidence.conditioning).map(([key, text]) => <li key={key}>{text}</li>)}</ul><p>{evidence.refinement_policy.reason}</p>
        {reasons.length > 0 && <><h4>Unresolved evidence</h4><ul>{reasons.map((reason, index) => <li key={index}>{reasonText(reason, '')}</li>)}</ul></>}
        <h4>Observed and missing team history</h4><p>{evidenceText(evidence.mapping_provenance.policy)}</p><ul>{evidence.mapping_provenance.teams.map((team) => <li key={team.team_id}>{prediction.teams.find((entry) => entry.id === team.team_id)?.name ?? team.team_id}: {team.observed ? `observed entries ${team.source_entries.map((entry) => entry.entry_id).join(', ') || 'explicit model input'}` : 'no observed AC40 strength; population prior retained'}.</li>)}</ul>
        <p>Selected input hash: <span className="cup-model-reference">{selected.input_hash}</span>. Seed {selected.seed}; {selected.trials.toLocaleString('en-US')} trials. {selected.numerical_error.scope}.</p><p>{evidence.build_budget.randomization_policy}</p>
      </details>
      <details className="cup-evidence"><summary>Envelope endpoint attribution</summary><p>Different endpoints can come from different assumptions. They do not form one joint scenario.</p><div className="workspace-table-wrap"><table aria-label="Cup envelope endpoint attribution"><thead><tr><th>Team</th><th>Lower endpoint scenarios</th><th>Upper endpoint scenarios</th></tr></thead><tbody>{prediction.teams.map((team) => <tr key={team.id}><th scope="row">{team.name}</th><td>{evidence.extrema_by_team[team.id]?.lower_scenario_ids.join(', ')}</td><td>{evidence.extrema_by_team[team.id]?.upper_scenario_ids.join(', ')}</td></tr>)}</tbody></table></div></details>
    </>}
    {prediction && <details><summary>Format and scenario evidence</summary><p>{evidenceText(prediction.header.method_and_assumption_refs?.join(' · ') || 'See the versioned event-rules and model manifest in the forecast downloads.')}</p>{prediction.evaluated_scenarios && <p>{prediction.evaluated_scenarios.length} generated scenarios: {prediction.evaluated_scenarios.join(', ')}.</p>}</details>}
  </article>
}

export function ForecastWorkspace(p: Props) {
  const [question, setQuestion] = useState<'live' | 'pre' | 'cup'>('live')
  const [index, setIndex] = useState<PredictionIndex | null>(null)
  const [race, setRace] = useState<RacePrediction | null>(null)
  const [cup, setCup] = useState<CupPrediction | null>(null)
  const [raceError, setRaceError] = useState<string | null>(null)
  const [cupError, setCupError] = useState<string | null>(null)
  const [conditionsMode, setConditionsMode] = useState('recorded')
  const [tws, setTws] = useState('12')
  const [offset, setOffset] = useState('0')
  const [presetResult, setPresetResult] = useState<{ key: string; prediction: RacePrediction | null; error: string | null } | null>(null)
  const [service, setService] = useState<ScenarioService | null>(null)
  const [serviceError, setServiceError] = useState<string | null>(null)
  const [generation, setGeneration] = useState<{ key: string; status: 'running' | 'complete' | 'failed'; message: string } | null>(null)
  const generationController = useRef<AbortController | null>(null)
  const entry = index?.races.find((item) => item.race_id === p.replay.id)
  const preset = findExactPreset(entry?.presets, Number(tws), Number(offset))
  const presetKey = `${tws}/${offset}/${preset?.id ?? ''}`
  const generationKey = `${p.replay.id}/${tws}/${offset}`
  const activeGeneration = generation?.key === generationKey ? generation : null
  const inputProblem = !tws.trim() || !offset.trim() ? 'Enter both wind conditions.' : !Number.isFinite(Number(tws)) || Number(tws) < 0 || Number(tws) > 80 ? 'Wind speed must be between 0 and 80 knots.' : !Number.isFinite(Number(offset)) || Math.abs(Number(offset)) > 180 ? 'Direction offset must be between −180° and +180°.' : null
  const directionProblem = Number(offset) !== 0 ? 'The current model supports a fixed course direction (0° offset). A direction response has not passed validation.' : null

  useEffect(() => {
    const controller = new AbortController()
    void loadScenarioService(controller.signal).then(setService).catch((error: unknown) => { if (!controller.signal.aborted) setServiceError(failure(error)) })
    return () => controller.abort()
  }, [])
  useEffect(() => {
    setGeneration((previous) => previous?.status === 'running' && previous.key !== generationKey ? null : previous)
    return () => generationController.current?.abort()
  }, [generationKey])

  useEffect(() => {
    const controller = new AbortController()
    setIndex(null); setRace(null); setCup(null); setRaceError(null); setCupError(null)
    void loadPredictionIndex(controller.signal).then((archive) => {
      if (controller.signal.aborted) return
      setIndex(archive)
      const selected = archive.races.find((item) => item.race_id === p.replay.id)
      if (!selected) setRaceError('There is no forecast artifact for this race.')
      else void loadRacePrediction(selected.path, { raceId: p.replay.id, boatIds: p.replay.competitors.map((boat) => boat.id), boatClass: p.replay.boat_class ?? 'AC40', reference: selected }, controller.signal)
        .then((data) => { if (!controller.signal.aborted) setRace(data) })
        .catch((error: unknown) => { if (!controller.signal.aborted) setRaceError(failure(error)) })
      void loadCupPrediction(archive.cup_path, controller.signal)
        .then((data) => { if (!controller.signal.aborted) setCup(data) })
        .catch((error: unknown) => { if (!controller.signal.aborted) setCupError(failure(error)) })
    }).catch((error: unknown) => { if (!controller.signal.aborted) { setRaceError(failure(error)); setCupError(failure(error)) } })
    return () => controller.abort()
  }, [p.replay])

  useEffect(() => {
    if (conditionsMode === 'recorded' || !preset?.path) return
    const controller = new AbortController()
    void loadRacePrediction(preset.path, { raceId: p.replay.id, boatIds: p.replay.competitors.map((boat) => boat.id), boatClass: p.replay.boat_class ?? 'AC40', reference: { model_ref: preset.model_ref ?? entry?.model_ref, source_manifest_hash: preset.source_manifest_hash ?? entry?.source_manifest_hash, scenario_hash: preset.scenario_hash, boat_ids: entry?.boat_ids, replay_boat_ids: entry?.replay_boat_ids }, scope: 'pre_race', conditions: { tws_kt: preset.tws_kt, direction_offset_deg: preset.direction_offset_deg } }, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setPresetResult({ key: presetKey, prediction: data, error: null }) })
      .catch((error: unknown) => { if (!controller.signal.aborted) setPresetResult({ key: presetKey, prediction: null, error: failure(error) }) })
    return () => controller.abort()
  }, [conditionsMode, preset, presetKey, p.replay, entry])

  const selectedPreset = presetResult?.key === presetKey ? presetResult : null
  const prePrediction = conditionsMode === 'recorded' ? race : selectedPreset?.prediction ?? null
  const preError = conditionsMode === 'recorded' ? raceError : inputProblem ?? (preset?.path ? selectedPreset ? selectedPreset.error : 'Loading the exact pre-race scenario…' : activeGeneration?.status === 'running' ? activeGeneration.message : activeGeneration?.status === 'failed' ? activeGeneration.message : directionProblem ?? (service?.available ? 'Choose Generate forecast to prepare these exact conditions.' : serviceError ?? service?.message ?? 'Checking forecast preparation…'))
  const preStateLabel = conditionsMode !== 'scenario' || prePrediction ? undefined : activeGeneration?.status === 'running' ? 'Preparing…' : directionProblem ? 'Direction unsupported' : inputProblem ? 'Check conditions' : service?.available ? 'Ready to generate' : 'Not prepared'
  const generate = async () => {
    if (inputProblem || directionProblem || !service?.available || activeGeneration?.status === 'running') return
    generationController.current?.abort()
    const controller = new AbortController(); generationController.current = controller
    const key = generationKey, speed = Number(tws), direction = Number(offset), rawSpeed = tws, rawDirection = offset
    setGeneration({ key, status: 'running', message: 'Preparing the forecast for these exact conditions…' })
    try {
      const job = await prepareScenario({ race_id: p.replay.id, tws_kt: speed, direction_offset_deg: direction }, controller.signal, (message) => { if (!controller.signal.aborted) setGeneration({ key, status: 'running', message }) })
      const fresh = await loadPredictionIndex(controller.signal)
      const freshEntry = fresh.races.find((item) => item.race_id === p.replay.id)
      const exact = findExactPreset(freshEntry?.presets, speed, direction)
      if (!exact?.path || exact.path !== job.path) throw new Error('The prepared forecast does not match these exact conditions. Please retry.')
      const prediction = await loadRacePrediction(exact.path, { raceId: p.replay.id, boatIds: p.replay.competitors.map((boat) => boat.id), boatClass: p.replay.boat_class ?? 'AC40', reference: { model_ref: exact.model_ref ?? freshEntry?.model_ref, source_manifest_hash: exact.source_manifest_hash ?? freshEntry?.source_manifest_hash, scenario_hash: exact.scenario_hash, boat_ids: freshEntry?.boat_ids, replay_boat_ids: freshEntry?.replay_boat_ids }, scope: 'pre_race', conditions: { tws_kt: speed, direction_offset_deg: direction } }, controller.signal)
      if (controller.signal.aborted) return
      setIndex(fresh); setPresetResult({ key: `${rawSpeed}/${rawDirection}/${exact.id}`, prediction, error: null })
      setGeneration({ key, status: 'complete', message: job.message })
    } catch (error) { if (!controller.signal.aborted) setGeneration({ key, status: 'failed', message: failure(error) }) }
  }
  const liveCheckpoint = race ? selectForecastCheckpoint(race, p.playhead) : null
  const liveStatus = race && liveCheckpoint?.index != null ? checkpointStatus(race, liveCheckpoint.index) : null
  const questions = [
    { id: 'live' as const, label: 'Live race', description: 'Win at the playhead', status: !race && !raceError ? 'Loading…' : ['available', 'estimated'].includes(liveStatus ?? '') ? liveStatus === 'estimated' ? 'Estimated state' : 'Available' : 'Unavailable' },
    { id: 'pre' as const, label: 'Before the start', description: 'Expected finishing position', status: preStateLabel ?? (!prePrediction && !preError ? 'Loading…' : prePrediction && !preError && ['available', 'estimated'].includes(prePrediction.pre_race.status) ? 'Available' : 'Unavailable') },
    { id: 'cup' as const, label: 'America’s Cup 2027', description: 'AC75 scenario bounds', status: !cup && !cupError ? 'Loading…' : cup && !cupError && ['available', 'estimated'].includes(cup.status) ? 'Scenario envelope' : 'Unavailable' },
  ]
  return <section className="dashboard-workspace forecast-workspace" aria-label="Forecast">
    <div className="workspace-heading"><div><h2>Forecast</h2><p>Explore the current race, pre-race expectations and the Cup. Each uses its own conditions and evidence.</p></div><label>Selected boat <select aria-label="Forecast selected boat" value={p.selectedId ?? ''} onChange={(event) => p.onSelectBoat(event.target.value)}>{p.replay.competitors.map((boat) => <option key={boat.id} value={boat.id}>{boat.team_code}</option>)}</select></label></div>
    <div className="forecast-question-nav" role="tablist" aria-label="Forecast questions">{questions.map((item) => <button key={item.id} id={`forecast-tab-${item.id}`} type="button" role="tab" aria-label={item.label} aria-describedby={`forecast-readiness-${item.id}`} aria-selected={question === item.id} aria-controls={`forecast-panel-${item.id}`} tabIndex={question === item.id ? 0 : -1} onClick={() => setQuestion(item.id)} onKeyDown={(event) => {
      const current = questions.findIndex((entry) => entry.id === item.id)
      const next = event.key === 'ArrowRight' ? (current + 1) % questions.length : event.key === 'ArrowLeft' ? (current + questions.length - 1) % questions.length : event.key === 'Home' ? 0 : event.key === 'End' ? questions.length - 1 : null
      if (next === null) return
      event.preventDefault()
      setQuestion(questions[next].id)
      document.getElementById(`forecast-tab-${questions[next].id}`)?.focus()
    }}><span className="forecast-question-label">{item.label}</span><span className="forecast-question-description">{item.description}</span><span id={`forecast-readiness-${item.id}`} className={`forecast-question-readiness ${['Available', 'Estimated state', 'Scenario envelope'].includes(item.status) ? 'is-ready' : ''}`}>{item.status}</span></button>)}</div>
    <div className="forecast-grid">
      <section id="forecast-panel-live" className="forecast-question-panel" role="tabpanel" aria-labelledby="forecast-tab-live" hidden={question !== 'live'}>
        <div className="forecast-playhead"><button onClick={p.onToggle}>{p.playing ? 'Pause replay' : 'Play replay'}</button><label>Race playhead <input aria-label="Forecast race playhead" type="range" min={p.replay.chronology.window_start} max={p.replay.chronology.window_end} step={1000} value={p.playhead} onChange={(event) => p.onSeek(Number(event.target.value))} /></label><output>{new Date(p.playhead).toISOString().slice(11, 19)} UTC</output></div>
        <LiveForecastCard prediction={race} error={raceError} playhead={p.playhead} replay={p.replay} selectedId={p.selectedId} />
      </section>
      <section id="forecast-panel-pre" className="forecast-question-panel" role="tabpanel" aria-labelledby="forecast-tab-pre" hidden={question !== 'pre'}>
      <PreRaceForecastCard prediction={prePrediction} rosterPrediction={race} error={preError} replay={p.replay} selectedId={p.selectedId} stateLabel={preStateLabel}>
        <label>Pre-race conditions <select aria-label="Pre-race conditions" value={conditionsMode} onChange={(event) => setConditionsMode(event.target.value)}><option value="recorded">Recorded start conditions</option><option value="scenario">Enter wind conditions</option></select></label>
        {conditionsMode === 'scenario' && <div className="forecast-conditions"><label>Wind speed (knots)<input aria-label="Pre-race wind speed" type="number" min="0" max="80" step="0.1" value={tws} onChange={(event) => setTws(event.target.value)} list="forecast-wind-presets" /><datalist id="forecast-wind-presets">{[8, 12, 16, 20].map((value) => <option key={value} value={value} />)}</datalist></label><label>Direction offset from course (°)<input aria-label="Pre-race wind direction offset" type="number" min="-180" max="180" step="1" value={offset} onChange={(event) => setOffset(event.target.value)} /></label><p>Prepare an exact wind-speed scenario here. The current model uses a fixed course direction and a zero-effect wind reference, so supported wind speeds can give the same expectation.</p><div className="forecast-scenario-actions"><button type="button" className="forecast-generate" disabled={!!inputProblem || !!directionProblem || !service?.available || activeGeneration?.status === 'running'} onClick={() => void generate()}>{activeGeneration?.status === 'running' ? 'Preparing forecast…' : activeGeneration?.status === 'failed' ? 'Retry forecast' : 'Generate forecast'}</button>{directionProblem && <button type="button" className="forecast-direction-reset" onClick={() => setOffset('0')}>Use 0° offset</button>}</div>{activeGeneration && <p role="status" aria-live="polite" className="forecast-generation-status">{evidenceText(activeGeneration.message)}</p>}{!service?.available && serviceError && <p className="forecast-service-notice">{serviceError}</p>}</div>}
      </PreRaceForecastCard>
      </section>
      <section id="forecast-panel-cup" className="forecast-question-panel" role="tabpanel" aria-labelledby="forecast-tab-cup" hidden={question !== 'cup'}>
        <CupForecastCard prediction={cup} error={cupError} />
      </section>
    </div>
  </section>
}
