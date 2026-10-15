import { useEffect, useMemo, useState } from 'react'
import type { RaceListing } from '../../engine/catalog'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { windAt } from '../../engine/analytics'

interface TacticalHeaderProps {
  replay: ReplayManifest
  frame?: ReplayFrame
  currentRace: RaceListing | null
  catalog: RaceListing[]
  activeNav: string
  onSelectNav: (nav: string) => void
  onSelectRace: (race: RaceListing) => void
  visibleBoats: string
  onVisibleBoatsChange: (val: string) => void
  onOpenPicker: () => void
  onOpenSettings: () => void
}

function formatTimeToStart(deltaMs: number): string {
  if (deltaMs <= 0) return '00:00'
  const absSec = Math.floor(deltaMs / 1000)
  const mm = Math.floor(absSec / 60)
  const ss = absSec % 60
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

export function TacticalHeader({
  replay,
  frame,
  currentRace,
  catalog,
  activeNav,
  onSelectNav,
  onSelectRace,
  visibleBoats,
  onVisibleBoatsChange,
  onOpenPicker,
  onOpenSettings,
}: TacticalHeaderProps) {
  const [raceDropdownOpen, setRaceDropdownOpen] = useState(false)
  const [boatsDropdownOpen, setBoatsDropdownOpen] = useState(false)
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setRaceDropdownOpen(false); setBoatsDropdownOpen(false) }
    }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [])

  const navItems = [
    { id: 'replay', label: 'Replay' },
    { id: 'analysis', label: 'Analysis' },
    { id: 'compare', label: 'Compare' },
    { id: 'reports', label: 'Reports' },
  ]

  const raceDisplayLabel = useMemo(() => {
    if (currentRace) {
      const match = currentRace.name.match(/Race\s+(\d+)/i)
      if (match) return `Race ${match[1]}`
      return currentRace.name
    }
    const match = replay.name.match(/Race\s+(\d+)/i)
    if (match) return `Race ${match[1]}`
    return replay.name
  }, [currentRace, replay.name])

  const venueCity = useMemo(() => {
    const raw = `${currentRace?.regattaName ?? ''} ${replay.venue ?? ''}`.toLowerCase()
    if (raw.includes('cagliari')) return 'Cagliari'
    if (raw.includes('naples')) return 'Naples'
    return replay.venue.split(',')[0].trim()
  }, [currentRace?.regattaName, replay.venue])

  const regattaFullTitle = useMemo(() => {
    return `${replay.boat_class ?? 'AC40'} Preliminary Regatta · ${venueCity} ${replay.date.slice(0, 4)}`
  }, [replay.boat_class, replay.date, venueCity])

  const regattaSubtitle = useMemo(() => {
    const dateFormatted = replay.date || 'Date unavailable'
    return `${raceDisplayLabel} · ${replay.venue} · ${dateFormatted}`
  }, [raceDisplayLabel, replay.date, replay.venue])

  // Environmental conditions
  const currentTs = frame?.timestamp ?? replay.chronology.window_start
  const wind = useMemo(() => windAt(replay, currentTs), [replay, currentTs])
  const deltaGunMs = replay.chronology.gun_time - currentTs
  const isPreStart = deltaGunMs > 0
  const timeToStartStr = isPreStart
    ? `${formatTimeToStart(deltaGunMs)} to start`
    : `+${formatTimeToStart(Math.abs(deltaGunMs))} elapsed`
  const phaseLabel = isPreStart ? 'Pre-start' : 'Racing'

  const locationText = useMemo(() => {
    const vLower = venueCity.toLowerCase()
    if (vLower.includes('cagliari')) return 'Cagliari, Sardinia'
    if (vLower.includes('naples')) return 'Naples, Italy'
    return `${venueCity}, Italy`
  }, [venueCity])

  const handleExportClick = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(replay))
    const downloadAnchor = document.createElement('a')
    downloadAnchor.setAttribute('href', dataStr)
    downloadAnchor.setAttribute('download', `${replay.id}_telemetry_export.json`)
    document.body.appendChild(downloadAnchor)
    downloadAnchor.click()
    downloadAnchor.remove()
  }

  return (
    <header className="tactical-header-container" role="banner">
      {/* 1. MAIN HEADER BAR */}
      <div className="main-header-bar">
        {/* Left Section: Brand & Venue */}
        <div className="header-left-brand">
          {/* America's Cup Silver Trophy Mark */}
          <div className="cup-trophy-mark" title="America's Cup" aria-label="America's Cup trophy mark">
            <svg width="22" height="30" viewBox="0 0 24 36" fill="none">
              <path
                d="M12 2C10.5 2 9.5 2.8 9.5 4C9.5 5.2 10.2 6 11 6.5V9C8 9.5 5 12 5 16C5 21 8.5 24 10.5 25.5V29H8C7.4 29 7 29.4 7 30V32H17V30C17 29.4 16.6 29 16 29H13.5V25.5C15.5 24 19 21 19 16C19 12 16 9.5 13 9V6.5C13.8 6 14.5 5.2 14.5 4C14.5 2.8 13.5 2 12 2Z"
                fill="url(#cupSilverGrad)"
              />
              <path
                d="M6 13C4 13.5 2.5 15.5 2.5 18C2.5 20.8 4.5 22.5 6.5 22.8"
                stroke="#64748b"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <rect x="6.5" y="32" width="11" height="2" rx="0.5" fill="#475569" />
              <defs>
                <linearGradient id="cupSilverGrad" x1="5" y1="2" x2="19" y2="34" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#f8fafc" />
                  <stop offset="0.35" stopColor="#cbd5e1" />
                  <stop offset="0.75" stopColor="#64748b" />
                  <stop offset="1" stopColor="#334155" />
                </linearGradient>
              </defs>
            </svg>
          </div>

          {/* America's Cup Title */}
          <div className="brand-text-block">
            <span className="brand-cup-title">AMERICA'S CUP</span>
            <span className="brand-replay-subtitle">AC40 REPLAY</span>
          </div>

          <div className="header-v-divider" aria-hidden="true" />

          {/* Country Flag & Regatta Title */}
          <div className="venue-meta-block">
            <div className="italian-flag-icon" title="Italy">
              <svg width="20" height="14" viewBox="0 0 20 14" fill="none">
                <rect width="6.6" height="14" fill="#009246" />
                <rect x="6.6" width="6.6" height="14" fill="#ffffff" />
                <rect x="13.2" width="6.8" height="14" fill="#ce2b37" />
                <rect x="0.5" y="0.5" width="19" height="13" stroke="rgba(0,0,0,0.12)" strokeWidth="0.8" rx="1" />
              </svg>
            </div>
            <div className="regatta-title-texts">
              <span className="regatta-main-title">{regattaFullTitle}</span>
              <span className="regatta-sub-details">{regattaSubtitle}</span>
            </div>
          </div>
        </div>

        {/* Center Section: Tabs (Replay, Analysis, Compare, Reports) */}
        <nav className="header-center-nav" aria-label="Main Navigation">
          {navItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-tab-link ${activeNav === item.id ? 'active' : ''}`}
              onClick={() => onSelectNav(item.id)}
              aria-current={activeNav === item.id ? 'page' : undefined}
            >
              {item.label}
              {activeNav === item.id && <span className="tab-active-indicator" />}
            </button>
          ))}
        </nav>

        {/* Right Section: Dropdowns, Export, Settings */}
        <div className="header-right-actions">
          {/* Race Dropdown */}
          <div className="header-dropdown-container">
            <button
              type="button"
              className="hdr-pill-dropdown-btn"
              onClick={() => setRaceDropdownOpen((prev) => !prev)}
              aria-expanded={raceDropdownOpen}
            >
              <span>{raceDisplayLabel}</span>
              <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
                <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
            {raceDropdownOpen && (
              <div className="hdr-dropdown-popover">
                <div className="popover-header">RACES ({catalog.length})</div>
                <div className="popover-list">
                  {catalog.map((race) => (
                    <button
                      key={race.id}
                      type="button"
                      className={`popover-item ${race.id === replay.id ? 'active' : ''}`}
                      onClick={() => {
                        onSelectRace(race)
                        setRaceDropdownOpen(false)
                      }}
                    >
                      <strong>{race.name}</strong>
                      <small>{race.regattaName ?? race.venue}</small>
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  className="popover-footer-btn"
                  onClick={() => {
                    setRaceDropdownOpen(false)
                    onOpenPicker()
                  }}
                >
                  FULL RACE ARCHIVE...
                </button>
              </div>
            )}
          </div>

          {/* All Boats Dropdown */}
          <div className="header-dropdown-container">
            <button
              type="button"
              className="hdr-pill-dropdown-btn"
              onClick={() => setBoatsDropdownOpen((prev) => !prev)}
              aria-expanded={boatsDropdownOpen}
            >
              <span>{visibleBoats === 'all' ? 'All Boats' : replay.competitors.find((boat) => boat.id === visibleBoats)?.team_code ?? 'All Boats'}</span>
              <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
                <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
            {boatsDropdownOpen && (
              <div className="hdr-dropdown-popover">
                <button
                  type="button"
                  className={`popover-item ${visibleBoats === 'all' ? 'active' : ''}`}
                  onClick={() => {
                    onVisibleBoatsChange('all')
                    setBoatsDropdownOpen(false)
                  }}
                >
                  <strong>All Boats</strong>
                  <small>({replay.competitors.length} competitors)</small>
                </button>
                {replay.competitors.map((boat) => (
                  <button
                    key={boat.id}
                    type="button"
                    className={`popover-item ${visibleBoats === boat.id ? 'active' : ''}`}
                    onClick={() => {
                      onVisibleBoatsChange(boat.id)
                      setBoatsDropdownOpen(false)
                    }}
                  >
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <i style={{ width: 8, height: 8, borderRadius: 2, background: boat.color, display: 'inline-block' }} />
                      {boat.team_code}
                    </span>
                    <small>{boat.team_name}</small>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Blue Export Button */}
          <button
            type="button"
            className="hdr-export-blue-btn"
            onClick={handleExportClick}
            title="Export race telemetry as JSON"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M21 15V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M7 10L12 15L17 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M12 15V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span>Export</span>
          </button>

          {/* Settings Gear Button */}
          <button
            type="button"
            className="hdr-gear-btn"
            onClick={onOpenSettings}
            title="Configure settings & race parameters"
            aria-label="Settings"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M19.4 15A1.65 1.65 0 0 0 20 16.3A2 2 0 0 1 18 19.7A1.65 1.65 0 0 0 16.6 19.1A1.65 1.65 0 0 0 15 19.4A1.65 1.65 0 0 0 14.7 21A2 2 0 0 1 11.3 21A1.65 1.65 0 0 0 11 19.4A1.65 1.65 0 0 0 9.4 19.1A1.65 1.65 0 0 0 8 19.7A2 2 0 0 1 6 16.3A1.65 1.65 0 0 0 6.6 15A1.65 1.65 0 0 0 6.3 13.4A1.65 1.65 0 0 0 4.7 13.1A2 2 0 0 1 4.7 9.7A1.65 1.65 0 0 0 6.3 9.4A1.65 1.65 0 0 0 6.6 7.8A1.65 1.65 0 0 0 6 6.4A2 2 0 0 1 8 3A1.65 1.65 0 0 0 9.4 3.6A1.65 1.65 0 0 0 11 3.3A1.65 1.65 0 0 0 11.3 1.7A2 2 0 0 1 14.7 1.7A1.65 1.65 0 0 0 15 3.3A1.65 1.65 0 0 0 16.6 3.6A1.65 1.65 0 0 0 18 3A2 2 0 0 1 20 6.4A1.65 1.65 0 0 0 19.4 7.8A1.65 1.65 0 0 0 19.7 9.4A1.65 1.65 0 0 0 21.3 9.7A2 2 0 0 1 21.3 13.1A1.65 1.65 0 0 0 19.7 13.4A1.65 1.65 0 0 0 19.4 15Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* 2. ENVIRONMENTAL CONDITIONS SUB-STRIP */}
      <div className="environmental-substrip">
        {/* Left: Live status dot + Date/phase + Time to start */}
        <div className="env-left-status">
          <span className="env-live-dot" />
          <span className="env-date-phase">{replay.date || 'Date unavailable'} · {phaseLabel}</span>
          <span className="env-v-bar" />
          <strong className="env-countdown-badge">{timeToStartStr}</strong>
        </div>

        {/* Right: Weather Badges */}
        <div className="env-right-badges">
          {/* Wind */}
          <div className="env-weather-badge">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="env-icon">
              <path d="M4 8H15C16.6569 8 18 6.65685 18 5C18 3.34315 16.6569 2 15 2C13.3431 2 12 3.34315 12 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <path d="M2 13H19C20.6569 13 22 14.3431 22 16C22 17.6569 20.6569 19 19 19C17.3431 19 16 17.6569 16 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <span>Wind {Number.isFinite(wind.tws) ? `${wind.tws.toFixed(1)} kt` : 'unavailable'} {Number.isFinite(wind.twd) ? `${Math.round(wind.twd)}° T` : ''}</span>
          </div>

          {/* Sea */}
          <div className="env-weather-badge">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="env-icon">
              <path d="M2 12C5 9 7 9 10 12C13 15 15 15 18 12C21 9 22 10 22 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <path d="M2 17C5 14 7 14 10 17C13 20 15 20 18 17C21 14 22 15 22 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <span title="No sea-state channel in the replay">Sea unavailable</span>
          </div>

          {/* Air */}
          <div className="env-weather-badge">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="env-icon">
              <path d="M14 14.76V3.5C14 2.67 13.33 2 12.5 2C11.67 2 11 2.67 11 3.5V14.76C9.78 15.6 9 17.02 9 18.5C9 20.43 10.57 22 12.5 22C14.43 22 16 20.43 16 18.5C16 17.02 15.22 15.6 14 14.76Z" stroke="currentColor" strokeWidth="1.8" />
            </svg>
            <span title="No air-temperature channel in the replay">Air unavailable</span>
          </div>

          {/* Water */}
          <div className="env-weather-badge">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="env-icon">
              <path d="M12 2.69L6.5 12.6C4.5 16.2 7.1 20.7 11.3 20.9C15.8 21.1 19.3 17.4 18.9 12.9C18.6 9.3 15.5 5.5 12 2.69Z" stroke="currentColor" strokeWidth="1.8" />
            </svg>
            <span title="No water-temperature channel in the replay">Water unavailable</span>
          </div>

          {/* Location */}
          <div className="env-weather-badge location-badge">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" className="env-icon">
              <path d="M21 10C21 17 12 23 12 23C12 23 3 17 3 10C3 5.02944 7.02944 1 12 1C16.9706 1 21 5.02944 21 10Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="12" cy="10" r="3" stroke="currentColor" strokeWidth="2" />
            </svg>
            <span>{locationText}</span>
          </div>
        </div>
      </div>
    </header>
  )
}
