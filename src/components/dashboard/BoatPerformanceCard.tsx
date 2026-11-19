import { useMemo } from 'react'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'

interface BoatPerformanceCardProps {
  replay: ReplayManifest
  frame: ReplayFrame
  selectedId: string | null
}

function renderCountryFlag(countryCode?: string) {
  const code = (countryCode || 'ITA').toUpperCase()
  if (code.includes('NZL') || code.includes('NZ')) {
    // New Zealand / Southern cross motif
    return (
      <svg width="22" height="15" viewBox="0 0 24 16" fill="none" className="team-flag-svg">
        <rect width="24" height="16" rx="2" fill="#00247d" />
        <path d="M0 0L10 8M10 0L0 8" stroke="#ffffff" strokeWidth="1.5" />
        <path d="M0 0L10 8M10 0L0 8" stroke="#cc142b" strokeWidth="0.8" />
        <path d="M5 0V8M0 4H10" stroke="#ffffff" strokeWidth="2.5" />
        <path d="M5 0V8M0 4H10" stroke="#cc142b" strokeWidth="1.5" />
        <circle cx="17" cy="4" r="1" fill="#cc142b" stroke="#ffffff" strokeWidth="0.4" />
        <circle cx="21" cy="7" r="1" fill="#cc142b" stroke="#ffffff" strokeWidth="0.4" />
        <circle cx="16" cy="11" r="1" fill="#cc142b" stroke="#ffffff" strokeWidth="0.4" />
        <circle cx="19" cy="13" r="1" fill="#cc142b" stroke="#ffffff" strokeWidth="0.4" />
      </svg>
    )
  }
  if (code.includes('GBR') || code.includes('UK')) {
    return (
      <svg width="22" height="15" viewBox="0 0 24 16" fill="none" className="team-flag-svg">
        <rect width="24" height="16" rx="2" fill="#012169" />
        <path d="M0 0L24 16M24 0L0 16" stroke="#ffffff" strokeWidth="3" />
        <path d="M0 0L24 16M24 0L0 16" stroke="#c8102e" strokeWidth="1.5" />
        <path d="M12 0V16M0 8H24" stroke="#ffffff" strokeWidth="5" />
        <path d="M12 0V16M0 8H24" stroke="#c8102e" strokeWidth="3" />
      </svg>
    )
  }
  if (code.includes('FRA')) {
    return (
      <svg width="22" height="15" viewBox="0 0 24 16" fill="none" className="team-flag-svg">
        <rect width="8" height="16" fill="#002654" />
        <rect x="8" width="8" height="16" fill="#ffffff" />
        <rect x="16" width="8" height="16" fill="#ce1126" />
      </svg>
    )
  }
  if (code.includes('SUI')) {
    return (
      <svg width="22" height="15" viewBox="0 0 24 16" fill="none" className="team-flag-svg">
        <rect width="24" height="16" rx="2" fill="#d52b1e" />
        <path d="M10 4H14V12H10Z" fill="#ffffff" />
        <path d="M7 6.5H17V9.5H7Z" fill="#ffffff" />
      </svg>
    )
  }
  if (code.includes('USA')) {
    return (
      <svg width="22" height="15" viewBox="0 0 24 16" fill="none" className="team-flag-svg">
        <rect width="24" height="16" rx="2" fill="#b22234" />
        <rect y="2.5" width="24" height="2.5" fill="#ffffff" />
        <rect y="7.5" width="24" height="2.5" fill="#ffffff" />
        <rect y="12.5" width="24" height="2.5" fill="#ffffff" />
        <rect width="10" height="9" fill="#3c3b6e" />
      </svg>
    )
  }
  // Default: Italy tricolore
  return (
    <svg width="22" height="15" viewBox="0 0 24 16" fill="none" className="team-flag-svg">
      <rect width="8" height="16" fill="#009246" />
      <rect x="8" width="8" height="16" fill="#ffffff" />
      <rect x="16" width="8" height="16" fill="#ce2b37" />
      <rect
        x="0.5"
        y="0.5"
        width="23"
        height="15"
        stroke="rgba(0,0,0,0.15)"
        strokeWidth="0.5"
        rx="2"
      />
    </svg>
  )
}

