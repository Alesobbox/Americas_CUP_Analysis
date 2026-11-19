import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import type { RaceListing } from '../../engine/catalog'
import type { AnalysisDetail } from '../../types/analysis'
import type {
  BoatScaleMode,
  CameraMode,
  FollowMode,
  PlaybackSpeed,
  ReplayFrame,
  ReplayManifest,
  TrailColor,
  TrailLength,
  TrailScope,
  ViewMode,
} from '../../types/replay'
import { CourseCanvas } from '../canvas/CourseCanvas'
import { ComparisonPanel } from '../panels/ComparisonPanel'
import { TacticalHeader } from './TacticalHeader'
import { RaceTimelinePanel } from './RaceTimelinePanel'
import { TacticalMapControls, TacticalMapOverlay } from './TacticalMapOverlay'
import { RaceStatusLeaderboard } from './RaceStatusLeaderboard'
import { BoatPerformanceCard } from './BoatPerformanceCard'
import { TelemetryWorkspace } from './TelemetryWorkspace'
import { EventsNotesPanel } from './EventsNotesPanel'
import { TacticalInsightsPanel } from './TacticalInsightsPanel'
import { BoatVisibilityFilter } from './BoatVisibilityFilter'
import { BoatCourseControls } from './BoatCourseControls'
import './dashboard.css'
import './workspaces.css'
import './analysis-light.css'
import './performance-radar.css'

const AnalysisModal = lazy(() =>
  import('../modals/AnalysisModal').then((m) => ({ default: m.AnalysisModal }))
)
const ReportsWorkspace = lazy(() =>
  import('./ReportsWorkspace').then((m) => ({ default: m.ReportsWorkspace }))
)

export type DashboardView = 'replay' | 'analysis' | 'compare' | 'reports'
export interface ReviewInterval {
  raceId: string
  boatId: string
  start_ms: number
  end_ms: number
}
interface Props {
  replay: ReplayManifest
  frame: ReplayFrame
  catalog: RaceListing[]
  currentRace: RaceListing | null
  activeView: DashboardView
  onViewChange: (view: DashboardView) => void
  playing: boolean
  speed: PlaybackSpeed
  onToggle: () => void
  onSeek: (time: number) => void
  onStep: (seconds: number) => void
  onSpeed: (speed: PlaybackSpeed) => void
  selectedId: string | null
  onSelectBoat: (id: string) => void
  comparisonId: string | null
  onSelectComparison: (id: string) => void
  visibleBoatId: string | null
  onVisibleBoatChange: (id: string | null) => void
  cameraMode: CameraMode
  onCameraModeChange: (mode: CameraMode) => void
  followMode: FollowMode
  onFollowModeChange: (mode: FollowMode) => void
  viewMode: ViewMode
  onViewModeChange: (mode: ViewMode) => void
  scaleMode: BoatScaleMode
  onScaleModeChange: (mode: BoatScaleMode) => void
  showSafetyBorders: boolean
  onToggleSafetyBorders: () => void
  trailLength: TrailLength
  onTrailLengthChange: (value: TrailLength) => void
  trailColor: TrailColor
  onTrailColorChange: (value: TrailColor) => void
  trailScope: TrailScope
  onTrailScopeChange: (value: TrailScope) => void
  showVmgLabels: boolean
  onShowVmgLabelsChange: (value: boolean) => void
  highlightComparison: boolean
  onHighlightComparisonChange: (value: boolean) => void
  resetView: number
  onResetView: () => void
  onSelectRace: (race: RaceListing) => void
  onOpenPicker: () => void
  analysisDetail: AnalysisDetail | null
  onOpenAnalysisReplay: (
    raceId: string,
    timestamp?: number,
    boatId?: string,
    intervalEnd?: number
  ) => void
  reviewInterval?: ReviewInterval | null
  onClearReview?: () => void
}

