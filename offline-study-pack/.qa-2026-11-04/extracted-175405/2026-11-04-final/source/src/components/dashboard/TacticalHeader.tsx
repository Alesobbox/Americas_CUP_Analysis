import { useEffect, useMemo, useRef, useState } from 'react'
import type { RaceListing } from '../../engine/catalog'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { windAt } from '../../engine/analytics'
import { environmentalReading, loadRaceEnvironment } from '../../engine/environment'
import type { RaceEnvironment } from '../../engine/environment'

interface TacticalHeaderProps {
  replay: ReplayManifest; frame?: ReplayFrame; currentRace: RaceListing | null; catalog: RaceListing[]
  activeNav: string; onSelectNav: (nav: string) => void; onSelectRace: (race: RaceListing) => void
  onOpenPicker: () => void; onOpenSettings: () => void
}
const navigation = ['Replay', 'Analysis', 'Compare', 'Reports', 'Forecast']
export function TacticalHeader({ replay, frame, currentRace, catalog, activeNav, onSelectNav, onSelectRace, onOpenPicker, onOpenSettings }: TacticalHeaderProps) {
  const [raceDropdownOpen, setRaceDropdownOpen] = useState(false)
  const raceButton = useRef<HTMLButtonElement>(null)
  const [environmentResult, setEnvironmentResult] = useState<{ raceId: string; data: RaceEnvironment | null; error: string | null } | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    void loadRaceEnvironment(replay.id, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setEnvironmentResult({ raceId: replay.id, data, error: null }) })
      .catch((error: unknown) => { if (!controller.signal.aborted) setEnvironmentResult({ raceId: replay.id, data: null, error: error instanceof Error ? error.message : 'Historical environmental data could not be loaded.' }) })
    return () => controller.abort()
  }, [replay.id])
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape' && raceDropdownOpen) { setRaceDropdownOpen(false); raceButton.current?.focus() } }
    const outside = (event: PointerEvent) => { if (!(event.target instanceof Element) || !event.target.closest('.header-dropdown-container')) setRaceDropdownOpen(false) }
    window.addEventListener('keydown', close); window.addEventListener('pointerdown', outside)
    return () => { window.removeEventListener('keydown', close); window.removeEventListener('pointerdown', outside) }
  }, [raceDropdownOpen])
  useEffect(() => { setRaceDropdownOpen(false) }, [activeNav, replay.id])
  const currentTs = frame?.timestamp ?? replay.chronology.window_start
  const wind = useMemo(() => windAt(replay, currentTs), [replay, currentTs])
  const environment = environmentResult?.raceId === replay.id ? environmentResult : null
  const readings = [
    { label: 'Sea', ...environmentalReading(environment?.data ?? null, 'wave_height_m', currentTs, environment?.error) },
    { label: 'Air', ...environmentalReading(environment?.data ?? null, 'air_temperature_c', currentTs, environment?.error) },
    { label: 'Water', ...environmentalReading(environment?.data ?? null, 'water_temperature_c', currentTs, environment?.error) },
  ]
  const venue = /cagliari/i.test(`${currentRace?.regattaName} ${replay.venue}`) ? 'Cagliari' : /naples/i.test(`${currentRace?.regattaName} ${replay.venue}`) ? 'Naples' : replay.venue
  const date = new Date(`${replay.date}T12:00:00Z`)
  const dateLabel = Number.isFinite(date.getTime()) ? date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }) : replay.date
  const raceName = currentRace?.name ?? replay.name
  const quickLabel = raceName.match(/Race\s+(\d+)/i)?.[0] ?? raceName
  const phase = currentTs < replay.chronology.gun_time ? 'Pre-start' : currentTs >= replay.chronology.window_end ? 'Replay end' : 'Racing'
  const handleExport = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(replay)], { type: 'application/json' }))
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${replay.id}_telemetry_export.json`; anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <header className="tactical-header-container" role="banner">
    <div className="main-header-bar">
      <a className="header-left-brand" href="?view=replay" onClick={(event) => { event.preventDefault(); onSelectNav('replay') }} aria-label="America's Cup race replay">
        <svg className="cup-trophy-mark" width="25" height="32" viewBox="0 0 24 36" aria-hidden="true"><path d="M12 2c-1.5 0-2.5.8-2.5 2 0 1.2.7 2 1.5 2.5V9c-3 .5-6 3-6 7 0 5 3.5 8 5.5 9.5V29H8v3h9v-3h-3.5v-3.5C15.5 24 19 21 19 16c0-4-3-6.5-6-7V6.5c.8-.5 1.5-1.3 1.5-2.5S13.5 2 12 2Z" fill="currentColor"/><path d="M6 13c-2 .5-3.5 2.5-3.5 5 0 2.8 2 4.5 4 4.8M6.5 34h11" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
        <span className="brand-text-block"><span className="brand-cup-title">America’s Cup</span><span className="brand-replay-subtitle">Race replay</span></span>
      </a>
      <nav className="header-center-nav" aria-label="Main Navigation">{navigation.map((label) => <button key={label} type="button" className={`nav-tab-link ${activeNav === label.toLowerCase() ? 'active' : ''}`} aria-current={activeNav === label.toLowerCase() ? 'page' : undefined} onClick={() => onSelectNav(label.toLowerCase())}>{label}</button>)}</nav>
      <div className="header-right-actions"><button className="race-library-trigger" onClick={onOpenPicker}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg><span>Race library</span></button><button className="hdr-gear-btn" onClick={onOpenSettings} title="Configure settings & race parameters" aria-label="Settings"><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="m9 3-.8 2.4-2.5.5-1.5 2.6 1.2 2.1v2.8l-1.2 2.1 1.5 2.6 2.5.5L9 21h6l.8-2.4 2.5-.5 1.5-2.6-1.2-2.1v-2.8l1.2-2.1-1.5-2.6-2.5-.5L15 3Z"/><circle cx="12" cy="12" r="3"/></svg></button></div>
    </div>
    <div className="race-context-row"><div className="race-context-title"><p className="race-context-meta">{venue}<span> / </span>{replay.boat_class ?? 'AC40'}<span> / </span>{dateLabel}</p><h1>{raceName}</h1></div><div className="race-context-actions"><span className="race-phase"><i aria-hidden="true" />{phase}</span><div className="header-dropdown-container"><button ref={raceButton} className="hdr-pill-dropdown-btn" onClick={() => setRaceDropdownOpen((open) => !open)} aria-expanded={raceDropdownOpen} aria-controls="quick-race-list">{quickLabel}<span aria-hidden="true">⌄</span></button>{raceDropdownOpen && <div id="quick-race-list" className="hdr-dropdown-popover"><div className="popover-header">{catalog.length} races in the archive</div><div className="popover-list">{catalog.map((race) => <button key={race.id} className={`popover-item ${race.id === replay.id ? 'active' : ''}`} onClick={() => { onSelectRace(race); setRaceDropdownOpen(false) }}><strong>{race.name}</strong><small>{race.venue} · {race.date}</small></button>)}</div><button className="popover-footer-btn" onClick={() => { setRaceDropdownOpen(false); onOpenPicker() }} aria-label="FULL RACE ARCHIVE...">Browse all races ↗</button></div>}</div><button className="header-export-link" onClick={handleExport} title="Export race telemetry as JSON">Export <span aria-hidden="true">↓</span></button></div></div>
    <div className="environmental-substrip"><span className="recorded-wind"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M3 8h11a3 3 0 1 0-3-3M2 13h16a3 3 0 1 1-3 3M5 18h5"/></svg>Recorded wind <strong>{Number.isFinite(wind.tws) ? `${wind.tws.toFixed(1)} kt` : 'Unavailable'}</strong><span>{Number.isFinite(wind.twd) ? `${Math.round(wind.twd)}° T` : 'Direction unavailable'}</span></span><details className="conditions-disclosure"><summary>Conditions <span aria-hidden="true">⌄</span></summary><div className="conditions-popover"><p className="conditions-title">Historical model estimates</p>{readings.map((reading) => <div className="env-weather-badge" key={reading.label}><span title={reading.title} aria-label={`${reading.label} ${reading.text}${reading.modeled ? ', historical model estimate' : ''}`}>{reading.label} {reading.text}</span></div>)}{environment?.data && Object.keys(environment.data.sources).length > 0 && <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo model</a>}<p>Separate from recorded boat telemetry and forecast inputs.</p></div></details></div>
  </header>
}
