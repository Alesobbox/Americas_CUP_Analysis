import { describe, it, expect } from 'vitest'
import {
  metricToLngLat,
  lngLatToMetric,
  computeAffineMatrixFromScreenPoints,
  computeAffineScreenTransform,
  type GeoOrigin,
  type GeoProjectionParams,
  type ScreenPoint,
} from './geoProjection'
import type { Point } from '../types/replay'

// Naples race course origin and projection parameters from official telemetry
const NAPLES_ORIGIN: GeoOrigin = {
  lat: 40.80948067,
  lon: 14.23726898,
}

const NAPLES_PROJECTION: GeoProjectionParams = {
  k_lat: 111047.746,
  k_lon: 84374.839,
}

const WGS84_A = 6378137.0 // Earth equatorial radius in metres

/**
 * Ground-truth Equirectangular camera projection model.
 * In this projection, geographic coordinates are linear in metric space.
 */
function createEquirectangularCamera(
  centerMetric: Point,
  scalePxPerM: number,
  bearingDeg: number,
  viewportWidth = 1920,
  viewportHeight = 1080,
  origin = NAPLES_ORIGIN,
  projection = NAPLES_PROJECTION
) {
  const rad = (bearingDeg * Math.PI) / 180
  const cx = viewportWidth / 2
  const cy = viewportHeight / 2
  const cosB = Math.cos(rad)
  const sinB = Math.sin(rad)

  return (lngLat: [number, number]): ScreenPoint => {
    const [mx, my] = lngLatToMetric(lngLat[0], lngLat[1], origin, projection)
    const dx = mx - centerMetric[0]
    const dy = my - centerMetric[1]

    // Clockwise camera bearing rotates world counter-clockwise
    const screenX = cx + (cosB * dx - sinB * dy) * scalePxPerM
    const screenY = cy - (sinB * dx + cosB * dy) * scalePxPerM
    return { x: screenX, y: screenY }
  }
}

/**
 * Ground-truth Spherical Web Mercator camera projection model (MapLibre GL JS native).
 * Models MapLibre's exact map.project(lngLat) behaviour without DOM or WebGL requirements.
 */
function createSphericalMercatorCamera(
  centerLngLat: [number, number],
  scalePxPerMAtCenter: number,
  bearingDeg: number,
  viewportWidth = 1920,
  viewportHeight = 1080
) {
  const rad = (bearingDeg * Math.PI) / 180
  const cx = viewportWidth / 2
  const cy = viewportHeight / 2
  const cosB = Math.cos(rad)
  const sinB = Math.sin(rad)

  // Circumference of latitude parallel at center
  const centerLatRad = (centerLngLat[1] * Math.PI) / 180
  const parallelCircumferenceM = 2 * Math.PI * WGS84_A * Math.cos(centerLatRad)
  // Total world pixel width = scale * parallel circumference
  const worldSizePx = scalePxPerMAtCenter * parallelCircumferenceM

  // Mercator tile coordinates [0, 1]
  const mercatorU = (lon: number): number => (lon + 180) / 360
  const mercatorV = (lat: number): number => {
    const clampedLat = Math.max(-85.05112878, Math.min(85.05112878, lat))
    const latR = (clampedLat * Math.PI) / 180
    return 0.5 - Math.log(Math.tan(Math.PI / 4 + latR / 2)) / (2 * Math.PI)
  }

  const u0 = mercatorU(centerLngLat[0])
  const v0 = mercatorV(centerLngLat[1])

  return (lngLat: [number, number]): ScreenPoint => {
    const u = mercatorU(lngLat[0])
    const v = mercatorV(lngLat[1])
    const dx = (u - u0) * worldSizePx
    const dy = (v - v0) * worldSizePx

    // Bearing rotation
    const screenX = cx + (cosB * dx - sinB * dy)
    const screenY = cy + (sinB * dx + cosB * dy)
    return { x: screenX, y: screenY }
  }
}

/**
 * Deterministic pseudo-random number generator (LCG) for reproducible test cases.
 */
function createDeterministicRng(seed = 42) {
  let s = seed
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296
    return s / 4294967296
  }
}

