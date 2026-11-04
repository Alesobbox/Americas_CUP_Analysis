import { evidenceText } from '../../utils/evidenceText'
import { useMemo, useState } from 'react'
import type { AnalysisEvent } from '../../types/analysis'
import type { PlaybackSpeed, ReplayFrame, ReplayManifest } from '../../types/replay'

export type DashboardEvent = AnalysisEvent

export function eventType(type: string): string {
  return type.toLowerCase().replace(/[\s-]+/g, '_')
}

export function eventColor(type: string): string {
  const normalized = eventType(type)
  if (normalized === 'gun' || normalized === 'start') return '#a855f7'
  if (normalized === 'finish') return '#f59e0b'
  if (normalized === 'gate' || normalized === 'mark') return '#0284c7'
  if (normalized === 'wind_shift') return '#38bdf8'
  if (normalized === 'tack' || normalized === 'gybe') return '#22c55e'
  return '#64748b'
}

export type TimelineFilter = 'marks' | 'all' | 'maneuvers' | 'wind_shifts'

export const TIMELINE_FILTER_TABS: Array<{ key: TimelineFilter; label: string }> = [
  { key: 'marks', label: 'Marks Only' },
  { key: 'all', label: 'All Events' },
  { key: 'maneuvers', label: 'Tacks / Gybes' },
  { key: 'wind_shifts', label: 'Wind Shifts' },
]

export interface RaceTimelinePanelProps {
  replay: ReplayManifest
  frame: ReplayFrame
  playing: boolean
  speed: PlaybackSpeed
  onToggle: () => void
  onSeek: (time: number) => void
  onStep: (seconds: number) => void
  onSpeed: (speed: PlaybackSpeed) => void
  selectedId: string | null
  events?: AnalysisEvent[]
  initialFilter?: TimelineFilter
  onFilterChange?: (filter: TimelineFilter) => void
}

export interface TimelineEventItem {
  id: string
  label: string
  timeRight: string
  timestamp: number
  color: string
  type: string
  source: string
  quality: string
}

