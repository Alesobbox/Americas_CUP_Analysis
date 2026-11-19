import { describe, expect, it, vi } from 'vitest'
import {
  VMG_COLOR_STEPS,
  getVmgTrailColor,
  drawWindFlowField,
} from '../components/canvas/DynamicVesselLayer'
import { createViewport, worldVectorToScreen } from '../components/canvas/ViewportMatrix'
import type { ReplayManifest } from '../types/replay'

/**
 * WCAG 2.1 relative luminance calculation
 * https://www.w3.org/WAI/GL/wiki/Relative_luminance
 */
function sRgbToLinear(channel8Bit: number): number {
  const s = channel8Bit / 255.0
  return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
}

function relativeLuminance(r: number, g: number, b: number): number {
  return 0.2126 * sRgbToLinear(r) + 0.7152 * sRgbToLinear(g) + 0.0722 * sRgbToLinear(b)
}

function contrastRatio(rgb1: [number, number, number], rgb2: [number, number, number]): number {
  const l1 = relativeLuminance(...rgb1)
  const l2 = relativeLuminance(...rgb2)
  const lighter = Math.max(l1, l2)
  const darker = Math.min(l1, l2)
  return (lighter + 0.05) / (darker + 0.05)
}

function euclideanRgbDistance(c1: [number, number, number], c2: [number, number, number]): number {
  return Math.hypot(c1[0] - c2[0], c1[1] - c2[1], c1[2] - c2[2])
}

describe('M2 Challenger: VMG 7-Step Color Scale Verification', () => {
  const BACKGROUND_HEX = '#0a0e17'
  const BACKGROUND_RGB: [number, number, number] = [10, 14, 23] // #0a0e17

  it('defines exactly 7 discrete color steps covering 0 to 60 kt', () => {
    expect(VMG_COLOR_STEPS).toHaveLength(7)
    expect(VMG_COLOR_STEPS[0].minKt).toBe(0)
    expect(VMG_COLOR_STEPS[0].maxKt).toBe(10)
    expect(VMG_COLOR_STEPS[6].minKt).toBe(35)
    expect(VMG_COLOR_STEPS[6].maxKt).toBe(60)

    // Check strict continuity between step intervals
    for (let i = 0; i < VMG_COLOR_STEPS.length - 1; i++) {
      expect(VMG_COLOR_STEPS[i].maxKt).toBe(VMG_COLOR_STEPS[i + 1].minKt)
    }
  })

  it('verifies hex string exactly matches rgb triplet for each step', () => {
    for (const step of VMG_COLOR_STEPS) {
      const hex = step.hex.toLowerCase()
      const r = parseInt(hex.slice(1, 3), 16)
      const g = parseInt(hex.slice(3, 5), 16)
      const b = parseInt(hex.slice(5, 7), 16)
      expect(step.rgb).toEqual([r, g, b])
    }
  })

  it('verifies Euclidean RGB distance ΔC >= 50 for every adjacent pair across 10-35 kt', () => {
    // Pairs covering the active 10-35 kt range:
    // Pair 0-1 (0-10 vs 10-15 kt)
    // Pair 1-2 (10-15 vs 15-20 kt)
    // Pair 2-3 (15-20 vs 20-25 kt)
    // Pair 3-4 (20-25 vs 25-30 kt)
    // Pair 4-5 (25-30 vs 30-35 kt)
    // Pair 5-6 (30-35 vs 35+ kt)
    const deltas: Array<{ pair: string; deltaC: number }> = []

    for (let i = 0; i < VMG_COLOR_STEPS.length - 1; i++) {
      const stepA = VMG_COLOR_STEPS[i]
      const stepB = VMG_COLOR_STEPS[i + 1]
      const deltaC = euclideanRgbDistance(stepA.rgb, stepB.rgb)
      deltas.push({
        pair: `[${stepA.name}] vs [${stepB.name}]`,
        deltaC,
      })

      // Strict requirement: deltaC >= 50
      expect(deltaC).toBeGreaterThanOrEqual(50.0)
    }

    // Verify minimum delta across the entire scale is >= 60
    const minDelta = Math.min(...deltas.map((d) => d.deltaC))
    expect(minDelta).toBeGreaterThanOrEqual(60.0)
  })

  it('verifies WCAG contrast ratio against background #0a0e17 is >= 4.5:1 (AA level) for all steps', () => {
    const contrasts: Array<{ step: string; cr: number }> = []

    for (const step of VMG_COLOR_STEPS) {
      const cr = contrastRatio(step.rgb, BACKGROUND_RGB)
      contrasts.push({ step: step.name, cr })

      // Standard graphical UI minimum is 3:1, text AA is 4.5:1. All 7 steps exceed 4.5:1
      expect(cr).toBeGreaterThanOrEqual(4.5)
    }

    // Red is reserved for active contacts; high VMG uses a contrasting violet.
    const highVmgStep = VMG_COLOR_STEPS.find((s) => s.hex === '#a78bfa')!
    expect(contrastRatio(highVmgStep.rgb, BACKGROUND_RGB)).toBeGreaterThan(4.75)
  })

  it('verifies getVmgTrailColor maps speed ranges and boundary conditions accurately', () => {
    // 0 kt to <10 kt: Step 0 (#38bdf8 cyan)
    expect(getVmgTrailColor(0.0)).toBe('#38bdf8')
    expect(getVmgTrailColor(5.5)).toBe('#38bdf8')
    expect(getVmgTrailColor(9.999)).toBe('#38bdf8')

    // 10 kt boundary: Step 1 (#2dd4bf teal)
    expect(getVmgTrailColor(10.0)).toBe('#2dd4bf')
    expect(getVmgTrailColor(12.3)).toBe('#2dd4bf')
    expect(getVmgTrailColor(14.999)).toBe('#2dd4bf')

    // 15 kt boundary: Step 2 (#84cc16 lime)
    expect(getVmgTrailColor(15.0)).toBe('#84cc16')
    expect(getVmgTrailColor(19.999)).toBe('#84cc16')

    // 20 kt boundary: Step 3 (#eab308 yellow)
    expect(getVmgTrailColor(20.0)).toBe('#eab308')
    expect(getVmgTrailColor(24.999)).toBe('#eab308')

    // 25 kt boundary: Step 4 (#f97316 amber)
    expect(getVmgTrailColor(25.0)).toBe('#f97316')
    expect(getVmgTrailColor(29.999)).toBe('#f97316')

    // 30 kt boundary: Step 5 (#a78bfa violet)
    expect(getVmgTrailColor(30.0)).toBe('#a78bfa')
    expect(getVmgTrailColor(34.999)).toBe('#a78bfa')

    // 35 kt boundary and above: Step 6 (#ec4899 magenta)
    expect(getVmgTrailColor(35.0)).toBe('#ec4899')
    expect(getVmgTrailColor(42.0)).toBe('#ec4899')
    expect(getVmgTrailColor(65.0)).toBe('#ec4899')

    // Negative VMG magnitudes handled identically via Math.abs
    expect(getVmgTrailColor(-8.0)).toBe('#38bdf8')
    expect(getVmgTrailColor(-12.0)).toBe('#2dd4bf')
    expect(getVmgTrailColor(-18.0)).toBe('#84cc16')
    expect(getVmgTrailColor(-22.0)).toBe('#eab308')
    expect(getVmgTrailColor(-28.0)).toBe('#f97316')
    expect(getVmgTrailColor(-32.0)).toBe('#a78bfa')
    expect(getVmgTrailColor(-45.0)).toBe('#ec4899')

    // Degenerate inputs safely default to top step without throwing
    expect(getVmgTrailColor(NaN)).toBe('#ec4899')
    expect(getVmgTrailColor(Infinity)).toBe('#ec4899')
    expect(getVmgTrailColor(-Infinity)).toBe('#ec4899')
  })
})

