import { useEffect, useMemo, useRef, useState } from 'react'
import { loadAnalysisDetail } from './engine/analysisCatalog'
import { loadCatalog, loadReplay, resolveAnalysisReplay, type RaceListing } from './engine/catalog'
import { ReplayEngine } from './engine/ReplayEngine'
import { RacePickerModal } from './components/modals/RacePickerModal'
import { TacticalDashboard, type DashboardView, type ReviewInterval } from './components/dashboard/TacticalDashboard'
import type { AnalysisDetail } from './types/analysis'
import type { BoatScaleMode, CameraMode, FollowMode, PlaybackSpeed, ReplayFrame, ReplayManifest, TrailColor, TrailLength, TrailScope, ViewMode } from './types/replay'

function initialView(params: URLSearchParams): DashboardView {
  const requested = params.get('view') ?? params.get('tab')
  if (params.get('modal') === 'analysis') return 'analysis'
  if (params.get('modal') === 'summary') return 'reports'
  if (requested === 'duel') return 'compare'
  if (requested === 'start') return 'analysis'
  return requested === 'analysis' || requested === 'compare' || requested === 'reports' || requested === 'forecast' || requested === 'simulator' ? requested : 'replay'
}

function savedViewMode(): ViewMode {
  try { return (window.localStorage.getItem('regatta_view_mode') ?? window.localStorage.getItem('regatta.viewMode')) === 'grid' ? 'grid' : 'map' }
  catch { return 'map' }
}

