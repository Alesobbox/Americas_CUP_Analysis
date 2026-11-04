import { describe, expect, it, vi } from 'vitest'
import type { ReplayFrame, ReplayManifest } from '../../types/replay'
import { AC40_PLATFORM_BORDER, AC75_PLATFORM_BORDER, transformLocalToWorld } from '../../engine/contactDetector'
import { computeBoatRenderScale } from './boatModels'
import { drawCourseGeometry, projectSafetyBorderToScreen } from './DynamicVesselLayer'
import { createViewport, fitViewportWithBottomClearance, worldToScreen } from './ViewportMatrix'

describe('dynamic course and metric geometry', () => {
  it('keeps the complete course above the floating toolbar at the default stage height', () => {
    const corners: Array<[number, number]> = [[-200, -500], [200, -500], [200, 500], [-200, 500]]
    const viewport = fitViewportWithBottomClearance(900, 460, corners, 'course', 25, 140)
    const screenCorners = corners.map((point) => worldToScreen(viewport, point))
    expect(Math.min(...screenCorners.map(([, y]) => y))).toBeGreaterThan(0)
    expect(Math.max(...screenCorners.map(([, y]) => y))).toBeLessThan(320)
  })

  it('renders Cagliari sequence marks and their moving frame positions', () => {
    const replay = {
      chronology: { gun_time: 100 },
      course: {
        marks: {
          RM3: { name: 'Start port', target: [0, 0] },
          RM7: { name: 'Start starboard', target: [40, 0] },
          RM1: { name: 'Top port', target: [0, 100] },
          RM5: { name: 'Top starboard', target: [40, 100] },
        },
        sequences: [
          { leg: 0, port_mark: 'RM3', starboard_mark: 'RM7', gate_type: 'START' },
          { leg: 1, port_mark: 'RM1', starboard_mark: 'RM5', gate_type: 'TOP' },
        ],
        start_marks: { port: 'RM3', starboard: 'RM7' },
      },
    } as unknown as ReplayManifest
    const frame = {
      timestamp: 50,
      boats: { boat: { leg: 0 } },
      marks: { RM3: { x: 5, y: 7 } },
    } as unknown as ReplayFrame
    const labels: string[] = []
    const arcs: number[][] = []
    const context = {
      save: vi.fn(), restore: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(),
      closePath: vi.fn(), stroke: vi.fn(), fill: vi.fn(), rect: vi.fn(), setLineDash: vi.fn(),
      measureText: (text: string) => ({ width: text.length * 6 }),
      fillText: (text: string) => labels.push(text),
      arc: (x: number, y: number, radius: number) => arcs.push([x, y, radius]),
    } as unknown as CanvasRenderingContext2D
    const viewport = createViewport(800, 600, [0, 0], 1, 'north', 0)

    drawCourseGeometry(context, replay, frame, viewport)
    expect(labels).toContain('START LINE')
    expect(labels).toEqual(expect.arrayContaining(['RM3', 'RM7', 'RM1', 'RM5']))
    expect(labels).not.toContain('RM8')
    expect(arcs).toContainEqual([405, 293, 4.5])

    labels.length = 0
    drawCourseGeometry(context, replay, { ...frame, timestamp: 150, boats: { boat: { leg: 1 } } } as ReplayFrame, viewport)
    expect(labels).toContain('WINDWARD GATE')
  })

  it.each([
    ['AC40', AC40_PLATFORM_BORDER, 5.415],
    ['AC75', AC75_PLATFORM_BORDER, 8],
  ] as const)('aligns %s border and hull physical metres at every heading', (boatClass, border, foilHalfSpan) => {
    const state = { x: 120, y: -75, heading: 47 }
    const viewport = createViewport(800, 600, [20, 30], 0.08, 'course', 25)
    const trueScale = computeBoatRenderScale(boatClass, viewport.scale, 'true')
    const metricPoints = transformLocalToWorld(border, state.x, state.y, state.heading)
      .map((point) => worldToScreen(viewport, point))
    const truePoints = projectSafetyBorderToScreen(state, viewport, border, trueScale)
    truePoints.forEach((point, index) => {
      expect(point[0]).toBeCloseTo(metricPoints[index][0], 8)
      expect(point[1]).toBeCloseTo(metricPoints[index][1], 8)
    })

    const enhancedScale = computeBoatRenderScale(boatClass, viewport.scale, 'enhanced')
    const enhancedPoints = projectSafetyBorderToScreen(state, viewport, border, enhancedScale)
    const center = worldToScreen(viewport, [state.x, state.y])
    const lateralTip = enhancedPoints[2]
    const tipDistance = Math.hypot(lateralTip[0] - center[0], lateralTip[1] - center[1])
    expect(tipDistance).toBeCloseTo(Math.hypot(foilHalfSpan, border[2].y) * enhancedScale, 8)
  })
})
