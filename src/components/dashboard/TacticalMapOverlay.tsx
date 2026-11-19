import { windAt } from '../../engine/analytics'
import type { AnalysisEvent } from '../../types/analysis'
import type { FollowMode, ReplayFrame, ReplayManifest, ViewMode } from '../../types/replay'

export interface TacticalMapOverlayProps {
  replay: ReplayManifest
  frame: ReplayFrame
  viewMode: ViewMode
  onViewModeChange: (mode: ViewMode) => void
  followMode: FollowMode
  onFollowModeChange: (mode: FollowMode) => void
  showSafetyBorders: boolean
  onToggleSafetyBorders: () => void
  onResetView: () => void
  onZoomIn: () => void
  onZoomOut: () => void
  onToggleFullscreen?: () => void
  selectedBoatId?: string | null
  controlsOutside?: boolean
  events?: AnalysisEvent[]
}

export function TacticalMapControls({
  viewMode,
  onViewModeChange,
  followMode,
  onFollowModeChange,
  showSafetyBorders,
  onToggleSafetyBorders,
  onResetView,
  onZoomIn,
  onZoomOut,
  onToggleFullscreen,
  selectedBoatId,
}: TacticalMapOverlayProps) {
  return (
    <div className="map-top-right-toolbar" role="toolbar" aria-label="Tactical map action toolbar">
      {/* 1. View Mode: Map vs Grid */}
      <div className="map-toolbar-group" aria-label="View mode toggle">
        <div className="map-segmented-toggle">
          <button
            type="button"
            className={viewMode === 'map' ? 'active' : ''}
            onClick={() => onViewModeChange('map')}
            title="OpenStreetMap view"
            aria-label="OpenStreetMap view"
          >
            Map
          </button>
          <button
            type="button"
            className={viewMode === 'grid' ? 'active' : ''}
            onClick={() => onViewModeChange('grid')}
            title="Technical 2D Metric Grid"
            aria-label="Technical 2D metric grid view"
          >
            Grid
          </button>
        </div>
      </div>

      <div className="map-toolbar-v-divider" />

      {/* 2. Follow Mode: Course, Fleet, Boat */}
      <div className="map-toolbar-group" aria-label="Camera follow mode">
        <div className="map-segmented-toggle">
          <button
            type="button"
            className={followMode === 'course' ? 'active' : ''}
            onClick={() => onFollowModeChange('course')}
            title="Fit Full Racecourse"
            aria-label="Fit full racecourse"
          >
            Course
          </button>
          <button
            type="button"
            className={followMode === 'fleet' ? 'active' : ''}
            onClick={() => onFollowModeChange('fleet')}
            title="Auto-track Fleet"
            aria-label="Auto-track fleet"
          >
            Fleet
          </button>
          <button
            type="button"
            className={followMode === 'boat' ? 'active' : ''}
            onClick={() => onFollowModeChange('boat')}
            disabled={!selectedBoatId}
            title={selectedBoatId ? 'Follow Selected Boat' : 'Select a boat first to follow'}
            aria-label="Follow selected boat"
          >
            Boat
          </button>
        </div>
      </div>

      <div className="map-toolbar-v-divider" />

      {/* 3. Safety Borders Toggle */}
      <button
        type="button"
        className={`map-tool-toggle-btn${showSafetyBorders ? ' active' : ''}`}
        onClick={onToggleSafetyBorders}
        title="Toggle Platform and Keep Clear Safety Borders"
        aria-label="Toggle safety borders"
        aria-pressed={showSafetyBorders}
      >
        <span className="tool-indicator-dot" />
        <span>Borders</span>
      </button>

      <div className="map-toolbar-v-divider" />

      {/* 4. Camera Reset, Zoom In, Zoom Out, Fullscreen */}
      <div className="map-tool-icon-group" aria-label="Camera and viewport tools">
        <button
          type="button"
          className="map-tool-icon-btn"
          onClick={onResetView}
          title="Reset View (fit course)"
          aria-label="Reset view"
        >
          ⟲
        </button>
        <button
          type="button"
          className="map-tool-icon-btn"
          onClick={onZoomIn}
          title="Zoom In"
          aria-label="Zoom in"
        >
          +
        </button>
        <button
          type="button"
          className="map-tool-icon-btn"
          onClick={onZoomOut}
          title="Zoom Out"
          aria-label="Zoom out"
        >
          −
        </button>
        <button
          type="button"
          className="map-tool-icon-btn"
          onClick={onToggleFullscreen}
          title="Toggle Fullscreen"
          aria-label="Toggle fullscreen"
        >
          ⛶
        </button>
      </div>
    </div>
  )
}

