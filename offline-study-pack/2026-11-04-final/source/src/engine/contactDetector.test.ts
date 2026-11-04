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
import type {
  BoatClass,
  ClassEvidence,
  ReplayData,
  SafetyBorders,
  VirtualContactIncident,
} from '../types/replay'

describe('2D SAT Contact Detector', () => {
  describe('Rotation Invariance', () => {
    it('preserves exact collision and penetration depth across 0, 45, 90, 180, 270 degrees', () => {
      // Two boats parallel with 10.0m lateral offset (penetration depth = 14.83 - 10.0 = 4.83m)
      const baseDistance = 10.0
      const testAnglesDeg = [0, 45, 90, 180, 270]

      const results = testAnglesDeg.map((angleDeg) => {
        const rad = (angleDeg * Math.PI) / 180.0
        // Boat A at origin (0, 0), Boat B laterally displaced by 10m perpendicular to heading
        // In local boat frame, +u is lateral (starboard)
        const boatA = { x: 0, y: 0, heading: angleDeg }
        // Offset vector rotated with the boat
        const boatB = {
          x: baseDistance * Math.cos(rad),
          y: -baseDistance * Math.sin(rad),
          heading: angleDeg,
        }

        return checkBoatsContact(boatA, boatB)
      })

      // All angles must detect contact
      for (const res of results) {
        expect(res.hasContact).toBe(true)
        expect(res.distanceM).toBeCloseTo(baseDistance, 5)
      }

      // Penetration depth and area must be identical across all rotation angles within precision tolerance
      const referenceDepth = results[0].overlapDepthM
      const referenceArea = results[0].overlapAreaM2

      expect(referenceDepth).toBeGreaterThan(0)
      expect(referenceArea).toBeGreaterThan(0)

      for (let i = 1; i < results.length; i++) {
        expect(results[i].overlapDepthM).toBeCloseTo(referenceDepth, 2)
        expect(results[i].overlapAreaM2).toBeCloseTo(referenceArea, 1)
      }
    })

    it('preserves non-collision status across 0, 45, 90, 180, 270 degrees for separated vessels', () => {
      const separationDistance = 20.0
      const testAnglesDeg = [0, 45, 90, 180, 270]

      for (const angleDeg of testAnglesDeg) {
        const rad = (angleDeg * Math.PI) / 180.0
        const boatA = { x: 0, y: 0, heading: angleDeg }
        const boatB = {
          x: separationDistance * Math.cos(rad),
          y: -separationDistance * Math.sin(rad),
          heading: angleDeg,
        }

        const res = checkBoatsContact(boatA, boatB)
        expect(res.hasContact).toBe(false)
        expect(res.overlapDepthM).toBe(0)
        expect(res.overlapAreaM2).toBe(0)
      }
    })
  })

  describe('Lateral Separation Thresholds (15.0m vs 12.0m)', () => {
    it('confirms exact non-collision at 15.0m separation', () => {
      // AC40 Keep Clear Border has max half-width of 7.415m (full span 14.83m).
      // Parallel boats at 15.0m lateral separation have 15.0m - 14.83m = 0.17m clearance.
      const boatA = { x: 0, y: 0, heading: 0 }
      const boatB = { x: 15.0, y: 0, heading: 0 }

      const res = checkBoatsContact(boatA, boatB)
      expect(res.hasContact).toBe(false)
      expect(res.overlapDepthM).toBe(0)
      expect(res.overlapAreaM2).toBe(0)
    })

    it('confirms exact collision at 12.0m separation', () => {
      // Parallel boats at 12.0m lateral separation have Keep Clear Border intersection.
      const boatA = { x: 0, y: 0, heading: 0 }
      const boatB = { x: 12.0, y: 0, heading: 0 }

      const res = checkBoatsContact(boatA, boatB)
      expect(res.hasContact).toBe(true)
      expect(res.overlapDepthM).toBeCloseTo(2.73, 1)
      expect(res.overlapAreaM2).toBeGreaterThan(0)
    })
  })

  describe('Fleet Frame Contact Evaluation', () => {
    it('detects multiple simultaneous contacts and isolates clear boats', () => {
      const fleet = {
        FRA: { x: 0, y: 0, heading: 45 },
        NZL_G: { x: 8, y: 0, heading: 45 }, // Colliding with FRA (8m < 14.83m)
        ITA_B: { x: 100, y: 100, heading: 45 }, // Isolated clear boat
      }

      const contacts = detectFrameContacts(fleet)
      expect(contacts.length).toBe(1)
      expect(contacts[0].boatA).toBe('FRA')
      expect(contacts[0].boatB).toBe('NZL_G')
      expect(contacts[0].distanceM).toBeCloseTo(8, 2)
      expect(contacts[0].overlapDepthM).toBeGreaterThan(0)
    })
  })

  describe('Schema Validation & Type Conformance', () => {
    it('validates BoatClass allowed union values', () => {
      const validClasses: BoatClass[] = ['AC40', 'AC75', 'UNKNOWN']
      expect(validClasses).toContain('AC40')
      expect(validClasses).toContain('AC75')
      expect(validClasses).toContain('UNKNOWN')
    })

    it('validates ClassEvidence structure', () => {
      const evidence: ClassEvidence = {
        description: 'Explicit ASSET_TYPE_AC40 in session metadata',
        confidence: 'CONFIRMED',
        source: 'session.assets',
      }
      expect(evidence.confidence).toBe('CONFIRMED')
      expect(evidence.source).toBeTruthy()
    })

    it('validates SafetyBorders coordinate definitions', () => {
      const borders: SafetyBorders = {
        platform_border: AC40_PLATFORM_BORDER,
        keep_clear_border: AC40_KEEP_CLEAR_BORDER,
      }
      expect(borders.platform_border.length).toBe(9)
      expect(borders.keep_clear_border.length).toBe(10)
      // Longitudinal bounds: -0.215 to 12.963m
      const platformYs = borders.platform_border.map((p) => p.y)
      expect(Math.min(...platformYs)).toBeCloseTo(-0.215, 3)
      expect(Math.max(...platformYs)).toBeCloseTo(12.963, 3)
    })

    it('conforms to ReplayData complete type contract', () => {
      const mockReplay: ReplayData = {
        id: 'naples_pr1',
        name: 'Practice Race 1',
        venue: 'Gulf of Naples, Italy',
        date: '2026-09-22',
        event_edition: "37th America's Cup Preliminary Regatta Naples 2026",
        boat_class: 'AC40',
        class_evidence: {
          description: 'Explicit ASSET_TYPE_AC40 and platform_border envelope',
          confidence: 'CONFIRMED',
          source: 'session.assets',
        },
        safety_borders: {
          platform_border: AC40_PLATFORM_BORDER,
          keep_clear_border: AC40_KEEP_CLEAR_BORDER,
        },
        virtual_contact_incidents: [],
        course: {
          axis_deg: 45.0,
          length_m: 2400.0,
          origin: { lat: 40.809, lon: 14.237 },
          projection: { k_lat: 111047, k_lon: 84374 },
          boundaries: { race: [], safety: [] },
          marks: {},
        },
        wind: { reference_twd_deg: 54.3, reference_tws_kt: 10.7, timeline: [] },
        chronology: { gun_time: 1790078940000, window_start: 1790078820000, window_end: 1790080000000 },
        competitors: [],
        telemetry: { timestamps: [], boats: {}, marks: {} },
      }

      expect(mockReplay.boat_class).toBe('AC40')
      expect(mockReplay.event_edition).toBe("37th America's Cup Preliminary Regatta Naples 2026")
      expect(mockReplay.class_evidence.confidence).toBe('CONFIRMED')
      expect(Array.isArray(mockReplay.virtual_contact_incidents)).toBe(true)
    })
  })
})
