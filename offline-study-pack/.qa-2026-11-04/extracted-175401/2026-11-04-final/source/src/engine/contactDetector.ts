import type { BoatClass, BorderPoint, Point, SafetyBorders } from '../types/replay'

/**
 * AC40 Platform Border in vessel-local metric coordinates.
 * GNSS origin (0, 0) is at the transom centerline.
 * y: -0.215m (rudder trailing edge) to +12.963m (bowsprit tip).
 * x: +/- 5.415m (outboard foil tips), +/- 1.5075m (transom half-beam).
 */
export const AC40_PLATFORM_BORDER: BorderPoint[] = [
  { x: 0.0, y: -0.215 },
  { x: 1.5075, y: 0.0 },
  { x: 5.415, y: 6.278 },
  { x: 5.415, y: 6.89 },
  { x: 0.0, y: 12.963 },
  { x: -5.415, y: 6.89 },
  { x: -5.415, y: 6.278 },
  { x: -1.5075, y: 0.0 },
  { x: 0.0, y: -0.215 },
]

/**
 * AC40 Keep Clear Border in vessel-local metric coordinates.
 * Strictly convex 9-vertex envelope expanded by +2.0m lateral buffer per America's Cup umpiring rules.
 * y: -0.215m to +12.963m.
 * x: +/- 7.415m (outboard buffer), +/- 3.5075m (transom buffer).
 */
export const AC40_KEEP_CLEAR_BORDER: BorderPoint[] = [
  { x: 0.0, y: -0.215 },
  { x: 3.5075, y: 0.0 },
  { x: 7.415, y: 6.278 },
  { x: 7.415, y: 6.89 },
  { x: 2.0, y: 12.963 },
  { x: -2.0, y: 12.963 },
  { x: -7.415, y: 6.89 },
  { x: -7.415, y: 6.278 },
  { x: -3.5075, y: 0.0 },
  { x: 0.0, y: -0.215 },
]

/** AC75 physical envelope in the same transom-centered metric coordinates. */
export const AC75_PLATFORM_BORDER: BorderPoint[] = [
  { x: 0, y: -0.4 },
  { x: 2.45, y: 0 },
  { x: 8, y: 10.9 },
  { x: 8, y: 11.8 },
  { x: 0, y: 21.5 },
  { x: -8, y: 11.8 },
  { x: -8, y: 10.9 },
  { x: -2.45, y: 0 },
  { x: 0, y: -0.4 },
]

/** AC75 display/contact envelope with a two-metre lateral clearance. */
export const AC75_KEEP_CLEAR_BORDER: BorderPoint[] = [
  { x: 0, y: -0.4 },
  { x: 4.45, y: 0 },
  { x: 10, y: 10.9 },
  { x: 10, y: 11.8 },
  { x: 2, y: 21.5 },
  { x: -2, y: 21.5 },
  { x: -10, y: 11.8 },
  { x: -10, y: 10.9 },
  { x: -4.45, y: 0 },
  { x: 0, y: -0.4 },
]

/**
 * Resolves class-appropriate canonical safety borders (Platform and Keep Clear borders).
 * Returns customBorders if provided and non-empty; otherwise returns canonical AC75 or AC40 borders.
 */
export function getSafetyBorders(
  boatClass?: BoatClass,
  customBorders?: SafetyBorders,
): SafetyBorders {
  if (
    customBorders &&
    Array.isArray(customBorders.platform_border) &&
    customBorders.platform_border.length > 0 &&
    Array.isArray(customBorders.keep_clear_border) &&
    customBorders.keep_clear_border.length > 0
  ) {
    return customBorders
  }
  if (boatClass === 'AC75') {
    return {
      platform_border: AC75_PLATFORM_BORDER,
      keep_clear_border: AC75_KEEP_CLEAR_BORDER,
    }
  }
  return {
    platform_border: AC40_PLATFORM_BORDER,
    keep_clear_border: AC40_KEEP_CLEAR_BORDER,
  }
}

/**
 * Transforms vessel-local polygon coordinates (u starboard, v forward)
 * to world Cartesian coordinates (x East, y North) given boat position and True heading.
 * Heading is in degrees clockwise from True North (0 = North, 90 = East).
 */
export function transformLocalToWorld(
  localCoords: Array<BorderPoint | Point>,
  boatX: number,
  boatY: number,
  headingDeg: number,
): Point[] {
  const rad = (headingDeg * Math.PI) / 180.0
  const cosH = Math.cos(rad)
  const sinH = Math.sin(rad)

  return localCoords.map((pt) => {
    const u = Array.isArray(pt) ? pt[0] : pt.x
    const v = Array.isArray(pt) ? pt[1] : pt.y
    const x = boatX + u * cosH + v * sinH
    const y = boatY - u * sinH + v * cosH
    return [x, y]
  })
}

