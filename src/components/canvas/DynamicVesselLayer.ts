import type {
  BoatClass,
  BoatScaleMode,
  BorderPoint,
  Competitor,
  GateSequence,
  Point,
  ReplayFrame,
  ReplayManifest,
  TrailColor,
  TrailLength,
  TrailScope,
} from '../../types/replay'
import { worldToScreen, worldVectorToScreen, type Viewport } from './ViewportMatrix'
import { windAt } from '../../engine/analytics'
import {
  detectFrameContacts,
  getSafetyBorders,
  transformLocalToWorld,
} from '../../engine/contactDetector'
import { computeBoatRenderScale, renderFoilingBoatModel } from './boatModels'
import { COURSE_PALETTE } from './renderPalette'
import { trailBoatIds } from './boatPresentation'

const bearingVector = (bearing: number): [number, number] => [
  Math.sin((bearing * Math.PI) / 180),
  Math.cos((bearing * Math.PI) / 180),
]

export interface VmgColorStep {
  minKt: number
  maxKt: number
  hex: string
  rgb: [number, number, number]
  name: string
}

/** 7 discrete high-contrast steps across 10-35 kt; red is reserved for contact incidents. */
export const VMG_COLOR_STEPS: VmgColorStep[] = [
  {
    minKt: 0,
    maxKt: 10,
    hex: '#38bdf8',
    rgb: [56, 189, 248],
    name: 'Displacement / Sub-Foiling (cyan)',
  },
  { minKt: 10, maxKt: 15, hex: '#2dd4bf', rgb: [45, 212, 191], name: 'Takeoff / Low VMG (teal)' },
  {
    minKt: 15,
    maxKt: 20,
    hex: '#84cc16',
    rgb: [132, 204, 22],
    name: 'Steady Foiling Upwind (lime)',
  },
  {
    minKt: 20,
    maxKt: 25,
    hex: '#eab308',
    rgb: [234, 179, 8],
    name: 'Electric Yellow / Strong Upwind (yellow)',
  },
  {
    minKt: 25,
    maxKt: 30,
    hex: '#f97316',
    rgb: [249, 115, 22],
    name: 'Vivid Amber / Fast Downwind (amber)',
  },
  { minKt: 30, maxKt: 35, hex: '#a78bfa', rgb: [167, 139, 250], name: 'High VMG (violet)' },
  {
    minKt: 35,
    maxKt: 60,
    hex: '#ec4899',
    rgb: [236, 72, 153],
    name: 'Hot Magenta / Peak Speed Burst (magenta)',
  },
]

export function getVmgTrailColor(vmgKt: number): string {
  const v = Math.abs(vmgKt)
  for (const step of VMG_COLOR_STEPS) {
    if (v < step.maxKt) return step.hex
  }
  return VMG_COLOR_STEPS[VMG_COLOR_STEPS.length - 1].hex
}

const colorForValue = (value: number, max: number) => {
  const ratio = Math.max(0, Math.min(1, value / Math.max(1, max)))
  return `hsl(${205 - ratio * 185} 86% 58%)`
}

export function drawWindFlowField(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  replay: ReplayManifest,
  timestamp: number,
  viewport: Viewport
): void {
  const wind = windAt(replay, timestamp)
  if (!Number.isFinite(wind.twd) || !Number.isFinite(wind.tws)) return
  // Atmospheric airflow travels downwind towards (wind.twd + 180) % 360
  const flowRad = (((wind.twd + 180) % 360) * Math.PI) / 180
  const [vx, vy] = worldVectorToScreen(viewport, [Math.sin(flowRad), Math.cos(flowRad)])
  const mag = Math.hypot(vx, vy) || 1
  const dx = vx / mag
  const dy = vy / mag

  const spacing = 85
  // Directional arrows describe the recorded wind without decorative drift.
  const drift = 0
  const shaftLength = 12 + Math.min(6, wind.tws * 0.35)
  const barbLength = 3.5
  const barbAngle = 0.45
  const angle = Math.atan2(dy, dx)
  const cosMinus = Math.cos(angle - barbAngle)
  const sinMinus = Math.sin(angle - barbAngle)
  const cosPlus = Math.cos(angle + barbAngle)
  const sinPlus = Math.sin(angle + barbAngle)

  context.save()
  context.strokeStyle = COURSE_PALETTE.airflow
  context.lineWidth = 1.0
  context.beginPath()

  for (let y = -spacing; y < height + spacing; y += spacing) {
    const rowOffset = (Math.abs(Math.floor(y / spacing)) % 2) * (spacing * 0.5)
    for (let x = -spacing; x < width + spacing; x += spacing) {
      const px = x + rowOffset + dx * drift
      const py = y + dy * drift
      if (px < -15 || px > width + 15 || py < -15 || py > height + 15) continue

      const x2 = px + dx * shaftLength
      const y2 = py + dy * shaftLength

      context.moveTo(px, py)
      context.lineTo(x2, y2)
      context.moveTo(x2, y2)
      context.lineTo(x2 - barbLength * cosMinus, y2 - barbLength * sinMinus)
      context.moveTo(x2, y2)
      context.lineTo(x2 - barbLength * cosPlus, y2 - barbLength * sinPlus)
    }
  }

  context.stroke()
  context.restore()
}

