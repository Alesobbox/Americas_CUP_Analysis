import type { BoatClass, BoatScaleMode } from '../../types/replay'

export {
  AC40_KEEP_CLEAR_BORDER,
  AC40_PLATFORM_BORDER,
  AC75_KEEP_CLEAR_BORDER,
  AC75_PLATFORM_BORDER,
  getSafetyBorders,
} from '../../engine/contactDetector'

export type Point2D = [number, number]

export interface BoatDimensions {
  hullLengthM: number
  bowspritLengthM: number
  totalLengthM: number
  maxHalfBeamM: number
  foilHalfSpanM: number
  minPixelFloor: number
}

/**
 * AC40 One-Design Metric Dimensions.
 * Transom GNSS mounting point is origin (0, 0).
 * Length: 11.8m hull + 1.163m bowsprit = 12.963m forward, -0.215m rudder aft (total 13.178m).
 * Foils: +/- 5.415m outboard span (total span 10.83m).
 */
export const AC40_DIMENSIONS: BoatDimensions = {
  hullLengthM: 11.8,
  bowspritLengthM: 1.163,
  totalLengthM: 13.178,
  maxHalfBeamM: 1.5075,
  foilHalfSpanM: 5.415,
  minPixelFloor: 22.0,
}

/**
 * AC75 Rule 9.4 Metric Dimensions.
 * Length: 20.65m hull forward point + 0.85m instrumentation wand = 21.5m forward, -0.4m rudder aft (total 21.9m).
 * Max Half-Beam: 2.45m per Rule 9.4 (total beam 4.90m).
 * Canting Foils: +/- 8.0m deployed wing tip span (total span 16.0m).
 */
export const AC75_DIMENSIONS: BoatDimensions = {
  hullLengthM: 20.65,
  bowspritLengthM: 0.85,
  totalLengthM: 21.9,
  maxHalfBeamM: 2.45,
  foilHalfSpanM: 8.0,
  minPixelFloor: 34.0,
}

/**
 * AC40 Tapered Hull Monohull Polygon in boat-local coordinates [u (starboard), v (forward)].
 */
export const AC40_HULL_POLYGON: Point2D[] = [
  [0.0, 12.963], // Bowsprit foremost tip
  [0.06, 11.8], // Starboard bowsprit root / stem
  [0.35, 10.5], // Forward hull taper
  [0.85, 9.0],
  [1.3, 7.5],
  [1.5075, 6.0], // Maximum half-beam (1.5075m)
  [1.48, 4.0],
  [1.42, 2.0],
  [1.38, 0.0], // Starboard transom corner
  [0.0, 0.0], // Transom centerline
  [-1.38, 0.0], // Port transom corner
  [-1.42, 2.0],
  [-1.48, 4.0],
  [-1.5075, 6.0], // Port maximum half-beam
  [-1.3, 7.5],
  [-0.85, 9.0],
  [-0.35, 10.5],
  [-0.06, 11.8], // Port bowsprit root / stem
  [0.0, 12.963], // Closure
]

/** AC40 Cockpit Trenches: [Port, Starboard] */
export const AC40_COCKPIT_STARBOARD: Point2D[] = [
  [0.45, 2.6],
  [1.15, 2.6],
  [1.15, 7.0],
  [0.45, 7.0],
]

export const AC40_COCKPIT_PORT: Point2D[] = [
  [-1.15, 2.6],
  [-0.45, 2.6],
  [-0.45, 7.0],
  [-1.15, 7.0],
]

/** AC40 Port/Starboard Foil Arms & Wings */
export const AC40_FOIL_ARM_PORT: Point2D[] = [
  [-1.45, 6.6],
  [-4.2, 6.55],
  [-4.2, 6.35],
  [-1.45, 6.3],
]

export const AC40_FOIL_ARM_STARBOARD: Point2D[] = [
  [1.45, 6.6],
  [4.2, 6.55],
  [4.2, 6.35],
  [1.45, 6.3],
]

export const AC40_FOIL_WING_PORT: Point2D[] = [
  [-4.0, 6.7],
  [-5.415, 6.89],
  [-5.415, 6.278],
  [-4.0, 6.4],
]

export const AC40_FOIL_WING_STARBOARD: Point2D[] = [
  [4.0, 6.7],
  [5.415, 6.89],
  [5.415, 6.278],
  [4.0, 6.4],
]

export const AC40_RUDDER_ELEVATOR: Point2D[] = [
  [-0.75, -0.15],
  [0.75, -0.15],
  [0.75, -0.215],
  [-0.75, -0.215],
]

/**
 * AC75 Monohull Hull Polygon in boat-local coordinates [u (starboard), v (forward)].
 */
