import { describe, expect, it, vi } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import {
  AC40_COCKPIT_PORT,
  AC40_COCKPIT_STARBOARD,
  AC40_DIMENSIONS,
  AC40_FOIL_ARM_PORT,
  AC40_FOIL_ARM_STARBOARD,
  AC40_FOIL_WING_PORT,
  AC40_FOIL_WING_STARBOARD,
  AC40_HULL_POLYGON,
  AC40_RUDDER_ELEVATOR,
  AC75_COCKPIT_PORT,
  AC75_COCKPIT_STARBOARD,
  AC75_DIMENSIONS,
  AC75_FOIL_ARM_PORT,
  AC75_FOIL_ARM_STARBOARD,
  AC75_FOIL_WING_PORT,
  AC75_FOIL_WING_STARBOARD,
  AC75_HULL_POLYGON,
  AC75_RUDDER_ELEVATOR,
  computeBoatRenderScale,
  getBoatDimensions,
  type Point2D,
} from './boatModels'
import {
  AC40_KEEP_CLEAR_BORDER,
  AC40_PLATFORM_BORDER,
  AC75_KEEP_CLEAR_BORDER,
  AC75_PLATFORM_BORDER,
  checkBoatsContact,
  computePolygonArea,
  detectFrameContacts,
  getSafetyBorders,
  testPolygonOverlapSAT,
  transformLocalToWorld,
} from '../../engine/contactDetector'
import {
  drawCourseGeometry,
  drawDynamicVessels,
  projectSafetyBorderToScreen,
} from './DynamicVesselLayer'
import { createViewport, type Viewport } from './ViewportMatrix'
import type { Point, ReplayFrame, ReplayManifest } from '../../types/replay'

function loadReplayManifest(): ReplayManifest {
  const livePath = path.resolve(__dirname, '../../../public/data/replays/naples_pr1.json')
  const replayPath = fs.existsSync(livePath)
    ? livePath
    : path.resolve(process.cwd(), 'tests/fixtures/synthetic_replay.json')
  return JSON.parse(fs.readFileSync(replayPath, 'utf8'))
}

/**
 * Creates a mock 2D Canvas Rendering Context that records all operations.
 */
function createInstrumentedCanvasContext() {
  const operations: Array<{ method: string; args: unknown[] }> = []
  const state = {
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 1,
    shadowColor: '',
    shadowBlur: 0,
    lineDash: [] as number[],
  }

  const ctx = {
    get fillStyle() {
      return state.fillStyle
    },
    set fillStyle(val: string) {
      state.fillStyle = val
      operations.push({ method: 'set_fillStyle', args: [val] })
    },
    get strokeStyle() {
      return state.strokeStyle
    },
    set strokeStyle(val: string) {
      state.strokeStyle = val
      operations.push({ method: 'set_strokeStyle', args: [val] })
    },
    get lineWidth() {
      return state.lineWidth
    },
    set lineWidth(val: number) {
      state.lineWidth = val
      operations.push({ method: 'set_lineWidth', args: [val] })
    },
    get shadowColor() {
      return state.shadowColor
    },
    set shadowColor(val: string) {
      state.shadowColor = val
      operations.push({ method: 'set_shadowColor', args: [val] })
    },
    get shadowBlur() {
      return state.shadowBlur
    },
    set shadowBlur(val: number) {
      state.shadowBlur = val
      operations.push({ method: 'set_shadowBlur', args: [val] })
    },
    save: vi.fn(() => operations.push({ method: 'save', args: [] })),
    restore: vi.fn(() => operations.push({ method: 'restore', args: [] })),
    beginPath: vi.fn(() => operations.push({ method: 'beginPath', args: [] })),
    closePath: vi.fn(() => operations.push({ method: 'closePath', args: [] })),
    moveTo: vi.fn((x: number, y: number) => operations.push({ method: 'moveTo', args: [x, y] })),
    lineTo: vi.fn((x: number, y: number) => operations.push({ method: 'lineTo', args: [x, y] })),
    arc: vi.fn((...args: unknown[]) => operations.push({ method: 'arc', args })),
    ellipse: vi.fn((...args: unknown[]) => operations.push({ method: 'ellipse', args })),
    rect: vi.fn((...args: unknown[]) => operations.push({ method: 'rect', args })),
    fill: vi.fn(() => operations.push({ method: 'fill', args: [state.fillStyle] })),
    stroke: vi.fn(() => operations.push({ method: 'stroke', args: [state.strokeStyle] })),
    clearRect: vi.fn((...args: unknown[]) => operations.push({ method: 'clearRect', args })),
    translate: vi.fn((...args: unknown[]) => operations.push({ method: 'translate', args })),
    rotate: vi.fn((...args: unknown[]) => operations.push({ method: 'rotate', args })),
    setLineDash: vi.fn((dash: number[]) => {
      state.lineDash = dash
      operations.push({ method: 'setLineDash', args: [dash] })
    }),
    fillText: vi.fn((text: string, x: number, y: number) =>
      operations.push({ method: 'fillText', args: [text, x, y, state.fillStyle] })
    ),
    measureText: vi.fn((text: string) => ({ width: text.length * 6 })),
  }

  return { ctx: ctx as unknown as CanvasRenderingContext2D, operations, state }
}