function getMarkScreenPos(
  code: string,
  frame: ReplayFrame,
  replay: ReplayManifest,
  viewport: Viewport
): [number, number] | null {
  const mark = frame.marks?.[code]
  if (mark && typeof mark.x === 'number' && typeof mark.y === 'number') {
    return worldToScreen(viewport, [mark.x, mark.y])
  }
  const fallback = replay.course.marks?.[code]?.target
  if (fallback) {
    return worldToScreen(viewport, fallback)
  }
  return null
}

function drawLineBadge(
  context: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  color: string
): void {
  context.save()
  context.font = '600 12px "DM Sans", sans-serif'
  const metrics = context.measureText(text)
  const padX = 6
  const padY = 5
  const badgeW = metrics.width + padX * 2
  const badgeH = 12 + padY * 2

  context.fillStyle = COURSE_PALETTE.label
  context.strokeStyle = COURSE_PALETTE.labelBorder
  context.lineWidth = 1
  context.beginPath()
  context.rect(x - badgeW / 2, y - badgeH / 2, badgeW, badgeH)
  context.fill()
  context.stroke()

  context.fillStyle = color
  context.textAlign = 'center'
  context.textBaseline = 'middle'
  context.fillText(text, x, y)
  context.restore()
}

export function drawCourseGeometry(
  context: CanvasRenderingContext2D,
  replay: ReplayManifest,
  frame: ReplayFrame,
  viewport: Viewport
): void {
  const isPreStart = frame.timestamp < replay.chronology.gun_time
  const activeLegs = Object.values(frame.boats)
    .map((b) => b.leg)
    .filter((leg): leg is number => typeof leg === 'number' && leg >= 0)
  const dominantLeg = isPreStart ? 0 : activeLegs.length > 0 ? Math.max(...activeLegs) : 0
  const legacySequences: GateSequence[] = [
    { leg: 0, port_mark: 'RM8', starboard_mark: 'RM6', gate_type: 'START' },
    { leg: 1, port_mark: 'RM4', starboard_mark: 'RM2', gate_type: 'TOP' },
    { leg: 2, port_mark: 'RM8', starboard_mark: 'RM6', gate_type: 'BOTTOM' },
    { leg: 3, port_mark: 'RM4', starboard_mark: 'RM2', gate_type: 'TOP' },
    { leg: 4, port_mark: 'RM8', starboard_mark: 'RM6', gate_type: 'FINISH' },
  ]
  const sequences = replay.course.sequences?.length ? replay.course.sequences : legacySequences
  const start = replay.course.start_marks
  const startSequence = sequences.find(
    (sequence) => sequence.gate_type === 'START' || sequence.leg === 0
  )
  const startPair = start
    ? [start.port, start.starboard]
    : startSequence
      ? [startSequence.port_mark, startSequence.starboard_mark]
      : null
  const topSequence = sequences.find((sequence) => sequence.gate_type === 'TOP')

  // The course axis connects the actual start and first windward gate, when present.
  if (startPair && topSequence) {
    const startA = getMarkScreenPos(startPair[0], frame, replay, viewport)
    const startB = getMarkScreenPos(startPair[1], frame, replay, viewport)
    const topA = getMarkScreenPos(topSequence.port_mark, frame, replay, viewport)
    const topB = getMarkScreenPos(topSequence.starboard_mark, frame, replay, viewport)
    if (startA && startB && topA && topB) {
      context.save()
      context.strokeStyle = COURSE_PALETTE.axis
      context.lineWidth = 1
      context.setLineDash([3, 8])
      context.beginPath()
      context.moveTo((startA[0] + startB[0]) / 2, (startA[1] + startB[1]) / 2)
      context.lineTo((topA[0] + topB[0]) / 2, (topA[1] + topB[1]) / 2)
      context.stroke()
      context.restore()
    }
  }

  // Draw every distinct sequence pair once; the current leg selects its label.
  const pairs = new Map<string, GateSequence[]>()
  for (const sequence of sequences) {
    if (!replay.course.marks[sequence.port_mark] || !replay.course.marks[sequence.starboard_mark])
      continue
    const key = [sequence.port_mark, sequence.starboard_mark].sort().join('|')
    const entries = pairs.get(key) ?? []
    entries.push(sequence)
    pairs.set(key, entries)
  }
  for (const pair of pairs.values()) {
    const { port_mark, starboard_mark } = pair[0]
    const port = getMarkScreenPos(port_mark, frame, replay, viewport)
    const starboard = getMarkScreenPos(starboard_mark, frame, replay, viewport)
    if (!port || !starboard) continue
    const active = pair.find((sequence) => sequence.leg === dominantLeg)
    const type = active?.gate_type
    const label =
      type === 'START'
        ? 'START LINE'
        : type === 'FINISH'
          ? 'FINISH LINE'
          : type === 'TOP'
            ? 'WINDWARD GATE'
            : type === 'BOTTOM'
              ? 'LEEWARD GATE'
              : null
    const color =
      type === 'START'
        ? COURSE_PALETTE.action
        : type === 'FINISH'
          ? COURSE_PALETTE.finish
          : COURSE_PALETTE.gate
    context.save()
    context.strokeStyle = active ? color : COURSE_PALETTE.safety
    context.lineWidth = active ? 2 : 1
    context.setLineDash(active ? [8, 5] : [4, 6])
    context.beginPath()
    context.moveTo(...port)
    context.lineTo(...starboard)
    context.stroke()
    context.restore()
    if (label)
      drawLineBadge(
        context,
        label,
        (port[0] + starboard[0]) / 2,
        (port[1] + starboard[1]) / 2 - 22,
        color
      )
  }

  // Every active mark present in course definition or frame telemetry can move;
  // the frame position takes priority. Render dynamically for RM1 through RM8, IRM, HAZ.
  const markCodes = Array.from(
    new Set([
      ...Object.keys(replay.course.marks ?? {}),
      ...Object.keys(frame.marks ?? {}).filter((code) => /^(RM\d+|IRM\w*|HAZ\w*)$/.test(code)),
    ])
  )

  for (const code of markCodes) {
    const pos = getMarkScreenPos(code, frame, replay, viewport)
    if (!pos) continue
    const [bx, by] = pos
    const isStart = startPair?.includes(code)
    const isHazard = code.startsWith('HAZ') || replay.course.marks?.[code]?.role === 'HAZARD'
    const isIntermediate =
      code.startsWith('IRM') || replay.course.marks?.[code]?.role === 'INTERMEDIATE'
    const isFinish = sequences.some(
      (s) => s.gate_type === 'FINISH' && (s.port_mark === code || s.starboard_mark === code)
    )
    const isWindward = sequences.some(
      (s) => s.gate_type === 'TOP' && (s.port_mark === code || s.starboard_mark === code)
    )
    const isLeeward = sequences.some(
      (s) => s.gate_type === 'BOTTOM' && (s.port_mark === code || s.starboard_mark === code)
    )

    const color = isHazard
      ? '#ef4444'
      : isStart
        ? '#06b6d4'
        : isFinish
          ? '#34d399'
          : isWindward
            ? '#f59e0b'
            : isLeeward
              ? '#fb923c'
              : isIntermediate
                ? '#38bdf8'
                : '#f59e0b'

    context.save()

    // Outer beacon halo ring
    context.beginPath()
    context.arc(bx, by, 7.5, 0, Math.PI * 2)
    context.strokeStyle =
      color === '#06b6d4'
        ? 'rgba(6, 182, 212, 0.40)'
        : color === '#ef4444'
          ? 'rgba(239, 68, 68, 0.45)'
          : color === '#34d399'
            ? 'rgba(52, 211, 153, 0.45)'
            : 'rgba(251, 191, 36, 0.35)'
    context.lineWidth = 1.0
    context.stroke()

    // Central solid buoy core with white rim (radius 4.5)
    context.beginPath()
    context.arc(bx, by, 4.5, 0, Math.PI * 2)
    context.fillStyle = color
    context.fill()
    context.strokeStyle = '#ffffff'
    context.lineWidth = 1.0
    context.stroke()

    // Neutral labels stay readable independently of each buoy's color.
    context.font = '500 12px "DM Sans", sans-serif'
    const tw = context.measureText(code).width
    const lx = bx
    const ly = by + 19
    context.fillStyle = COURSE_PALETTE.label
    context.strokeStyle = COURSE_PALETTE.labelBorder
    context.lineWidth = 1
    context.beginPath()
    context.rect(lx - tw / 2 - 5, ly - 10, tw + 10, 20)
    context.fill()
    context.stroke()

    context.fillStyle = COURSE_PALETTE.ink
    context.textAlign = 'center'
    context.textBaseline = 'middle'
    context.fillText(code, lx, ly)
    context.restore()
  }
}

