import { useEffect, useState } from 'react'
import type { RaceListing } from '../../engine/catalog'
import type { AnalysisDetail } from '../../types/analysis'
import type { BoatScaleMode, CameraMode, FollowMode, PlaybackSpeed, ReplayFrame, ReplayManifest, TrailColor, TrailLength, ViewMode } from '../../types/replay'
import { CourseCanvas } from '../canvas/CourseCanvas'
import { AnalysisModal } from '../modals/AnalysisModal'
import { ComparisonPanel } from '../panels/ComparisonPanel'
import { TacticalHeader } from './TacticalHeader'
import { RaceTimelinePanel } from './RaceTimelinePanel'
import { TacticalMapOverlay } from './TacticalMapOverlay'
import { RaceStatusLeaderboard } from './RaceStatusLeaderboard'
import { BoatPerformanceCard } from './BoatPerformanceCard'
import { TelemetryWorkspace } from './TelemetryWorkspace'
import { EventsNotesPanel } from './EventsNotesPanel'
import { ReportsWorkspace } from './ReportsWorkspace'
import { ForecastWorkspace } from './ForecastWorkspace'
import './dashboard.css'
import './workspaces.css'

export type DashboardView = 'replay' | 'analysis' | 'compare' | 'reports' | 'forecast'
interface Props {
  replay: ReplayManifest; frame: ReplayFrame; catalog: RaceListing[]; currentRace: RaceListing | null
  activeView: DashboardView; onViewChange: (view: DashboardView) => void
  playing: boolean; speed: PlaybackSpeed; onToggle: () => void; onSeek: (time: number) => void; onStep: (seconds: number) => void; onSpeed: (speed: PlaybackSpeed) => void
  selectedId: string | null; onSelectBoat: (id: string) => void
  comparisonId: string | null; onSelectComparison: (id: string) => void
  visibleBoatId: string | null; onVisibleBoatChange: (id: string | null) => void
  cameraMode: CameraMode; onCameraModeChange: (mode: CameraMode) => void
  followMode: FollowMode; onFollowModeChange: (mode: FollowMode) => void
  viewMode: ViewMode; onViewModeChange: (mode: ViewMode) => void
  scaleMode: BoatScaleMode; onScaleModeChange: (mode: BoatScaleMode) => void
  showSafetyBorders: boolean; onToggleSafetyBorders: () => void
  trailLength: TrailLength; onTrailLengthChange: (value: TrailLength) => void
  trailColor: TrailColor; onTrailColorChange: (value: TrailColor) => void
  resetView: number; onResetView: () => void
  onSelectRace: (race: RaceListing) => void; onOpenPicker: () => void
  analysisDetail: AnalysisDetail | null; onOpenAnalysisReplay: (raceId: string, timestamp?: number) => void
}

