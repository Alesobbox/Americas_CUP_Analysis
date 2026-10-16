import { useEffect, useState } from 'react'
import { checkpointStatus, findExactPreset, loadCupPrediction, loadPredictionIndex, loadRacePrediction, selectForecastCheckpoint } from '../../engine/predictionCatalog'
import type { CupPrediction, PredictionIndex, RacePrediction } from '../../types/prediction'
import type { ReplayManifest } from '../../types/replay'
import './forecast.css'

const percent = (value: number) => `${(value * 100).toFixed(1)}%`
const reasonText = (reason: string | undefined, fallback: string) => reason?.replaceAll('_', ' ') || fallback
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
      return <tr key={boat.id} aria-selected={boat.id === selectedId}><th scope="row">{boat.team_code}</th><td>{value == null ? '—' : percent(value)}</td><td>{age == null ? '—' : `${(age / 1000).toFixed(1)} s`}</td></tr>
    })}</tbody></table></div>
    {available && prediction && index !== null && <p className="forecast-footnote">State: {new Date(prediction.live.state_timestamps_ms[index]).toISOString().slice(11, 19)} UTC · published: {new Date(prediction.live.published_at_ms[index]).toISOString().slice(11, 19)} UTC.{numericalError !== null && <> Monte Carlo precision: ±{(numericalError * 100).toFixed(2)} percentage points; model uncertainty is separate.</>}</p>}
    {prediction && <details><summary>Method and evidence</summary><p>Model: {prediction.header.model_ref}. {prediction.header.method_and_assumption_refs.join(' · ')}</p><p className="forecast-hash">Input: {prediction.header.source_manifest_hash}<br />Scenario: {prediction.header.scenario_hash}</p></details>}
  </article>
}

export function PreRaceForecastCard({ prediction, error, replay, selectedId, children }: Pick<Props, 'replay' | 'selectedId'> & { prediction: RacePrediction | null; error: string | null; children?: React.ReactNode }) {
  const available = prediction && ['available', 'estimated'].includes(prediction.pre_race.status) && !error
  return <article className="forecast-card" aria-labelledby="pre-forecast-title">
    <div className="forecast-card-heading"><span className="forecast-scope">Before the start · AC40</span><span className={`forecast-status ${available ? 'forecast-status-ready' : ''}`}>{available ? 'Available' : 'Unavailable'}</span></div>
    <h3 id="pre-forecast-title">Expected finishing position</h3>
    <p>Expected position · nonfinish scored N ({prediction?.header.boat_ids.length ?? replay.competitors.length}). Uses the scheduled opponents and the selected conditions.</p>
    {children}
    {!available && <p role="status" className="forecast-unavailable">{reasonText(error ?? prediction?.pre_race.reason, prediction ? 'Audited completion and outcome evidence is required for an unconditional expected position.' : 'Loading the pre-race forecast…')}</p>}
    <div className="workspace-table-wrap"><table><thead><tr><th>Boat</th><th>Expected position</th></tr></thead><tbody>{forecastBoats(prediction, replay).map((boat) => {
      const value = available ? prediction.pre_race.expected_position_by_boat[boat.id] : null
      return <tr key={boat.id} aria-selected={boat.id === selectedId}><th scope="row">{boat.team_code}</th><td>{value == null ? '—' : value.toFixed(2)}</td></tr>
    })}</tbody></table></div>
    {available && <p className="forecast-footnote">These positions include noncompletion and do not have to sum to the usual rank total.</p>}
  </article>
}

export function CupForecastCard({ prediction, error }: { prediction: CupPrediction | null; error: string | null }) {
  const available = prediction && ['available', 'estimated'].includes(prediction.status) && !error
  return <article className="forecast-card" aria-labelledby="cup-forecast-title">
    <div className="forecast-card-heading"><span className="forecast-scope">America’s Cup 2027 · AC75</span><span className={`forecast-status ${available ? 'forecast-status-ready' : ''}`}>{available ? 'Scenario envelope' : 'Unavailable'}</span></div>
    <h3 id="cup-forecast-title">Win the whole America’s Cup</h3>
    <p>Includes Challenger selection and the final Match against the Defender.</p>
    {!available && <p role="status" className="forecast-unavailable">{reasonText(error ?? prediction?.reason, prediction ? 'The available evidence and event rules do not support a Cup estimate.' : 'Loading the America’s Cup scenarios…')}</p>}
    {prediction && <div className="workspace-table-wrap"><table><thead><tr><th>Team</th><th>Transfer scenarios</th>{prediction.rule_bounds_by_team && <th>Unresolved rule bounds</th>}</tr></thead><tbody>{prediction.teams.map((team) => {
      const range = available ? prediction.scenario_envelope_by_team?.[team.id] : null
      const rules = available ? prediction.rule_bounds_by_team?.[team.id] : null
      return <tr key={team.id}><th scope="row">{team.name}</th><td>{range ? `${percent(range.lower)}–${percent(range.upper)}` : '—'}</td>{prediction.rule_bounds_by_team && <td>{rules ? `${percent(rules.lower)}–${percent(rules.upper)}` : '—'}</td>}</tr>
    })}</tbody></table></div>}
    {available && <p className="forecast-footnote">AC40-informed scenario ranges cover only generated transfer assumptions; they are not calibrated AC75 confidence intervals. Rule bounds describe unresolved permitted outcomes and need not sum to 100%.</p>}
    {prediction && <details><summary>Format and scenario evidence</summary><p>{prediction.header.method_and_assumption_refs?.join(' · ') || 'See the versioned event-rules and model manifest in the forecast downloads.'}</p>{prediction.evaluated_scenarios && <p>{prediction.evaluated_scenarios.length} generated scenarios: {prediction.evaluated_scenarios.join(', ')}.</p>}</details>}
  </article>
}