function drawTrail(
  context: CanvasRenderingContext2D,
  replay: ReplayManifest,
  boat: Competitor,
  frame: ReplayFrame,
  viewport: Viewport,
  length: TrailLength,
  colorMode: TrailColor
): void {
  if (length === 'off') return
  const data = replay.telemetry.boats[boat.id]
  if (!data) return
  let start = 0
  if (length !== 'race') {
    const seconds = length === 'leg' ? Infinity : Number.parseInt(length, 10)
    if (length === 'leg') {
      const leg = data.leg[frame.index]
      start = frame.index
      while (start > 0 && data.leg[start - 1] === leg) start -= 1
    } else {
      start = Math.max(0, frame.index - seconds * 10)
    }
  }
  const stride = Math.max(1, Math.ceil((frame.index - start) / 500))
  context.save()
  context.lineWidth = 1.6
  context.lineCap = 'round'

  for (let index = start; index < frame.index; index += stride) {
    const next = Math.min(frame.index, index + stride)
    const from = worldToScreen(viewport, [data.x[index], data.y[index]])
    const to = worldToScreen(viewport, [data.x[next], data.y[next]])
    const strokeColor =
      colorMode === 'team'
        ? boat.color
        : colorMode === 'vmg'
          ? getVmgTrailColor(Math.abs(data.vmg[index]))
          : colorForValue(data.sog[index], 52)
    const opacity = 0.4 + (0.5 * (index - start)) / Math.max(1, frame.index - start)
    context.beginPath()
    context.moveTo(from[0], from[1])
    context.lineTo(to[0], to[1])
    // A quiet under-stroke keeps pale team colors legible over water and tiles.
    context.strokeStyle = COURSE_PALETTE.traceOutline
    context.globalAlpha = opacity
    context.lineWidth = 3.2
    context.stroke()
    context.strokeStyle = strokeColor
    context.lineWidth = 1.6
    context.stroke()
  }
  context.restore()
}