/** Removes any closing vertex that duplicates the initial vertex. */
function getUniqueVertices(poly: Point[]): Point[] {
  if (poly.length <= 1) return poly
  const first = poly[0]
  const last = poly[poly.length - 1]
  if (Math.abs(first[0] - last[0]) < 1e-6 && Math.abs(first[1] - last[1]) < 1e-6) {
    return poly.slice(0, poly.length - 1)
  }
  return poly
}

export interface SATResult {
  hasContact: boolean
  overlapDepthM: number
}

/**
 * Evaluates 2D collision between two strictly convex polygons using the Separating Axis Theorem (SAT).
 * If a separating axis exists, collision is impossible and function exits immediately with false.
 * If all edge normals exhibit interval overlap, collision is confirmed and minimum penetration depth is returned.
 */
export function testPolygonOverlapSAT(polyA: Point[], polyB: Point[]): SATResult {
  const vertsA = getUniqueVertices(polyA)
  const vertsB = getUniqueVertices(polyB)

  if (vertsA.length < 3 || vertsB.length < 3) {
    return { hasContact: false, overlapDepthM: 0 }
  }

  let minOverlap = Number.POSITIVE_INFINITY
  const polygons = [vertsA, vertsB]

  for (let p = 0; p < 2; p++) {
    const current = polygons[p]
    const count = current.length

    for (let i = 0; i < count; i++) {
      const p1 = current[i]
      const p2 = current[(i + 1) % count]

      const ex = p2[0] - p1[0]
      const ey = p2[1] - p1[1]
      const edgeLen = Math.hypot(ex, ey)
      if (edgeLen < 1e-9) continue

      // Outward normal axis
      const nx = -ey / edgeLen
      const ny = ex / edgeLen

      // Project Polygon A onto normal axis
      let minA = Number.POSITIVE_INFINITY
      let maxA = Number.NEGATIVE_INFINITY
      for (let a = 0; a < vertsA.length; a++) {
        const dot = vertsA[a][0] * nx + vertsA[a][1] * ny
        if (dot < minA) minA = dot
        if (dot > maxA) maxA = dot
      }

      // Project Polygon B onto normal axis
      let minB = Number.POSITIVE_INFINITY
      let maxB = Number.NEGATIVE_INFINITY
      for (let b = 0; b < vertsB.length; b++) {
        const dot = vertsB[b][0] * nx + vertsB[b][1] * ny
        if (dot < minB) minB = dot
        if (dot > maxB) maxB = dot
      }

      // Check 1D interval overlap along the candidate separating axis
      const overlap = Math.min(maxA, maxB) - Math.max(minA, minB)
      if (overlap <= 0) {
        return { hasContact: false, overlapDepthM: 0 }
      }

      if (overlap < minOverlap) {
        minOverlap = overlap
      }
    }
  }

  return {
    hasContact: true,
    overlapDepthM: minOverlap === Number.POSITIVE_INFINITY ? 0 : minOverlap,
  }
}

/**
 * Computes polygon area using the Shoelace formula.
 */
export function computePolygonArea(vertices: Point[]): number {
  const n = vertices.length
  if (n < 3) return 0
  let areaSum = 0
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n
    areaSum += vertices[i][0] * vertices[j][1] - vertices[j][0] * vertices[i][1]
  }
  return Math.abs(areaSum) * 0.5
}

/**
 * Clips subject convex polygon by an infinite directed clip line using Sutherland-Hodgman.
 * Preserves points on the left side of the directed line (p1 -> p2).
 */
function clipConvexPolygonByLine(subject: Point[], p1: Point, p2: Point): Point[] {
  const result: Point[] = []
  if (!subject.length) return result

  const isInside = (pt: Point) => (p2[0] - p1[0]) * (pt[1] - p1[1]) - (p2[1] - p1[1]) * (pt[0] - p1[0]) >= -1e-9

  const lineIntersection = (s: Point, e: Point): Point => {
    const a1 = e[1] - s[1]
    const b1 = s[0] - e[0]
    const c1 = a1 * s[0] + b1 * s[1]

    const a2 = p2[1] - p1[1]
    const b2 = p1[0] - p2[0]
    const c2 = a2 * p1[0] + b2 * p1[1]

    const det = a1 * b2 - a2 * b1
    if (Math.abs(det) < 1e-11) return s
    return [(b2 * c1 - b1 * c2) / det, (a1 * c2 - a2 * c1) / det]
  }

  let s = subject[subject.length - 1]
  for (let i = 0; i < subject.length; i++) {
    const e = subject[i]
    if (isInside(e)) {
      if (!isInside(s)) {
        result.push(lineIntersection(s, e))
      }
      result.push(e)
    } else if (isInside(s)) {
      result.push(lineIntersection(s, e))
    }
    s = e
  }

  return result
}

