import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { ReplayEngine, sampleMark } from './ReplayEngine'
import type { ReplayFrame, ReplayManifest } from '../types/replay'

describe('sampleMark interpolation', () => {
  it('interpolates x and y linearly across fractions', () => {
    const stream = {
      x: [100, 200, 300],
      y: [10, 50, 90],
    }

    const atZero = sampleMark(stream, 0, 0)
    expect(atZero).toEqual({ x: 100, y: 10 })

    const atHalf = sampleMark(stream, 0, 0.5)
    expect(atHalf).toEqual({ x: 150, y: 30 })

    const atOne = sampleMark(stream, 0, 1)
    expect(atOne).toEqual({ x: 200, y: 50 })

    const nextSpan = sampleMark(stream, 1, 0.25)
    expect(nextSpan).toEqual({ x: 225, y: 60 })
  })

  it('clamps at end of stream array', () => {
    const stream = {
      x: [500],
      y: [250],
    }
    const end = sampleMark(stream, 0, 0.8)
    expect(end).toEqual({ x: 500, y: 250 })
  })
})

describe('ReplayEngine dynamic marks', () => {
  it('maps mark codes to interpolated coordinates and falls back to static targets', () => {
    const mockManifest: ReplayManifest = {
      id: 'test_race',
      name: 'Test Race',
      venue: 'Test Venue',
      date: '2026-10-07',
      course: {
        axis_deg: 45,
        length_m: 2000,
        origin: { lat: 40.8, lon: 14.2 },
        projection: { k_lat: 111100, k_lon: 84300 },
        boundaries: { race: [], safety: [] },
        marks: {
          RM8: { name: 'RM8', target: [-800, -700], asset_id: 'uuid-rm8' },
          RM6: { name: 'RM6', target: [-500, -1000], asset_id: 'uuid-rm6' },
          RM4: { name: 'RM4', target: [600, 900], asset_id: 'uuid-rm4' },
          RM2: { name: 'RM2', target: [800, 800], asset_id: 'uuid-rm2' },
        },
      },
      wind: { reference_twd_deg: 50, reference_tws_kt: 10, timeline: [] },
      chronology: {
        gun_time: 1000,
        window_start: 0,
        window_end: 2000,
      },
      competitors: [],
      telemetry: {
        timestamps: [0, 1000, 2000],
        boats: {},
        marks: {
          'uuid-rm2': {
            x: [1000, 1100, 1200],
            y: [500, 540, 580],
          },
          'uuid-rm4': {
            x: [900, 950, 1000],
            y: [700, 710, 720],
          },
        },
      },
    }

    const engine = new ReplayEngine(mockManifest)
    let currentFrame: ReplayFrame | null = null
    engine.subscribe((f) => {
      currentFrame = f
    })

    // At t = 500ms (halfway between t=0 and t=1000)
    engine.seek(500)
    expect(currentFrame).not.toBeNull()
    const marks = currentFrame!.marks

    // RM2 dynamic interpolation: midway between 1000 and 1100 for x, 500 and 540 for y
    expect(marks.RM2).toBeDefined()
    expect(marks.RM2.x).toBeCloseTo(1050, 4)
    expect(marks.RM2.y).toBeCloseTo(520, 4)

    // RM4 dynamic interpolation: midway between 900 and 950 for x, 700 and 710 for y
    expect(marks.RM4).toBeDefined()
    expect(marks.RM4.x).toBeCloseTo(925, 4)
    expect(marks.RM4.y).toBeCloseTo(705, 4)

    // RM8 has no telemetry stream -> falls back to static target [-800, -700]
    expect(marks.RM8).toBeDefined()
    expect(marks.RM8.x).toBe(-800)
    expect(marks.RM8.y).toBe(-700)

    // RM6 has no telemetry stream -> falls back to static target [-500, -1000]
    expect(marks.RM6).toBeDefined()
    expect(marks.RM6.x).toBe(-500)
    expect(marks.RM6.y).toBe(-1000)
  })

  const liveReplayPath = path.resolve(__dirname, '../../public/data/replays/naples_pr1.json')

  it.skipIf(!fs.existsSync(liveReplayPath))(
    'empirically verifies RM2 at t = 1790079233000 (frame 4130) is within 21.03m of FRA rounding position (< 30m SLA)',
    () => {
      const replayPath = liveReplayPath

      const rawData = fs.readFileSync(replayPath, 'utf8')
      const manifest: ReplayManifest = JSON.parse(rawData)

      const engine = new ReplayEngine(manifest)
      let currentFrame: ReplayFrame | null = null
      engine.subscribe((f) => {
        currentFrame = f
      })

      // Seek to Leg 1 rounding timestamp
      const tRounding = 1790079233000
      engine.seek(tRounding)

      expect(currentFrame).not.toBeNull()
      expect(currentFrame!.index).toBe(4130)

      const marks = currentFrame!.marks
      expect(marks.RM2).toBeDefined()
      expect(marks.RM4).toBeDefined()

      // Dynamic RM2 position at frame 4130
      expect(marks.RM2.x).toBeCloseTo(1103.6, 1)
      expect(marks.RM2.y).toBeCloseTo(537.55, 1)

      // Dynamic RM4 position at frame 4130
      expect(marks.RM4.x).toBeCloseTo(955.05, 1)
      expect(marks.RM4.y).toBeCloseTo(708.4, 1)

      // Find FRA boat
      const fraCompetitor = manifest.competitors.find((c) => c.team_code === 'FRA')
      expect(fraCompetitor).toBeDefined()
      const fraBoat = currentFrame!.boats[fraCompetitor!.id]
      expect(fraBoat).toBeDefined()

      // FRA position at Leg 1 crossing
      expect(fraBoat.x).toBeCloseTo(1088.33, 1)
      expect(fraBoat.y).toBeCloseTo(523.08, 1)

      // Compute rounding distance to dynamic RM2
      const dx = marks.RM2.x - fraBoat.x
      const dy = marks.RM2.y - fraBoat.y
      const distanceM = Math.hypot(dx, dy)

      // Target is approximately 21.03m, strictly satisfying the < 30m SLA
      expect(distanceM).toBeCloseTo(21.03, 1)
      expect(distanceM).toBeLessThan(30.0)

      // In contrast, compare with the static target distance to show why dynamic marks are essential
      const staticRM2 = manifest.course.marks.RM2.target
      const staticDx = staticRM2[0] - fraBoat.x
      const staticDy = staticRM2[1] - fraBoat.y
      const staticDistanceM = Math.hypot(staticDx, staticDy)
      expect(staticDistanceM).toBeGreaterThan(170.0) // ~197.25m away!
    }
  )
})
