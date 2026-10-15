import { describe, expect, it } from 'vitest'
import { boundaryAt } from './course'
import { createViewport, screenToWorld, worldToScreen } from '../components/canvas/ViewportMatrix'
import type { ReplayFrame, ReplayManifest } from '../types/replay'

describe('course replay geometry', () => {
  it('switches boundaries only at the recorded revision time', () => {
    const first = { race: [[0, 0], [1, 0], [1, 1]] as Array<[number, number]>, safety: [] }
    const second = { race: [[0, 0], [2, 0], [2, 2], [0, 2]] as Array<[number, number]>, safety: [] }
    const replay = { course: { boundaries: first, boundary_timeline: [{ t: 100, ...first }, { t: 200, ...second }] } } as unknown as ReplayManifest
    expect(boundaryAt(replay, 199).race).toHaveLength(3)
    expect(boundaryAt(replay, 200).race).toHaveLength(4)
  })


  it('round-trips picked points in course-up mode and keeps the course axis vertical', () => {
    const viewport = createViewport(1000, 600, [20, -10], 0.7, 'course', 40)
    const point: [number, number] = [345, 678]
    const screen = worldToScreen(viewport, point)
    const inverse = screenToWorld(viewport, screen)
    expect(inverse[0]).toBeCloseTo(point[0], 8)
    expect(inverse[1]).toBeCloseTo(point[1], 8)
    const axisPoint: [number, number] = [20 + Math.sin(40 * Math.PI / 180) * 100, -10 + Math.cos(40 * Math.PI / 180) * 100]
    expect(worldToScreen(viewport, axisPoint)[0]).toBeCloseTo(500, 8)
  })
})