describe('Challenger M2.1 Empirical Stress Suite — Geographic Projection & Affine Synchronizer', () => {
  // Mission required rotation angles
  const ROTATION_ANGLES = [0, 30, 45, 90, 180, 270, 359]
  // Mission required scale ranges: extreme zoom-out (0.05 px/m) to extreme zoom-in (50.0 px/m)
  const SCALE_LEVELS = [0.05, 0.1, 0.25, 0.5, 1.0, 5.0, 10.0, 50.0]

  describe('1. Roundtrip Metric <-> WGS84 Geodetic Precision (SLA < 10^-6 m)', () => {
    it('verifies roundtrip precision across 10,000 random points within regatta envelope [-3000, +3000] m', () => {
      const rng = createDeterministicRng(1001)
      let maxErrorM = 0
      let totalErrorM = 0
      const pointCount = 10000

      for (let i = 0; i < pointCount; i++) {
        const x = (rng() * 2 - 1) * 3000
        const y = (rng() * 2 - 1) * 3000

        const [lon, lat] = metricToLngLat(x, y, NAPLES_ORIGIN, NAPLES_PROJECTION)
        const [rx, ry] = lngLatToMetric(lon, lat, NAPLES_ORIGIN, NAPLES_PROJECTION)

        const err = Math.hypot(rx - x, ry - y)
        if (err > maxErrorM) maxErrorM = err
        totalErrorM += err

        expect(err).toBeLessThan(1e-6) // Required SLA: < 10^-6 m
      }

      const avgErrorM = totalErrorM / pointCount
      console.log(`[Metric Roundtrip] 10,000 pts: Max error = ${maxErrorM.toExponential(3)} m, Avg error = ${avgErrorM.toExponential(3)} m`)
      expect(maxErrorM).toBeLessThan(1e-6)
    })

    it('verifies roundtrip precision on boundary extremities up to [-10000, +10000] m', () => {
      const extremePoints: Point[] = [
        [0, 0],
        [3000, 3000],
        [-3000, 3000],
        [3000, -3000],
        [-3000, -3000],
        [10000, 10000],
        [-10000, -10000],
        [10000, -10000],
        [-10000, 10000],
        [0.001, -0.001],
      ]

      for (const [x, y] of extremePoints) {
        const [lon, lat] = metricToLngLat(x, y, NAPLES_ORIGIN, NAPLES_PROJECTION)
        const [rx, ry] = lngLatToMetric(lon, lat, NAPLES_ORIGIN, NAPLES_PROJECTION)
        const err = Math.hypot(rx - x, ry - y)
        expect(err).toBeLessThan(1e-6)
      }
    })

    it('verifies inverse roundtrip: WGS84 -> metric -> WGS84 with sub-nanodegree precision', () => {
      const rng = createDeterministicRng(2002)
      for (let i = 0; i < 1000; i++) {
        const lon = NAPLES_ORIGIN.lon + (rng() * 2 - 1) * 0.05
        const lat = NAPLES_ORIGIN.lat + (rng() * 2 - 1) * 0.05

        const [x, y] = lngLatToMetric(lon, lat, NAPLES_ORIGIN, NAPLES_PROJECTION)
        const [rlon, rlat] = metricToLngLat(x, y, NAPLES_ORIGIN, NAPLES_PROJECTION)

        const lonErr = Math.abs(rlon - lon)
        const latErr = Math.abs(rlat - lat)

        expect(lonErr).toBeLessThan(1e-11)
        expect(latErr).toBeLessThan(1e-11)
      }
    })
  })

  describe('2. Affine Transformation Distortion vs Ground-Truth Equirectangular Camera', () => {
    it('evaluates affine screen error across 1000 random points in [-3000, 3000] m envelope under 7 rotations and 8 scale levels', () => {
      const rng = createDeterministicRng(3003)
      const points: Point[] = Array.from({ length: 1000 }, () => [
        (rng() * 2 - 1) * 3000,
        (rng() * 2 - 1) * 3000,
      ])

      let globalMaxErrorPx = 0

      for (const bearing of ROTATION_ANGLES) {
        for (const scale of SCALE_LEVELS) {
          const projectFn = createEquirectangularCamera([0, 0], scale, bearing)
          const transform = computeAffineScreenTransform(projectFn, NAPLES_ORIGIN, NAPLES_PROJECTION)

          let maxErrorForConfig = 0
          for (const pt of points) {
            const lngLat = metricToLngLat(pt[0], pt[1], NAPLES_ORIGIN, NAPLES_PROJECTION)
            const trueScreen = projectFn(lngLat)
            const affineScreen = transform.toScreen(pt)

            const err = Math.hypot(trueScreen.x - affineScreen[0], trueScreen.y - affineScreen[1])
            if (err > maxErrorForConfig) maxErrorForConfig = err
          }

          if (maxErrorForConfig > globalMaxErrorPx) globalMaxErrorPx = maxErrorForConfig
          expect(maxErrorForConfig).toBeLessThan(0.05) // Strict SLA < 0.05 px
        }
      }

      console.log(`[Equirectangular Affine] 1000 pts x 7 rotations x 8 scales: Global Max error = ${globalMaxErrorPx.toExponential(3)} px`)
      expect(globalMaxErrorPx).toBeLessThan(0.05)
    })

    it('verifies affine scale and rotation decomposition matches ground truth across all angles and scales', () => {
      for (const bearing of ROTATION_ANGLES) {
        for (const scale of SCALE_LEVELS) {
          const projectFn = createEquirectangularCamera([150, -250], scale, bearing)
          const transform = computeAffineScreenTransform(projectFn, NAPLES_ORIGIN, NAPLES_PROJECTION)

          expect(transform.scale).toBeCloseTo(scale, 5)
          expect(transform.scaleX).toBeCloseTo(scale, 5)
          expect(transform.scaleY).toBeCloseTo(scale, 5)

          let expectedBearing = bearing % 360
          let diffDeg = Math.abs(transform.rotationDeg - expectedBearing)
          if (diffDeg > 180) diffDeg = 360 - diffDeg
          expect(diffDeg).toBeLessThan(0.01)
        }
      }
    })
  })

  describe('3. Affine Transformation Distortion vs Ground-Truth Spherical Mercator (MapLibre Camera)', () => {
    it('evaluates spherical Mercator projection distortion within regatta envelope [-3000, 3000] m at overview scale (0.05 px/m)', () => {
      const scale = 0.05 // Extreme zoom-out full overview
      const rng = createDeterministicRng(4004)
      const points: Point[] = Array.from({ length: 1000 }, () => [
        (rng() * 2 - 1) * 3000,
        (rng() * 2 - 1) * 3000,
      ])

      let maxMercatorErrPx = 0

      for (const bearing of ROTATION_ANGLES) {
        const centerLngLat: [number, number] = [NAPLES_ORIGIN.lon, NAPLES_ORIGIN.lat]
        const projectFn = createSphericalMercatorCamera(centerLngLat, scale, bearing)
        const transform = computeAffineScreenTransform(projectFn, NAPLES_ORIGIN, NAPLES_PROJECTION)

        for (const pt of points) {
          const lngLat = metricToLngLat(pt[0], pt[1], NAPLES_ORIGIN, NAPLES_PROJECTION)
          const trueScreen = projectFn(lngLat)
          const affineScreen = transform.toScreen(pt)

          const err = Math.hypot(trueScreen.x - affineScreen[0], trueScreen.y - affineScreen[1])
          if (err > maxMercatorErrPx) maxMercatorErrPx = err
        }
      }

      console.log(`[Spherical Mercator at 0.05 px/m] 1000 pts x 7 rotations: Max error = ${maxMercatorErrPx.toFixed(5)} px`)
      // At 0.05 px/m, theoretical maximum Mercator non-linear deviation across 3000m is ~0.0408 px (< 0.05 px SLA)
      expect(maxMercatorErrPx).toBeLessThan(0.05)
    })

    it('empirically maps spherical Mercator non-linear distortion profile across the scale continuum', () => {
      // Maps the maximum distortion within visible display bounds for each scale level
      const rng = createDeterministicRng(5005)
      const distortionProfile: Record<number, number> = {}

      for (const scale of SCALE_LEVELS) {
        // Visible half-extent in metres on 1920x1080 screen
        const visibleM = Math.min(3000, (1920 / 2) / scale)
        const points: Point[] = Array.from({ length: 100 }, () => [
          (rng() * 2 - 1) * visibleM,
          (rng() * 2 - 1) * visibleM,
        ])

        let maxErr = 0
        const centerLngLat: [number, number] = [NAPLES_ORIGIN.lon, NAPLES_ORIGIN.lat]
        const projectFn = createSphericalMercatorCamera(centerLngLat, scale, 40.0) // Course axis 40 deg
        const transform = computeAffineScreenTransform(projectFn, NAPLES_ORIGIN, NAPLES_PROJECTION)

        for (const pt of points) {
          const lngLat = metricToLngLat(pt[0], pt[1], NAPLES_ORIGIN, NAPLES_PROJECTION)
          const trueScreen = projectFn(lngLat)
          const affineScreen = transform.toScreen(pt)
          const err = Math.hypot(trueScreen.x - affineScreen[0], trueScreen.y - affineScreen[1])
          if (err > maxErr) maxErr = err
        }

        distortionProfile[scale] = maxErr
      }

      console.log('[Mercator Visible Profile by Scale px/m]:', JSON.stringify(distortionProfile, (k, v) => typeof v === 'number' ? Number(v.toFixed(4)) : v))
      // Verify overview distortion remains strictly under 0.05 px
      expect(distortionProfile[0.05]).toBeLessThan(0.05)
      // Verify visible distortion at all scales never exceeds 0.20 px (imperceptible sub-pixel fraction < 1/5th px)
      for (const scale of SCALE_LEVELS) {
        expect(distortionProfile[scale]).toBeLessThan(0.20)
      }
    })
  })

  describe('4. Inversion Precision & Vector Transform Stability', () => {
    it('verifies exact roundtrip toScreen -> toWorld across 1000 points', () => {
      const rng = createDeterministicRng(6006)
      const projectFn = createEquirectangularCamera([0, 0], 0.35, 40.0)
      const transform = computeAffineScreenTransform(projectFn, NAPLES_ORIGIN, NAPLES_PROJECTION)

      for (let i = 0; i < 1000; i++) {
        const pt: Point = [(rng() * 2 - 1) * 3000, (rng() * 2 - 1) * 3000]
        const screen = transform.toScreen(pt)
        const world = transform.toWorld(screen)

        expect(Math.hypot(world[0] - pt[0], world[1] - pt[1])).toBeLessThan(1e-6)
      }
    })

    it('verifies vectorToScreen preserves metric length scaling across orientations', () => {
      const vectorLengthM = 15.0 // AC40 boat hull length approx
      for (const bearing of ROTATION_ANGLES) {
        for (const scale of [0.1, 0.5, 2.0, 10.0]) {
          const projectFn = createEquirectangularCamera([0, 0], scale, bearing)
          const transform = computeAffineScreenTransform(projectFn, NAPLES_ORIGIN, NAPLES_PROJECTION)

          for (const angleDeg of [0, 30, 60, 90, 135, 180, 270]) {
            const rad = (angleDeg * Math.PI) / 180
            const v: Point = [vectorLengthM * Math.cos(rad), vectorLengthM * Math.sin(rad)]
            const sv = transform.vectorToScreen(v)

            const expectedPx = vectorLengthM * scale
            const actualPx = Math.hypot(sv[0], sv[1])
            expect(Math.abs(actualPx - expectedPx)).toBeLessThan(1e-6)
          }
        }
      }
    })

    it('handles degenerate anchor distances gracefully', () => {
      expect(() => {
        computeAffineMatrixFromScreenPoints({ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0, y: 1 }, -100)
      }).toThrow('Anchor distance must be greater than zero')

      expect(() => {
        computeAffineMatrixFromScreenPoints({ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0, y: 1 }, 0)
      }).toThrow('Anchor distance must be greater than zero')
    })
  })
})