/**
 * Calculates perpendicular distance from point p to line segment [a, b].
 */
function distancePointToSegment(p: Point, a: Point, b: Point): number {
  const l2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
  if (l2 === 0) return Math.hypot(p[0] - a[0], p[1] - a[1])
  let t = ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / l2
  t = Math.max(0, Math.min(1, t))
  const projX = a[0] + t * (b[0] - a[0])
  const projY = a[1] + t * (b[1] - a[1])
  return Math.hypot(p[0] - projX, p[1] - projY)
}

/**
 * Tests whether a point is inside or on the boundary of a convex polygon (within tolerance).
 */
function isPointInsideOrOnBoundary(pt: Point, poly: Point[], toleranceM = 1e-3): boolean {
  // Ray casting
  let inside = false
  const [px, py] = pt
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [ix, iy] = poly[i]
    const [jx, jy] = poly[j]
    const intersect = iy > py !== jy > py && px < ((jx - ix) * (py - iy)) / (jy - iy) + ix
    if (intersect) inside = !inside
  }
  if (inside) return true

  // If outside due to boundary precision, check distance to polygon edges
  for (let i = 0; i < poly.length - 1; i++) {
    if (distancePointToSegment(pt, poly[i], poly[i + 1]) <= toleranceM) {
      return true
    }
  }
  return false
}