export const AC75_HULL_POLYGON: Point2D[] = [
  [0.0, 21.5], // Forward instrumentation wand
  [0.08, 20.65], // Hull forward point stem (Rule 9.4)
  [0.35, 19.0], // Fine entry
  [0.8, 17.0],
  [1.4, 15.0],
  [2.0, 13.0],
  [2.45, 11.0], // Maximum half-beam (2.45m)
  [2.45, 8.5],
  [2.35, 5.5],
  [2.15, 2.5],
  [1.95, 0.0], // Starboard transom corner
  [0.0, 0.0], // Transom centerline
  [-1.95, 0.0], // Port transom corner
  [-2.15, 2.5],
  [-2.35, 5.5],
  [-2.45, 8.5],
  [-2.45, 11.0], // Port maximum half-beam
  [-2.0, 13.0],
  [-1.4, 15.0],
  [-0.8, 17.0],
  [-0.35, 19.0],
  [-0.08, 20.65], // Port stem
  [0.0, 21.5], // Closure
]

/** AC75 Cockpit Trenches */
export const AC75_COCKPIT_STARBOARD: Point2D[] = [
  [0.65, 3.5],
  [1.85, 3.5],
  [1.85, 12.0],
  [0.65, 12.0],
]

export const AC75_COCKPIT_PORT: Point2D[] = [
  [-1.85, 3.5],
  [-0.65, 3.5],
  [-0.65, 12.0],
  [-1.85, 12.0],
]

/** AC75 Port/Starboard Canting Foil Arms & Wings */
export const AC75_FOIL_ARM_PORT: Point2D[] = [
  [-2.4, 11.5],
  [-6.2, 11.4],
  [-6.2, 11.1],
  [-2.4, 11.0],
]

export const AC75_FOIL_ARM_STARBOARD: Point2D[] = [
  [2.4, 11.5],
  [6.2, 11.4],
  [6.2, 11.1],
  [2.4, 11.0],
]

export const AC75_FOIL_WING_PORT: Point2D[] = [
  [-6.0, 11.6],
  [-8.0, 11.8],
  [-8.0, 10.9],
  [-6.0, 11.0],
]

export const AC75_FOIL_WING_STARBOARD: Point2D[] = [
  [6.0, 11.6],
  [8.0, 11.8],
  [8.0, 10.9],
  [6.0, 11.0],
]

export const AC75_RUDDER_ELEVATOR: Point2D[] = [
  [-1.2, -0.25],
  [1.2, -0.25],
  [1.2, -0.4],
  [-1.2, -0.4],
]

/**
 * Returns canonical dimensions for a given yacht class.
 */
export function getBoatDimensions(boatClass?: BoatClass): BoatDimensions {
  if (boatClass === 'AC75') return AC75_DIMENSIONS
  return AC40_DIMENSIONS
}

/**
 * Calculates render scale factor (screen pixels per metric metre).
 * True mode preserves physical map scale. Enhanced mode applies the documented
 * minimum pixel floor so distant boats remain visible.
 */
export function computeBoatRenderScale(
  boatClass: BoatClass | undefined,
  viewportScalePxPerM: number,
  mode: BoatScaleMode = 'enhanced'
): number {
  const metricScale = Number.isFinite(viewportScalePxPerM) ? Math.max(0, viewportScalePxPerM) : 0
  if (mode === 'true') return metricScale
  const dims = getBoatDimensions(boatClass)
  const minScaleFromFloor = dims.minPixelFloor / dims.totalLengthM
  return Math.max(metricScale, minScaleFromFloor)
}

/**
 * Helper to trace a closed polygon in a canvas 2D context.
 * In rotated boat-local coordinates:
 * local forward (v) is on the x-axis, and local starboard (u) is on the y-axis.
 */
export function tracePolygonInCanvas(
  ctx: CanvasRenderingContext2D,
  polygon: Point2D[],
  scale: number
): void {
  if (polygon.length === 0) return
  ctx.beginPath()
  // pt[0] is u (starboard), pt[1] is v (forward)
  ctx.moveTo(polygon[0][1] * scale, polygon[0][0] * scale)
  for (let i = 1; i < polygon.length; i++) {
    ctx.lineTo(polygon[i][1] * scale, polygon[i][0] * scale)
  }
  ctx.closePath()
}

/**
 * Draws class-specific parametric foiling monohull in boat-local canvas space.
 * Assumes context is translated to boat position and rotated to screen heading.
 */