/**
 * Renders a crisp miniature SVG sparkline wave
 */
function MiniSparkline({
  points,
  color,
  width = 36,
  height = 14,
}: {
  points: number[]
  color: string
  width?: number
  height?: number
}) {
  const pathD = useMemo(() => {
    if (points.length < 2) return null
    const min = Math.min(...points)
    const max = Math.max(...points)
    const range = max - min || 1
    const coords = points.map((val, idx) => {
      const x = (idx / (points.length - 1)) * width
      const y = height - ((val - min) / range) * (height - 4) - 2
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    return `M ${coords.join(' L ')}`
  }, [points, width, height])

  if (!pathD) return null
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="mini-sparkline-svg"
    >
      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function BoatPerformanceCard({ replay, frame, selectedId }: BoatPerformanceCardProps) {
  const selectedBoat = useMemo(() => {
    return replay.competitors.find((b) => b.id === selectedId) ?? replay.competitors[0]
  }, [replay.competitors, selectedId])

  const boatState = frame.boats[selectedBoat.id]

  // The replay exports these four channels. Missing samples have no drawn substitute.
  const sparklines = useMemo(() => {
    const tel = replay.telemetry?.boats?.[selectedBoat.id]
    const end = Math.min(frame.index ?? 0, (tel?.sog.length ?? 0) - 1)
    const start = Math.max(0, end - 20)
    const values = (key: 'sog' | 'vmg' | 'twa' | 'tws') =>
      end >= start ? (tel?.[key].slice(start, end + 1) ?? []).filter(Number.isFinite) : []
    return { sog: values('sog'), vmg: values('vmg'), twa: values('twa'), tws: values('tws') }
  }, [frame.index, replay.telemetry?.boats, selectedBoat.id])

  const format = (value: number | undefined, digits: number, unit: string) =>
    typeof value === 'number' && Number.isFinite(value)
      ? `${value.toFixed(digits)}${unit}`
      : 'Unavailable'
  const metrics = [
    {
      label: 'SOG',
      value: format(boatState?.sog, 1, ' kt'),
      points: sparklines.sog,
      color: 'var(--telemetry-cyan)',
    },
    {
      label: 'VMG',
      value: format(boatState?.vmg, 1, ' kt'),
      points: sparklines.vmg,
      color: 'var(--telemetry-cyan)',
    },
    {
      label: 'TWA',
      value: format(boatState?.twa, 0, '°'),
      points: sparklines.twa,
      color: 'var(--telemetry-cyan)',
    },
    {
      label: 'TWS',
      value: format(boatState?.tws, 1, ' kt'),
      points: sparklines.tws,
      color: 'var(--telemetry-cyan)',
    },
  ]

  return (
    <article className="selected-boat-kpi-banner-card" aria-label="Selected Boat Performance KPIs">
      {/* 1. Left Boat Identifier */}
      <div className="banner-boat-id-cell">
        <div className="flag-icon-wrap" title={selectedBoat.country || 'ITA'}>
          {renderCountryFlag(selectedBoat.country || selectedBoat.team_code)}
        </div>
        <div className="boat-names-wrap">
          <strong
            className="boat-code-strong"
            style={{ borderLeft: `3px solid ${selectedBoat.color}`, paddingLeft: 8 }}
          >
            {selectedBoat.team_code}
          </strong>
          <span className="boat-team-span">{selectedBoat.team_name}</span>
        </div>
      </div>

      <div className="banner-divider" />

      {/* Four synchronized channels from the exported replay. */}
      <div className="banner-kpis-strip">
        {metrics.map((metric) => (
          <div className="banner-kpi-item" key={metric.label}>
            <div className="kpi-label-line">
              <span className="kpi-item-title">{metric.label}</span>
            </div>
            <div className="kpi-val-sparkline-row">
              <strong className="kpi-number-val">{metric.value}</strong>
              <div className="kpi-trend-pill">
                <MiniSparkline points={metric.points} color={metric.color} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </article>
  )
}