/**
 * Renders boat-oriented Platform Border (inner polygon) and Keep Clear Border (outer polygon).
 */
export function projectSafetyBorderToScreen(
  state: { x: number; y: number; heading: number },
  viewport: Viewport,
  border: BorderPoint[],
  renderScale: number
): Point[] {
  const center = worldToScreen(viewport, [state.x, state.y])
  const scaledViewport = { ...viewport, scale: renderScale }
  return transformLocalToWorld(border, state.x, state.y, state.heading).map((worldPoint) => {
    const displacement = worldVectorToScreen(scaledViewport, [
      worldPoint[0] - state.x,
      worldPoint[1] - state.y,
    ])
    return [center[0] + displacement[0], center[1] + displacement[1]]
  })
}

function drawSafetyBordersForBoat(
  context: CanvasRenderingContext2D,
  state: { x: number; y: number; heading: number },
  viewport: Viewport,
  platformCoords: BorderPoint[],
  keepClearCoords: BorderPoint[],
  inContact: boolean,
  showBorders: boolean,
  timestamp: number,
  renderScale: number
): void {
  // 1. Keep Clear Border
  if (showBorders || inContact) {
    const keepClearScreen = projectSafetyBorderToScreen(
      state,
      viewport,
      keepClearCoords,
      renderScale
    )

    context.save()
    context.beginPath()
    context.moveTo(keepClearScreen[0][0], keepClearScreen[0][1])
    for (let i = 1; i < keepClearScreen.length; i++) {
      context.lineTo(keepClearScreen[i][0], keepClearScreen[i][1])
    }
    context.closePath()

    if (inContact) {
      // High-visibility racing red (#FF3B30) collision pulse
      const pulseAlpha = 0.22 + 0.18 * Math.sin(timestamp / 70)
      context.fillStyle = `rgba(255, 59, 48, ${pulseAlpha})`
      context.fill()
      context.strokeStyle = '#ff3b30'
      context.lineWidth = 2.5
      context.stroke()
    } else {
      // Normal state: Technical dashed semi-transparent yellow/orange
      context.fillStyle = 'rgba(245, 158, 11, 0.05)'
      context.fill()
      context.setLineDash([4, 4])
      context.strokeStyle = 'rgba(245, 158, 11, 0.65)'
      context.lineWidth = 1.2
      context.stroke()
    }
    context.restore()
  }

  // 2. Platform Border (inner polygon, only when safety borders toggle is ON)
  if (showBorders) {
    const platformScreen = projectSafetyBorderToScreen(state, viewport, platformCoords, renderScale)

    context.save()
    context.beginPath()
    context.moveTo(platformScreen[0][0], platformScreen[0][1])
    for (let i = 1; i < platformScreen.length; i++) {
      context.lineTo(platformScreen[i][0], platformScreen[i][1])
    }
    context.closePath()

    context.fillStyle = 'rgba(56, 189, 248, 0.06)'
    context.fill()
    context.strokeStyle = 'rgba(56, 189, 248, 0.55)'
    context.lineWidth = 1.0
    context.stroke()
    context.restore()
  }
}

