import { describe, expect, it } from 'vitest'
import {
  AC40_KEEP_CLEAR_BORDER,
  AC40_PLATFORM_BORDER,
  checkBoatsContact,
  computePolygonArea,
  computePolygonIntersectionArea,
  detectFrameContacts,
  testPolygonOverlapSAT,
  transformLocalToWorld,
} from './contactDetector'
import type { BoatPose, Point, VirtualContactIncident } from '../types/replay'

describe('Adversarial Stress Test: 2D SAT Contact Detector', () => {
  describe('Rapid Rotation Sweeps (0° to 359° at 1° Increments)', () => {
    it('preserves collision detection and numerical stability across 360 orientations', () => {
      const baseDistance = 10.0 // 10m < 14.83m span (overlap ~4.83m)
      let refDepth: number | null = null
      let refArea: number | null = null

      for (let deg = 0; deg < 360; deg++) {
        const rad = (deg * Math.PI) / 180.0
        const boatA: BoatPose = { x: 50.0, y: 50.0, heading: deg }
        const boatB: BoatPose = {
          x: 50.0 + baseDistance * Math.cos(rad),
          y: 50.0 - baseDistance * Math.sin(rad),
          heading: deg,
        }

        const res = checkBoatsContact(boatA, boatB)

        // Strict numerical guarantees
        expect(Number.isNaN(res.overlapDepthM)).toBe(false)
        expect(Number.isFinite(res.overlapDepthM)).toBe(true)
        expect(Number.isNaN(res.overlapAreaM2)).toBe(false)
        expect(Number.isFinite(res.overlapAreaM2)).toBe(true)

        expect(res.hasContact).toBe(true)
        expect(res.overlapDepthM).toBeGreaterThan(0)
        expect(res.overlapAreaM2).toBeGreaterThan(0)

        if (refDepth === null) {
          refDepth = res.overlapDepthM
          refArea = res.overlapAreaM2
        } else {
          expect(res.overlapDepthM).toBeCloseTo(refDepth, 1)
          expect(res.overlapAreaM2).toBeCloseTo(refArea, 0)
        }
      }
    })

    it('guarantees zero false positives across 360 orientations for separated boats', () => {
      const sepDistance = 20.0 // Clearance 20.0 - 14.83 = 5.17m
      for (let deg = 0; deg < 360; deg++) {
        const rad = (deg * Math.PI) / 180.0
        const boatA: BoatPose = { x: 0, y: 0, heading: deg }
        const boatB: BoatPose = {
          x: sepDistance * Math.cos(rad),
          y: -sepDistance * Math.sin(rad),
          heading: deg,
        }

        const res = checkBoatsContact(boatA, boatB)
        expect(res.hasContact).toBe(false)
        expect(res.overlapDepthM).toBe(0)
        expect(res.overlapAreaM2).toBe(0)
      }
    })
  })

  describe('Glancing Touches & Sub-Centimeter Clearances', () => {
    it('differentiates 1mm clearance from 1mm overlap at foil tips', () => {
      const exactSpan = 14.83 // 2 * 7.415m

      // 1mm separated
      const boatA: BoatPose = { x: 0, y: 0, heading: 0 }
      const boatBClear: BoatPose = { x: exactSpan + 0.001, y: 0, heading: 0 }
      const resClear = checkBoatsContact(boatA, boatBClear)
      expect(resClear.hasContact).toBe(false)
      expect(resClear.overlapDepthM).toBe(0)
      expect(resClear.overlapAreaM2).toBe(0)

      // 1mm overlapping
      const boatBTouch: BoatPose = { x: exactSpan - 0.001, y: 0, heading: 0 }
      const resTouch = checkBoatsContact(boatA, boatBTouch)
      expect(resTouch.hasContact).toBe(true)
      expect(resTouch.overlapDepthM).toBeGreaterThan(0)
      expect(resTouch.overlapDepthM).toBeLessThanOrEqual(0.01)
    })

    it('differentiates 5mm clearance from 5mm overlap at bowsprit head-on touch', () => {
      const exactLongitudinal = 25.926 // 2 * 12.963m

      // 5mm separated
      const boatA: BoatPose = { x: 0, y: 0, heading: 0 }
      const boatBClear: BoatPose = { x: 0, y: exactLongitudinal + 0.005, heading: 180 }
      const resClear = checkBoatsContact(boatA, boatBClear)
      expect(resClear.hasContact).toBe(false)
      expect(resClear.overlapDepthM).toBe(0)

      // 5mm overlapping
      const boatBTouch: BoatPose = { x: 0, y: exactLongitudinal - 0.005, heading: 180 }
      const resTouch = checkBoatsContact(boatA, boatBTouch)
      expect(resTouch.hasContact).toBe(true)
      expect(resTouch.overlapDepthM).toBeCloseTo(0.005, 3)
      expect(resTouch.overlapAreaM2).toBeGreaterThan(0)
    })
  })

  describe('High-Velocity Crossings (40 Knots Closing Velocity)', () => {
    it('captures rapid perpendicular crossing without frame tunneling', () => {
      // 40 knots = 20.578 m/s = 2.058 m/frame at 100ms
      const distPerFrame = 40.0 * 0.514444444 * 0.1
      const nFrames = 51

      let contactFramesCount = 0
      let maxOverlapDepth = 0
      let maxOverlapArea = 0

      for (let i = 0; i < nFrames; i++) {
        const boatA: BoatPose = { x: 0, y: 0, heading: 0 }
        const boatB: BoatPose = {
          x: -50.0 + i * distPerFrame,
          y: 6.5,
          heading: 90,
        }

        const res = checkBoatsContact(boatA, boatB)
        if (res.hasContact) {
          contactFramesCount++
          if (res.overlapDepthM > maxOverlapDepth) maxOverlapDepth = res.overlapDepthM
          if (res.overlapAreaM2 > maxOverlapArea) maxOverlapArea = res.overlapAreaM2
        }
      }

      // Crossing envelope is ~28m total width, so at 2.06m/frame it must be caught across 10-14 consecutive frames
      expect(contactFramesCount).toBeGreaterThanOrEqual(10)
      expect(contactFramesCount).toBeLessThanOrEqual(16)
      expect(maxOverlapDepth).toBeGreaterThan(5.0)
      expect(maxOverlapArea).toBeGreaterThan(20.0)
    })
  })

  describe('Numerical Robustness & Degenerate Polygons', () => {
    it('handles identical coincident polygons cleanly', () => {
      const polyA = transformLocalToWorld(AC40_KEEP_CLEAR_BORDER, 100, 200, 45)
      const polyB = transformLocalToWorld(AC40_KEEP_CLEAR_BORDER, 100, 200, 45)

      const sat = testPolygonOverlapSAT(polyA, polyB)
      expect(sat.hasContact).toBe(true)
      expect(Number.isNaN(sat.overlapDepthM)).toBe(false)
      expect(sat.overlapDepthM).toBeGreaterThan(0)

      const intersectionArea = computePolygonIntersectionArea(polyA, polyB)
      const baseArea = computePolygonArea(polyA)
      expect(Number.isNaN(intersectionArea)).toBe(false)
      expect(intersectionArea).toBeCloseTo(baseArea, 1)
    })

    it('returns zero safely for degenerate empty or collinear inputs', () => {
      const emptyPoly: Point[] = []
      const pointPoly: Point[] = [[0, 0]]
      const linePoly: Point[] = [
        [0, 0],
        [10, 0],
      ]

      expect(testPolygonOverlapSAT(emptyPoly, emptyPoly).hasContact).toBe(false)
      expect(testPolygonOverlapSAT(pointPoly, linePoly).hasContact).toBe(false)
      expect(computePolygonIntersectionArea(emptyPoly, pointPoly)).toBe(0)
      expect(computePolygonArea(linePoly)).toBe(0)
    })

    it('handles extreme spatial coordinates without overflow', () => {
      const boatA: BoatPose = { x: 1_000_000, y: 1_000_000, heading: 45 }
      const boatB: BoatPose = { x: 1_000_010, y: 1_000_000, heading: 45 }

      const res = checkBoatsContact(boatA, boatB)
      expect(res.hasContact).toBe(true)
      expect(Number.isNaN(res.overlapDepthM)).toBe(false)
      expect(Number.isFinite(res.overlapDepthM)).toBe(true)
    })
  })

  describe('Ground Truth Incident Frames from Naples PR1', () => {
    it('confirms physical Keep Clear Border overlap for known incident frames', () => {
      // Known peak frame for vci-GBR G-GBR B (start 1790079088400):
      // GBR G and GBR B in Naples PR1
      // Evaluated at exact poses
      const poseGBRG: BoatPose = { x: 341.25, y: -482.10, heading: 48.2 }
      const poseGBRB: BoatPose = { x: 350.12, y: -477.50, heading: 46.5 }

      const res = checkBoatsContact(poseGBRG, poseGBRB)
      expect(res.hasContact).toBe(true)
      expect(res.overlapDepthM).toBeGreaterThan(0)
      expect(res.overlapAreaM2).toBeGreaterThan(0)
    })
  })
})
