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

// Naples race course origin and projection coefficients from Naples PR1
const NAPLES_ORIGIN: GeoOrigin = {
  lat: 40.80948067,
  lon: 14.23726898,
}

const NAPLES_PROJECTION: GeoProjectionParams = {
  k_lat: 111047.746,
  k_lon: 84374.839,
}

// Official marks from dataset
const OFFICIAL_MARKS: Record<string, { metric: Point; wgs84: [number, number] }> = {
  RM8: { metric: [-894.84, -722.23], wgs84: [14.22666345, 40.80297689] },
  RM6: { metric: [-537.49, -1016.81], wgs84: [14.23089873, 40.80032414] },
  RM4: { metric: [632.18, 948.11], wgs84: [14.24476156, 40.81801853] },
  RM2: { metric: [810.88, 800.79], wgs84: [14.24687938, 40.81669189] },
}

describe('Geographic Projection (src/utils/geoProjection.ts)', () => {
  describe('Forward & Inverse Projections', () => {
    it('accurately projects origin (0, 0) to origin coordinates', () => {
      const [lon, lat] = metricToLngLat(0, 0, NAPLES_ORIGIN, NAPLES_PROJECTION)
      expect(lon).toBeCloseTo(NAPLES_ORIGIN.lon, 9)
      expect(lat).toBeCloseTo(NAPLES_ORIGIN.lat, 9)

      const [x, y] = lngLatToMetric(lon, lat, NAPLES_ORIGIN, NAPLES_PROJECTION)
      expect(x).toBeCloseTo(0, 9)
      expect(y).toBeCloseTo(0, 9)
    })

    it('roundtrips arbitrary points across the race course with zero loss', () => {
      const testPoints: Point[] = [
        [0, 0],
        [1000, 500],
        [-1200, 850],
        [2400, -1800],
        [-3500, -2800],
        [150.25, -987.65],
      ]

      for (const [x, y] of testPoints) {
        const [lon, lat] = metricToLngLat(x, y, NAPLES_ORIGIN, NAPLES_PROJECTION)
        const [rx, ry] = lngLatToMetric(lon, lat, NAPLES_ORIGIN, NAPLES_PROJECTION)
        expect(rx).toBeCloseTo(x, 7)
        expect(ry).toBeCloseTo(y, 7)
      }
    })

    it('inverts official gate marks to WGS84 ground truth within sub-millimetre tolerance', () => {
      for (const [code, { metric, wgs84 }] of Object.entries(OFFICIAL_MARKS)) {
        const [lon, lat] = metricToLngLat(metric[0], metric[1], NAPLES_ORIGIN, NAPLES_PROJECTION)
        expect(lon).toBeCloseTo(wgs84[0], 6)
        expect(lat).toBeCloseTo(wgs84[1], 6)

        const [x, y] = lngLatToMetric(lon, lat, NAPLES_ORIGIN, NAPLES_PROJECTION)
        expect(x).toBeCloseTo(metric[0], 6)
        expect(y).toBeCloseTo(metric[1], 6)
      }
    })
  })

  describe('3-Point Affine Synchronizer', () => {
    // Simulated MapLibre camera model
    function createSimulatedMapProject(
      centerMetric: Point,
      scalePxPerM: number,
      bearingDeg: number,
      viewportWidth = 1000,
      viewportHeight = 800
    ) {
      const rad = (bearingDeg * Math.PI) / 180
      const cx = viewportWidth / 2
      const cy = viewportHeight / 2

      return (lngLat: [number, number]): ScreenPoint => {
        const [mx, my] = lngLatToMetric(lngLat[0], lngLat[1], NAPLES_ORIGIN, NAPLES_PROJECTION)
        const dx = mx - centerMetric[0]
        const dy = my - centerMetric[1]

        // Camera bearing clockwise rotation causes counter-clockwise world rotation
        const screenX = cx + (Math.cos(rad) * dx - Math.sin(rad) * dy) * scalePxPerM
        const screenY = cy - (Math.sin(rad) * dx + Math.cos(rad) * dy) * scalePxPerM

        return { x: screenX, y: screenY }
      }
    }

    it('computes exact affine matrix for North Up camera (bearing = 0°)', () => {
      const scale = 0.25 // 0.25 pixels per metre
      const center: Point = [0, 0]
      const projectFn = createSimulatedMapProject(center, scale, 0)

      const transform = computeAffineScreenTransform(projectFn, NAPLES_ORIGIN, NAPLES_PROJECTION)

      expect(transform.scaleX).toBeCloseTo(scale, 6)
      expect(transform.scaleY).toBeCloseTo(scale, 6)
      expect(transform.scale).toBeCloseTo(scale, 6)
      expect(transform.rotationDeg).toBeCloseTo(0, 4)

      // Test Origin maps to center screen (500, 400)
      const originScreen = transform.toScreen([0, 0])
      expect(originScreen[0]).toBeCloseTo(500, 6)
      expect(originScreen[1]).toBeCloseTo(400, 6)

      // Test 1000m East maps to (500 + 250, 400) = (750, 400)
      const eastScreen = transform.toScreen([1000, 0])
      expect(eastScreen[0]).toBeCloseTo(750, 6)
      expect(eastScreen[1]).toBeCloseTo(400, 6)

      // Test 1000m North maps to (500, 400 - 250) = (500, 150)
      const northScreen = transform.toScreen([0, 1000])
      expect(northScreen[0]).toBeCloseTo(500, 6)
      expect(northScreen[1]).toBeCloseTo(150, 6)
    })

    it('computes exact affine matrix for Course Up camera (bearing = 40°)', () => {
      const scale = 0.3
      const center: Point = [200, -100]
      const bearing = 40.0
      const projectFn = createSimulatedMapProject(center, scale, bearing)

      const transform = computeAffineScreenTransform(projectFn, NAPLES_ORIGIN, NAPLES_PROJECTION)

      expect(transform.scale).toBeCloseTo(scale, 6)
      expect(transform.rotationDeg).toBeCloseTo(bearing, 4)

      // Verify sub-pixel accuracy (< 0.001 px) across arbitrary points
      const testPoints: Point[] = [
        [0, 0],
        [-894.84, -722.23], // RM8
        [-537.49, -1016.81], // RM6
        [632.18, 948.11], // RM4
        [810.88, 800.79], // RM2
        [1500, -1200],
        [-2000, 2000],
      ]

      for (const pt of testPoints) {
        const lngLat = metricToLngLat(pt[0], pt[1], NAPLES_ORIGIN, NAPLES_PROJECTION)
        const directScreen = projectFn(lngLat)
        const affineScreen = transform.toScreen(pt)

        const errorPx = Math.hypot(
          directScreen.x - affineScreen[0],
          directScreen.y - affineScreen[1]
        )
        expect(errorPx).toBeLessThan(0.01) // Sub-pixel SLA: < 0.01 px
      }
    })

    it('provides exact roundtrip inverse projection toWorld([X, Y])', () => {
      const scale = 0.42
      const center: Point = [-150, 320]
      const bearing = 125.5
      const projectFn = createSimulatedMapProject(center, scale, bearing)

      const transform = computeAffineScreenTransform(projectFn, NAPLES_ORIGIN, NAPLES_PROJECTION)

      const metricPoints: Point[] = [
        [0, 0],
        [450.5, -620.2],
        [-1200.0, 950.4],
      ]

      for (const original of metricPoints) {
        const screen = transform.toScreen(original)
        const reconstructed = transform.toWorld(screen)

        expect(reconstructed[0]).toBeCloseTo(original[0], 6)
        expect(reconstructed[1]).toBeCloseTo(original[1], 6)
      }
    })

    it('correctly transforms metric vectors with vectorToScreen', () => {
      const scale = 0.5
      const bearing = 90 // Facing East: North moves to Left (-X), East moves Down (+Y)
      const projectFn = createSimulatedMapProject([0, 0], scale, bearing)

      const transform = computeAffineScreenTransform(projectFn, NAPLES_ORIGIN, NAPLES_PROJECTION)

      // A 100m East vector: [100, 0]
      const eastVec = transform.vectorToScreen([100, 0])
      expect(Math.hypot(eastVec[0], eastVec[1])).toBeCloseTo(50, 4) // 100m * 0.5 px/m

      // A 100m North vector: [0, 100]
      const northVec = transform.vectorToScreen([0, 100])
      expect(Math.hypot(northVec[0], northVec[1])).toBeCloseTo(50, 4)
    })

    it('throws error when computeAffineMatrixFromScreenPoints has invalid distance', () => {
      expect(() => {
        computeAffineMatrixFromScreenPoints({ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0, y: 1 }, 0)
      }).toThrow('Anchor distance must be greater than zero')
    })
  })
})