function drawBoat(
  context: CanvasRenderingContext2D,
  frame: ReplayFrame,
  boat: Competitor,
  viewport: Viewport,
  selected: boolean,
  boatClass: BoatClass,
  inContact: boolean,
  showSafetyBorders: boolean,
  platformCoords: BorderPoint[],
  keepClearCoords: BorderPoint[],
  scaleMode: BoatScaleMode,
  drawCallout = true
): void {
  const state = frame.boats[boat.id]
  if (!state) return
  const [x, y] = worldToScreen(viewport, [state.x, state.y])
  const [hx, hy] = worldVectorToScreen(viewport, bearingVector(state.heading))
  const headingAngle = Math.atan2(hy, hx)
  const renderScale = computeBoatRenderScale(boatClass, viewport.scale, scaleMode)

  // 1. Draw Safety Borders (underneath boat hull)
  drawSafetyBordersForBoat(
    context,
    state,
    viewport,
    platformCoords,
    keepClearCoords,
    inContact,
    showSafetyBorders,
    frame.timestamp,
    renderScale
  )

  // The hull and foils are drawn at the same scale as their safety borders.
  context.save()
  context.translate(x, y)
  context.rotate(headingAngle)
  renderFoilingBoatModel(context, boatClass, boat.color, renderScale, selected, scaleMode)
  context.restore()

  // 4. Velocity Vector (COG)
  const [vx, vy] = worldVectorToScreen(viewport, bearingVector(state.cog))
  const speedScale = Math.min(38, Math.max(10, state.sog * 0.72))
  const magnitude = Math.hypot(vx, vy) || 1
  context.save()
  context.strokeStyle = selected ? COURSE_PALETTE.action : 'rgba(95, 99, 104, 0.6)'
  context.lineWidth = selected ? 1.6 : 1.0
  context.beginPath()
  context.moveTo(x, y)
  context.lineTo(x + (vx / magnitude) * speedScale, y + (vy / magnitude) * speedScale)
  context.stroke()
  context.restore()

  // 5. Team Code Label & Tactical Callout
  if (selected && drawCallout) {
    context.save()
    const sogText = `${state.sog.toFixed(1)} kt`
    const vmgText = `${state.vmg.toFixed(1)} kt VMG`
    const metricsText = `${sogText}   |   ${vmgText}`

    // Measure required box width to ensure zero clipping
    context.font = '500 12px "DM Sans", sans-serif'
    const metricsWidth = context.measureText(metricsText).width
    const calloutW = Math.max(160, Math.round(metricsWidth + 24))
    const calloutH = 44
    const calloutX = Math.max(8, Math.min(viewport.width - calloutW - 8, x + 18))
    const calloutY = Math.max(8, Math.min(viewport.height - calloutH - 8, y - 50))

    // Pointer line
    context.strokeStyle = boat.color || '#f97316'
    context.lineWidth = 1.4
    context.beginPath()
    context.moveTo(x, y)
    context.lineTo(calloutX, calloutY + calloutH / 2)
    context.stroke()

    // Callout Box
    context.fillStyle = COURSE_PALETTE.label
    context.strokeStyle = boat.color || '#f97316'
    context.lineWidth = 1.6
    context.beginPath()
    if (typeof (context as any).roundRect === 'function') {
      ;(context as any).roundRect(calloutX, calloutY, calloutW, calloutH, 8)
    } else {
      context.rect(calloutX, calloutY, calloutW, calloutH)
    }
    context.fill()
    context.stroke()

    // Team identity remains in the border and hull; text uses readable ink.
    context.font = '600 12px "DM Sans", sans-serif'
    context.fillStyle = COURSE_PALETTE.ink
    context.textAlign = 'left'
    context.fillText(boat.team_code, calloutX + 12, calloutY + 17)

    // Line 2: SOG & VMG separated by divider
    context.font = '500 12px "DM Sans", sans-serif'
    context.fillStyle = COURSE_PALETTE.secondary
    context.fillText(metricsText, calloutX + 12, calloutY + 34)

    context.restore()
  } else if (inContact && drawCallout) {
    context.save()
    context.font = '600 12px "DM Sans", sans-serif'
    context.fillStyle = '#ff3b30'
    context.fillText(`${boat.team_code} [CONTACT]`, x + 14, y - 10)
    context.restore()
  }
}