export function ForecastWorkspace(p: Props) {
  const [index, setIndex] = useState<PredictionIndex | null>(null)
  const [race, setRace] = useState<RacePrediction | null>(null)
  const [cup, setCup] = useState<CupPrediction | null>(null)
  const [raceError, setRaceError] = useState<string | null>(null)
  const [cupError, setCupError] = useState<string | null>(null)
  const [conditionsMode, setConditionsMode] = useState('recorded')
  const [tws, setTws] = useState('12')
  const [offset, setOffset] = useState('0')
  const [presetResult, setPresetResult] = useState<{ key: string; prediction: RacePrediction | null; error: string | null } | null>(null)
  const entry = index?.races.find((item) => item.race_id === p.replay.id)
  const preset = findExactPreset(entry?.presets, Number(tws), Number(offset))
  const presetKey = `${tws}/${offset}/${preset?.id ?? ''}`

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
  const preError = conditionsMode === 'recorded' ? raceError : !tws.trim() || !offset.trim() ? 'Enter both wind conditions.' : !preset ? 'No supported pre-race artifact exists for these exact conditions. Build a custom scenario in the Python pipeline.' : !preset.path ? reasonText(preset.reason, 'This preset has insufficient historical support.') : selectedPreset ? selectedPreset.error : 'Loading the exact pre-race scenario…'
  return <section className="dashboard-workspace forecast-workspace" aria-label="Forecast">
    <div className="workspace-heading"><div><h2>Forecast</h2><p>Three estimates, each tied to its race, conditions, evidence and event format.</p></div><label>Selected boat <select aria-label="Forecast selected boat" value={p.selectedId ?? ''} onChange={(event) => p.onSelectBoat(event.target.value)}>{p.replay.competitors.map((boat) => <option key={boat.id} value={boat.id}>{boat.team_code}</option>)}</select></label></div>
    <p className="forecast-evidence">Experimental estimates · calibration has not been established for this archive. “Available” describes input availability.</p>
    <div className="forecast-playhead"><button onClick={p.onToggle}>{p.playing ? 'Pause replay' : 'Play replay'}</button><label>Race playhead <input aria-label="Forecast race playhead" type="range" min={p.replay.chronology.window_start} max={p.replay.chronology.window_end} step={1000} value={p.playhead} onChange={(event) => p.onSeek(Number(event.target.value))} /></label><output>{new Date(p.playhead).toISOString().slice(11, 19)} UTC</output></div>
    <div className="forecast-grid">
      <LiveForecastCard prediction={race} error={raceError} playhead={p.playhead} replay={p.replay} selectedId={p.selectedId} />
      <PreRaceForecastCard prediction={prePrediction} error={preError} replay={p.replay} selectedId={p.selectedId}>
        <label>Pre-race conditions <select aria-label="Pre-race conditions" value={conditionsMode} onChange={(event) => setConditionsMode(event.target.value)}><option value="recorded">Recorded start conditions</option><option value="scenario">Enter wind conditions</option></select></label>
        {conditionsMode === 'scenario' && <div className="forecast-conditions"><label>Wind speed (knots)<input aria-label="Pre-race wind speed" type="number" min="0" step="0.1" value={tws} onChange={(event) => setTws(event.target.value)} list="forecast-wind-presets" /><datalist id="forecast-wind-presets">{[8, 12, 16, 20].map((value) => <option key={value} value={value} />)}</datalist></label><label>Direction offset from course (°)<input aria-label="Pre-race wind direction offset" type="number" step="1" value={offset} onChange={(event) => setOffset(event.target.value)} list="forecast-direction-presets" /><datalist id="forecast-direction-presets">{[-15, 0, 15].map((value) => <option key={value} value={value} />)}</datalist></label><p>Applies to expected position only. Presets use exactly 8, 12, 16 or 20 knots and −15°, 0° or +15° when supported.</p></div>}
      </PreRaceForecastCard>
      <CupForecastCard prediction={cup} error={cupError} />
    </div>
  </section>
}
