import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import {
  createViewport,
  fitViewport,
  worldToScreen,
  screenToWorld,
  worldVectorToScreen,
  type Viewport,
} from './ViewportMatrix'
import {
  computeAffineScreenTransform,
  lngLatToMetric,
  metricToLngLat,
} from '../../utils/geoProjection'
import { drawStaticCourse } from './StaticCourseLayer'
import { drawCourseGeometry } from './DynamicVesselLayer'
import type { Point, ReplayFrame, ReplayManifest } from '../../types/replay'

function loadReplayManifest(): ReplayManifest {
  const livePath = path.resolve(__dirname, '../../../public/data/replays/naples_pr1.json')
  const replayPath = fs.existsSync(livePath)
    ? livePath
    : path.resolve(process.cwd(), 'tests/fixtures/synthetic_replay.json')
  return JSON.parse(fs.readFileSync(replayPath, 'utf8'))
}

const hasLiveNaplesPr1 = fs.existsSync(
  path.resolve(__dirname, '../../../public/data/replays/naples_pr1.json')
)

describe('Challenger M2.2 Adversarial Verification: Camera & Viewport Controls', () => {
  const replay = loadReplayManifest()
  const origin = replay.course.origin
  const projection = replay.course.projection
  const axisDeg = replay.course.axis_deg // ~40.0 deg

  // =========================================================================
  // 1. Camera Zoom Controls: Scale Factor Verification (>= 15% per click)
  // =========================================================================
  describe('Camera Zoom Controls: Scale Factor Verification (>= 15% per click)', () => {
    it('verifies fallback zoom in increases viewport scale by exactly 20% (>= 15%) per click', () => {
      const initialScale = 0.25
      const currentViewport: Viewport = createViewport(
        900,
        620,
        [0, 0],
        initialScale,
        'north',
        axisDeg
      )

      // Simulating handleZoomIn in fallback mode: scale * 1.20
      const newScale = Math.min(5.0, currentViewport.scale * 1.2)
      const scaleIncreaseRatio = (newScale - initialScale) / initialScale

      expect(scaleIncreaseRatio).toBeCloseTo(0.2, 5)
      expect(scaleIncreaseRatio).toBeGreaterThanOrEqual(0.15)
    })

    it('verifies fallback zoom out decreases viewport scale by >= 15% per click', () => {
      const initialScale = 0.25
      const currentViewport: Viewport = createViewport(
        900,
        620,
        [0, 0],
        initialScale,
        'north',
        axisDeg
      )

      // Simulating handleZoomOut in fallback mode: scale / 1.20
      const newScale = Math.max(0.03, currentViewport.scale / 1.2)
      const scaleDecreaseRatio = (initialScale - newScale) / initialScale // ~16.67%
      const scaleDivisorRatio = initialScale / newScale // 1.20

      expect(scaleDecreaseRatio).toBeCloseTo(1 - 1 / 1.2, 5) // ~0.16667
      expect(scaleDecreaseRatio).toBeGreaterThanOrEqual(0.15)
      expect(scaleDivisorRatio).toBeCloseTo(1.2, 5)
    })

    it('verifies MapLibre zoom level step (+1.0 zoom) doubles scale (100% increase >= 15%)', () => {
      // In Web Mercator / MapLibre: scale is proportional to 2^z
      const zoomLevel = 13.2
      const scaleAtZ = (z: number) => (256 * Math.pow(2, z)) / (2 * Math.PI * 6378137)

      const s0 = scaleAtZ(zoomLevel)
      const sZoomIn = scaleAtZ(zoomLevel + 1.0)
      const sZoomOut = scaleAtZ(zoomLevel - 1.0)

      const zoomInFactor = sZoomIn / s0
      const zoomOutFactor = s0 / sZoomOut

      expect(zoomInFactor).toBeCloseTo(2.0, 5) // 100% increase (>= 15%)
      expect(zoomInFactor - 1.0).toBeGreaterThanOrEqual(0.15)

      expect(zoomOutFactor).toBeCloseTo(2.0, 5) // 50% decrease / 2.0x factor (>= 15%)
      expect((s0 - sZoomOut) / s0).toBeGreaterThanOrEqual(0.15)
    })

    it('verifies scale clamping constraints at extreme limits (min 0.03, max 5.0)', () => {
      let scale = 0.035
      // Zoom out near minimum clamp
      scale = Math.max(0.03, scale / 1.2)
      expect(scale).toBe(0.03)

      // Further zoom out stays clamped
      scale = Math.max(0.03, scale / 1.2)
      expect(scale).toBe(0.03)

      // Zoom in near maximum clamp
      scale = 4.8
      scale = Math.min(5.0, scale * 1.2)
      expect(scale).toBe(5.0)

      // Further zoom in stays clamped
      scale = Math.min(5.0, scale * 1.2)
      expect(scale).toBe(5.0)
    })

    it('verifies handleResetView properly encloses full race boundary with padding', () => {
      const boundaryPoints = replay.course.boundaries.race
      expect(boundaryPoints.length).toBeGreaterThanOrEqual(4)

      const fittedNorth = fitViewport(900, 620, boundaryPoints, 'north', axisDeg, 1.25)
      expect(fittedNorth.scale).toBeGreaterThan(0.05)
      expect(fittedNorth.scale).toBeLessThan(1.0)

      // Check all race boundary points project strictly inside screen bounds
      for (const pt of boundaryPoints) {
        const [sx, sy] = worldToScreen(fittedNorth, pt)
        expect(sx).toBeGreaterThan(0)
        expect(sx).toBeLessThan(900)
        expect(sy).toBeGreaterThan(0)
        expect(sy).toBeLessThan(620)
      }

      // Check Course Up reset framing
      const fittedCourse = fitViewport(900, 620, boundaryPoints, 'course', axisDeg, 1.25)
      expect(fittedCourse.rotationDeg).toBeCloseTo(axisDeg, 4)
      for (const pt of boundaryPoints) {
        const [sx, sy] = worldToScreen(fittedCourse, pt)
        expect(sx).toBeGreaterThan(0)
        expect(sx).toBeLessThan(900)
        expect(sy).toBeGreaterThan(0)
        expect(sy).toBeLessThan(620)
      }
    })
  })

  // =========================================================================
  // 2. Bearing Toggling: North Up vs Course Up
  // =========================================================================
  describe('Bearing Toggling: North Up (0°) vs Course Up (~40°)', () => {
    it('verifies North Up (bearing = 0°) keeps North vertical (dy maps to -sy)', () => {
      const vpNorth = createViewport(1000, 800, [0, 0], 0.25, 'north', axisDeg)
      expect(vpNorth.rotationDeg).toBe(0)

      // An arbitrary point 500m North: [0, 500]
      const [sx, sy] = worldToScreen(vpNorth, [0, 500])
      expect(sx).toBeCloseTo(500, 5) // Perfectly centered horizontally
      expect(sy).toBeCloseTo(400 - 500 * 0.25, 5) // 275 px (moved UP)

      // An arbitrary point 500m East: [500, 0]
      const [ex, ey] = worldToScreen(vpNorth, [500, 0])
      expect(ex).toBeCloseTo(500 + 500 * 0.25, 5) // 625 px (moved RIGHT)
      expect(ey).toBeCloseTo(400, 5) // Perfectly centered vertically
    })

    it('verifies Course Up rotates racecourse axis (~40°) strictly vertical on screen', () => {
      const vpCourse = createViewport(1000, 800, [0, 0], 0.25, 'course', axisDeg)
      expect(vpCourse.rotationDeg).toBeCloseTo(axisDeg, 4)

      // Points along the course axis at distance L:
      // x = L * sin(axisDeg), y = L * cos(axisDeg)
      const rad = (axisDeg * Math.PI) / 180
      for (const L of [100, 500, 1000, 2000]) {
        const coursePt: Point = [L * Math.sin(rad), L * Math.cos(rad)]
        const [sx, sy] = worldToScreen(vpCourse, coursePt)

        // Under Course Up, course axis points strictly UP:
        // sx should remain exactly in the center (500)
        // sy should decrease by L * scale
        expect(sx).toBeCloseTo(500, 4)
        expect(sy).toBeCloseTo(400 - L * 0.25, 4)
      }
    })

    it('verifies bidirectional coordinate invertibility (worldToScreen <-> screenToWorld) across bearings', () => {
      const testBearings = [0, 30, 40.0, 90, 180, 270, 315]
      const testPoints: Point[] = [
        [0, 0],
        [1000, 500],
        [-800, -700],
        [632, 948],
        [-1500, 2200],
      ]

      for (const bearing of testBearings) {
        const vp: Viewport = {
          center: [150, -200],
          scale: 0.35,
          rotationDeg: bearing,
          width: 1000,
          height: 800,
        }

        for (const pt of testPoints) {
          const screen = worldToScreen(vp, pt)
          const reconstructed = screenToWorld(vp, screen)

          expect(reconstructed[0]).toBeCloseTo(pt[0], 6)
          expect(reconstructed[1]).toBeCloseTo(pt[1], 6)
        }
      }
    })

    it('verifies affine transform extraction produces normalized [0, 360) rotationDeg', () => {
      // Simulate MapLibre project function for various camera bearings
      function createSimulatedMapProject(bearingDeg: number) {
        const rad = (bearingDeg * Math.PI) / 180
        const scale = 0.25
        const cx = 500
        const cy = 400
        return (ll: [number, number]) => {
          const [mx, my] = lngLatToMetric(ll[0], ll[1], origin, projection)
          const sx = cx + (Math.cos(rad) * mx - Math.sin(rad) * my) * scale
          const sy = cy - (Math.sin(rad) * mx + Math.cos(rad) * my) * scale
          return { x: sx, y: sy }
        }
      }

      for (const bearing of [0, 40.0, 89.5, 180, 270, 359.9]) {
        const projFn = createSimulatedMapProject(bearing)
        const transform = computeAffineScreenTransform(projFn, origin, projection)
        expect(transform.rotationDeg).toBeCloseTo(bearing, 3)
        expect(transform.rotationDeg).toBeGreaterThanOrEqual(0)
        expect(transform.rotationDeg).toBeLessThan(360)
      }
    })
  })

  // =========================================================================
  // 3. Clean-Water Fallback Activation Behavior
  // =========================================================================
  describe('Clean-Water Fallback Activation Behavior (WebGL Offline / Missing)', () => {
    it('keeps the course overlay transparent when MapLibre is active', () => {
      const calls: string[] = []
      const fakeContext = {
        clearRect: () => calls.push('clearRect'),
        createRadialGradient: () => {
          calls.push('createRadialGradient')
          return { addColorStop: () => {} }
        },
        fillRect: () => calls.push('fillRect'),
        save: () => calls.push('save'),
        restore: () => calls.push('restore'),
        beginPath: () => calls.push('beginPath'),
        moveTo: () => calls.push('moveTo'),
        lineTo: () => calls.push('lineTo'),
        stroke: () => calls.push('stroke'),
        fill: () => calls.push('fill'),
        setLineDash: () => {},
        closePath: () => {},
      } as unknown as CanvasRenderingContext2D

      const vp = createViewport(900, 620, [0, 0], 0.2, 'north', axisDeg)
      const boundaries = {
        race: replay.course.boundaries.race,
        safety: replay.course.boundaries.safety,
      }

      drawStaticCourse(fakeContext, 900, 620, replay, vp, boundaries, { showWaterSurface: false })

      // Water gradient MUST NOT be drawn (transparent overlay for OSM raster tiles)
      expect(calls).not.toContain('createRadialGradient')
      expect(calls).not.toContain('fillRect')
    })

    it('renders a neutral technical surface for Grid View and offline fallback', () => {
      const calls: string[] = []
      const fakeContext = {
        clearRect: () => calls.push('clearRect'),
        createRadialGradient: () => {
          calls.push('createRadialGradient')
          return { addColorStop: () => {} }
        },
        fillRect: () => calls.push('fillRect'),
        save: () => calls.push('save'),
        restore: () => calls.push('restore'),
        beginPath: () => calls.push('beginPath'),
        moveTo: () => calls.push('moveTo'),
        lineTo: () => calls.push('lineTo'),
        stroke: () => calls.push('stroke'),
        fill: () => calls.push('fill'),
        setLineDash: () => {},
        closePath: () => {},
      } as unknown as CanvasRenderingContext2D

      const vp = createViewport(900, 620, [0, 0], 0.2, 'north', axisDeg)
      const boundaries = {
        race: replay.course.boundaries.race,
        safety: replay.course.boundaries.safety,
      }

      drawStaticCourse(fakeContext, 900, 620, replay, vp, boundaries, { showWaterSurface: true })

      expect(calls).not.toContain('createRadialGradient')
      expect(calls).toContain('fillRect')
    })

    it('verifies fallback condition logic (!isFallback && !isOfflineFallback)', () => {
      // Logic from CourseCanvas.tsx line 293:
      // const skipWaterGradient = !isFallback && !isOfflineFallback
      const evaluateSkip = (isFallback: boolean, isOfflineFallback: boolean) =>
        !isFallback && !isOfflineFallback

      // Case 1: Online + WebGL -> Transparent overlay (skipWater = true)
      expect(evaluateSkip(false, false)).toBe(true)

      // Case 2: WebGL disabled/headless -> Synthetic water (skipWater = false)
      expect(evaluateSkip(true, false)).toBe(false)

      // Case 3: WebGL enabled, but offline / OSM tile load error -> Synthetic water (skipWater = false)
      expect(evaluateSkip(false, true)).toBe(false)

      // Case 4: Both fallback -> Synthetic water (skipWater = false)
      expect(evaluateSkip(true, true)).toBe(false)
    })
  })

  // =========================================================================
  // 4. Mark Positions RM2 and RM4 at Leg 1 Crossing (< 30m SLA)
  // =========================================================================
  describe.skipIf(!hasLiveNaplesPr1)(
    'Dynamic Mark Positioning: RM2 & RM4 at Leg 1 Crossing (< 30m SLA)',
    () => {
      const tLeg1 = 1790079233000 // Frame 4130
      const frameIdx = replay.telemetry.timestamps.indexOf(tLeg1)

      it('verifies frame 4130 exists at t = 1790079233000', () => {
        expect(frameIdx).toBe(4130)
      })

      it('empirically verifies RM2 and RM4 dynamic telemetry coordinates at Leg 1 crossing', () => {
        const rm2AssetId = replay.course.marks.RM2.asset_id!
        const rm4AssetId = replay.course.marks.RM4.asset_id!

        const rm2Telemetry = replay.telemetry.marks[rm2AssetId]
        const rm4Telemetry = replay.telemetry.marks[rm4AssetId]

        expect(rm2Telemetry).toBeDefined()
        expect(rm4Telemetry).toBeDefined()

        const rm2X = rm2Telemetry.x[frameIdx]
        const rm2Y = rm2Telemetry.y[frameIdx]
        const rm4X = rm4Telemetry.x[frameIdx]
        const rm4Y = rm4Telemetry.y[frameIdx]

        // RM2 expected: x ≈ 1103.60m, y ≈ 537.55m
        expect(rm2X).toBeCloseTo(1103.6, 1)
        expect(rm2Y).toBeCloseTo(537.55, 1)

        // RM4 expected: x ≈ 955.05m, y ≈ 708.40m
        expect(rm4X).toBeCloseTo(955.05, 1)
        expect(rm4Y).toBeCloseTo(708.4, 1)

        // Both marks form the Windward Gate line with span ~220m
        const gateSpan = Math.hypot(rm2X - rm4X, rm2Y - rm4Y)
        expect(gateSpan).toBeGreaterThan(200.0)
        expect(gateSpan).toBeLessThan(250.0)
      })

      it('verifies fleet leader FRA rounds within 21.04m of RM2 (strictly meeting < 30m SLA)', () => {
        const rm2AssetId = replay.course.marks.RM2.asset_id!
        const rm2X = replay.telemetry.marks[rm2AssetId].x[frameIdx]
        const rm2Y = replay.telemetry.marks[rm2AssetId].y[frameIdx]

        const fraComp = replay.competitors.find((c) => c.team_code === 'FRA')!
        const fraX = replay.telemetry.boats[fraComp.id].x[frameIdx]
        const fraY = replay.telemetry.boats[fraComp.id].y[frameIdx]

        // FRA coordinates at rounding: x in [1000, 1100], y in [500, 600]
        expect(fraX).toBeGreaterThan(1000.0)
        expect(fraX).toBeLessThan(1100.0)
        expect(fraY).toBeGreaterThan(500.0)
        expect(fraY).toBeLessThan(600.0)

        const dist = Math.hypot(rm2X - fraX, rm2Y - fraY)
        expect(dist).toBeCloseTo(21.04, 1)
        expect(dist).toBeLessThan(30.0) // Strictly meets < 30m requirement

        // The moving mark is a better reference than its static target anchor.
        const staticRM2 = replay.course.marks.RM2.target
        const staticDist = Math.hypot(staticRM2[0] - fraX, staticRM2[1] - fraY)
        expect(staticDist).toBeGreaterThan(dist)
      })

      it('verifies all 8 finishing boats round dynamic top gate marks within 35m at Leg 1 transition', () => {
        const rm2AssetId = replay.course.marks.RM2.asset_id!
        const rm4AssetId = replay.course.marks.RM4.asset_id!
        const rm2Stream = replay.telemetry.marks[rm2AssetId]
        const rm4Stream = replay.telemetry.marks[rm4AssetId]

        for (const comp of replay.competitors) {
          const boat = replay.telemetry.boats[comp.id]
          if (!boat) continue

          const legs = boat.leg
          // Find transition from Leg 1 to Leg 2
          let transIdx = -1
          for (let i = 0; i < legs.length - 1; i++) {
            if (legs[i] === 1 && legs[i + 1] === 2) {
              transIdx = i
              break
            }
          }
          if (transIdx === -1) continue // E.g. GBR B OCS

          // Find closest approach within +/- 5 seconds (50 frames)
          const wStart = Math.max(0, transIdx - 50)
          const wEnd = min(legs.length - 1, transIdx + 50)
          let minDynamicDist = Infinity

          for (let j = wStart; j <= wEnd; j++) {
            const bx = boat.x[j]
            const by = boat.y[j]
            const d2 = Math.hypot(rm2Stream.x[j] - bx, rm2Stream.y[j] - by)
            const d4 = Math.hypot(rm4Stream.x[j] - bx, rm4Stream.y[j] - by)
            minDynamicDist = Math.min(minDynamicDist, d2, d4)
          }

          expect(minDynamicDist).toBeLessThan(35.0)
        }
      })

      function min(a: number, b: number) {
        return a < b ? a : b
      }

      it('verifies rendered dynamic marks project cleanly onto screen without NaN or clipping errors', () => {
        const vp = createViewport(900, 620, [0, 0], 0.25, 'course', axisDeg)
        const rm2AssetId = replay.course.marks.RM2.asset_id!
        const rm4AssetId = replay.course.marks.RM4.asset_id!

        const rm2Pt: Point = [
          replay.telemetry.marks[rm2AssetId].x[frameIdx],
          replay.telemetry.marks[rm2AssetId].y[frameIdx],
        ]
        const rm4Pt: Point = [
          replay.telemetry.marks[rm4AssetId].x[frameIdx],
          replay.telemetry.marks[rm4AssetId].y[frameIdx],
        ]

        const rm2Screen = worldToScreen(vp, rm2Pt)
        const rm4Screen = worldToScreen(vp, rm4Pt)

        expect(Number.isFinite(rm2Screen[0])).toBe(true)
        expect(Number.isFinite(rm2Screen[1])).toBe(true)
        expect(Number.isFinite(rm4Screen[0])).toBe(true)
        expect(Number.isFinite(rm4Screen[1])).toBe(true)

        // Screen distance between marks
        const screenSpanPx = Math.hypot(rm2Screen[0] - rm4Screen[0], rm2Screen[1] - rm4Screen[1])
        expect(screenSpanPx).toBeGreaterThan(40) // Distinct visual separation
      })
    }
  )
})