export function TacticalMapOverlay({
  replay,
  frame,
  viewMode,
  onViewModeChange,
  followMode,
  onFollowModeChange,
  showSafetyBorders,
  onToggleSafetyBorders,
  onResetView,
  onZoomIn,
  onZoomOut,
  onToggleFullscreen,
  selectedBoatId,
  events,
  controlsOutside = false,
}: TacticalMapOverlayProps) {
  const wind = windAt(replay, frame.timestamp)
  const activeShift = events
    ?.filter(
      (event) =>
        event.type === 'wind_shift' &&
        event.timestamp_ms <= frame.timestamp &&
        frame.timestamp - event.timestamp_ms <= 30000
    )
    .at(-1)

  return (
    <div className="tactical-map-overlay" aria-hidden="false">
      {/* Top Left: Compass Rose and recorded wind */}
      <div className="map-top-left-hud">
        {/* Circular Compass Rose */}
        <div className="compass-rose-widget" title={`Course North / TWD ${Math.round(wind.twd)}°`}>
          <svg width="44" height="44" viewBox="0 0 50 50">
            {/* Dark glass circular backing */}
            <circle
              cx="25"
              cy="25"
              r="23"
              fill="var(--bg-surface)"
              stroke="var(--border-subtle)"
              strokeWidth="1.2"
            />
            <circle
              cx="25"
              cy="25"
              r="19"
              fill="none"
              stroke="var(--border-subtle)"
              strokeWidth="0.8"
              strokeDasharray="2 2"
            />

            {/* Cardinal marks */}
            <text
              x="25"
              y="11"
              fill="#ef4444"
              fontSize="8"
              fontWeight="800"
              textAnchor="middle"
              fontFamily="sans-serif"
            >
              N
            </text>
            <text
              x="41"
              y="27"
              fill="#64748b"
              fontSize="6"
              fontWeight="600"
              textAnchor="middle"
              fontFamily="sans-serif"
            >
              E
            </text>
            <text
              x="25"
              y="43"
              fill="#64748b"
              fontSize="6"
              fontWeight="600"
              textAnchor="middle"
              fontFamily="sans-serif"
            >
              S
            </text>
            <text
              x="9"
              y="27"
              fill="#64748b"
              fontSize="6"
              fontWeight="600"
              textAnchor="middle"
              fontFamily="sans-serif"
            >
              W
            </text>

            {/* Compass needle */}
            <polygon points="25,12 28,25 25,23 22,25" fill="#ef4444" />
            <polygon points="25,38 28,25 25,23 22,25" fill="#94a3b8" />
            <circle cx="25" cy="25" r="2.5" fill="#0f172a" stroke="#ffffff" strokeWidth="1" />
          </svg>
        </div>

        {/* Official replay wind */}
        <div className="dual-hud-glass-card">
          {/* Wind Cell */}
          <div className="hud-metric-cell">
            <div className="hud-metric-header-row">
              <span className="hud-metric-caption">Official wind (replay)</span>
              {activeShift && (
                <span className="hud-shift-badge" title={activeShift.source}>
                  {activeShift.label}
                </span>
              )}
            </div>
            <div className="hud-metric-body">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="wind-wave-svg"
              >
                <path d="M4 8h11a3 3 0 1 0-3-3" />
                <path d="M2 13h16a3 3 0 1 1-3 3" />
                <path d="M5 18h7a2.5 2.5 0 1 0-2.5-2.5" />
              </svg>
              <div className="hud-val-group">
                <strong className="hud-bold-val">
                  {Number.isFinite(wind.tws) ? `${wind.tws.toFixed(1)} kt` : 'Unavailable'}
                </strong>
                <span className="hud-sub-angle">
                  {Number.isFinite(wind.twd)
                    ? Math.round(wind.twd) + '° T'
                    : 'No prior source sample'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {!controlsOutside &&
        TacticalMapControls({
          replay,
          frame,
          viewMode,
          onViewModeChange,
          followMode,
          onFollowModeChange,
          showSafetyBorders,
          onToggleSafetyBorders,
          onResetView,
          onZoomIn,
          onZoomOut,
          onToggleFullscreen,
          selectedBoatId,
        })}

      {/* Scale requires the current camera projection; fixed pixels would misstate distance. */}
      <div
        className="map-bottom-scale-bar"
        title="Map scale is unavailable until it is linked to the current zoom"
      >
        <div className="scale-notches-text">
          <span>Scale unavailable</span>
        </div>
      </div>
    </div>
  )
}