export function TacticalDashboard(p: Props) {
  const [zoomIn, setZoomIn] = useState(0)
  const [zoomOut, setZoomOut] = useState(0)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const settingsDialog = useRef<HTMLElement>(null)
  const settingsOpener = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (!settingsOpen) return
    const dialog = settingsDialog.current
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !dialog) return
      const controls = [
        ...dialog.querySelectorAll<HTMLElement>(
          'button:not(:disabled), select:not(:disabled), input:not(:disabled), a[href]'
        ),
      ].filter((element) => element.getClientRects().length)
      const first = controls[0],
        last = controls[controls.length - 1]
      if (
        event.shiftKey &&
        (document.activeElement === first || !dialog.contains(document.activeElement))
      ) {
        event.preventDefault()
        last?.focus()
      } else if (
        !event.shiftKey &&
        (document.activeElement === last || !dialog.contains(document.activeElement))
      ) {
        event.preventDefault()
        first?.focus()
      }
    }
    document.addEventListener('keydown', trapFocus)
    return () => {
      document.removeEventListener('keydown', trapFocus)
      document.body.style.overflow = previousOverflow
      if (settingsOpener.current?.isConnected) settingsOpener.current.focus()
    }
  }, [settingsOpen])
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSettingsOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  const events = p.analysisDetail?.event_feed?.events
  const primary =
    p.replay.competitors.find((boat) => boat.id === p.selectedId) ?? p.replay.competitors[0]
  const timeline = (
    <RaceTimelinePanel
      replay={p.replay}
      frame={p.frame}
      playing={p.playing}
      speed={p.speed}
      onToggle={p.onToggle}
      onSeek={p.onSeek}
      onStep={p.onStep}
      onSpeed={p.onSpeed}
      selectedId={p.selectedId}
      events={events}
    />
  )
  const telemetry = (
    <TelemetryWorkspace
      replay={p.replay}
      frame={p.frame}
      selectedId={p.selectedId}
      onSelectBoat={p.onSelectBoat}
      onSeek={p.onSeek}
      visibleBoatId={p.visibleBoatId}
    />
  )
  const chooseView = (view: string) => {
    if (['replay', 'analysis', 'compare', 'reports'].includes(view))
      p.onViewChange(view as DashboardView)
  }
  return (
    <div className="tactical-dashboard-root theme-tactical-light" data-view={p.activeView}>
      <TacticalHeader
        replay={p.replay}
        frame={p.frame}
        currentRace={p.currentRace}
        catalog={p.catalog}
        activeNav={p.activeView}
        onSelectNav={chooseView}
        onSelectRace={p.onSelectRace}
        onOpenPicker={p.onOpenPicker}
        onOpenSettings={() => {
          settingsOpener.current = document.activeElement as HTMLElement
          setSettingsOpen(true)
        }}
      />
      {p.activeView === 'replay' && (
        <>
          {p.reviewInterval?.raceId === p.replay.id && (
            <section className="review-interval" aria-label="Reviewed leg interval">
              <strong>
                {
                  p.replay.competitors.find((boat) => boat.id === p.reviewInterval?.boatId)
                    ?.team_code
                }{' '}
                · reviewed leg
              </strong>
              <span>
                {new Date(p.reviewInterval.start_ms).toISOString().slice(11, 19)}–
                {new Date(p.reviewInterval.end_ms).toISOString().slice(11, 19)} UTC
              </span>
              <button onClick={() => p.onSeek(p.reviewInterval!.start_ms)}>
                Seek to leg start
              </button>
              <button onClick={() => p.onSeek(p.reviewInterval!.end_ms)}>Seek to leg end</button>
              <button onClick={p.onClearReview}>Clear review interval</button>
            </section>
          )}
          <section className="tactical-stage-band">
            <div className="center-tactical-stage-wrap">
              <div className="course-section-header">
                <h2>On the water</h2>
                <BoatVisibilityFilter
                  boats={p.replay.competitors}
                  visibleId={p.visibleBoatId}
                  onChange={p.onVisibleBoatChange}
                />
              </div>
              <div className="course-controls-row">
                <TacticalMapControls
                  replay={p.replay}
                  frame={p.frame}
                  viewMode={p.viewMode}
                  onViewModeChange={p.onViewModeChange}
                  followMode={p.followMode}
                  onFollowModeChange={p.onFollowModeChange}
                  showSafetyBorders={p.showSafetyBorders}
                  onToggleSafetyBorders={p.onToggleSafetyBorders}
                  onResetView={p.onResetView}
                  onZoomIn={() => setZoomIn((value) => value + 1)}
                  onZoomOut={() => setZoomOut((value) => value + 1)}
                  onToggleFullscreen={() => {
                    const element = document.querySelector(
                      '.center-tactical-stage-wrap'
                    ) as HTMLElement | null
                    if (document.fullscreenElement) void document.exitFullscreen?.()
                    else void element?.requestFullscreen?.().catch(() => {})
                  }}
                  selectedBoatId={p.selectedId}
                  events={events}
                />
              </div>
              <BoatCourseControls
                boats={p.replay.competitors}
                selectedId={p.selectedId}
                comparisonId={p.comparisonId}
                onComparison={p.onSelectComparison}
                scaleMode={p.scaleMode}
                onScaleMode={p.onScaleModeChange}
                trailScope={p.trailScope}
                onTrailScope={p.onTrailScopeChange}
                trailLength={p.trailLength}
                onTrailLength={p.onTrailLengthChange}
                trailColor={p.trailColor}
                onTrailColor={p.onTrailColorChange}
                showVmgLabels={p.showVmgLabels}
                onShowVmgLabels={p.onShowVmgLabelsChange}
                highlightComparison={p.highlightComparison}
                onHighlightComparison={p.onHighlightComparisonChange}
              />
              <div className="map-viewport-frame">
                <CourseCanvas
                  replay={p.replay}
                  frame={p.frame}
                  cameraMode={p.cameraMode}
                  followMode={p.followMode}
                  selectedId={p.selectedId}
                  comparisonId={p.comparisonId}
                  visibleBoatId={p.visibleBoatId}
                  resetView={p.resetView}
                  trailLength={p.trailLength}
                  trailColor={p.trailColor}
                  showSafetyBorders={p.showSafetyBorders}
                  viewMode={p.viewMode}
                  scaleMode={p.scaleMode}
                  trailScope={p.trailScope}
                  showVmgLabels={p.showVmgLabels}
                  highlightComparison={p.highlightComparison}
                  onSelectBoat={p.onSelectBoat}
                  zoomInTrigger={zoomIn}
                  zoomOutTrigger={zoomOut}
                />
                <TacticalMapOverlay
                  replay={p.replay}
                  frame={p.frame}
                  viewMode={p.viewMode}
                  onViewModeChange={p.onViewModeChange}
                  followMode={p.followMode}
                  onFollowModeChange={p.onFollowModeChange}
                  showSafetyBorders={p.showSafetyBorders}
                  onToggleSafetyBorders={p.onToggleSafetyBorders}
                  onResetView={p.onResetView}
                  onZoomIn={() => setZoomIn((value) => value + 1)}
                  onZoomOut={() => setZoomOut((value) => value + 1)}
                  onToggleFullscreen={() => {
                    const element = document.querySelector(
                      '.center-tactical-stage-wrap'
                    ) as HTMLElement | null
                    if (document.fullscreenElement) void document.exitFullscreen?.()
                    else void element?.requestFullscreen?.().catch(() => {})
                  }}
                  selectedBoatId={p.selectedId}
                  events={events}
                  controlsOutside
                />
              </div>
              {timeline}
              <section className="selected-boat-kpi-banner">
                <BoatPerformanceCard replay={p.replay} frame={p.frame} selectedId={p.selectedId} />
              </section>
            </div>
            <RaceStatusLeaderboard
              replay={p.replay}
              frame={p.frame}
              selectedId={p.selectedId}
              onSelectBoat={p.onSelectBoat}
            />
          </section>
          <section className="tactical-bottom-band">
            {telemetry}
            <EventsNotesPanel
              key={p.replay.id}
              replay={p.replay}
              frame={p.frame}
              onSeek={p.onSeek}
              selectedId={p.selectedId}
              events={events}
            />
          </section>
          <TacticalInsightsPanel
            detail={p.analysisDetail}
            raceId={p.replay.id}
            playhead={p.frame.timestamp}
          />
        </>
      )}
      {p.activeView === 'analysis' && (
        <Suspense
          fallback={
            <section className="dashboard-workspace">
              <p>Loading analysis…</p>
            </section>
          }
        >
          <AnalysisModal
            inline
            selectedBoatId={p.selectedId}
            onSelectBoat={p.onSelectBoat}
            comparisonId={p.comparisonId}
            onSelectComparison={p.onSelectComparison}
            onSelectRace={(id) => {
              const race = p.catalog.find((item) => item.id === id)
              if (race) p.onSelectRace(race)
            }}
            currentRaceId={p.replay.id}
            replayRaceIds={p.catalog.map((race) => race.id)}
            onOpenReplay={p.onOpenAnalysisReplay}
            onClose={() => p.onViewChange('replay')}
          />
        </Suspense>
      )}
      {p.activeView === 'compare' && (
        <div className="dashboard-secondary-layout">
          <section className="dashboard-workspace compare-workspace" aria-label="Compare boats">
            <div className="compare-introduction">
              <div>
                <p className="workspace-kicker">Boat comparison</p>
                <h2>Side by side.</h2>
                <p>Two boats. One moment on the course.</p>
              </div>
              <BoatVisibilityFilter
                boats={p.replay.competitors}
                visibleId={p.visibleBoatId}
                onChange={p.onVisibleBoatChange}
              />
            </div>
            <ComparisonPanel
              replay={p.replay}
              frame={p.frame}
              primary={primary}
              secondaryId={p.comparisonId}
              onSecondary={p.onSelectComparison}
              onPrimary={p.onSelectBoat}
            />
            {timeline}
            {telemetry}
            <p className="comparison-context">
              Values follow the shared playhead. Open Analysis for exported race and leg aggregates.
            </p>
            <TacticalInsightsPanel
              detail={p.analysisDetail}
              raceId={p.replay.id}
              playhead={p.frame.timestamp}
              embedded
            />
          </section>
        </div>
      )}
      {p.activeView === 'reports' && (
        <Suspense
          fallback={
            <section className="dashboard-workspace">
              <p>Loading reports…</p>
            </section>
          }
        >
          <ReportsWorkspace
            replay={p.replay}
            analysisDetail={p.analysisDetail}
            catalog={p.catalog}
            onOpenRace={(race, view) => {
              p.onSelectRace(race)
              chooseView(view.toLowerCase())
            }}
          />
        </Suspense>
      )}
      {settingsOpen && (
        <div
          className="modal-shade"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setSettingsOpen(false)
          }}
        >
          <section
            ref={settingsDialog}
            role="dialog"
            aria-modal="true"
            aria-label="Dashboard settings"
            className="dashboard-settings dashboard-workspace"
          >
            <div className="workspace-heading">
              <h2>Dashboard settings</h2>
              <button autoFocus aria-label="Close settings" onClick={() => setSettingsOpen(false)}>
                ×
              </button>
            </div>
            <label>
              Map source{' '}
              <select
                aria-label="Map source"
                value={p.viewMode}
                onChange={(event) => p.onViewModeChange(event.target.value as ViewMode)}
              >
                <option value="map">OpenStreetMap</option>
                <option value="grid">Offline Grid</option>
              </select>
            </label>
            <label>
              Orientation{' '}
              <select
                aria-label="Orientation"
                value={p.cameraMode}
                onChange={(event) => p.onCameraModeChange(event.target.value as CameraMode)}
              >
                <option value="north">North up</option>
                <option value="course">Course up</option>
              </select>
            </label>
            <label>
              Boat display{' '}
              <select
                aria-label="Boat display"
                value={p.scaleMode}
                onChange={(event) => p.onScaleModeChange(event.target.value as BoatScaleMode)}
              >
                <option value="true">True metric scale</option>
                <option value="enhanced">Enhanced visibility</option>
              </select>
            </label>
            <label>
              Trail length{' '}
              <select
                aria-label="Trail length"
                value={p.trailLength}
                onChange={(event) => p.onTrailLengthChange(event.target.value as TrailLength)}
              >
                {['off', '10s', '30s', '60s', 'leg', 'race'].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Trail colour{' '}
              <select
                aria-label="Trail colour"
                value={p.trailColor}
                onChange={(event) => p.onTrailColorChange(event.target.value as TrailColor)}
              >
                {['team', 'speed', 'vmg'].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <input
                type="checkbox"
                checked={p.showSafetyBorders}
                onChange={p.onToggleSafetyBorders}
              />{' '}
              Show virtual safety borders
            </label>
            <p>
              Space plays or pauses; arrow keys seek 5 seconds; keys 1–4 select the main tabs. Notes
              are saved locally for each race.
            </p>
          </section>
        </div>
      )}
    </div>
  )
}
