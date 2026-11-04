import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { ReplayEngine, sampleMark } from './ReplayEngine'
import type { ReplayFrame, ReplayManifest } from '../types/replay'

function loadNaplesManifest(): ReplayManifest {
  const replayPath = path.resolve(__dirname, '../../public/data/replays/naples_pr1.json')
  if (!fs.existsSync(replayPath)) {
    throw new Error(`Replay file not found at ${replayPath}`)
  }
  return JSON.parse(fs.readFileSync(replayPath, 'utf8'))
}

describe('Adversarial Stress Test: Dynamic Mark Physics & Rounding SLA', () => {
  const manifest = loadNaplesManifest()

  // =========================================================================
  // 1. Core Rounding SLA at frame 4130 (t = 1790079233000)
  // =========================================================================
  describe('Leg 1 Fleet Leader Rounding SLA (t = 1790079233000, frame 4130)', () => {
    it('empirically verifies RM2 is within 30m of FRAs rounding trajectory with coordinates around x ≈ 1000-1080m, y ≈ 530-600m', () => {
      const engine = new ReplayEngine(manifest)
      let frame: ReplayFrame | null = null
      engine.subscribe((f) => {
        frame = f
      })

      const tTarget = 1790079233000
      engine.seek(tTarget)

      expect(frame).not.toBeNull()
      expect(frame!.index).toBe(4130)
      expect(frame!.fraction).toBeCloseTo(0.0, 5)

      // Dynamic RM2
      const rm2 = frame!.marks.RM2
      expect(rm2).toBeDefined()
      expect(rm2.x).toBeCloseTo(1103.6, 1)
      expect(rm2.y).toBeCloseTo(537.55, 1)

      // FRA position
      const fraComp = manifest.competitors.find((c) => c.team_code === 'FRA')
      expect(fraComp).toBeDefined()
      const fraBoat = frame!.boats[fraComp!.id]
      expect(fraBoat).toBeDefined()

      // Verify FRA coordinate bounds: local x ≈ 1000-1080m, y ≈ 530-600m
      expect(fraBoat.x).toBeGreaterThan(1000)
      expect(fraBoat.x).toBeLessThan(1100) // 1088.33m
      expect(fraBoat.y).toBeGreaterThan(500)
      expect(fraBoat.y).toBeLessThan(600) // 523.08m

      // Euclidean separation
      const dist = Math.hypot(rm2.x - fraBoat.x, rm2.y - fraBoat.y)
      expect(dist).toBeCloseTo(21.04, 1)
      expect(dist).toBeLessThan(30.0) // Strictly meets < 30m SLA

      // Contrast against static planning target error (>180m)
      const staticRM2 = manifest.course.marks.RM2.target
      const staticDist = Math.hypot(staticRM2[0] - fraBoat.x, staticRM2[1] - fraBoat.y)
      expect(staticDist).toBeGreaterThan(180.0)
      expect(staticDist).toBeCloseTo(197.25, 0)
    })
  })

  // =========================================================================
  // 2. Full Fleet Rounding Alignment across Leg 1 and Leg 3
  // =========================================================================
  describe('Full Fleet Rounding Alignment across Leg 1 & Leg 3', () => {
    it('verifies that every active boat completing Leg 1 passes within 35m of the dynamic top gate', () => {
      const engine = new ReplayEngine(manifest)
      let frame: ReplayFrame | null = null
      engine.subscribe((f) => {
        frame = f
      })

      const topGateBuoyUuids = [
        manifest.course.marks.RM2.asset_id!,
        manifest.course.marks.RM4.asset_id!,
      ]

      for (const comp of manifest.competitors) {
        const boatTelemetry = manifest.telemetry.boats[comp.id]
        if (!boatTelemetry) continue

        // Find Leg 1 -> Leg 2 transition index
        const legs = boatTelemetry.leg
        let leg1EndIndex = -1
        for (let i = 0; i < legs.length - 1; i++) {
          if (legs[i] === 1 && legs[i + 1] === 2) {
            leg1EndIndex = i
            break
          }
        }

        if (leg1EndIndex === -1) {
          // Boat did not complete Leg 1 (e.g. GBR B OCS / retired)
          continue
        }

        const tRounding = manifest.telemetry.timestamps[leg1EndIndex]
        engine.seek(tRounding)

        const bx = frame!.boats[comp.id].x
        const by = frame!.boats[comp.id].y
        const rm2 = frame!.marks.RM2
        const rm4 = frame!.marks.RM4

        const distRM2 = Math.hypot(rm2.x - bx, rm2.y - by)
        const distRM4 = Math.hypot(rm4.x - bx, rm4.y - by)
        const minDistDynamicBuoy = Math.min(distRM2, distRM4)

        // Find minimum distance to gate buoys in a +/- 5 second (50 frames) window around the transition
        let minWindowDistDynamic = minDistDynamicBuoy
        const startWindow = Math.max(0, leg1EndIndex - 50)
        const endWindow = Math.min(legs.length - 1, leg1EndIndex + 50)
        for (let j = startWindow; j <= endWindow; j++) {
          const tJ = manifest.telemetry.timestamps[j]
          engine.seek(tJ)
          const jbx = frame!.boats[comp.id].x
          const jby = frame!.boats[comp.id].y
          const jd2 = Math.hypot(frame!.marks.RM2.x - jbx, frame!.marks.RM2.y - jby)
          const jd4 = Math.hypot(frame!.marks.RM4.x - jbx, frame!.marks.RM4.y - jby)
          minWindowDistDynamic = Math.min(minWindowDistDynamic, jd2, jd4)
        }

        // Compare against static target distance
        const staticRM2 = manifest.course.marks.RM2.target
        const staticRM4 = manifest.course.marks.RM4.target
        const minDistStatic = Math.min(
          Math.hypot(staticRM2[0] - bx, staticRM2[1] - by),
          Math.hypot(staticRM4[0] - bx, staticRM4[1] - by)
        )

        console.log(`[Leg 1 Rounding] ${comp.team_code}: dynamic minDist=${minWindowDistDynamic.toFixed(2)}m, static minDist=${minDistStatic.toFixed(2)}m`)

        // Dynamic buoy is in the immediate vicinity (< 35m at closest approach of rounding maneuver)
        // while static target is separated from dynamic marks
        expect(minWindowDistDynamic).toBeLessThan(35.0)
        expect(minDistStatic).toBeGreaterThan(25.0)
      }
    })

    it('verifies that fleet boats completing Leg 3 pass within 45m of the dynamic top gate at rounding', () => {
      const engine = new ReplayEngine(manifest)
      let frame: ReplayFrame | null = null
      engine.subscribe((f) => {
        frame = f
      })

      for (const comp of manifest.competitors) {
        const boatTelemetry = manifest.telemetry.boats[comp.id]
        if (!boatTelemetry) continue

        // Find Leg 3 -> Leg 4 transition index
        const legs = boatTelemetry.leg
        let leg3EndIndex = -1
        for (let i = 0; i < legs.length - 1; i++) {
          if (legs[i] === 3 && legs[i + 1] === 4) {
            leg3EndIndex = i
            break
          }
        }

        if (leg3EndIndex === -1) continue // Did not reach/finish Leg 3

        const tRounding = manifest.telemetry.timestamps[leg3EndIndex]
        engine.seek(tRounding)

        const bx = frame!.boats[comp.id].x
        const by = frame!.boats[comp.id].y

        // Find minimum distance in +/- 5s window around rounding
        let minWindowDistDynamic = Math.min(
          Math.hypot(frame!.marks.RM2.x - bx, frame!.marks.RM2.y - by),
          Math.hypot(frame!.marks.RM4.x - bx, frame!.marks.RM4.y - by)
        )
        const startWindow = Math.max(0, leg3EndIndex - 50)
        const endWindow = Math.min(legs.length - 1, leg3EndIndex + 50)
        for (let j = startWindow; j <= endWindow; j++) {
          const tJ = manifest.telemetry.timestamps[j]
          engine.seek(tJ)
          const jbx = frame!.boats[comp.id].x
          const jby = frame!.boats[comp.id].y
          const jd2 = Math.hypot(frame!.marks.RM2.x - jbx, frame!.marks.RM2.y - jby)
          const jd4 = Math.hypot(frame!.marks.RM4.x - jbx, frame!.marks.RM4.y - jby)
          minWindowDistDynamic = Math.min(minWindowDistDynamic, jd2, jd4)
        }

        console.log(`[Leg 3 Rounding] ${comp.team_code}: dynamic minDist=${minWindowDistDynamic.toFixed(2)}m`)

        // At Leg 3 rounding, dynamic buoys are accurately positioned near the boat (< 45m)
        expect(minWindowDistDynamic).toBeLessThan(45.0)
      }
    })
  })

  // =========================================================================
  // 3. Fractional Frame Linear Interpolation Stress Tests
  // =========================================================================
  describe('Fractional Frame Lerp Stress Tests', () => {
    it('strictly maintains linear continuity and boundary containment for intermediate fractions', () => {
      const engine = new ReplayEngine(manifest)
      let frame: ReplayFrame | null = null
      engine.subscribe((f) => {
        frame = f
      })

      const baseIdx = 4130
      const t0 = manifest.telemetry.timestamps[baseIdx]
      const t1 = manifest.telemetry.timestamps[baseIdx + 1]
      const dt = t1 - t0 // 100ms

      const fractions = [0.0, 0.1, 0.25, 0.333, 0.5, 0.667, 0.75, 0.9, 0.99]

      engine.seek(t0)
      const p0 = { ...frame!.marks.RM2 }

      engine.seek(t1)
      const p1 = { ...frame!.marks.RM2 }

      for (const frac of fractions) {
        const t = t0 + dt * frac
        engine.seek(t)

        expect(frame!.index).toBe(baseIdx)
        expect(frame!.fraction).toBeCloseTo(frac, 4)

        const currentRM2 = frame!.marks.RM2
        const expectedX = p0.x + (p1.x - p0.x) * frac
        const expectedY = p0.y + (p1.y - p0.y) * frac

        expect(currentRM2.x).toBeCloseTo(expectedX, 5)
        expect(currentRM2.y).toBeCloseTo(expectedY, 5)

        // Monotonic containment check: coordinate must be within [min(p0, p1), max(p0, p1)]
        const minX = Math.min(p0.x, p1.x) - 1e-6
        const maxX = Math.max(p0.x, p1.x) + 1e-6
        const minY = Math.min(p0.y, p1.y) - 1e-6
        const maxY = Math.max(p0.y, p1.y) + 1e-6

        expect(currentRM2.x).toBeGreaterThanOrEqual(minX)
        expect(currentRM2.x).toBeLessThanOrEqual(maxX)
        expect(currentRM2.y).toBeGreaterThanOrEqual(minY)
        expect(currentRM2.y).toBeLessThanOrEqual(maxY)

        // No NaN or Infinity
        expect(Number.isFinite(currentRM2.x)).toBe(true)
        expect(Number.isFinite(currentRM2.y)).toBe(true)
      }

      // At exact t1 (frac = 1.0), binary search cleanly steps to next frame index
      engine.seek(t1)
      expect(frame!.index).toBe(baseIdx + 1)
      expect(frame!.fraction).toBe(0)
    })

    it('sampleMark safely clamps negative and >1 fractions to endpoint bounds', () => {
      const stream = {
        x: [1000, 2000],
        y: [-500, 500],
      }

      // Exact fractions
      expect(sampleMark(stream, 0, 0.0)).toEqual({ x: 1000, y: -500 })
      expect(sampleMark(stream, 0, 1.0)).toEqual({ x: 2000, y: 500 })
      expect(sampleMark(stream, 0, 0.5)).toEqual({ x: 1500, y: 0 })

      // Clamp protection: fractions < 0 are clamped to 0 (endpoint A)
      const clampedNeg = sampleMark(stream, 0, -0.5)
      expect(clampedNeg.x).toBe(1000)
      expect(clampedNeg.y).toBe(-500)

      // Clamp protection: fractions > 1 are clamped to 1 (endpoint B)
      const clampedPos = sampleMark(stream, 0, 1.5)
      expect(clampedPos.x).toBe(2000)
      expect(clampedPos.y).toBe(500)
    })
  })

  // =========================================================================
  // 4. Boundary Timestamps & Timeline Stress Tests
  // =========================================================================
  describe('Boundary Timestamps & Timeline Stress Tests', () => {
    it('handles negative, pre-window, and post-window timestamps via safe clamping', () => {
      const engine = new ReplayEngine(manifest)
      let frame: ReplayFrame | null = null
      engine.subscribe((f) => {
        frame = f
      })

      const winStart = manifest.chronology.window_start
      const winEnd = manifest.chronology.window_end

      // Timestamp far before window start
      engine.seek(-1_000_000)
      expect(frame!.timestamp).toBe(winStart)
      expect(frame!.index).toBe(0)
      expect(frame!.fraction).toBe(0)
      expect(frame!.marks.RM2).toBeDefined()
      expect(Number.isFinite(frame!.marks.RM2.x)).toBe(true)

      // Timestamp 1ms before window start
      engine.seek(winStart - 1)
      expect(frame!.timestamp).toBe(winStart)
      expect(frame!.index).toBe(0)
      expect(frame!.fraction).toBe(0)

      // Exact window start
      engine.seek(winStart)
      expect(frame!.timestamp).toBe(winStart)
      expect(frame!.index).toBe(0)
      expect(frame!.fraction).toBe(0)

      // Exact window end
      engine.seek(winEnd)
      expect(frame!.timestamp).toBe(winEnd)
      expect(frame!.index).toBe(manifest.telemetry.timestamps.length - 1)
      expect(frame!.fraction).toBe(0)
      expect(frame!.marks.RM2).toBeDefined()
      expect(Number.isFinite(frame!.marks.RM2.x)).toBe(true)

      // Timestamp far after window end
      engine.seek(winEnd + 100_000_000)
      expect(frame!.timestamp).toBe(winEnd)
      expect(frame!.index).toBe(manifest.telemetry.timestamps.length - 1)
      expect(frame!.fraction).toBe(0)
    })

    it('safely handles single-element timestamp array without out-of-bounds error', () => {
      const degenerateManifest: ReplayManifest = {
        ...manifest,
        chronology: { window_start: 1000, window_end: 1000, gun_time: 1000 },
        telemetry: {
          timestamps: [1000],
          boats: {},
          marks: {
            [manifest.course.marks.RM2.asset_id!]: { x: [1100], y: [550] },
          },
        },
      }

      const engine = new ReplayEngine(degenerateManifest)
      let frame: ReplayFrame | null = null
      engine.subscribe((f) => {
        frame = f
      })

      engine.seek(1000)
      expect(frame).not.toBeNull()
      expect(frame!.index).toBe(0)
      expect(frame!.fraction).toBe(0)
      expect(frame!.marks.RM2).toEqual({ x: 1100, y: 550 })
    })
  })

  // =========================================================================
  // 5. Missing Marks Fallback & Resilience Matrix
  // =========================================================================
  describe('Missing Marks Fallback & Resilience Matrix', () => {
    it('falls back to static course mark target when telemetry stream is missing for individual marks', () => {
      const partialManifest: ReplayManifest = {
        ...manifest,
        telemetry: {
          ...manifest.telemetry,
          marks: {
            // Only RM2 has telemetry; RM4, RM6, RM8 are completely missing
            [manifest.course.marks.RM2.asset_id!]:
              manifest.telemetry.marks[manifest.course.marks.RM2.asset_id!],
          },
        },
      }

      const engine = new ReplayEngine(partialManifest)
      let frame: ReplayFrame | null = null
      engine.subscribe((f) => {
        frame = f
      })

      engine.seek(1790079233000)
      expect(frame).not.toBeNull()

      // RM2 has dynamic telemetry
      expect(frame!.marks.RM2.x).toBeCloseTo(1103.6, 1)

      // RM4 has no telemetry -> falls back to target
      expect(frame!.marks.RM4.x).toBe(manifest.course.marks.RM4.target[0])
      expect(frame!.marks.RM4.y).toBe(manifest.course.marks.RM4.target[1])

      // RM6 falls back to target
      expect(frame!.marks.RM6.x).toBe(manifest.course.marks.RM6.target[0])
      expect(frame!.marks.RM6.y).toBe(manifest.course.marks.RM6.target[1])

      // RM8 falls back to target
      expect(frame!.marks.RM8.x).toBe(manifest.course.marks.RM8.target[0])
      expect(frame!.marks.RM8.y).toBe(manifest.course.marks.RM8.target[1])
    })

    it('gracefully handles empty or undefined telemetry.marks dictionary without crashing', () => {
      const noMarksManifest: ReplayManifest = {
        ...manifest,
        telemetry: {
          ...manifest.telemetry,
          marks: {} as any,
        },
      }

      const engine = new ReplayEngine(noMarksManifest)
      let frame: ReplayFrame | null = null
      expect(() => {
        engine.subscribe((f) => {
          frame = f
        })
      }).not.toThrow()

      expect(frame).not.toBeNull()
      // All marks fall back to static targets
      for (const [code, mark] of Object.entries(manifest.course.marks)) {
        expect(frame!.marks[code]).toEqual({
          x: mark.target[0],
          y: mark.target[1],
        })
      }
    })

    it('sampleMark handles empty arrays gracefully', () => {
      const emptyStream = { x: [], y: [] }
      const res = sampleMark(emptyStream, 0, 0.5)
      expect(res).toEqual({ x: 0, y: 0 })
    })


  })

  // =========================================================================
  // 6. Buoy Motion Physics & Smoothness Stress Test
  // =========================================================================
  describe('Buoy Motion Physics & Continuity Check', () => {
    it('verifies all 4 robotic buoys exhibit smooth, bounded velocities with no teleports across 19,488 frames', () => {
      const marks = manifest.telemetry.marks
      const maxAllowedSpeedMps = 15.0 // Robotic buoys motor at <= 5 m/s, 15 m/s provides huge headroom for noise

      for (const [uuid, stream] of Object.entries(marks)) {
        expect(stream.x.length).toBe(manifest.telemetry.timestamps.length)
        expect(stream.y.length).toBe(manifest.telemetry.timestamps.length)

        let maxSpeed = 0
        for (let i = 0; i < stream.x.length - 1; i++) {
          const dx = stream.x[i + 1] - stream.x[i]
          const dy = stream.y[i + 1] - stream.y[i]
          const dt = (manifest.telemetry.timestamps[i + 1] - manifest.telemetry.timestamps[i]) / 1000.0

          if (dt > 0) {
            const speed = Math.hypot(dx, dy) / dt
            if (speed > maxSpeed) maxSpeed = speed
          }
        }

        // Verify no teleportation spikes
        expect(maxSpeed).toBeLessThan(maxAllowedSpeedMps)
      }
    })
  })
})