function formatSignedCountdown(deltaMs: number): string {
  const sign = deltaMs >= 0 ? '+' : '−'
  const absSec = Math.floor(Math.abs(deltaMs) / 1000)
  const mm = Math.floor(absSec / 60)
  const ss = absSec % 60
  return `${sign}${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

export function RaceTimelinePanel({
  replay,
  frame,
  playing,
  speed,
  onToggle,
  onSeek,
  onStep,
  onSpeed,
  selectedId: _selectedId,
  events: sourceEvents,
  initialFilter,
  onFilterChange,
}: RaceTimelinePanelProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [activeFilter, setActiveFilter] = useState<TimelineFilter>(initialFilter ?? 'marks')

  const { chronology } = replay
  const totalWindowDuration = Math.max(1, chronology.window_end - chronology.window_start)
  const elapsedWindowSec = Math.max(
    0,
    Math.round((frame.timestamp - chronology.window_start) / 1000),
  )
  const totalWindowSec = Math.round(totalWindowDuration / 1000)
  const deltaGunMs = frame.timestamp - chronology.gun_time

  // Countdown string: e.g. -02:46
  const countdownStr = formatSignedCountdown(deltaGunMs)

  const timelineEvents = useMemo<TimelineEventItem[]>(() => {
    const seen = new Set<string>()
    return (sourceEvents ?? [])
      .filter((event) => {
        if (seen.has(event.id) || !Number.isFinite(event.timestamp_ms)) return false
        seen.add(event.id)
        return (event.timestamp_ms as number) >= chronology.window_start &&
          (event.timestamp_ms as number) <= Math.min(frame.timestamp, chronology.window_end)
      })
      .map((event) => ({
        id: event.id,
        label: evidenceText(event.label),
        timeRight: formatSignedCountdown((event.timestamp_ms as number) - chronology.gun_time),
        timestamp: event.timestamp_ms as number,
        color: eventColor(event.type),
        type: eventType(event.type),
        source: evidenceText(event.source),
        quality: evidenceText(event.quality),
      }))
      .sort((a, b) => a.timestamp - b.timestamp)
  }, [sourceEvents, chronology.window_start, chronology.window_end, chronology.gun_time, frame.timestamp])

  const displayedEvents = useMemo(() => {
    if (activeFilter === 'marks') {
      return timelineEvents.filter((e) => ['gun', 'mark', 'gate', 'start', 'finish'].includes(e.type))
    }
    if (activeFilter === 'maneuvers') {
      return timelineEvents.filter((e) => ['tack', 'gybe', 'cross', 'manoeuvre', 'maneuver'].includes(e.type))
    }
    if (activeFilter === 'wind_shifts') {
      return timelineEvents.filter((e) => e.type === 'wind_shift')
    }
    return timelineEvents
  }, [activeFilter, timelineEvents])

  // Scrubber progress calculation (0 to 100%)
  const progressPct = Math.max(
    0,
    Math.min(
      100,
      ((frame.timestamp - chronology.window_start) / totalWindowDuration) * 100,
    ),
  )

  const handleScrubberClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    const target = chronology.window_start + frac * totalWindowDuration
    onSeek(Math.round(target))
  }

  const speedOptions: PlaybackSpeed[] = [0.5, 1, 2, 4]

  return (
    <aside className="race-timeline-panel-card" aria-label="Race timeline">
      {/* Header with collapse chevron */}
      <div className="card-header timeline-header">
        <strong className="panel-title">Race timeline</strong>
        <button
          type="button"
          className="collapse-btn"
          onClick={() => setCollapsed((v) => !v)}
          title={collapsed ? 'Expand panel' : 'Collapse panel'}
        >
          {collapsed ? '⌄' : '⌃'}
        </button>
      </div>

      {!collapsed && (
        <div className="timeline-panel-body">
          {/* Prominent Countdown Display */}
          <div className="countdown-display-block">
            <span className="countdown-sub-title">{deltaGunMs < 0 ? 'TIME TO START' : 'ELAPSED FROM GUN'}</span>
            <strong className="countdown-main-digits">{countdownStr}</strong>
            <span className="countdown-seconds-sub">
              {elapsedWindowSec}s / {totalWindowSec}s
            </span>
          </div>

          {/* Transport Controls (-5s, Circular Play/Pause, +5s) */}
          <div className="transport-controls-row">
            <button
              type="button"
              className="transport-step-btn"
              onClick={() => onStep(-5)}
              title="Step backward 5 seconds"
            >
              −5s
            </button>

            <button
              type="button"
              className={`transport-play-circle-btn ${playing ? 'playing' : 'paused'}`}
              onClick={onToggle}
              title={playing ? 'Pause replay (Space)' : 'Play replay (Space)'}
            >
              {playing ? (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                  <rect x="2" y="1" width="3.5" height="12" rx="1" />
                  <rect x="8.5" y="1" width="3.5" height="12" rx="1" />
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                  <path d="M3.5 1.5L12 7L3.5 12.5V1.5Z" />
                </svg>
              )}
            </button>

            <button
              type="button"
              className="transport-step-btn"
              onClick={() => onStep(5)}
              title="Step forward 5 seconds"
            >
              +5s
            </button>
          </div>

          {/* Playback Speed Segmented Chips */}
          <div className="speed-chips-row" role="radiogroup" aria-label="Playback Speed">
            {speedOptions.map((s) => (
              <button
                key={s}
                type="button"
                className={`speed-chip-btn ${speed === s ? 'active' : ''}`}
                onClick={() => onSpeed(s)}
                aria-checked={speed === s}
                role="radio"
              >
                {s}x
              </button>
            ))}
          </div>

          {/* Timeline Scrubber Track with Event Tick Markers */}
          <div
            className="timeline-scrubber-track-wrap"
            role="slider"
            tabIndex={0}
            aria-label="Race playhead"
            aria-valuemin={chronology.window_start}
            aria-valuemax={chronology.window_end}
            aria-valuenow={Math.round(frame.timestamp)}
            onKeyDown={(event) => {
              if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
                event.preventDefault(); event.stopPropagation()
                onSeek(event.key === 'Home' ? chronology.window_start : event.key === 'End' ? chronology.window_end : frame.timestamp + (event.key === 'ArrowRight' ? 5000 : -5000))
              }
            }}
            onClick={handleScrubberClick}
            title="Click to seek along timeline"
          >
            <div className="scrubber-base-track">
              <div
                className="scrubber-fill-bar"
                style={{ width: `${progressPct}%` }}
              />
              {/* Event Ticks synchronized with displayedEvents */}
              {displayedEvents.map((evt) => {
                const tickFrac = Math.max(
                  0,
                  Math.min(
                    1,
                    (evt.timestamp - chronology.window_start) / totalWindowDuration,
                  ),
                )
                return (
                  <span
                    key={`tick-${evt.id}`}
                    className="scrubber-tick-dot"
                    style={{
                      left: `${tickFrac * 100}%`,
                      backgroundColor: evt.color,
                    }}
                    title={`${evt.label} (${evt.timeRight})`}
                  />
                )
              })}
              <div
                className="scrubber-handle-thumb"
                style={{ left: `${progressPct}%` }}
              />
            </div>
          </div>

          <details className="timeline-event-disclosure"><summary>{sourceEvents ? 'Events reached' : 'Event feed unavailable'} <span>{sourceEvents ? timelineEvents.length : '—'}</span><span aria-hidden="true">⌄</span></summary>
          {/* 4-Tab Filter Bar */}
          <div
            className="timeline-filter-strip"
            role="tablist"
            aria-label="Filter timeline events"
          >
            {TIMELINE_FILTER_TABS.map((tab) => {
              const isSelected = activeFilter === tab.key
              return (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  id={`timeline-tab-${tab.key}`}
                  aria-selected={isSelected}
                  className={`timeline-filter-chip ${isSelected ? 'active' : ''}`}
                  onClick={() => {
                    setActiveFilter(tab.key)
                    onFilterChange?.(tab.key)
                  }}
                >
                  {tab.label}
                </button>
              )
            })}
          </div>

          {/* Event Timeline List */}
          <div className="timeline-events-list">
            {displayedEvents.length === 0 ? (
              <div className="timeline-empty-message">{sourceEvents ? 'No sourced events for this filter' : 'Event feed unavailable for this race'}</div>
            ) : (
              displayedEvents.map((evt) => {
              const isNearby = Math.abs(frame.timestamp - evt.timestamp) < 4000
              return (
                <div
                  key={evt.id}
                  className={`timeline-event-item ${isNearby ? 'active' : ''}`}
                  onClick={() => onSeek(evt.timestamp)}
                   title={`${evt.label} · ${evt.quality} · ${evt.source}`}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onSeek(evt.timestamp)
                    }
                  }}
                >
                  <div className="event-item-left">
                    <span
                      className="event-color-dot"
                      style={{ backgroundColor: evt.color }}
                    />
                    <span className="event-label-text">{evt.label}</span>
                  </div>
                  <span className="event-time-right">{evt.timeRight}</span>
                </div>
              )
            }))}
          </div>

          {/* Bottom Filter events button */}
          <div className="timeline-bottom-action">
            <button
              type="button"
              className="filter-events-outline-btn"
              onClick={() => {
                const next: TimelineFilter = activeFilter === 'marks' ? 'all' : 'marks'
                setActiveFilter(next)
                onFilterChange?.(next)
              }}
              title={activeFilter === 'marks' ? 'Show all events' : 'Filter to marks only'}
            >
              {activeFilter === 'marks' ? 'Show all events' : 'Filter to marks only'}
            </button>
          </div>
          </details>
        </div>
      )}
    </aside>
  )
}
