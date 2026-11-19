import React, { useMemo, useState, useRef, useCallback, useEffect } from 'react'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'

interface TelemetryWorkspaceProps {
  replay: ReplayManifest
  frame: ReplayFrame
  selectedId: string | null
  visibleBoatId?: string | null
  onSelectBoat: (id: string) => void
  onSeek: (time: number) => void
}

function formatRelativeClock(deltaMs: number): string {
  const sign = deltaMs >= 0 ? '+' : '−'
  const totalSec = Math.floor(Math.abs(deltaMs) / 1000)
  const mm = Math.floor(totalSec / 60)
  const ss = totalSec % 60
  return `${sign}${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

function lowerBound(values: number[], target: number): number {
  let low = 0
  let high = values.length
  while (low < high) {
    const mid = (low + high) >>> 1
    if (values[mid] < target) low = mid + 1
    else high = mid
  }
  return low
}

export function TelemetryWorkspace({
  replay,
  frame,
  selectedId,
  visibleBoatId,
  onSelectBoat,
  onSeek,
}: TelemetryWorkspaceProps) {
  const [activeBoats, setActiveBoats] = useState<Set<string>>(() => {
    return new Set(replay.competitors.map((b) => b.id))
  })
  useEffect(() => {
    setActiveBoats(new Set(replay.competitors.map((boat) => boat.id)))
  }, [replay.id, replay.competitors])
  const [activeMetrics, setActiveMetrics] = useState<Set<string>>(
    () => new Set(['sog', 'vmg', 'twa'])
  )
  const [windowOption, setWindowOption] = useState<string>('5 min')
  const [windowMenuOpen, setWindowMenuOpen] = useState(false)

  const chartContainerRef = useRef<HTMLDivElement>(null)
  const isDraggingRef = useRef(false)

  const currentTimestamp = frame.timestamp
  const { chronology } = replay

  const windowDurationMs = useMemo(() => {
    if (windowOption === '1 min') return 60000
    if (windowOption === '3 min') return 180000
    if (windowOption === '10 min') return 600000
    if (windowOption === 'Full Race') {
      return Math.max(60000, chronology.window_end - chronology.window_start)
    }
    return 300000 // 5 min default
  }, [chronology.window_end, chronology.window_start, windowOption])

  // Window starts before current timestamp and spans windowDurationMs
  const windowStartMs =
    windowOption === 'Full Race'
      ? chronology.window_start
      : Math.max(chronology.window_start, currentTimestamp - windowDurationMs * 0.65)
  const windowEndMs = windowStartMs + windowDurationMs

  const toggleBoat = (id: string) => {
    setActiveBoats((prev) => {
      const next = new Set(prev)
      next.add(id)
      return next
    })
    onSelectBoat(id)
  }

  const toggleMetric = (key: string) => {
    setActiveMetrics((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        if (next.size > 1) next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  // Generate multi-boat time-series polylines
  const chartWidth = 740
  const chartHeight = 60

  const processedData = useMemo(() => {
    const rawTimestamps = replay.telemetry?.timestamps ?? []
    const hasTel = rawTimestamps.length > 0

    const startIdx = lowerBound(rawTimestamps, windowStartMs)
    const endIdx = lowerBound(rawTimestamps, windowEndMs + 1) - 1

    const totalPoints = Math.max(0, endIdx - startIdx + 1)
    const targetSteps = 120
    const defaultStride = Math.max(1, Math.floor(totalPoints / targetSteps))

    // Build series for each boat
    const boatsTraces: Record<
      string,
      {
        sogPoints: string
        vmgPoints: string
        twaPoints: string
        currentSogY: number | null
        currentVmgY: number | null
        currentTwaY: number | null
      }
    > = {}

    // Needle X calculation
    const needleFrac = Math.max(
      0,
      Math.min(1, (currentTimestamp - windowStartMs) / windowDurationMs)
    )
    const needleX = needleFrac * chartWidth

    replay.competitors.forEach((boat) => {
      if (!activeBoats.has(boat.id) || (visibleBoatId && boat.id !== visibleBoatId)) return

      const isSelected = boat.id === selectedId
      const boatTel = replay.telemetry?.boats?.[boat.id]
      const sogPts: string[] = []
      const vmgPts: string[] = []
      const twaPts: string[] = []

      // Determine current telemetry values for scrubber dot from continuous 100ms frame
      const liveBoat = frame.boats[boat.id]
      const curSog: number | undefined = liveBoat?.sog
      const curVmg: number | undefined = liveBoat?.vmg
      const curTwa: number | undefined = liveBoat?.twa

      const exactSog = typeof curSog === 'number' && Number.isFinite(curSog) ? curSog : null
      const exactVmg = typeof curVmg === 'number' && Number.isFinite(curVmg) ? curVmg : null
      const exactTwa = typeof curTwa === 'number' && Number.isFinite(curTwa) ? curTwa : null

      // Exact dot coordinates matching polyline affine transformation
      const exactDotSogY =
        exactSog === null
          ? null
          : chartHeight - (Math.max(0, Math.min(60, exactSog)) / 60) * (chartHeight - 8) - 4
      const exactDotVmgY =
        exactVmg === null
          ? null
          : chartHeight -
            ((Math.max(-40, Math.min(20, exactVmg)) + 40) / 60) * (chartHeight - 8) -
            4
      const exactDotTwaY =
        exactTwa === null
          ? null
          : chartHeight -
            ((Math.max(-180, Math.min(180, exactTwa)) + 180) / 360) * (chartHeight - 8) -
            4

      // For selected boat, stride = 1 gives exact 100ms vertex resolution without chord decimation
      const stride = isSelected ? 1 : defaultStride

      if (hasTel && boatTel && totalPoints > 0) {
        for (let idx = startIdx; idx <= endIdx; idx += stride) {
          const t = rawTimestamps[idx]
          const frac = Math.max(0, Math.min(1, (t - windowStartMs) / windowDurationMs))
          const x = frac * chartWidth

          const sogRaw = boatTel.sog[idx]
          const vmgRaw = boatTel.vmg[idx]
          const twaRaw = boatTel.twa[idx]

          // SOG scale: 0 to 60 kt -> y: chartHeight to 4
          const ySog = Number.isFinite(sogRaw)
            ? chartHeight - (Math.max(0, Math.min(60, sogRaw)) / 60) * (chartHeight - 8) - 4
            : null
          // VMG scale: -40 to +20 kt -> y: chartHeight to 4
          const yVmg = Number.isFinite(vmgRaw)
            ? chartHeight -
              ((Math.max(-40, Math.min(20, vmgRaw)) + 40) / 60) * (chartHeight - 8) -
              4
            : null
          // TWA scale: -180 to +180 deg -> y: chartHeight to 4
          const yTwa = Number.isFinite(twaRaw)
            ? chartHeight -
              ((Math.max(-180, Math.min(180, twaRaw)) + 180) / 360) * (chartHeight - 8) -
              4
            : null

          if (ySog !== null) sogPts.push(`${x.toFixed(2)},${ySog.toFixed(2)}`)
          if (yVmg !== null) vmgPts.push(`${x.toFixed(2)},${yVmg.toFixed(2)}`)
          if (yTwa !== null) twaPts.push(`${x.toFixed(2)},${yTwa.toFixed(2)}`)
        }
      }

      boatsTraces[boat.id] = {
        sogPoints: sogPts.join(' '),
        vmgPoints: vmgPts.join(' '),
        twaPoints: twaPts.join(' '),
        currentSogY: exactDotSogY,
        currentVmgY: exactDotVmgY,
        currentTwaY: exactDotTwaY,
      }
    })

    return {
      needleX,
      boatsTraces,
    }
  }, [
    activeBoats,
    chartHeight,
    chartWidth,
    currentTimestamp,
    frame.boats,
    replay.competitors,
    replay.telemetry,
    selectedId,
    visibleBoatId,
    windowDurationMs,
    windowEndMs,
    windowStartMs,
  ])

  // Dynamic Time X-Axis Ticks computed from windowDurationMs and windowStartMs
  const xTicks = useMemo(() => {
    let tickCount = 6
    if (windowDurationMs <= 60000) {
      tickCount = 5
    } else if (windowDurationMs <= 180000) {
      tickCount = 7
    } else if (windowDurationMs <= 300000) {
      tickCount = 6
    } else if (windowDurationMs <= 600000) {
      tickCount = 6
    } else {
      tickCount = 7
    }
    const ticks: string[] = []
    for (let i = 0; i < tickCount; i++) {
      const t = windowStartMs + (i / (tickCount - 1)) * windowDurationMs
      ticks.push(formatRelativeClock(t - chronology.gun_time))
    }
    return ticks
  }, [chronology.gun_time, windowDurationMs, windowStartMs])

  // Scrubbing on chart
  const handleSeekFromClientX = useCallback(
    (clientX: number) => {
      const container = chartContainerRef.current
      if (!container) return
      const rect = container.getBoundingClientRect()
      const yAxisWidth = 68
      const plotWidth = Math.max(1, rect.width - yAxisWidth)
      const plotX = Math.max(0, Math.min(plotWidth, clientX - rect.left - yAxisWidth))
      const frac = plotX / plotWidth
      const targetTime = windowStartMs + frac * windowDurationMs
      onSeek(Math.round(targetTime))
    },
    [onSeek, windowDurationMs, windowStartMs]
  )

  const handlePointerDown = (e: React.PointerEvent) => {
    isDraggingRef.current = true
    handleSeekFromClientX(e.clientX)
  }

  const handlePointerMove = (e: React.PointerEvent) => {
    if (isDraggingRef.current) {
      handleSeekFromClientX(e.clientX)
    }
  }

  const handlePointerUp = () => {
    isDraggingRef.current = false
  }

  const relClockStr = formatRelativeClock(currentTimestamp - chronology.gun_time)

  return (
    <article className="telemetry-workspace-card" aria-label="Synchronized Multi-Boat Telemetry">
      {/* Control Strip & Filters Header */}
      <div className="telemetry-ctrl-header">
        <div className="header-title-wrap">
          <strong className="panel-title">Synchronized telemetry</strong>
          <span
            className="info-mark"
            title="Synchronized multi-boat telemetry aligned to playback cursor"
          >
            ⓘ
          </span>
        </div>

        {/* Competitor Boat Chips */}
        <div className="boats-filter-wrap">
          <span className="filter-sub-label">Boats</span>
          <div className="boat-chips-row">
            {replay.competitors.map((boat) => {
              const isActive =
                activeBoats.has(boat.id) && (!visibleBoatId || visibleBoatId === boat.id)
              const isSelected = boat.id === selectedId
              return (
                <button
                  key={boat.id}
                  type="button"
                  className={`boat-chip-btn ${isActive ? 'active' : 'dimmed'} ${isSelected ? 'selected' : ''}`}
                  onClick={() => toggleBoat(boat.id)}
                  aria-pressed={isSelected}
                  title={`${boat.team_name} (${boat.team_code})`}
                >
                  <span className="boat-color-square" style={{ backgroundColor: boat.color }} />
                  <span className="boat-chip-code">{boat.team_code}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Metrics Chips */}
        <div className="metrics-filter-wrap">
          <span className="filter-sub-label">Metrics</span>
          <div className="metric-chips-row">
            {(['sog', 'vmg', 'twa'] as const).map((mKey) => (
              <button
                key={mKey}
                type="button"
                className={`metric-chip-btn ${activeMetrics.has(mKey) ? 'active' : 'inactive'}`}
                onClick={() => toggleMetric(mKey)}
              >
                <span>{mKey.toUpperCase()}</span>
                <span className="close-x">×</span>
              </button>
            ))}
          </div>
        </div>

        {/* Time Window Selector */}
        <div className="window-selector-wrap">
          <span className="filter-sub-label">Time window</span>
          <div className="window-dropdown-rel">
            <button
              type="button"
              className="window-select-btn"
              onClick={() => setWindowMenuOpen((prev) => !prev)}
            >
              <span>{windowOption}</span>
              <svg width="8" height="5" viewBox="0 0 8 5" fill="none">
                <path
                  d="M1 1L4 4L7 1"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </button>
            {windowMenuOpen && (
              <div className="window-dropdown-menu">
                {['1 min', '3 min', '5 min', '10 min', 'Full Race'].map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    className={`window-dropdown-item ${windowOption === opt ? 'active' : ''}`}
                    onClick={() => {
                      setWindowOption(opt)
                      setWindowMenuOpen(false)
                    }}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Auto Scale Switch */}
      </div>

      {/* 3 Synchronized Multi-Boat Charts Stage */}
      <div
        className="stacked-charts-stage"
        ref={chartContainerRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        {!Object.values(processedData.boatsTraces).some(
          (trace) => trace.sogPoints || trace.vmgPoints || trace.twaPoints
        ) && <p className="timeline-empty-message">Telemetry unavailable for this time window</p>}
        {/* CHART 1: SOG */}
        {activeMetrics.has('sog') && (
          <div className="chart-row-container">
            <div className="chart-y-axis-col">
              <span className="y-axis-title">SOG (kt)</span>
              <div className="y-axis-ticks">
                <span>60</span>
                <span>30</span>
                <span>0</span>
              </div>
            </div>

            <div className="chart-plot-area">
              <svg
                viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                preserveAspectRatio="none"
                className="chart-svg-canvas"
              >
                {/* Horizontal reference grid lines */}
                <line x1="0" y1="4" x2={chartWidth} y2="4" stroke="#e2e8f0" strokeDasharray="3 3" />
                <line
                  x1="0"
                  y1={chartHeight / 2}
                  x2={chartWidth}
                  y2={chartHeight / 2}
                  stroke="#f1f5f9"
                />
                <line
                  x1="0"
                  y1={chartHeight - 4}
                  x2={chartWidth}
                  y2={chartHeight - 4}
                  stroke="#e2e8f0"
                />

                {/* Multi-boat traces */}
                {replay.competitors.map((boat) => {
                  const trace = processedData.boatsTraces[boat.id]
                  if (!trace || !trace.sogPoints) return null
                  const isSelected = boat.id === selectedId
                  return (
                    <polyline
                      key={boat.id}
                      fill="none"
                      stroke={boat.color}
                      strokeWidth={isSelected ? 2.4 : 1.4}
                      strokeOpacity={isSelected ? 1.0 : 0.75}
                      points={trace.sogPoints}
                    />
                  )
                })}

                {/* Internal SVG needle line co-located with needleX */}
                <line
                  className="chart-needle-line"
                  x1={processedData.needleX}
                  y1="0"
                  x2={processedData.needleX}
                  y2={chartHeight}
                  stroke="#0f172a"
                  strokeWidth="1.2"
                  strokeDasharray="2 2"
                  opacity="0.65"
                />

                {/* Needle Dot on SOG */}
                {replay.competitors.map((boat) => {
                  const trace = processedData.boatsTraces[boat.id]
                  if (!trace || boat.id !== selectedId || trace.currentSogY === null) return null
                  return (
                    <circle
                      key={`dot-sog-${boat.id}`}
                      className="scrubber-dot scrubber-dot-sog"
                      cx={processedData.needleX}
                      cy={trace.currentSogY}
                      r="3.5"
                      fill="#0f172a"
                      stroke="#ffffff"
                      strokeWidth="1.5"
                    />
                  )
                })}
              </svg>
            </div>
          </div>
        )}

        {/* CHART 2: VMG */}
        {activeMetrics.has('vmg') && (
          <div className="chart-row-container">
            <div className="chart-y-axis-col">
              <span className="y-axis-title">VMG (kt)</span>
              <div className="y-axis-ticks">
                <span>20</span>
                <span>0</span>
                <span>-20</span>
                <span>-40</span>
              </div>
            </div>

            <div className="chart-plot-area">
              <svg
                viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                preserveAspectRatio="none"
                className="chart-svg-canvas"
              >
                <line x1="0" y1="4" x2={chartWidth} y2="4" stroke="#e2e8f0" strokeDasharray="3 3" />
                <line
                  x1="0"
                  y1={chartHeight * 0.33}
                  x2={chartWidth}
                  y2={chartHeight * 0.33}
                  stroke="#f1f5f9"
                />
                <line
                  x1="0"
                  y1={chartHeight * 0.66}
                  x2={chartWidth}
                  y2={chartHeight * 0.66}
                  stroke="#f1f5f9"
                />
                <line
                  x1="0"
                  y1={chartHeight - 4}
                  x2={chartWidth}
                  y2={chartHeight - 4}
                  stroke="#e2e8f0"
                />

                {replay.competitors.map((boat) => {
                  const trace = processedData.boatsTraces[boat.id]
                  if (!trace || !trace.vmgPoints) return null
                  const isSelected = boat.id === selectedId
                  return (
                    <polyline
                      key={boat.id}
                      fill="none"
                      stroke={boat.color}
                      strokeWidth={isSelected ? 2.4 : 1.4}
                      strokeOpacity={isSelected ? 1.0 : 0.75}
                      points={trace.vmgPoints}
                    />
                  )
                })}

                {/* Internal SVG needle line co-located with needleX */}
                <line
                  className="chart-needle-line"
                  x1={processedData.needleX}
                  y1="0"
                  x2={processedData.needleX}
                  y2={chartHeight}
                  stroke="#0f172a"
                  strokeWidth="1.2"
                  strokeDasharray="2 2"
                  opacity="0.65"
                />

                {/* Needle Dot on VMG */}
                {replay.competitors.map((boat) => {
                  const trace = processedData.boatsTraces[boat.id]
                  if (!trace || boat.id !== selectedId || trace.currentVmgY === null) return null
                  return (
                    <circle
                      key={`dot-vmg-${boat.id}`}
                      className="scrubber-dot scrubber-dot-vmg"
                      cx={processedData.needleX}
                      cy={trace.currentVmgY}
                      r="3.5"
                      fill="#0f172a"
                      stroke="#ffffff"
                      strokeWidth="1.5"
                    />
                  )
                })}
              </svg>
            </div>
          </div>
        )}

        {/* CHART 3: TWA */}
        {activeMetrics.has('twa') && (
          <div className="chart-row-container">
            <div className="chart-y-axis-col">
              <span className="y-axis-title">TWA (°)</span>
              <div className="y-axis-ticks">
                <span>180</span>
                <span>0</span>
                <span>-180</span>
              </div>
            </div>

            <div className="chart-plot-area">
              <svg
                viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                preserveAspectRatio="none"
                className="chart-svg-canvas"
              >
                <line x1="0" y1="4" x2={chartWidth} y2="4" stroke="#e2e8f0" strokeDasharray="3 3" />
                <line
                  x1="0"
                  y1={chartHeight / 2}
                  x2={chartWidth}
                  y2={chartHeight / 2}
                  stroke="#f1f5f9"
                />
                <line
                  x1="0"
                  y1={chartHeight - 4}
                  x2={chartWidth}
                  y2={chartHeight - 4}
                  stroke="#e2e8f0"
                />

                {replay.competitors.map((boat) => {
                  const trace = processedData.boatsTraces[boat.id]
                  if (!trace || !trace.twaPoints) return null
                  const isSelected = boat.id === selectedId
                  return (
                    <polyline
                      key={boat.id}
                      fill="none"
                      stroke={boat.color}
                      strokeWidth={isSelected ? 2.4 : 1.4}
                      strokeOpacity={isSelected ? 1.0 : 0.75}
                      points={trace.twaPoints}
                    />
                  )
                })}

                {/* Internal SVG needle line co-located with needleX */}
                <line
                  className="chart-needle-line"
                  x1={processedData.needleX}
                  y1="0"
                  x2={processedData.needleX}
                  y2={chartHeight}
                  stroke="#0f172a"
                  strokeWidth="1.2"
                  strokeDasharray="2 2"
                  opacity="0.65"
                />

                {/* Needle Dot on TWA */}
                {replay.competitors.map((boat) => {
                  const trace = processedData.boatsTraces[boat.id]
                  if (!trace || boat.id !== selectedId || trace.currentTwaY === null) return null
                  return (
                    <circle
                      key={`dot-twa-${boat.id}`}
                      className="scrubber-dot scrubber-dot-twa"
                      cx={processedData.needleX}
                      cy={trace.currentTwaY}
                      r="3.5"
                      fill="#0f172a"
                      stroke="#ffffff"
                      strokeWidth="1.5"
                    />
                  )
                })}
              </svg>
            </div>
          </div>
        )}

        {/* Continuous Vertical Needle Spanning All Charts */}
        <div
          className="synchronized-needle-cursor"
          style={{
            left: `calc(68px + (100% - 68px) * ${Math.max(0, Math.min(1, (currentTimestamp - windowStartMs) / windowDurationMs))})`,
          }}
        >
          <div className="needle-time-pill">{relClockStr}</div>
          <div className="needle-vertical-line" />
        </div>
      </div>

      {/* Synchronized Time X-Axis */}
      <div className="charts-x-axis-bar">
        <div className="x-axis-spacer" />
        <div className="x-axis-ticks-row">
          {xTicks.map((label, i) => (
            <span key={i} className="x-tick-label">
              {label}
            </span>
          ))}
        </div>
      </div>
    </article>
  )
}
