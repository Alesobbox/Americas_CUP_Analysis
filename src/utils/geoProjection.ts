import type { Point } from '../types/replay'

export interface GeoOrigin {
  lat: number
  lon: number
}

export interface GeoProjectionParams {
  k_lat: number
  k_lon: number
}

export interface ScreenPoint {
  x: number
  y: number
}

/**
 * 2D Affine Transformation Matrix coefficients:
 * [ X ]   [ a11  a12 ] [ x ]   [ tx ]
 * [ Y ] = [ a21  a22 ] [ y ] + [ ty ]
 */
export interface AffineMatrix2D {
  a11: number
  a12: number
  tx: number
  a21: number
  a22: number
  ty: number
}

export interface AffineScreenTransform {
  matrix: AffineMatrix2D
  toScreen: (metricPoint: Point) => Point
  vectorToScreen: (metricVector: Point) => Point
  toWorld: (screenPoint: Point) => Point
  originScreen: Point
  scaleX: number
  scaleY: number
  scale: number
  rotationRad: number
  rotationDeg: number
}

/**
 * Closed-form inverse equirectangular projection:
 * Inverts local metric Cartesian coordinates (x, y) in metres relative to course origin
 * into WGS84 geographic coordinates [longitude, latitude].
 * (Returns [lon, lat] adhering to GeoJSON and MapLibre conventions).
 */
export function metricToLngLat(
  x: number,
  y: number,
  origin: GeoOrigin,
  projection: GeoProjectionParams
): [number, number] {
  const lon = origin.lon + x / projection.k_lon
  const lat = origin.lat + y / projection.k_lat
  return [lon, lat]
}

/**
 * Forward projection:
 * Converts WGS84 geographic coordinates [longitude, latitude] into local metric Cartesian coordinates (x, y) in metres.
 */
export function lngLatToMetric(
  lon: number,
  lat: number,
  origin: GeoOrigin,
  projection: GeoProjectionParams
): Point {
  const x = (lon - origin.lon) * projection.k_lon
  const y = (lat - origin.lat) * projection.k_lat
  return [x, y]
}

/**
 * Computes the 2D affine matrix from screen projections of 3 anchor points:
 * - Origin (0, 0) m -> s0
 * - East (distanceM, 0) m -> sx
 * - North (0, distanceM) m -> sy
 */
export function computeAffineMatrixFromScreenPoints(
  s0: ScreenPoint,
  sx: ScreenPoint,
  sy: ScreenPoint,
  distanceM = 1000
): AffineMatrix2D {
  if (distanceM <= 0) {
    throw new Error('Anchor distance must be greater than zero')
  }
  return {
    a11: (sx.x - s0.x) / distanceM,
    a12: (sy.x - s0.x) / distanceM,
    tx: s0.x,
    a21: (sx.y - s0.y) / distanceM,
    a22: (sy.y - s0.y) / distanceM,
    ty: s0.y,
  }
}

/**
 * 3-Point Affine Anchor calculation:
 * Computes 2D affine matrix (a11, a12, tx, a21, a22, ty) from MapLibre camera projections
 * of Origin (0, 0), East (1000, 0), and North (0, 1000).
 *
 * Allows the 2D canvas overlay to map metric metres directly to screen pixels
 * in O(1) constant time with sub-pixel (< 0.01 px) accuracy.
 *
 * ZERO DOM and ZERO MapLibre runtime imports.
 */
export function computeAffineScreenTransform(
  projectFn: (lngLat: [number, number]) => ScreenPoint,
  origin: GeoOrigin,
  projection: GeoProjectionParams,
  anchorDistanceM = 1000
): AffineScreenTransform {
  // 1. Origin (0, 0) m
  const s0 = projectFn([origin.lon, origin.lat])

  // 2. East (anchorDistanceM, 0) m
  const eastLngLat = metricToLngLat(anchorDistanceM, 0, origin, projection)
  const sx = projectFn(eastLngLat)

  // 3. North (0, anchorDistanceM) m
  const northLngLat = metricToLngLat(0, anchorDistanceM, origin, projection)
  const sy = projectFn(northLngLat)

  const matrix = computeAffineMatrixFromScreenPoints(s0, sx, sy, anchorDistanceM)

  // Scale in pixels per metre
  const scaleX = Math.hypot(matrix.a11, matrix.a21)
  const scaleY = Math.hypot(matrix.a12, matrix.a22)
  const scale = (scaleX + scaleY) / 2

  // Determinant for 2x2 inverse
  const det = matrix.a11 * matrix.a22 - matrix.a12 * matrix.a21

  // Rotation: East vector on screen has angle atan2(a21, a11)
  // When bearing = 0, East vector points right (0 rad).
  // Clockwise camera bearing rotates the on-screen East vector counter-clockwise.
  const eastAngleRad = Math.atan2(matrix.a21, matrix.a11)
  let rotationDeg = -eastAngleRad * (180 / Math.PI)
  while (rotationDeg < 0) rotationDeg += 360
  while (rotationDeg >= 360) rotationDeg -= 360
  const rotationRad = (rotationDeg * Math.PI) / 180

  const toScreen = ([x, y]: Point): Point => [
    matrix.a11 * x + matrix.a12 * y + matrix.tx,
    matrix.a21 * x + matrix.a22 * y + matrix.ty,
  ]

  const vectorToScreen = ([dx, dy]: Point): Point => [
    matrix.a11 * dx + matrix.a12 * dy,
    matrix.a21 * dx + matrix.a22 * dy,
  ]

  const toWorld = ([X, Y]: Point): Point => {
    if (Math.abs(det) < 1e-12) return [0, 0]
    const dx = X - matrix.tx
    const dy = Y - matrix.ty
    return [(matrix.a22 * dx - matrix.a12 * dy) / det, (-matrix.a21 * dx + matrix.a11 * dy) / det]
  }

  return {
    matrix,
    toScreen,
    vectorToScreen,
    toWorld,
    originScreen: [s0.x, s0.y],
    scaleX,
    scaleY,
    scale,
    rotationRad,
    rotationDeg,
  }
}