export function TacticalDashboard(p: Props) {
  const [zoomIn, setZoomIn] = useState(0)
  const [zoomOut, setZoomOut] = useState(0)
  const [settingsOpen, setSettingsOpen] = useState(false)
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setSettingsOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  const events = p.analysisDetail?.event_feed?.events
  const primary = p.replay.competitors.find((boat) => boat.id === p.selectedId) ?? p.replay.competitors[0]
  const timeline = <RaceTimelinePanel replay={p.replay} frame={p.frame} playing={p.playing} speed={p.speed} onToggle={p.onToggle} onSeek={p.onSeek} onStep={p.onStep} onSpeed={p.onSpeed} selectedId={p.selectedId} events={events} />
  const telemetry = <TelemetryWorkspace replay={p.replay} frame={p.frame} selectedId={p.selectedId} onSelectBoat={p.onSelectBoat} onSeek={p.onSeek} visibleBoatId={p.visibleBoatId} />
  const chooseView = (view: string) => { if (['replay', 'analysis', 'compare', 'reports', 'forecast'].includes(view)) p.onViewChange(view as DashboardView) }
  return <div className="tactical-dashboard-root theme-tactical-light">
    <TacticalHeader replay={p.replay} frame={p.frame} currentRace={p.currentRace} catalog={p.catalog} activeNav={p.activeView} onSelectNav={chooseView} onSelectRace={p.onSelectRace} visibleBoats={p.visibleBoatId ?? 'all'} onVisibleBoatsChange={(id) => p.onVisibleBoatChange(id === 'all' ? null : id)} onOpenPicker={p.onOpenPicker} onOpenSettings={() => setSettingsOpen(true)} />
    {p.activeView === 'replay' && <>
      <section className="tactical-stage-band">
        {timeline}
        <div className="center-tactical-stage-wrap"><div className="map-viewport-frame">
          <CourseCanvas replay={p.replay} frame={p.frame} cameraMode={p.cameraMode} followMode={p.followMode} selectedId={p.selectedId} comparisonId={p.comparisonId} visibleBoatId={p.visibleBoatId} resetView={p.resetView} trailLength={p.trailLength} trailColor={p.trailColor} showSafetyBorders={p.showSafetyBorders} viewMode={p.viewMode} scaleMode={p.scaleMode} onSelectBoat={p.onSelectBoat} zoomInTrigger={zoomIn} zoomOutTrigger={zoomOut} />
          <TacticalMapOverlay replay={p.replay} frame={p.frame} viewMode={p.viewMode} onViewModeChange={p.onViewModeChange} followMode={p.followMode} onFollowModeChange={p.onFollowModeChange} showSafetyBorders={p.showSafetyBorders} onToggleSafetyBorders={p.onToggleSafetyBorders} onResetView={p.onResetView} onZoomIn={() => setZoomIn((value) => value + 1)} onZoomOut={() => setZoomOut((value) => value + 1)} onToggleFullscreen={() => {
            const element = document.querySelector('.center-tactical-stage-wrap') as HTMLElement | null
            if (document.fullscreenElement) void document.exitFullscreen?.()
            else void element?.requestFullscreen?.().catch(() => {})
          }} selectedBoatId={p.selectedId} events={events} />
        </div></div>
        <RaceStatusLeaderboard replay={p.replay} frame={p.frame} selectedId={p.selectedId} onSelectBoat={p.onSelectBoat} />
      </section>
      <section className="selected-boat-kpi-banner"><BoatPerformanceCard replay={p.replay} frame={p.frame} selectedId={p.selectedId} /></section>
      <section className="tactical-bottom-band">{telemetry}<EventsNotesPanel key={p.replay.id} replay={p.replay} frame={p.frame} onSeek={p.onSeek} selectedId={p.selectedId} events={events} /></section>
    </>}
    {p.activeView === 'analysis' && <AnalysisModal inline selectedBoatId={p.selectedId} onSelectBoat={p.onSelectBoat} comparisonId={p.comparisonId} onSelectComparison={p.onSelectComparison} onSelectRace={(id) => { const race = p.catalog.find((item) => item.id === id); if (race) p.onSelectRace(race) }} currentRaceId={p.replay.id} replayRaceIds={p.catalog.map((race) => race.id)} onOpenReplay={p.onOpenAnalysisReplay} onClose={() => p.onViewChange('replay')} />}
    {p.activeView === 'compare' && <div className="dashboard-secondary-layout">{timeline}<section className="dashboard-workspace" aria-label="Compare boats"><h2>Compare at the shared playhead</h2><label>Primary boat A <select aria-label="Primary boat A" value={primary.id} onChange={(event) => p.onSelectBoat(event.target.value)}>{p.replay.competitors.map((boat) => <option key={boat.id} value={boat.id}>{boat.team_code} · {boat.team_name}</option>)}</select></label><ComparisonPanel replay={p.replay} frame={p.frame} primary={primary} secondaryId={p.comparisonId} onSecondary={p.onSelectComparison} /><p>Changing A preserves your explicit B selection. Instantaneous comparison uses replay positions, speeds and leg progress at the playhead; the historical Analysis tab exposes exported race aggregates.</p>{telemetry}</section></div>}
    {p.activeView === 'reports' && <ReportsWorkspace replay={p.replay} catalog={p.catalog} onOpenRace={(race, view) => { p.onSelectRace(race); chooseView(view.toLowerCase()) }} />}
    {p.activeView === 'forecast' && <ForecastWorkspace key={p.replay.id} replay={p.replay} playhead={p.frame.timestamp} selectedId={p.selectedId} onSelectBoat={p.onSelectBoat} onSeek={p.onSeek} playing={p.playing} onToggle={p.onToggle} />}
    {settingsOpen && <div className="modal-shade" onMouseDown={(event) => { if (event.target === event.currentTarget) setSettingsOpen(false) }}><section role="dialog" aria-modal="true" aria-label="Dashboard settings" className="dashboard-settings dashboard-workspace">
      <div className="workspace-heading"><h2>Dashboard settings</h2><button autoFocus aria-label="Close settings" onClick={() => setSettingsOpen(false)}>×</button></div>
      <label>Map source <select aria-label="Map source" value={p.viewMode} onChange={(event) => p.onViewModeChange(event.target.value as ViewMode)}><option value="map">OpenStreetMap</option><option value="grid">Offline Grid</option></select></label>
      <label>Orientation <select aria-label="Orientation" value={p.cameraMode} onChange={(event) => p.onCameraModeChange(event.target.value as CameraMode)}><option value="north">North up</option><option value="course">Course up</option></select></label>
      <label>Boat display <select aria-label="Boat display" value={p.scaleMode} onChange={(event) => p.onScaleModeChange(event.target.value as BoatScaleMode)}><option value="true">True metric scale</option><option value="enhanced">Enhanced visibility</option></select></label>
      <label>Trail length <select aria-label="Trail length" value={p.trailLength} onChange={(event) => p.onTrailLengthChange(event.target.value as TrailLength)}>{['off', '10s', '30s', '60s', 'leg', 'race'].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
      <label>Trail colour <select aria-label="Trail colour" value={p.trailColor} onChange={(event) => p.onTrailColorChange(event.target.value as TrailColor)}>{['team', 'speed', 'vmg'].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
      <label><input type="checkbox" checked={p.showSafetyBorders} onChange={p.onToggleSafetyBorders} /> Show virtual safety borders</label>
      <p>Space plays or pauses; arrow keys seek 5 seconds; keys 1–5 select the main tabs. Notes are saved locally for each race.</p>
    </section></div>}
  </div>
}