export default function App() {
  const params = useMemo(() => new URLSearchParams(window.location.search), [])
  const [catalog, setCatalog] = useState<RaceListing[]>([])
  const [currentRace, setCurrentRace] = useState<RaceListing | null>(null)
  const [replay, setReplay] = useState<ReplayManifest | null>(null)
  const [frame, setFrame] = useState<ReplayFrame | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState<PlaybackSpeed>(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [comparisonId, setComparisonId] = useState<string | null>(null)
  const [visibleBoatId, setVisibleBoatId] = useState<string | null>(null)
  const [activeView, setActiveView] = useState<DashboardView>(() => initialView(params))
  const [pickerOpen, setPickerOpen] = useState(params.get('modal') === 'races')
  const [cameraMode, setCameraMode] = useState<CameraMode>('north')
  const [followMode, setFollowMode] = useState<FollowMode>('course')
  const [viewMode, setViewMode] = useState<ViewMode>(savedViewMode)
  const [scaleMode, setScaleMode] = useState<BoatScaleMode>('enhanced')
  const [trailLength, setTrailLength] = useState<TrailLength>('30s')
  const [trailColor, setTrailColor] = useState<TrailColor>('team')
  const [trailScope, setTrailScope] = useState<TrailScope>('all')
  const [showVmgLabels, setShowVmgLabels] = useState(true)
  const [highlightComparison, setHighlightComparison] = useState(false)
  const [showSafetyBorders, setShowSafetyBorders] = useState(false)
  const [resetView, setResetView] = useState(0)
  const [analysisDetail, setAnalysisDetail] = useState<AnalysisDetail | null>(null)
  const [reviewInterval, setReviewInterval] = useState<ReviewInterval | null>(null)
  const loadController = useRef<AbortController | null>(null)
  const initialSeekDone = useRef(false)
  const pendingAnalysisSeek = useRef<{ raceId: string; timestamp: number; boatId?: string; intervalEnd?: number } | null>(null)

  useEffect(() => {
    if (params.has('layout')) {
      const clean = new URL(window.location.href)
      clean.searchParams.delete('layout')
      window.history.replaceState(null, '', clean)
    }
  }, [params])
  useEffect(() => {
    try {
      window.localStorage.setItem('regatta_view_mode', viewMode)
      window.localStorage.setItem('regatta.viewMode', viewMode)
    } catch { /* Storage can be disabled. */ }
  }, [viewMode])
  useEffect(() => {
    const controller = new AbortController()
    loadController.current = controller
    loadCatalog(controller.signal).then(async (races) => {
      if (controller.signal.aborted) return
      setCatalog(races)
      const race = races.find((item) => item.id === params.get('race')) ?? races[0]
      const data = await loadReplay(race, controller.signal)
      if (controller.signal.aborted) return
      setCurrentRace(race)
      setReplay(data)
      const boats = [...data.competitors].sort((a, b) => a.team_code.localeCompare(b.team_code))
      setSelectedId(boats[0]?.id ?? null)
      setComparisonId(boats[1]?.id ?? null)
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Race data could not be loaded')
    })
    return () => controller.abort()
  }, [params])
  useEffect(() => {
    if (!replay) return
    const controller = new AbortController()
    setAnalysisDetail(null)
    loadAnalysisDetail({ id: replay.id, analysis_file: `analysis/${replay.id}.json` }, controller.signal)
      .then((detail) => { if (!controller.signal.aborted) setAnalysisDetail(detail) }).catch(() => {})
    return () => controller.abort()
  }, [replay])

  const engine = useMemo(() => replay ? new ReplayEngine(replay) : null, [replay])
  useEffect(() => { engine?.setSpeed(speed) }, [engine, speed])
  useEffect(() => {
    if (!engine || !replay) return
    if (pendingAnalysisSeek.current?.raceId === replay.id) {
      const pending = pendingAnalysisSeek.current
      engine.seek(pending.timestamp)
      if (pending.boatId && replay.competitors.some((boat) => boat.id === pending.boatId)) setSelectedId(pending.boatId)
      setReviewInterval(pending.boatId && pending.intervalEnd !== undefined && pending.intervalEnd > pending.timestamp
        ? { raceId: replay.id, boatId: pending.boatId, start_ms: pending.timestamp, end_ms: pending.intervalEnd } : null)
      pendingAnalysisSeek.current = null
    } else if (!initialSeekDone.current) {
      initialSeekDone.current = true
      const raw = params.get('t')
      if (raw === 'gun' || raw === 'start') engine.seek(replay.chronology.gun_time)
      else if (raw) {
        const number = Number(raw)
        if (Number.isFinite(number)) engine.seek(number > 1e10 ? number : replay.chronology.gun_time + number * 1000)
      }
    }
    const unsubscribe = engine.subscribe((next) => { setFrame(next); setPlaying(engine.isPlaying()) })
    return () => { unsubscribe(); engine.dispose() }
  }, [engine, replay, params])

  const chooseRace = async (race: RaceListing, preserveAnalysisSeek = false) => {
    if (!preserveAnalysisSeek) pendingAnalysisSeek.current = null
    setPickerOpen(false)
    if (race.id === currentRace?.id) return
    loadController.current?.abort()
    const controller = new AbortController()
    loadController.current = controller
    setError(null); setFrame(null); setReplay(null); setPlaying(false)
    setReviewInterval(null)
    try {
      const data = await loadReplay(race, controller.signal)
      if (controller.signal.aborted) return
      setCurrentRace(race); setReplay(data)
      const boats = [...data.competitors].sort((a, b) => a.team_code.localeCompare(b.team_code))
      setSelectedId(boats[0]?.id ?? null)
      setComparisonId(boats[1]?.id ?? null)
      setVisibleBoatId(null); setHighlightComparison(false)
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Race data could not be loaded')
    }
  }
  const openAnalysisReplay = (raceId: string, timestamp?: number, boatId?: string, intervalEnd?: number) => {
    const target = resolveAnalysisReplay(catalog, currentRace?.id ?? '', raceId, timestamp)
    if (!target) return
    setActiveView('replay')
    engine?.pause(); setPlaying(false)
    if (target.sameRace) {
      if (target.seekTimestamp !== undefined) engine?.seek(target.seekTimestamp)
      if (boatId && replay?.competitors.some((boat) => boat.id === boatId)) { setSelectedId(boatId); if (visibleBoatId) setVisibleBoatId(boatId) }
      setReviewInterval(boatId && target.seekTimestamp !== undefined && Number.isFinite(intervalEnd) && intervalEnd! > target.seekTimestamp
        ? { raceId, boatId, start_ms: target.seekTimestamp, end_ms: intervalEnd! } : null)
    } else {
      pendingAnalysisSeek.current = target.seekTimestamp === undefined ? null : { raceId, timestamp: target.seekTimestamp, boatId, intervalEnd }
      void chooseRace(target.race, true)
    }
  }
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement
      if (event.defaultPrevented || target.closest('input,select,textarea,button,a,[role="button"],[role="slider"],[role="dialog"]') || target.isContentEditable) return
      if (document.querySelector('[role="dialog"][aria-modal="true"]')) return
      if (event.key === 'Escape') setPickerOpen(false)
      else if (event.key === ' ' && engine) {
        event.preventDefault()
        if (!engine.isPlaying() && replay && engine.getTime() >= replay.chronology.window_end) engine.seek(replay.chronology.window_start)
        engine.toggle(); setPlaying(engine.isPlaying())
      } else if (event.key === 'ArrowLeft' && engine) engine.seekBy(-5)
      else if (event.key === 'ArrowRight' && engine) engine.seekBy(5)
      else if (event.key === '1') setActiveView('replay')
      else if (event.key === '2') setActiveView('analysis')
      else if (event.key === '3') setActiveView('compare')
      else if (event.key === '4') setActiveView('reports')
      else if (event.key === '5') setActiveView('forecast')
      else if (event.key === '6') setActiveView('simulator')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [engine, replay])

  if (error) return <main className="screen-message"><p>DATA LOAD ERROR</p><strong>{error}</strong><button onClick={() => window.location.reload()}>Retry</button></main>
  if (!replay || !frame || !engine) return <main className="screen-message"><p>AC40 TACTICAL REPLAY</p><strong>Loading race telemetry…</strong></main>
  const selected = replay.competitors.find((boat) => boat.id === selectedId) ?? replay.competitors[0]
  return <main className="app-shell">
    <TacticalDashboard
      replay={replay} frame={frame} catalog={catalog} currentRace={currentRace}
      activeView={activeView} onViewChange={setActiveView}
      playing={playing} speed={speed}
      onToggle={() => { if (!engine.isPlaying() && engine.getTime() >= replay.chronology.window_end) engine.seek(replay.chronology.window_start); engine.toggle(); setPlaying(engine.isPlaying()) }}
      onSeek={(time) => engine.seek(time)} onStep={(seconds) => engine.seekBy(seconds)}
      onSpeed={(value) => { engine.setSpeed(value); setSpeed(value) }}
      selectedId={selected.id} onSelectBoat={(id) => { setSelectedId(id); if (visibleBoatId) setVisibleBoatId(id) }}
      comparisonId={comparisonId} onSelectComparison={(id) => { setComparisonId(id); setHighlightComparison(true) }}
      visibleBoatId={visibleBoatId}
      onVisibleBoatChange={(id) => { setVisibleBoatId(id); if (id) setSelectedId(id) }}
      cameraMode={cameraMode} onCameraModeChange={setCameraMode}
      followMode={followMode} onFollowModeChange={setFollowMode}
      viewMode={viewMode} onViewModeChange={setViewMode}
      scaleMode={scaleMode} onScaleModeChange={setScaleMode}
      showSafetyBorders={showSafetyBorders} onToggleSafetyBorders={() => setShowSafetyBorders((value) => !value)}
      trailLength={trailLength} onTrailLengthChange={setTrailLength}
      trailColor={trailColor} onTrailColorChange={setTrailColor}
      trailScope={trailScope} onTrailScopeChange={setTrailScope}
      showVmgLabels={showVmgLabels} onShowVmgLabelsChange={setShowVmgLabels}
      highlightComparison={highlightComparison} onHighlightComparisonChange={setHighlightComparison}
      resetView={resetView} onResetView={() => setResetView((value) => value + 1)}
      onSelectRace={chooseRace} onOpenPicker={() => setPickerOpen(true)}
      analysisDetail={analysisDetail} onOpenAnalysisReplay={openAnalysisReplay}
      reviewInterval={reviewInterval} onClearReview={() => setReviewInterval(null)}
    />
    {pickerOpen && <RacePickerModal races={catalog} currentId={replay.id} onSelect={chooseRace} onClose={() => setPickerOpen(false)} />}
  </main>
}