export function renderFoilingBoatModel(
  ctx: CanvasRenderingContext2D,
  boatClass: BoatClass | undefined,
  teamColor: string,
  scale: number,
  selected: boolean,
  mode: BoatScaleMode = 'enhanced'
): void {
  const isAc75 = boatClass === 'AC75'

  const hullPoly = isAc75 ? AC75_HULL_POLYGON : AC40_HULL_POLYGON
  const cockpitStbd = isAc75 ? AC75_COCKPIT_STARBOARD : AC40_COCKPIT_STARBOARD
  const cockpitPort = isAc75 ? AC75_COCKPIT_PORT : AC40_COCKPIT_PORT
  const foilArmPort = isAc75 ? AC75_FOIL_ARM_PORT : AC40_FOIL_ARM_PORT
  const foilArmStbd = isAc75 ? AC75_FOIL_ARM_STARBOARD : AC40_FOIL_ARM_STARBOARD
  const foilWingPort = isAc75 ? AC75_FOIL_WING_PORT : AC40_FOIL_WING_PORT
  const foilWingStbd = isAc75 ? AC75_FOIL_WING_STARBOARD : AC40_FOIL_WING_STARBOARD
  const rudderElevator = isAc75 ? AC75_RUDDER_ELEVATOR : AC40_RUDDER_ELEVATOR

  ctx.save()

  // At course zoom, true-metric hulls are only a few pixels long. Suppress
  // fixed-pixel fittings so they cannot masquerade as a much larger boat.
  if (mode === 'true' && scale < 0.5) {
    ctx.fillStyle = teamColor
    tracePolygonInCanvas(ctx, foilWingPort, scale)
    ctx.fill()
    tracePolygonInCanvas(ctx, foilWingStbd, scale)
    ctx.fill()
    ctx.fillStyle = '#ffffff'
    tracePolygonInCanvas(ctx, hullPoly, scale)
    ctx.fill()
    ctx.restore()
    return
  }

  // 1. Rudder elevator assembly (drawn under hull)
  ctx.fillStyle = '#1e293b'
  ctx.strokeStyle = '#0f172a'
  ctx.lineWidth = Math.max(0.75, 0.1 * scale)
  tracePolygonInCanvas(ctx, rudderElevator, scale)
  ctx.fill()
  ctx.stroke()

  // Rudder stock connecting line
  ctx.beginPath()
  ctx.moveTo(0, 0)
  ctx.lineTo((isAc75 ? -0.3 : -0.18) * scale, 0)
  ctx.strokeStyle = '#334155'
  ctx.lineWidth = Math.max(1, 0.18 * scale)
  ctx.stroke()

  // 2. Canting Foil Arms (structural carbon grey)
  ctx.fillStyle = '#27272a'
  ctx.strokeStyle = '#18181b'
  ctx.lineWidth = Math.max(0.75, 0.08 * scale)

  tracePolygonInCanvas(ctx, foilArmPort, scale)
  ctx.fill()
  ctx.stroke()

  tracePolygonInCanvas(ctx, foilArmStbd, scale)
  ctx.fill()
  ctx.stroke()

  // 3. Canting Foil Wings / T-Foils (with team / foiling cyan accents)
  ctx.fillStyle = '#0f172a'
  ctx.strokeStyle = teamColor
  ctx.lineWidth = Math.max(1.0, 0.12 * scale)

  tracePolygonInCanvas(ctx, foilWingPort, scale)
  ctx.fill()
  ctx.stroke()

  tracePolygonInCanvas(ctx, foilWingStbd, scale)
  ctx.fill()
  ctx.stroke()

  // Wing tip winglet highlights
  ctx.fillStyle = selected ? '#00d2ff' : teamColor
  const tipSpan = isAc75 ? 8.0 : 5.415
  const tipV = isAc75 ? 11.35 : 6.58
  const tipR = Math.max(1.5, 0.22 * scale)

  ctx.beginPath()
  ctx.arc(tipV * scale, -tipSpan * scale, tipR, 0, Math.PI * 2)
  ctx.arc(tipV * scale, tipSpan * scale, tipR, 0, Math.PI * 2)
  ctx.fill()

  // 4. Main Hull Structure (Crisp white monohull with aerodynamic taper)
  tracePolygonInCanvas(ctx, hullPoly, scale)
  ctx.fillStyle = '#ffffff'
  ctx.fill()

  // Hull outer perimeter outline
  ctx.strokeStyle = selected ? '#00d2ff' : 'rgba(15, 23, 42, 0.95)'
  ctx.lineWidth = selected ? Math.max(1.8, 0.22 * scale) : Math.max(1.0, 0.12 * scale)
  ctx.stroke()

  // 5. Team Livery Deck Accent Strip
  const stemV = isAc75 ? 20.65 : 11.8
  ctx.beginPath()
  ctx.moveTo(0, 0)
  ctx.lineTo(stemV * scale, 0)
  ctx.strokeStyle = teamColor
  ctx.lineWidth = Math.max(1.5, 0.25 * scale)
  ctx.stroke()

  // 6. Recessed Cockpit Trenches (carbon black aero cockpits)
  ctx.fillStyle = '#090e17'
  ctx.strokeStyle = '#1e293b'
  ctx.lineWidth = Math.max(0.5, 0.06 * scale)

  tracePolygonInCanvas(ctx, cockpitPort, scale)
  ctx.fill()
  ctx.stroke()

  tracePolygonInCanvas(ctx, cockpitStbd, scale)
  ctx.fill()
  ctx.stroke()

  // 7. Bowsprit Spar / Forward Instrumentation Wand
  const bowspritTipV = isAc75 ? 21.5 : 12.963
  ctx.beginPath()
  ctx.moveTo(stemV * scale, 0)
  ctx.lineTo(bowspritTipV * scale, 0)
  ctx.strokeStyle = '#090e17'
  ctx.lineWidth = Math.max(1.2, 0.16 * scale)
  ctx.stroke()

  // Foremost tip bead
  ctx.fillStyle = selected ? '#ffffff' : '#94a3b8'
  ctx.beginPath()
  ctx.arc(bowspritTipV * scale, 0, Math.max(1.5, 0.18 * scale), 0, Math.PI * 2)
  ctx.fill()

  ctx.restore()
}