/**
 * Computes exact 2D intersection area (m^2) between two convex polygons
 * using Sutherland-Hodgman clipping and the Shoelace formula.
 */
export function computePolygonIntersectionArea(polyA: Point[], polyB: Point[]): number {
  let subject = getUniqueVertices(polyA)
  const clipper = getUniqueVertices(polyB)

  if (subject.length < 3 || clipper.length < 3) return 0

  // Ensure clipper vertices are counter-clockwise
  const isClipperCcw = (vertices: Point[]): boolean => {
    let sum = 0
    for (let i = 0; i < vertices.length; i++) {
      const j = (i + 1) % vertices.length
      sum += vertices[i][0] * vertices[j][1] - vertices[j][0] * vertices[i][1]
    }
    return sum > 0
  }

  const orientedClipper = isClipperCcw(clipper) ? clipper : [...clipper].reverse()

  for (let i = 0; i < orientedClipper.length; i++) {
    const p1 = orientedClipper[i]
    const p2 = orientedClipper[(i + 1) % orientedClipper.length]
    subject = clipConvexPolygonByLine(subject, p1, p2)
    if (subject.length < 3) return 0
  }

  return computePolygonArea(subject)
}

export interface BoatPose {
  x: number
  y: number
  heading: number
}

export interface BoatContactEvaluation {
  hasContact: boolean
  overlapDepthM: number
  overlapAreaM2: number
  distanceM: number
}

/**
 * Evaluates live pairwise virtual contact between two boats.
 * Uses bounding radius broadphase filter (O(1)) followed by narrowphase SAT.
 */
export function checkBoatsContact(
  boatA: BoatPose,
  boatB: BoatPose,
  borderCoords: Array<BorderPoint | Point> = AC40_KEEP_CLEAR_BORDER,
): BoatContactEvaluation {
  const dx = boatB.x - boatA.x
  const dy = boatB.y - boatA.y
  const distanceM = Math.hypot(dx, dy)

  // Broadphase: compute maximum radius of the safety envelope from transom origin
  let maxBorderRadius = 15.0
  for (const pt of borderCoords) {
    const u = Array.isArray(pt) ? pt[0] : pt.x
    const v = Array.isArray(pt) ? pt[1] : pt.y
    const r = Math.hypot(u, v)
    if (r > maxBorderRadius) maxBorderRadius = r
  }
  const broadphaseThreshold = maxBorderRadius * 2 + 0.5

  // Two boats cannot touch if center distance > broadphase threshold
  if (distanceM > broadphaseThreshold) {
    return {
      hasContact: false,
      overlapDepthM: 0,
      overlapAreaM2: 0,
      distanceM,
    }
  }

  const polyA = transformLocalToWorld(borderCoords, boatA.x, boatA.y, boatA.heading)
  const polyB = transformLocalToWorld(borderCoords, boatB.x, boatB.y, boatB.heading)

  const sat = testPolygonOverlapSAT(polyA, polyB)
  if (!sat.hasContact) {
    return {
      hasContact: false,
      overlapDepthM: 0,
      overlapAreaM2: 0,
      distanceM,
    }
  }

  const overlapAreaM2 = computePolygonIntersectionArea(polyA, polyB)
  return {
    hasContact: true,
    overlapDepthM: sat.overlapDepthM,
    overlapAreaM2,
    distanceM,
  }
}

export interface ActiveFrameContact {
  boatA: string
  boatB: string
  distanceM: number
  overlapDepthM: number
  overlapAreaM2: number
}

/**
 * Evaluates all unique pairwise contacts among an arbitrary fleet of boats in a single playback frame.
 */
export function detectFrameContacts(
  boats: Record<string, BoatPose>,
  borderCoords: Array<BorderPoint | Point> = AC40_KEEP_CLEAR_BORDER,
): ActiveFrameContact[] {
  const boatKeys = Object.keys(boats)
  const contacts: ActiveFrameContact[] = []

  for (let i = 0; i < boatKeys.length; i++) {
    const keyA = boatKeys[i]
    const poseA = boats[keyA]
    if (!poseA) continue

    for (let j = i + 1; j < boatKeys.length; j++) {
      const keyB = boatKeys[j]
      const poseB = boats[keyB]
      if (!poseB) continue

      const result = checkBoatsContact(poseA, poseB, borderCoords)
      if (result.hasContact) {
        contacts.push({
          boatA: keyA,
          boatB: keyB,
          distanceM: result.distanceM,
          overlapDepthM: result.overlapDepthM,
          overlapAreaM2: result.overlapAreaM2,
        })
      }
    }
  }

  return contacts
}

/**
 * Retrieves all precomputed virtual contact incidents active at the given playback timestamp.
 */