describe('Challenger M3.1 Empirical Stress Suite — Foiling Geometry & Canvas Rendering', () => {
  const baseReplay = loadReplayManifest()

  // =========================================================================
  // 1. DYNAMIC RENDER SCALING & PIXEL LEGIBILITY FLOOR STRESS TEST
  // =========================================================================
  describe('1. Dynamic Render Scaling & Pixel Legibility Floor Stress Test', () => {
    const TEST_SCALES = [
      0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0,
    ]

    it('verifies AC40 rendered pixel dimension never drops below 22.0 px across all scales (0.001 to 100.0 px/m)', () => {
      for (const scale of TEST_SCALES) {
        const renderScale = computeBoatRenderScale('AC40', scale)
        const renderedLengthPx = renderScale * AC40_DIMENSIONS.totalLengthM

        expect(renderedLengthPx).toBeGreaterThanOrEqual(21.9999)

        const floorScale = AC40_DIMENSIONS.minPixelFloor / AC40_DIMENSIONS.totalLengthM
        if (scale < floorScale) {
          // Below transition, clamped to floor scale
          expect(renderScale).toBeCloseTo(floorScale, 6)
          expect(renderedLengthPx).toBeCloseTo(22.0, 5)
        } else {
          // Above transition, tracks viewport scale 1:1
          expect(renderScale).toBe(scale)
          expect(renderedLengthPx).toBeCloseTo(scale * AC40_DIMENSIONS.totalLengthM, 5)
        }
      }
    })

    it('verifies AC75 rendered pixel dimension never drops below 34.0 px across all scales (0.001 to 100.0 px/m)', () => {
      for (const scale of TEST_SCALES) {
        const renderScale = computeBoatRenderScale('AC75', scale)
        const renderedLengthPx = renderScale * AC75_DIMENSIONS.totalLengthM

        expect(renderedLengthPx).toBeGreaterThanOrEqual(33.9999)

        const floorScale = AC75_DIMENSIONS.minPixelFloor / AC75_DIMENSIONS.totalLengthM
        if (scale < floorScale) {
          expect(renderScale).toBeCloseTo(floorScale, 6)
          expect(renderedLengthPx).toBeCloseTo(34.0, 5)
        } else {
          expect(renderScale).toBe(scale)
          expect(renderedLengthPx).toBeCloseTo(scale * AC75_DIMENSIONS.totalLengthM, 5)
        }
      }
    })

    it('verifies adversarial scale values (zero, negative, ultra-large)', () => {
      // Scale = 0 (completely zoomed out / uninitialized)
      const zeroScaleAc40 = computeBoatRenderScale('AC40', 0)
      expect(zeroScaleAc40 * AC40_DIMENSIONS.totalLengthM).toBeCloseTo(22.0, 5)

      const zeroScaleAc75 = computeBoatRenderScale('AC75', 0)
      expect(zeroScaleAc75 * AC75_DIMENSIONS.totalLengthM).toBeCloseTo(34.0, 5)

      // Negative scale
      const negScale = computeBoatRenderScale('AC40', -50.0)
      expect(negScale * AC40_DIMENSIONS.totalLengthM).toBeCloseTo(22.0, 5)

      // Extreme zoom-in (10,000 px/m)
      const hugeScale = computeBoatRenderScale('AC40', 10000.0)
      expect(hugeScale).toBe(10000.0)
    })

    it('verifies UNKNOWN and undefined boat_class fallback safely to AC40 dimensions', () => {
      const undefinedScale = computeBoatRenderScale(undefined, 0.001)
      expect(undefinedScale * AC40_DIMENSIONS.totalLengthM).toBeCloseTo(22.0, 5)

      const unknownScale = computeBoatRenderScale('UNKNOWN', 0.001)
      expect(unknownScale * AC40_DIMENSIONS.totalLengthM).toBeCloseTo(22.0, 5)
    })
  })

  // =========================================================================
  // 2. PARAMETRIC GEOMETRY SYMMETRY & CANONICAL BOUNDING BOXES
  // =========================================================================
  describe('2. Parametric Geometry Symmetry & Canonical Bounding Boxes', () => {
    function verifyPolygonSymmetry(starboard: Point2D[], port: Point2D[]) {
      expect(starboard.length).toBe(port.length)
      for (let i = 0; i < starboard.length; i++) {
        const [stbdU, stbdV] = starboard[i]
        // Corresponding port point must have u = -stbdU and identical v
        const hasReflectedPoint = port.some(
          ([portU, portV]) => Math.abs(portU + stbdU) < 1e-4 && Math.abs(portV - stbdV) < 1e-4
        )
        expect(hasReflectedPoint).toBe(true)
      }
    }

    it('verifies AC40 hull polygon bilateral reflection symmetry', () => {
      // For every starboard vertex u > 0, an identical mirrored port vertex u < 0 exists
      const stbdPoints = AC40_HULL_POLYGON.filter(([u]) => u > 1e-4)
      const portPoints = AC40_HULL_POLYGON.filter(([u]) => u < -1e-4)
      expect(stbdPoints.length).toBe(portPoints.length)

      for (const [stbdU, stbdV] of stbdPoints) {
        const hasMatch = portPoints.some(
          ([pU, pV]) => Math.abs(pU + stbdU) < 1e-4 && Math.abs(pV - stbdV) < 1e-4
        )
        expect(hasMatch).toBe(true)
      }
    })

    it('verifies AC75 hull polygon bilateral reflection symmetry', () => {
      const stbdPoints = AC75_HULL_POLYGON.filter(([u]) => u > 1e-4)
      const portPoints = AC75_HULL_POLYGON.filter(([u]) => u < -1e-4)
      expect(stbdPoints.length).toBe(portPoints.length)

      for (const [stbdU, stbdV] of stbdPoints) {
        const hasMatch = portPoints.some(
          ([pU, pV]) => Math.abs(pU + stbdU) < 1e-4 && Math.abs(pV - stbdV) < 1e-4
        )
        expect(hasMatch).toBe(true)
      }
    })

    it('verifies AC40 component pair symmetries (cockpits, foil arms, foil wings)', () => {
      verifyPolygonSymmetry(AC40_COCKPIT_STARBOARD, AC40_COCKPIT_PORT)
      verifyPolygonSymmetry(AC40_FOIL_ARM_STARBOARD, AC40_FOIL_ARM_PORT)
      verifyPolygonSymmetry(AC40_FOIL_WING_STARBOARD, AC40_FOIL_WING_PORT)
    })

    it('verifies AC75 component pair symmetries (cockpits, foil arms, foil wings)', () => {
      verifyPolygonSymmetry(AC75_COCKPIT_STARBOARD, AC75_COCKPIT_PORT)
      verifyPolygonSymmetry(AC75_FOIL_ARM_STARBOARD, AC75_FOIL_ARM_PORT)
      verifyPolygonSymmetry(AC75_FOIL_WING_STARBOARD, AC75_FOIL_WING_PORT)
    })

    it('verifies rudder elevators are symmetrically centered on u = 0', () => {
      const ac40MinU = Math.min(...AC40_RUDDER_ELEVATOR.map(([u]) => u))
      const ac40MaxU = Math.max(...AC40_RUDDER_ELEVATOR.map(([u]) => u))
      expect(ac40MinU).toBeCloseTo(-ac40MaxU, 4)

      const ac75MinU = Math.min(...AC75_RUDDER_ELEVATOR.map(([u]) => u))
      const ac75MaxU = Math.max(...AC75_RUDDER_ELEVATOR.map(([u]) => u))
      expect(ac75MinU).toBeCloseTo(-ac75MaxU, 4)
    })
  })

  // =========================================================================
  // 3. RIGID BODY ISOMETRY & HEADING ROTATIONS (0° to 360°)
  // =========================================================================
  describe('3. Rigid Body Isometry & Heading Rotations (0° to 360°)', () => {
    const ROTATION_STEPS = Array.from({ length: 25 }, (_, i) => i * 15) // 0°, 15°, ..., 360°

    it('verifies polygon area and edge lengths remain strictly invariant under all heading rotations', () => {
      const baseAreaPlatform = computePolygonArea(
        AC40_PLATFORM_BORDER.map((p) => [p.x, p.y] as Point)
      )
      const baseAreaKeepClear = computePolygonArea(
        AC40_KEEP_CLEAR_BORDER.map((p) => [p.x, p.y] as Point)
      )

      for (const heading of ROTATION_STEPS) {
        const worldPlatform = transformLocalToWorld(AC40_PLATFORM_BORDER, 1500, -750, heading)
        const worldKeepClear = transformLocalToWorld(AC40_KEEP_CLEAR_BORDER, 1500, -750, heading)

        const areaPlatform = computePolygonArea(worldPlatform)
        const areaKeepClear = computePolygonArea(worldKeepClear)

        expect(Math.abs(areaPlatform - baseAreaPlatform)).toBeLessThan(1e-6)
        expect(Math.abs(areaKeepClear - baseAreaKeepClear)).toBeLessThan(1e-6)

        // Verify edge distances between adjacent vertices are strictly preserved
        for (let i = 0; i < AC40_KEEP_CLEAR_BORDER.length - 1; i++) {
          const origDx = AC40_KEEP_CLEAR_BORDER[i + 1].x - AC40_KEEP_CLEAR_BORDER[i].x
          const origDy = AC40_KEEP_CLEAR_BORDER[i + 1].y - AC40_KEEP_CLEAR_BORDER[i].y
          const origDist = Math.hypot(origDx, origDy)

          const rotDx = worldKeepClear[i + 1][0] - worldKeepClear[i][0]
          const rotDy = worldKeepClear[i + 1][1] - worldKeepClear[i][1]
          const rotDist = Math.hypot(rotDx, rotDy)

          expect(Math.abs(rotDist - origDist)).toBeLessThan(1e-8)
        }
      }
    })

    it('verifies heading vector points in exact clock direction clockwise from North', () => {
      const boatX = 0
      const boatY = 0

      for (const deg of [0, 45, 90, 135, 180, 225, 270, 315]) {
        // Local forward tip is at u = 0, v = 10
        const [tip] = transformLocalToWorld([{ x: 0, y: 10 }], boatX, boatY, deg)
        const rad = (deg * Math.PI) / 180.0
        const expectedX = 10 * Math.sin(rad)
        const expectedY = 10 * Math.cos(rad)

        expect(tip[0]).toBeCloseTo(expectedX, 8)
        expect(tip[1]).toBeCloseTo(expectedY, 8)
      }
    })
  })

  // =========================================================================
  // 4. SAFETY BORDERS GEOMETRIC ENCLOSURE & DYNAMIC ROTATION
  // =========================================================================
  describe('4. Safety Borders Geometric Enclosure & Dynamic Rotation', () => {
    it('verifies AC40 Keep Clear Border strictly encloses Platform Border at all rotations', () => {
      for (let heading = 0; heading < 360; heading += 30) {
        const platWorld = transformLocalToWorld(AC40_PLATFORM_BORDER, 200, 300, heading)
        const keepClearWorld = transformLocalToWorld(AC40_KEEP_CLEAR_BORDER, 200, 300, heading)

        // Every vertex of Platform Border must lie inside or on the boundary of Keep Clear Border
        for (const pt of platWorld) {
          const enclosed = isPointInsideOrOnBoundary(pt, keepClearWorld, 1e-3)
          expect(enclosed).toBe(true)
        }
      }
    })

    it('verifies +2.0m lateral expansion margin of Keep Clear Border over Platform Border', () => {
      // Lateral wing tip comparison:
      // Platform border max x = 5.415m
      // Keep Clear border max x = 7.415m (exactly +2.0m)
      const platMaxX = Math.max(...AC40_PLATFORM_BORDER.map((p) => p.x))
      const keepClearMaxX = Math.max(...AC40_KEEP_CLEAR_BORDER.map((p) => p.x))
      expect(keepClearMaxX - platMaxX).toBeCloseTo(2.0, 4)

      // Transom half-beam comparison:
      // Platform border transom x = 1.5075m
      // Keep Clear border transom x = 3.5075m (exactly +2.0m)
      const platTransomX = AC40_PLATFORM_BORDER.find((p) => Math.abs(p.y) < 1e-4 && p.x > 0)?.x
      const keepTransomX = AC40_KEEP_CLEAR_BORDER.find((p) => Math.abs(p.y) < 1e-4 && p.x > 0)?.x
      expect(keepTransomX! - platTransomX!).toBeCloseTo(2.0, 4)

      // Enclosure area check: Keep Clear Border area is significantly larger than Platform Border
      const platArea = computePolygonArea(AC40_PLATFORM_BORDER.map((p) => [p.x, p.y] as Point))
      const keepArea = computePolygonArea(AC40_KEEP_CLEAR_BORDER.map((p) => [p.x, p.y] as Point))
      expect(keepArea).toBeGreaterThan(platArea * 1.3)
    })
  })

  // =========================================================================
  // 5. CONTINUOUS SAT COLLISION DETECTION & CANVAS RED FLASHING HARNESS
  // =========================================================================
  describe('5. Continuous SAT Collision Detection & Canvas Red Flashing Harness', () => {
    it('detects SAT collision for intersecting boats across various collision geometries', () => {
      // 1. Direct Head-on collision (facing each other, overlapping bows)
      const headOnA = { x: 0, y: 0, heading: 0 } // Bow reaches y = +12.963
      const headOnB = { x: 0, y: 20, heading: 180 } // Bow reaches y = 20 - 12.963 = 7.037
      const headOnResult = checkBoatsContact(headOnA, headOnB)
      expect(headOnResult.hasContact).toBe(true)
      expect(headOnResult.overlapDepthM).toBeGreaterThan(0)
      expect(headOnResult.overlapAreaM2).toBeGreaterThan(0)

      // 2. Parallel Foil-to-Foil collision (lateral separation 12.0m < 2 * 7.415m = 14.83m)
      const lateralA = { x: 0, y: 0, heading: 0 }
      const lateralB = { x: 12.0, y: 0, heading: 0 }
      const lateralResult = checkBoatsContact(lateralA, lateralB)
      expect(lateralResult.hasContact).toBe(true)
      expect(lateralResult.overlapDepthM).toBeGreaterThan(0)
      expect(lateralResult.overlapAreaM2).toBeGreaterThan(0)

      // 3. T-Bone 90° crossing collision
      const tboneA = { x: 0, y: 0, heading: 0 }
      const tboneB = { x: 5.0, y: 6.5, heading: 270 }
      const tboneResult = checkBoatsContact(tboneA, tboneB)
      expect(tboneResult.hasContact).toBe(true)
      expect(tboneResult.overlapDepthM).toBeGreaterThan(0)

      // 4. Safely separated boats (separation > 30m)
      const distantA = { x: 0, y: 0, heading: 0 }
      const distantB = { x: 35.0, y: 0, heading: 0 }
      const distantResult = checkBoatsContact(distantA, distantB)
      expect(distantResult.hasContact).toBe(false)
      expect(distantResult.overlapDepthM).toBe(0)
    })

    it('triggers racing red Keep Clear border flashing in drawDynamicVessels when in contact', () => {
      const { ctx, operations } = createInstrumentedCanvasContext()

      const replay: ReplayManifest = {
        ...baseReplay,
        competitors: [
          { id: 'boat-1', name: 'Boat 1', team_code: 'FRA', color: '#ff80c0' },
          { id: 'boat-2', name: 'Boat 2', team_code: 'NZL', color: '#ff0000' },
        ],
      }

      // Colliding poses: Boat 1 and Boat 2 foil tips overlap (separation 10m)
      const collidingFrame: ReplayFrame = {
        index: 0,
        timestamp: 1000,
        boats: {
          'boat-1': { x: 0, y: 0, heading: 0, sog: 25, cog: 0, vmg: 20, leg: 1 },
          'boat-2': { x: 10, y: 0, heading: 0, sog: 25, cog: 0, vmg: 20, leg: 1 },
        },
      }

      const viewport: Viewport = createViewport(1200, 800, [5, 0], 2.0, 'north', 40)

      // Test with showSafetyBorders = false: Virtual contact MUST STILL flash in racing red!
      drawDynamicVessels(
        ctx,
        1200,
        800,
        replay,
        collidingFrame,
        viewport,
        'off',
        'team',
        null,
        null,
        false // showSafetyBorders is OFF
      )

      // Verify that racing red (#ff3b30) was used for stroke and fill
      const redStrokes = operations.filter(
        (op) => op.method === 'stroke' && (op.args[0] === '#ff3b30' || op.args[0] === '#FF3B30')
      )
      expect(redStrokes.length).toBeGreaterThanOrEqual(2) // Both boats flash Keep Clear Border

      const redFills = operations.filter(
        (op) =>
          op.method === 'fill' &&
          typeof op.args[0] === 'string' &&
          op.args[0].includes('255, 59, 48')
      )
      expect(redFills.length).toBeGreaterThanOrEqual(2)

      // Verify Contact Alert Badge was drawn with fillText
      const badgeTexts = operations.filter(
        (op) =>
          op.method === 'fillText' &&
          typeof op.args[0] === 'string' &&
          op.args[0].includes('VIRTUAL CONTACT')
      )
      expect(badgeTexts.length).toBe(1)
      expect(badgeTexts[0].args[0] as string).toMatch(/VIRTUAL CONTACT · \d+\.\d+m/)

      // Verify boat label displayed [CONTACT]
      const contactLabels = operations.filter(
        (op) =>
          op.method === 'fillText' &&
          typeof op.args[0] === 'string' &&
          op.args[0].includes('[CONTACT]')
      )
      expect(contactLabels.length).toBe(2)
    })

    it('renders normal borders without red flash when boats are separated', () => {
      const { ctx, operations } = createInstrumentedCanvasContext()

      const replay: ReplayManifest = {
        ...baseReplay,
        competitors: [
          { id: 'boat-1', name: 'Boat 1', team_code: 'FRA', color: '#ff80c0' },
          { id: 'boat-2', name: 'Boat 2', team_code: 'NZL', color: '#ff0000' },
        ],
      }

      // Safe separation: 100m apart
      const safeFrame: ReplayFrame = {
        index: 0,
        timestamp: 1000,
        boats: {
          'boat-1': { x: 0, y: 0, heading: 0, sog: 25, cog: 0, vmg: 20, leg: 1 },
          'boat-2': { x: 100, y: 0, heading: 0, sog: 25, cog: 0, vmg: 20, leg: 1 },
        },
      }

      const viewport: Viewport = createViewport(1200, 800, [50, 0], 2.0, 'north', 40)

      // Run with showSafetyBorders = true
      drawDynamicVessels(
        ctx,
        1200,
        800,
        replay,
        safeFrame,
        viewport,
        'off',
        'team',
        null,
        null,
        true
      )

      // Verify NO red strokes or contact badges exist
      const redStrokes = operations.filter(
        (op) => op.method === 'stroke' && (op.args[0] === '#ff3b30' || op.args[0] === '#FF3B30')
      )
      expect(redStrokes.length).toBe(0)

      const badgeTexts = operations.filter(
        (op) =>
          op.method === 'fillText' &&
          typeof op.args[0] === 'string' &&
          op.args[0].includes('VIRTUAL CONTACT')
      )
      expect(badgeTexts.length).toBe(0)

      // Verify amber/yellow Keep Clear borders and cyan Platform borders WERE drawn
      const amberStrokes = operations.filter(
        (op) =>
          op.method === 'stroke' &&
          typeof op.args[0] === 'string' &&
          op.args[0].includes('245, 158, 11')
      )
      expect(amberStrokes.length).toBe(2)

      const platformStrokes = operations.filter(
        (op) =>
          op.method === 'stroke' &&
          typeof op.args[0] === 'string' &&
          op.args[0] === 'rgba(56, 189, 248, 0.55)'
      )
      expect(platformStrokes.length).toBe(2)
    })
  })

  describe('Zero Scale Divergence Invariance Across All Zooms and Headings', () => {
    const boatClasses = ['AC40', 'AC75'] as const
    const testScales = [0.02, 0.05, 0.15, 0.5, 1.0, 4.0, 15.0]
    const testHeadings = [0, 45, 90, 135, 180, 225, 270, 315]

    it.each(boatClasses)(
      'guarantees 1:1 scale alignment between boat hull and safety borders for %s in true metric mode',
      (bClass) => {
        const borders = getSafetyBorders(bClass)
        const hullPoly = bClass === 'AC75' ? AC75_HULL_POLYGON : AC40_HULL_POLYGON
        const maxHullV = Math.max(...hullPoly.map(([, v]) => v))
        const maxPlatformV = Math.max(...borders.platform_border.map((p) => p.y))
        const maxKeepClearV = Math.max(...borders.keep_clear_border.map((p) => p.y))

        // Envelope containment in metric space
        expect(maxPlatformV).toBeGreaterThanOrEqual(maxHullV)
        expect(maxKeepClearV).toBeGreaterThanOrEqual(maxPlatformV)

        for (const zoom of testScales) {
          for (const heading of testHeadings) {
            const state = { x: 50, y: -80, heading }
            const viewport: Viewport = createViewport(1000, 700, [0, 0], zoom, 'north', 0)
            const renderScale = computeBoatRenderScale(bClass, zoom, 'true')

            // In true mode, renderScale MUST exactly match viewport scale
            expect(renderScale).toBe(zoom)

            const platformScreen = projectSafetyBorderToScreen(
              state,
              viewport,
              borders.platform_border,
              renderScale
            )
            const keepClearScreen = projectSafetyBorderToScreen(
              state,
              viewport,
              borders.keep_clear_border,
              renderScale
            )

            expect(platformScreen.length).toBe(borders.platform_border.length)
            expect(keepClearScreen.length).toBe(borders.keep_clear_border.length)

            // Center-to-vertex screen distance ratio must equal renderScale
            const center = [500 + 50 * zoom, 350 - -80 * zoom]
            for (let i = 0; i < borders.platform_border.length; i++) {
              const bp = borders.platform_border[i]
              const metricDist = Math.hypot(bp.x, bp.y)
              const screenDist = Math.hypot(
                platformScreen[i][0] - center[0],
                platformScreen[i][1] - center[1]
              )
              expect(screenDist).toBeCloseTo(metricDist * renderScale, 4)
            }
          }
        }
      }
    )

    it.each(boatClasses)(
      'guarantees concentric scaling without divergence for %s in enhanced mode',
      (bClass) => {
        const borders = getSafetyBorders(bClass)
        const wideZoom = 0.03
        const state = { x: 100, y: 200, heading: 45 }
        const viewport: Viewport = createViewport(1000, 700, [100, 200], wideZoom, 'course', 40)
        const renderScale = computeBoatRenderScale(bClass, wideZoom, 'enhanced')

        expect(renderScale).toBeGreaterThan(wideZoom) // Enhanced scale floor active

        const platformScreen = projectSafetyBorderToScreen(
          state,
          viewport,
          borders.platform_border,
          renderScale
        )
        const keepClearScreen = projectSafetyBorderToScreen(
          state,
          viewport,
          borders.keep_clear_border,
          renderScale
        )

        const center = [500, 350] // Camera centered on boat
        // Verify both borders scale by the exact same renderScale multiplier
        for (let i = 0; i < borders.platform_border.length; i++) {
          const bp = borders.platform_border[i]
          const metricDist = Math.hypot(bp.x, bp.y)
          const screenDist = Math.hypot(
            platformScreen[i][0] - center[0],
            platformScreen[i][1] - center[1]
          )
          expect(screenDist).toBeCloseTo(metricDist * renderScale, 4)
        }

        for (let i = 0; i < borders.keep_clear_border.length; i++) {
          const kp = borders.keep_clear_border[i]
          const metricDist = Math.hypot(kp.x, kp.y)
          const screenDist = Math.hypot(
            keepClearScreen[i][0] - center[0],
            keepClearScreen[i][1] - center[1]
          )
          expect(screenDist).toBeCloseTo(metricDist * renderScale, 4)
        }
      }
    )
  })

  describe('SAT Virtual Contact Physics Invariance', () => {
    it('evaluates contact in physical metric space completely invariant to screen viewport', () => {
      // Two AC40 boats at known overlapping pose
      const boatA = { x: 0, y: 0, heading: 0 }
      const boatB = { x: 5, y: 5, heading: 90 }

      const baseline = checkBoatsContact(boatA, boatB, AC40_KEEP_CLEAR_BORDER)
      expect(baseline.hasContact).toBe(true)
      expect(baseline.overlapDepthM).toBeGreaterThan(0)
      expect(baseline.overlapAreaM2).toBeGreaterThan(0)

      // Check contact detection across different viewport zooms
      const zooms = [0.01, 0.05, 0.2, 1.0, 10.0, 100.0]
      for (const zoom of zooms) {
        const frameBoats = {
          'boat-1': { ...boatA, sog: 25, cog: 0, vmg: 20, leg: 1 },
          'boat-2': { ...boatB, sog: 25, cog: 90, vmg: 20, leg: 1 },
        }
        const contacts = detectFrameContacts(frameBoats, AC40_KEEP_CLEAR_BORDER)
        expect(contacts).toHaveLength(1)
        expect(contacts[0].distanceM).toBeCloseTo(baseline.distanceM, 8)
        expect(contacts[0].overlapDepthM).toBeCloseTo(baseline.overlapDepthM, 8)
        expect(contacts[0].overlapAreaM2).toBeCloseTo(baseline.overlapAreaM2, 8)
      }
    })

    it('evaluates AC75 contact using AC75 canonical safety borders', () => {
      const borders = getSafetyBorders('AC75')
      expect(borders.platform_border).toBe(AC75_PLATFORM_BORDER)
      expect(borders.keep_clear_border).toBe(AC75_KEEP_CLEAR_BORDER)

      // AC75 boats separated by 35m (outside AC40 30m broadphase, but within AC75 envelope overlap reach)
      const boatA = { x: 0, y: 0, heading: 0 }
      const boatB = { x: 0, y: 35, heading: 180 } // Bows pointing at each other: bowsprit tips at 21.5m and 35 - 21.5 = 13.5m!

      const ac75Contact = checkBoatsContact(boatA, boatB, AC75_KEEP_CLEAR_BORDER)
      expect(ac75Contact.hasContact).toBe(true)
      expect(ac75Contact.overlapDepthM).toBeGreaterThan(0)

      // Two AC75 boats 60m apart should NOT touch
      const farB = { x: 0, y: 60, heading: 180 }
      const noContact = checkBoatsContact(boatA, farB, AC75_KEEP_CLEAR_BORDER)
      expect(noContact.hasContact).toBe(false)
    })
  })

  describe('Dynamic Mark Beacons & Sequence Lines Rendering (RM1 - RM8, IRM, HAZ)', () => {
    it('renders all marks RM1 through RM8, IRM, HAZ with distinct beacon styling', () => {
      const labels: string[] = []
      const arcs: Array<[number, number, number]> = []
      const strokes: string[] = []
      const fills: string[] = []

      const mockCtx = {
        save: vi.fn(),
        restore: vi.fn(),
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        closePath: vi.fn(),
        rect: vi.fn(),
        setLineDash: vi.fn(),
        measureText: (text: string) => ({ width: text.length * 6 }),
        fillText: (text: string) => labels.push(text),
        arc: (x: number, y: number, r: number) => arcs.push([x, y, r]),
        stroke: vi.fn(),
        fill: vi.fn(),
        set strokeStyle(val: string) {
          strokes.push(val)
        },
        set fillStyle(val: string) {
          fills.push(val)
        },
      } as unknown as CanvasRenderingContext2D

      const testReplay = {
        chronology: { gun_time: 1000 },
        course: {
          marks: {
            RM1: { name: 'Mark 1', target: [0, 500] },
            RM2: { name: 'Mark 2', target: [40, 500] },
            RM3: { name: 'Mark 3', target: [0, 0] },
            RM4: { name: 'Mark 4', target: [40, 0] },
            RM5: { name: 'Mark 5', target: [-50, 250] },
            RM6: { name: 'Mark 6', target: [50, 250] },
            RM7: { name: 'Mark 7', target: [-20, 0] },
            RM8: { name: 'Mark 8', target: [20, 0] },
            IRM1: { name: 'Intermediate 1', target: [0, 250], role: 'INTERMEDIATE' },
            HAZ1: { name: 'Hazard 1', target: [-100, 100], role: 'HAZARD' },
          },
          sequences: [
            { leg: 0, port_mark: 'RM3', starboard_mark: 'RM7', gate_type: 'START' },
            { leg: 1, port_mark: 'RM1', starboard_mark: 'RM2', gate_type: 'TOP' },
            { leg: 2, port_mark: 'RM8', starboard_mark: 'RM6', gate_type: 'BOTTOM' },
            { leg: 3, port_mark: 'RM4', starboard_mark: 'RM5', gate_type: 'TOP' },
            { leg: 4, port_mark: 'RM3', starboard_mark: 'RM7', gate_type: 'FINISH' },
          ],
          start_marks: { port: 'RM3', starboard: 'RM7' },
        },
      } as unknown as ReplayManifest

      const frame: ReplayFrame = {
        index: 0,
        timestamp: 500,
        boats: { boat: { leg: 0 } as any },
        marks: {
          RM3: { x: 2, y: 1 },
        },
      }

      const viewport = createViewport(800, 600, [0, 250], 0.5, 'north', 0)
      drawCourseGeometry(mockCtx, testReplay, frame, viewport)

      // Verify all mark codes are rendered as label badges
      expect(labels).toContain('RM1')
      expect(labels).toContain('RM2')
      expect(labels).toContain('RM3')
      expect(labels).toContain('RM4')
      expect(labels).toContain('RM5')
      expect(labels).toContain('RM6')
      expect(labels).toContain('RM7')
      expect(labels).toContain('RM8')
      expect(labels).toContain('IRM1')
      expect(labels).toContain('HAZ1')
      expect(labels).toContain('START LINE')

      // Verify each mark has both an outer beacon halo (radius 7.5) and a solid core (radius 4.5)
      const haloArcs = arcs.filter(([, , r]) => r === 7.5)
      const coreArcs = arcs.filter(([, , r]) => r === 4.5)
      expect(haloArcs.length).toBeGreaterThanOrEqual(10)
      expect(coreArcs.length).toBeGreaterThanOrEqual(10)
    })
  })
})