export function drawDynamicVessels(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  replay: ReplayManifest,
  frame: ReplayFrame,
  viewport: Viewport,
  trailLength: TrailLength,
  trailColor: TrailColor,
  selectedId: string | null,
  comparisonId: string | null,
  showSafetyBorders: boolean = false,
  scaleMode: BoatScaleMode = 'true',
  visibleBoatId: string | null = null,
  presentation: { trailScope?: TrailScope; highlightedIds?: string[]; drawCallouts?: boolean } = {}
): void {
  context.clearRect(0, 0, width, height)

  const boatClass: BoatClass = replay.boat_class ?? 'AC40'
  const safetyBorders = getSafetyBorders(boatClass, replay.safety_borders)
  const platformCoords = safetyBorders.platform_border
  const keepClearCoords = safetyBorders.keep_clear_border

  // 1. Live Continuous 2D SAT Pairwise Virtual Contact Detection
  const displayedBoats = visibleBoatId
    ? replay.competitors.filter((boat) => boat.id === visibleBoatId)
    : replay.competitors
  const displayedFrameBoats = visibleBoatId
    ? Object.fromEntries(Object.entries(frame.boats).filter(([id]) => id === visibleBoatId))
    : frame.boats
  const activeContacts = detectFrameContacts(displayedFrameBoats, keepClearCoords)
  const contactBoatIds = new Set<string>()
  for (const contact of activeContacts) {
    contactBoatIds.add(contact.boatA)
    contactBoatIds.add(contact.boatB)
  }

  // 2. Wind flow field (underneath vessels and trails)
  drawWindFlowField(context, width, height, replay, frame.timestamp, viewport)

  // 3. Dynamic course geometry (active gates, buoys, axis)
  drawCourseGeometry(context, replay, frame, viewport)

  // 4. Trail scope is independent of visible vessel and contact geometry.
  const highlightedIds =
    presentation.highlightedIds ?? [selectedId].filter((id): id is string => !!id)
  const trailIds = new Set(
    trailBoatIds(
      displayedBoats.map((boat) => boat.id),
      presentation.trailScope ?? 'all',
      highlightedIds
    )
  )
  displayedBoats
    .filter((boat) => trailIds.has(boat.id))
    .forEach((boat) => drawTrail(context, replay, boat, frame, viewport, trailLength, trailColor))

  // 5. Vessel hulls, safety borders, and vectors
  displayedBoats.forEach((boat) =>
    drawBoat(
      context,
      frame,
      boat,
      viewport,
      highlightedIds.includes(boat.id),
      boatClass,
      contactBoatIds.has(boat.id),
      showSafetyBorders,
      platformCoords,
      keepClearCoords,
      scaleMode,
      presentation.drawCallouts ?? true
    )
  )

  // 6. Contact Incidents Active Bridge Visualizer
  for (const contact of activeContacts) {
    const boatA = frame.boats[contact.boatA]
    const boatB = frame.boats[contact.boatB]
    if (!boatA || !boatB) continue

    const pA = worldToScreen(viewport, [boatA.x, boatA.y])
    const pB = worldToScreen(viewport, [boatB.x, boatB.y])
    const midX = (pA[0] + pB[0]) / 2
    const midY = (pA[1] + pB[1]) / 2

    context.save()
    // Flashing collision link line
    context.strokeStyle = '#ff3b30'
    context.lineWidth = 2.0
    context.setLineDash([4, 3])
    context.beginPath()
    context.moveTo(...pA)
    context.lineTo(...pB)
    context.stroke()
    context.setLineDash([])

    // Contact Incident Alert Badge
    const alertLabel = `VIRTUAL CONTACT · ${contact.overlapDepthM.toFixed(1)}m`
    context.font = '600 12px "DM Sans", sans-serif'
    const tw = context.measureText(alertLabel).width
    const bw = tw + 14
    const bh = 24

    context.fillStyle = COURSE_PALETTE.label
    context.strokeStyle = '#ff3b30'
    context.lineWidth = 1.5
    context.beginPath()
    context.rect(midX - bw / 2, midY - bh / 2, bw, bh)
    context.fill()
    context.stroke()

    context.fillStyle = '#ff3b30'
    context.textAlign = 'center'
    context.textBaseline = 'middle'
    context.fillText(alertLabel, midX, midY)
    context.restore()
  }

  // 7. Head-to-head measurement line (Match Race or comparison mode)
  const isMatchRace =
    replay.competitors.length === 2 &&
    Boolean(frame.boats[replay.competitors[0].id] && frame.boats[replay.competitors[1].id])
  const idA = isMatchRace ? replay.competitors[0].id : selectedId
  const idB = isMatchRace ? replay.competitors[1].id : comparisonId

  if (
    idA &&
    idB &&
    idA !== idB &&
    frame.boats[idA] &&
    frame.boats[idB] &&
    !visibleBoatId &&
    (isMatchRace || presentation.highlightedIds === undefined || highlightedIds.includes(idB))
  ) {
    const a = frame.boats[idA]
    const b = frame.boats[idB]
    const p1 = worldToScreen(viewport, [a.x, a.y])
    const p2 = worldToScreen(viewport, [b.x, b.y])
    const distM = Math.hypot(b.x - a.x, b.y - a.y)

    context.save()
    context.setLineDash([5, 4])
    context.strokeStyle = isMatchRace ? COURSE_PALETTE.action : 'rgba(95, 99, 104, 0.6)'
    context.lineWidth = 1.5
    context.beginPath()
    context.moveTo(...p1)
    context.lineTo(...p2)
    context.stroke()
    context.setLineDash([])

    const midX = (p1[0] + p2[0]) / 2
    const midY = (p1[1] + p2[1]) / 2
    const label = `${Math.round(distM)} m`
    context.font = '500 12px "DM Sans", sans-serif'
    const textWidth = context.measureText(label).width
    const badgeW = textWidth + 16
    const badgeH = 24

    context.fillStyle = COURSE_PALETTE.label
    context.strokeStyle = COURSE_PALETTE.labelBorder
    context.lineWidth = 1
    context.beginPath()
    context.rect(midX - badgeW / 2, midY - badgeH / 2, badgeW, badgeH)
    context.fill()
    context.stroke()

    context.fillStyle = COURSE_PALETTE.ink
    context.textAlign = 'center'
    context.textBaseline = 'middle'
    context.fillText(label, midX, midY)
    context.restore()
  }
}