describe('M2 Challenger: Wind Flow Field Rendering Math Verification', () => {
  const dummyManifest: ReplayManifest = {
    id: 'test',
    name: 'Test Regatta',
    venue: 'Naples',
    date: '2026-09-22',
    course: {
      axis_deg: 40,
      length_m: 2200,
      origin: [14.2, 40.8],
      projection: 'equirectangular',
      boundaries: { race: [], safety: [] },
      marks: {
        RM2: { target: [1000, 500] },
        RM4: { target: [900, 500] },
        RM6: { target: [100, -500] },
        RM8: { target: [0, -500] },
      },
    },
    wind: {
      reference_twd_deg: 40,
      reference_tws_kt: 12,
      timeline: [
        { t: 1000, twd: 40, tws: 12 },
        { t: 2000, twd: 90, tws: 15 },
        { t: 3000, twd: 180, tws: 8 },
        { t: 4000, twd: 270, tws: 10 },
        { t: 5000, twd: 0, tws: 14 },
      ],
    },
    chronology: { window_start: 1000, window_end: 5000, gun_time: 1500 },
    competitors: [],
    telemetry: { timestamps: [1000, 2000, 3000, 4000, 5000], boats: {}, marks: {} },
  }

  it('verifies vectors orient downwind ((twd + 180) % 360) in world Cartesian and screen coordinates', () => {
    // In meteorological convention:
    // TWD is direction wind blows FROM.
    // Downwind is direction wind travels TOWARDS = (TWD + 180) % 360.
    const testCases = [
      { twd: 0, expectedDownwind: 180, desc: 'North wind blows South (towards negative Y)' },
      {
        twd: 40,
        expectedDownwind: 220,
        desc: 'Northeast wind blows Southwest (course axis windward to leeward)',
      },
      { twd: 90, expectedDownwind: 270, desc: 'East wind blows West (towards negative X)' },
      { twd: 180, expectedDownwind: 0, desc: 'South wind blows North (towards positive Y)' },
      { twd: 270, expectedDownwind: 90, desc: 'West wind blows East (towards positive X)' },
      { twd: 350, expectedDownwind: 170, desc: 'Near-North wind' },
    ]

    for (const tc of testCases) {
      const downwindDeg = (tc.twd + 180) % 360
      expect(downwindDeg).toBe(tc.expectedDownwind)

      const flowRad = (downwindDeg * Math.PI) / 180
      const worldVec: [number, number] = [Math.sin(flowRad), Math.cos(flowRad)]

      // Verify North-up viewport (rotation = 0)
      const vpNorthUp = createViewport(900, 600, [0, 0], 1.0, 'north', 40)
      const [vx, vy] = worldVectorToScreen(vpNorthUp, worldVec)

      if (tc.twd === 0) {
        // Downwind = 180 (South) -> on screen, pointing DOWN (positive Y in screen coordinates)
        expect(vx).toBeCloseTo(0, 5)
        expect(vy).toBeGreaterThan(0)
      } else if (tc.twd === 90) {
        // Downwind = 270 (West) -> on screen, pointing LEFT (negative X in screen coordinates)
        expect(vx).toBeLessThan(0)
        expect(vy).toBeCloseTo(0, 5)
      } else if (tc.twd === 180) {
        // Downwind = 0 (North) -> on screen, pointing UP (negative Y in screen coordinates)
        expect(vx).toBeCloseTo(0, 5)
        expect(vy).toBeLessThan(0)
      } else if (tc.twd === 270) {
        // Downwind = 90 (East) -> on screen, pointing RIGHT (positive X in screen coordinates)
        expect(vx).toBeGreaterThan(0)
        expect(vy).toBeCloseTo(0, 5)
      }
    }
  })

  it('verifies Course-Up camera mode correctly rotates downwind flow down the screen', () => {
    // When course axis is 40° and camera is in Course-Up mode, 40° points UP on screen.
    // If wind blows from 40° (windward), downwind is 220° (towards leeward bottom gate).
    // On screen, the airflow MUST point straight DOWN (positive Y, zero X)!
    const vpCourseUp = createViewport(900, 600, [0, 0], 1.0, 'course', 40)
    const twd = 40
    const downwindDeg = (twd + 180) % 360
    const flowRad = (downwindDeg * Math.PI) / 180
    const worldVec: [number, number] = [Math.sin(flowRad), Math.cos(flowRad)]

    const [vx, vy] = worldVectorToScreen(vpCourseUp, worldVec)
    expect(vx).toBeCloseTo(0, 5)
    expect(vy).toBeGreaterThan(0) // Directly DOWN the screen towards bottom gate
  })

  it('verifies wind flow field renders with low-contrast opacity (0.10) to avoid hull distraction', () => {
    const mockContext = {
      save: vi.fn(),
      restore: vi.fn(),
      beginPath: vi.fn(),
      stroke: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      strokeStyle: '',
      lineWidth: 0,
    } as unknown as CanvasRenderingContext2D

    const vp = createViewport(900, 600, [0, 0], 0.2, 'north', 40)

    drawWindFlowField(mockContext, 900, 600, dummyManifest, 1000, vp)

    // Stroke style must strictly equal rgba(50, 104, 134, 0.1)
    expect(mockContext.strokeStyle).toBe('rgba(50, 104, 134, 0.1)')
    expect(mockContext.lineWidth).toBe(1.0)
    expect(mockContext.beginPath).toHaveBeenCalled()
    expect(mockContext.stroke).toHaveBeenCalled()
    expect(mockContext.save).toHaveBeenCalled()
    expect(mockContext.restore).toHaveBeenCalled()

    // Multiple arrows drawn across viewport
    const moveToCalls = (mockContext.moveTo as any).mock.calls.length
    const lineToCalls = (mockContext.lineTo as any).mock.calls.length
    expect(moveToCalls).toBeGreaterThan(50)
    expect(lineToCalls).toBeGreaterThan(150)
  })

  it('stress-tests boundary edge cases: zero wind, extreme wind speed, wrapping angles', () => {
    const mockContext = {
      save: vi.fn(),
      restore: vi.fn(),
      beginPath: vi.fn(),
      stroke: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      strokeStyle: '',
      lineWidth: 0,
    } as unknown as CanvasRenderingContext2D

    const vp = createViewport(900, 600, [0, 0], 0.2, 'north', 40)

    // Case 1: TWS = 0 (calm air)
    const calmManifest = {
      ...dummyManifest,
      wind: { ...dummyManifest.wind, timeline: [{ t: 1000, twd: 120, tws: 0 }] },
    }
    expect(() => {
      drawWindFlowField(mockContext, 900, 600, calmManifest, 1000, vp)
    }).not.toThrow()

    // Case 2: Extreme hurricane wind speed (100 kt)
    const stormManifest = {
      ...dummyManifest,
      wind: { ...dummyManifest.wind, timeline: [{ t: 1000, twd: 120, tws: 100 }] },
    }
    expect(() => {
      drawWindFlowField(mockContext, 900, 600, stormManifest, 1000, vp)
    }).not.toThrow()

    // Case 3: Empty timeline fallback to reference wind
    const fallbackManifest = {
      ...dummyManifest,
      wind: { reference_twd_deg: 45, reference_tws_kt: 16, timeline: [] },
    }
    expect(() => {
      drawWindFlowField(mockContext, 900, 600, fallbackManifest, 1000, vp)
    }).not.toThrow()
  })
})
